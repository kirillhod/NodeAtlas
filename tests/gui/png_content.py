# SPDX-License-Identifier: GPL-3.0-or-later
"""Pixel checks shared by the live GUI tests.

The size assertions catch empty files but not a capture that is uniformly the
theme background or whose padding contains a scrollbar/frame strip. These
checks read the final PNG, verify that the outer ``padding`` pixels are real
background, and that the content area is not uniform. They also verify that the
writer did not leave transparent holes.
"""

from __future__ import annotations

import numpy as np


def park_cursor() -> None:
    """Move the pointer to the screen corner so no node row draws a hover highlight.

    Two screenshots of the same graph otherwise differ when the pointer happens to
    rest over a node: the hovered row is drawn lighter and with its arrows, and the
    capture includes it. Best effort: other platforms keep the pointer where it is.
    """
    try:
        import ctypes

        ctypes.windll.user32.SetCursorPos(0, 0)
    except Exception:
        pass


def read_rgba(path: str) -> np.ndarray:
    import bpy

    image = bpy.data.images.load(path, check_existing=False)
    try:
        image.colorspace_settings.name = "Non-Color"
        width, height = image.size
        buffer = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(buffer)
        return np.clip(
            buffer.reshape(height, width, 4) * 255.0 + 0.5, 0, 255
        ).astype(np.uint8)
    finally:
        bpy.data.images.remove(image)


def _mode_color(samples: np.ndarray) -> np.ndarray:
    """Return the most frequent RGB tuple in a small sample."""
    flat = samples.reshape(-1, samples.shape[-1])
    if flat.size == 0:
        raise AssertionError("empty pixel sample")
    colors, counts = np.unique(flat, axis=0, return_counts=True)
    return colors[int(counts.argmax())]


def check_capture(path: str, padding: int, tolerance: int = 8) -> dict:
    """Assert opaque pixels, real padding and non-uniform content.

    ``padding`` is the final-image padding in pixels. The test must use the same
    value it configured in the preferences. A link or glow can cross the band and
    fill a few of its lines at full strength, so a strip must cover most of the
    band to count as a leak; the outer 2 px are checked separately below.
    """
    if padding < 0:
        raise AssertionError(f"negative padding {padding}")
    pixels = read_rgba(path)
    height, width, _channels = pixels.shape
    if width <= 0 or height <= 0:
        raise AssertionError(f"empty image {width}x{height}")
    if 2 * padding >= min(width, height):
        raise AssertionError(
            f"padding {padding} does not fit a {width}x{height} image"
        )

    alpha = pixels[:, :, 3]
    if not np.all(alpha == 255):
        holes = int(np.count_nonzero(alpha != 255))
        raise AssertionError(f"{holes} transparent pixels in {path}")

    if padding:
        # A link or a node glow can enter the pixels next to the content edge;
        # 1.5.1 keeps such links at full strength. A frame or scrollbar covers
        # most of the band, so the thresholds below require a wide strip.
        bands = {
            "top": (pixels[:padding, :, :3], 1),
            "bottom": (pixels[-padding:, :, :3], 1),
            "left": (pixels[:, :padding, :3], 0),
            "right": (pixels[:, -padding:, :3], 0),
        }
        background = _mode_color(pixels[:padding:2, ::2, :3])
        border = np.concatenate(
            (
                pixels[:2, :, :3].reshape(-1, 3),
                pixels[-2:, :, :3].reshape(-1, 3),
                pixels[:, :2, :3].reshape(-1, 3),
                pixels[:, -2:, :3].reshape(-1, 3),
            )
        )
        border_difference = np.abs(
            border.astype(np.int16) - background.astype(np.int16)
        ).max(axis=1)
        border_fraction = float((border_difference > tolerance).mean())
        if border_fraction > 0.05:
            raise AssertionError(
                f"outer border has {border_fraction:.1%} non-background pixels; "
                "a frame or scrollbar leaked into the padding"
            )

        stats = {}
        for name, (band, axis) in bands.items():
            difference = np.abs(
                band.astype(np.int16) - background.astype(np.int16)
            ).max(axis=2)
            line_mean = difference.mean(axis=axis)
            outlier_fraction = float((difference > tolerance).mean())
            stats[name] = {
                "line_mean_max": round(float(line_mean.max()), 2),
                "outlier_fraction": round(outlier_fraction, 4),
            }
            if line_mean.max() > 80:
                raise AssertionError(
                    f"{name} padding has a bright strip (line mean "
                    f"{line_mean.max():.1f}); a frame or scrollbar leaked in"
                )
            if outlier_fraction > 0.5:
                raise AssertionError(
                    f"{name} padding has {outlier_fraction:.1%} non-background "
                    "pixels; a frame or scrollbar leaked in"
                )

        content = pixels[padding:height - padding, padding:width - padding, :3]
        background_stats = {
            "color": [int(v) for v in background],
            "border_fraction": round(border_fraction, 4),
            "bands": stats,
        }
    else:
        content = pixels[:, :, :3]
        background = _mode_color(pixels[::4, ::4, :3])
        background_stats = {"color": [int(v) for v in background]}

    difference = np.abs(
        content.astype(np.int16) - background.astype(np.int16)
    ).max(axis=2)
    changed = int(np.count_nonzero(difference > tolerance))
    minimum = max(16, content.shape[0] * content.shape[1] // 1000)
    if changed < minimum:
        raise AssertionError(
            f"content area looks empty: {changed} changed pixels, need {minimum}"
        )

    return {
        "size": [width, height],
        "padding": padding,
        "background": background_stats,
        "content_pixels": changed,
    }
