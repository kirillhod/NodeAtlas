"""Tile stitching, final crop and PNG writing."""

from __future__ import annotations

import math
import os

import numpy as np


class StitchError(RuntimeError):
    pass


def _ramp(length: int, overlap: int, lower: bool, upper: bool) -> np.ndarray:
    weights = np.ones(length, dtype=np.float32)
    if overlap > 0:
        ramp = (np.arange(overlap, dtype=np.float32) + 0.5) / overlap
        if lower:
            weights[:overlap] = ramp
        if upper:
            weights[length - overlap:] = ramp[::-1]
    return weights


def stitch_tiles(tiles, layout, region_w: int, region_h: int, padding: int):
    """Stitch cropped bottom-up tiles into final RGBA, returning (image, holes)."""
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
    acc = np.zeros((canvas_h, canvas_w, 3), dtype=np.float32)
    weights = np.zeros((canvas_h, canvas_w), dtype=np.float32)

    for (i, j), tile in tiles.items():
        if tile.shape[0] != tile_h or tile.shape[1] != tile_w:
            raise StitchError(
                f"Tile {i},{j} has shape {tile.shape}, expected {(tile_h, tile_w, 4)}"
            )
        rgb = tile[:, :, :3].astype(np.float32)
        wx = _ramp(tile_w, overlap_x, i > 0, i < layout.grid_x - 1)
        wy = _ramp(tile_h, overlap_y, j > 0, j < layout.grid_y - 1)
        weight = np.outer(wy, wx)
        x = i * layout.step_x + pad
        y = canvas_h - region_h - j * layout.step_y + pad
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

    image = acc[c0:c0 + final_h, pad:pad + final_w] / np.maximum(
        cropped_weights[:, :, None], 1e-6
    )
    rgb8 = np.clip(image + 0.5, 0, 255).astype(np.uint8)
    rgba = np.empty((final_h, final_w, 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb8
    rgba[:, :, 3] = 255
    return rgba, holes


def save_png(image: np.ndarray, filepath: str) -> None:
    """Write bottom-up RGBA via imbuf, using an atomic rename."""
    import bpy
    import imbuf

    path = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    height, width, channels = image.shape
    if channels != 4:
        raise ValueError("Expected an RGBA image")

    try:
        img = imbuf.new((width, height), planes=32, buffer_type="BYTE")
        with img.with_buffer(write=True) as buffer:
            np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)[:] = image
        temp_path = path + ".tmp.png"
        imbuf.write(img, filepath=temp_path)
        img.free()
        os.replace(temp_path, path)
        return
    except Exception:
        # Blender 4.2 fallback: float image through bpy.data.images.
        if bpy.app.version >= (5, 2, 0):
            raise
        temp_path = path + ".tmp.png"
        pixels = image[::-1].astype(np.float32) / 255.0
        bpy_image = bpy.data.images.new("NodeAtlasTemp", width=width, height=height, alpha=True)
        try:
            bpy_image.pixels.foreach_set(pixels.ravel())
            bpy_image.filepath_raw = temp_path
            bpy_image.file_format = "PNG"
            bpy_image.save()
        finally:
            bpy.data.images.remove(bpy_image)
        os.replace(temp_path, path)
