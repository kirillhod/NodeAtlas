# SPDX-License-Identifier: GPL-3.0-or-later
"""Tile stitching, final crop and PNG writing."""

from __future__ import annotations

import errno
import os
import tempfile

import numpy as np

MEMORY_LIMIT = 512 * 1024 * 1024


class StitchError(RuntimeError):
    pass


class OutputError(StitchError):
    """The output path cannot be created or the image cannot be written."""


def resolve_path(filepath: str) -> str:
    """Expand ``~`` and Blender's ``//`` prefix, then return an absolute path.

    ``bpy.path.abspath`` leaves a leading ``~`` untouched, so a hand-typed
    ``~/Pictures`` stayed relative on Linux and macOS and the export landed in a
    literal ``~`` directory next to the working directory.
    """
    import bpy

    return os.path.abspath(os.path.expanduser(bpy.path.abspath(filepath)))


def _disk_full(exc: OSError) -> bool:
    # EDQUOT is a quota exhausted on Linux and macOS; the write fails the same way.
    if getattr(exc, "errno", None) in (errno.ENOSPC, getattr(errno, "EDQUOT", None)):
        return True
    # Windows reports a full volume as ERROR_DISK_FULL / ERROR_HANDLE_DISK_FULL.
    return getattr(exc, "winerror", None) in (39, 112)


def _detail(exc: OSError) -> str:
    if _disk_full(exc):
        return "the disk is full"
    return getattr(exc, "strerror", None) or str(exc) or type(exc).__name__


def _output_message(path: str, exc: OSError) -> str:
    if _disk_full(exc):
        return f"Not enough free disk space to save {path}"
    return f"Cannot write {path}: {_detail(exc)}"


def _probe_writable(directory: str) -> None:
    """Create and remove one probe file, raising the real OS error on failure.

    ``tempfile.mkstemp`` is not used here: on Windows it retries forever when
    the directory denies writes but ``os.access`` still reports it writable.
    """
    import uuid

    probe = os.path.join(
        directory, f".nodeatlas_probe_{os.getpid()}_{uuid.uuid4().hex}"
    )
    descriptor = os.open(probe, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        os.remove(probe)
    except OSError:
        pass


def check_output_path(filepath: str) -> None:
    """Fail early when the destination directory is missing or read-only."""
    path = resolve_path(filepath)
    directory = os.path.dirname(path)
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise OutputError(
            f"Cannot create output directory {directory}: {_detail(exc)}"
        ) from exc

    try:
        _probe_writable(directory)
    except OSError as exc:
        raise OutputError(
            f"Output directory {directory} is not writable: {_detail(exc)}"
        ) from exc


def _allocate_canvas(canvas_h: int, canvas_w: int, memory_limit: int, with_alpha: bool = False):
    planes = 4 if with_alpha else 3
    needed = canvas_h * canvas_w * (planes + 1) * 4
    if needed <= memory_limit:
        return (
            np.zeros((canvas_h, canvas_w, 3), dtype=np.float32),
            np.zeros((canvas_h, canvas_w), dtype=np.float32) if with_alpha else None,
            np.zeros((canvas_h, canvas_w), dtype=np.float32),
            (),
        )

    suffixes = [".acc.f32"]
    if with_alpha:
        suffixes.append(".alpha.f32")
    suffixes.append(".weights.f32")
    paths = []
    try:
        for suffix in suffixes:
            descriptor, path = tempfile.mkstemp(prefix="nodeatlas_stitch_", suffix=suffix)
            os.close(descriptor)
            paths.append(path)
        acc = np.memmap(paths[0], dtype=np.float32, mode="w+", shape=(canvas_h, canvas_w, 3))
        acc_alpha = None
        weights_index = 1
        if with_alpha:
            acc_alpha = np.memmap(
                paths[1], dtype=np.float32, mode="w+", shape=(canvas_h, canvas_w)
            )
            acc_alpha[:] = 0
            weights_index = 2
        weights = np.memmap(
            paths[weights_index], dtype=np.float32, mode="w+", shape=(canvas_h, canvas_w)
        )
        acc[:] = 0
        weights[:] = 0
        return acc, acc_alpha, weights, tuple(paths)
    except Exception:
        _release_canvas(None, None, None, tuple(paths))
        raise


def _release_canvas(acc, acc_alpha, weights, paths) -> None:
    for array in (acc, acc_alpha, weights):
        memory_map = getattr(array, "_mmap", None)
        if memory_map is not None:
            try:
                memory_map.close()
            except Exception:
                pass
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


def matte_step(dark: np.ndarray, light: np.ndarray, block: int = 8) -> float:
    """Return the background step in bytes between the two captures.

    The first tile of a capture starts with real padding at its bottom-left corner,
    so a small block there is pure background; a link can cross it, hence the
    median. When that block is not background, the whole tile is used as a
    fallback. The step is measured rather than assumed because the theme colour is
    converted to bytes by Blender's colour management.
    """
    delta = light[:block, :block, :3].astype(np.int32) - dark[:block, :block, :3]
    step = float(np.median(delta))
    if step < 32.0:
        delta = light[:, :, :3].astype(np.int32) - dark[:, :, :3]
        step = float(np.percentile(delta, 99.0))
    if step < 1.0:
        raise StitchError(
            "Could not measure the background step between the two captures"
        )
    return step


def matte_from_pair(dark: np.ndarray, light: np.ndarray, step: float = 254.0) -> np.ndarray:
    """Recover straight RGBA from one tile captured over two flat backgrounds.

    The node editor composites in sRGB, so ``I = aF + (1 - a)B`` is solved on the
    bytes: ``a = 1 - mean(I_light - I_dark) / step`` and ``F = I_dark / a``.
    Report section 11.14 measured the two-background pairs agreeing at
    mean |da| = 0.000000, with padding at a = 0 and node pixels at a >= 0.9908.
    """
    if dark.shape != light.shape or dark.ndim != 3 or dark.shape[2] < 4:
        raise StitchError("Matting needs two RGBA tiles of the same size")
    if step < 1.0:
        raise StitchError("Matting needs a background step of at least one byte")
    dark_rgb = dark[:, :, :3].astype(np.float32)
    delta = light[:, :, :3].astype(np.float32) - dark_rgb
    alpha = 1.0 - delta.mean(axis=2) / float(step)
    np.clip(alpha, 0.0, 1.0, out=alpha)
    # The measured step carries up to one byte of quantisation, which leaves the
    # flat background at alpha ~0.003. Snap it to zero so the padding is exactly
    # transparent; real shadows start an order of magnitude higher.
    alpha[alpha < 2.5 / 255.0] = 0.0
    rgba = np.empty(dark.shape, dtype=np.uint8)
    color = dark_rgb / np.maximum(alpha[:, :, None], 1.0 / 255.0)
    rgba[:, :, :3] = np.clip(color + 0.5, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return rgba


def stitch_tiles(
    tiles, layout, region_w: int, region_h: int,
    memory_limit: int | None = None,
    transparent: bool = False,
):
    """Stitch cropped bottom-up tiles into the final RGBA image.

    With ``transparent`` the tile alpha is stitched too: colour is accumulated
    premultiplied by alpha so a seam between tiles cannot darken or lighten the
    edge of a node shadow. Large canvases spill the float32 accumulator and
    weights to temporary memmaps instead of holding them in RAM.
    """
    pad = layout.pad
    overlap = layout.overlap
    tile_w = region_w - 2 * pad
    tile_h = region_h - 2 * pad
    overlap_x = overlap - 2 * pad
    overlap_y = overlap - 2 * pad
    if tile_w <= 0 or tile_h <= 0:
        raise StitchError("Tile is smaller than the edge padding")

    canvas_w = layout.canvas_w
    canvas_h = layout.canvas_h
    if memory_limit is None:
        memory_limit = MEMORY_LIMIT
    acc, acc_alpha, weights, paths = _allocate_canvas(
        canvas_h, canvas_w, memory_limit, with_alpha=transparent
    )

    try:
        for (i, j), tile in tiles.items():
            if tile.shape[0] != tile_h or tile.shape[1] != tile_w:
                raise StitchError(
                    f"Tile {i},{j} has shape {tile.shape}, expected {(tile_h, tile_w, 4)}"
                )
            wx = _ramp(tile_w, overlap_x, i > 0, i < layout.grid_x - 1)
            wy = _ramp(tile_h, overlap_y, j > 0, j < layout.grid_y - 1)
            weight = np.outer(wy, wx)
            x = i * layout.step_x + pad
            y = canvas_h - region_h - j * layout.step_y + pad
            if transparent:
                alpha = tile[:, :, 3].astype(np.float32) / 255.0
                rgb = tile[:, :, :3].astype(np.float32) * alpha[:, :, None]
                acc_alpha[y:y + tile_h, x:x + tile_w] += alpha * weight
            else:
                rgb = tile[:, :, :3].astype(np.float32)
            acc[y:y + tile_h, x:x + tile_w] += rgb * weight[:, :, None]
            weights[y:y + tile_h, x:x + tile_w] += weight

        final_w = layout.final_w
        final_h = layout.final_h
        c0 = canvas_h - final_h - pad
        if c0 < 0:
            raise StitchError("Final crop starts outside the canvas")

        cropped_weights = weights[c0:c0 + final_h, pad:pad + final_w]
        holes = int((cropped_weights <= 0).sum())
        if holes:
            raise StitchError(f"Final crop has {holes} uncovered pixels")

        denominator = np.maximum(cropped_weights[:, :, None], 1e-6)
        rgba = np.empty((final_h, final_w, 4), dtype=np.uint8)
        if transparent:
            alpha_out = acc_alpha[c0:c0 + final_h, pad:pad + final_w] / denominator[:, :, 0]
            np.clip(alpha_out, 0.0, 1.0, out=alpha_out)
            premultiplied = acc[c0:c0 + final_h, pad:pad + final_w] / denominator
            color = premultiplied / np.maximum(alpha_out[:, :, None], 1e-6)
            rgba[:, :, :3] = np.clip(color + 0.5, 0, 255).astype(np.uint8)
            rgba[:, :, 3] = np.clip(alpha_out * 255.0 + 0.5, 0, 255).astype(np.uint8)
        else:
            image = acc[c0:c0 + final_h, pad:pad + final_w] / denominator
            rgba[:, :, :3] = np.clip(image + 0.5, 0, 255).astype(np.uint8)
            rgba[:, :, 3] = 255
        return rgba
    finally:
        _release_canvas(acc, acc_alpha, weights, paths)


def _ramp(length: int, overlap: int, lower: bool, upper: bool) -> np.ndarray:
    weights = np.ones(length, dtype=np.float32)
    if overlap > 0:
        ramp = (np.arange(overlap, dtype=np.float32) + 0.5) / overlap
        if lower:
            weights[:overlap] = ramp
        if upper:
            weights[length - overlap:] = ramp[::-1]
    return weights


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    import struct
    import zlib

    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def phys_ppm(dpi: float) -> int:
    """Convert dots per inch to the PNG pHYs pixels-per-metre value."""
    return max(1, int(round(float(dpi) / 0.0254)))


def _phys_chunk(dpi: float) -> bytes:
    import struct

    ppm = phys_ppm(dpi)
    return _png_chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))


def _insert_png_phys(filepath: str, dpi: float) -> None:
    """Set pHYs on a PNG written by imbuf and drop its 72-dpi EXIF block.

    imbuf writes a fixed 72-dpi ``pHYs`` and an EXIF resolution block, which
    viewers show instead of the requested density. Rewrite the chunks in a
    streaming pass so large images are not loaded into memory: write one pHYs
    directly after IHDR and skip every original pHYs and eXIf chunk.
    """
    import struct

    if not dpi or dpi <= 0:
        return

    temp_path = filepath + ".phys"
    try:
        with open(filepath, "rb") as source, open(temp_path, "wb") as target:
            signature = source.read(8)
            if signature != b"\x89PNG\r\n\x1a\n":
                raise OutputError("imbuf wrote an unexpected PNG signature")
            target.write(signature)
            while True:
                header = source.read(8)
                if len(header) < 8:
                    break
                length = struct.unpack(">I", header[:4])[0]
                tag = header[4:8]
                if tag in (b"eXIf", b"pHYs"):
                    source.seek(length + 4, 1)
                    continue
                target.write(header)
                target.write(source.read(length))
                target.write(source.read(4))
                if tag == b"IHDR":
                    target.write(_phys_chunk(dpi))
                if tag == b"IEND":
                    break
        os.replace(temp_path, filepath)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _write_png_numpy(image: np.ndarray, filepath: str, dpi: float | None = None) -> None:
    """Write RGBA bottom-up bytes as PNG without Blender's color management."""
    import struct
    import zlib

    height, width, channels = image.shape
    if channels != 4:
        raise ValueError("Expected an RGBA image")
    rows = np.empty((height, width * 4 + 1), dtype=np.uint8)
    rows[:, 0] = 0  # filter type: none
    rows[:, 1:] = image[::-1].reshape(height, width * 4)
    compressed = zlib.compress(rows.tobytes(), 6)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    with open(filepath, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(_png_chunk(b"IHDR", header))
        if dpi and dpi > 0:
            handle.write(_phys_chunk(dpi))
        handle.write(_png_chunk(b"IDAT", compressed))
        handle.write(_png_chunk(b"IEND", b""))


def save_png(image: np.ndarray, filepath: str, dpi: float | None = None) -> None:
    """Write bottom-up RGBA, using imbuf when available and a NumPy PNG fallback."""
    import bpy

    path = resolve_path(filepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp.png"

    try:
        if bpy.app.version >= (5, 2, 0):
            try:
                import imbuf

                img = imbuf.new(
                    (image.shape[1], image.shape[0]), planes=32, buffer_type="BYTE"
                )
                try:
                    with img.with_buffer(write=True) as buffer:
                        np.frombuffer(buffer, dtype=np.uint8).reshape(image.shape)[:] = image
                    imbuf.write(img, filepath=temp_path)
                finally:
                    img.free()
                if dpi and dpi > 0:
                    _insert_png_phys(temp_path, dpi)
                os.replace(temp_path, path)
                return
            except OSError as exc:
                if _disk_full(exc):
                    raise OutputError(_output_message(path, exc)) from exc
            except Exception:
                # Fall through to the dependency-free writer.
                pass

        try:
            _write_png_numpy(image, temp_path, dpi=dpi)
            os.replace(temp_path, path)
        except OSError as exc:
            raise OutputError(_output_message(path, exc)) from exc
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
