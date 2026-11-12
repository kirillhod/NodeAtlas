"""Headless core tests. Run with:

blender --background --factory-startup --python tests/unit/test_core.py
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from node_atlas import bounds, stitch  # noqa: E402


class Vec:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class FakeNode:
    def __init__(self, x, y, w, h):
        self.location_absolute = Vec(x, y)
        self.dimensions = Vec(w, h)


class FakeV2D:
    def __init__(self, upp=0.8, ox=50.0, oy=70.0):
        self.upp = upp
        self.ox = ox
        self.oy = oy

    def region_to_view(self, x, y):
        return x * self.upp, y * self.upp

    def view_to_region(self, x, y, clip=True):
        return self.ox + x / self.upp, self.oy + y / self.upp


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_view_metrics():
    v2d = FakeV2D(upp=0.8, ox=50, oy=70)
    vm = bounds.measure_view(v2d, 1.25, 2.0)
    check(abs(vm.upp - 0.8) < 1e-9, "upp")
    check(abs(vm.k - 1.25) < 1e-9, "k")
    check(abs(vm.s - 1.25 * 2.0 * 1.25) < 1e-9, "s")
    check((vm.ox, vm.oy) == (50, 70), "origin")


def test_rect_and_layout():
    vm = bounds.ViewMetrics(upp=0.5, k=2.0, s=2.5, ox=10, oy=20)
    node = FakeNode(100, 200, 40, 30)
    rect = bounds.node_rect(node, vm)
    check(rect.left == 260 and rect.top == 520, "rect origin")
    check(rect.width == 80 and rect.height == 60, "rect size")

    content = bounds.Rect(0, 500, 1000, 0)
    layout = bounds.compute_layout(content, 800, 600, 20, 1.0)
    check(layout.pad == 16, "pad")
    check(layout.overlap == 120, "overlap")
    check(layout.margin == 36, "margin")
    check(layout.step_x == 680 and layout.step_y == 480, "steps")
    check(layout.grid_x == 2 and layout.grid_y == 1, "grid")
    check(layout.final_w == 1040 and layout.final_h == 540, "final size")
    check(layout.canvas_w == 1480 and layout.canvas_h == 600, "canvas")


def test_density():
    upp, used, dpi_max = bounds.target_upp(96, 1.25, 1.0)
    check(abs(upp - 1.25) < 1e-9, "D=1 upp")
    check(abs(used - 96) < 1e-9, "D=1 dpi")
    check(abs(dpi_max - (1.25 / 0.43311) * 96) < 1e-6, "Dmax")
    upp, used, _ = bounds.target_upp(10000, 1.25, 1.0)
    check(abs(upp - bounds.UPP_MIN) < 1e-9, "clamp max density")
    check(used < 10000, "clamped dpi")


def test_stitch_single_tile():
    region_w, region_h, pad, padding = 200, 100, 16, 10
    tile_w, tile_h = region_w - 2 * pad, region_h - 2 * pad
    content_w = region_w - 2 * (padding + pad)
    content_h = region_h - 2 * (padding + pad)
    layout = bounds.Layout(
        pad=pad, overlap=120, margin=padding + pad,
        content_w=content_w, content_h=content_h,
        grid_x=1, grid_y=1, step_x=region_w - 120, step_y=region_h - 120,
        canvas_w=region_w, canvas_h=region_h,
        final_w=math.ceil(content_w) + 2 * padding,
        final_h=math.ceil(content_h) + 2 * padding,
    )
    tile = np.zeros((tile_h, tile_w, 4), dtype=np.uint8)
    tile[:, :, 0] = 10
    tile[:, :, 1] = 20
    tile[:, :, 2] = 30
    tile[:, :, 3] = 255
    image, holes = stitch.stitch_tiles(
        {(0, 0): tile}, layout, region_w, region_h, padding
    )
    check(holes == 0, "holes")
    check(image.shape == (layout.final_h, layout.final_w, 4), "shape")
    check(image[0, 0, 0] == 10 and image[0, 0, 1] == 20 and image[0, 0, 2] == 30, "pixels")
    check((image[:, :, 3] == 255).all(), "alpha")


def test_png_writer():
    import os
    import tempfile

    import bpy

    height, width = 7, 9
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[:, :, 0] = np.arange(width, dtype=np.uint8)[None, :] * 20
    image[:, :, 1] = np.arange(height, dtype=np.uint8)[:, None] * 30
    image[:, :, 2] = 123
    image[:, :, 3] = 200
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        stitch._write_png_numpy(image, path)
        loaded = bpy.data.images.load(path, check_existing=False)
        try:
            loaded.colorspace_settings.name = "Non-Color"
            check(tuple(loaded.size) == (width, height), "png size")
            pixels = np.empty(width * height * 4, dtype=np.float32)
            loaded.pixels.foreach_get(pixels)
            result = np.clip(
                pixels.reshape(height, width, 4) * 255.0 + 0.5, 0, 255
            ).astype(np.uint8)
            check((result == image).all(), "png pixels")
        finally:
            bpy.data.images.remove(loaded)
    finally:
        os.remove(path)


def test_registration():
    import bpy

    import node_atlas  # noqa: F401

    bpy.ops.preferences.addon_enable(module="node_atlas")
    try:
        prefs = None
        for key, addon in bpy.context.preferences.addons.items():
            if key == "node_atlas" or key.endswith(".node_atlas"):
                prefs = addon.preferences
                break
        check(prefs is not None, "preferences registered")
        check(prefs.output_dpi == 96, "default dpi")
        check(prefs.padding == 20, "default padding")
        check(prefs.scope == "CURRENT", "default scope")
    finally:
        bpy.ops.preferences.addon_disable(module="node_atlas")


def test_version_consistency():
    import tomllib
    from pathlib import Path

    import node_atlas

    manifest = tomllib.loads(
        (Path(ROOT) / "node_atlas" / "blender_manifest.toml").read_text(encoding="utf-8")
    )
    check(manifest["version"] == node_atlas.__version__, "manifest version")
    check(
        ".".join(str(part) for part in node_atlas.bl_info["version"])
        == node_atlas.__version__,
        "bl_info version",
    )


def main():
    tests = [
        test_view_metrics,
        test_rect_and_layout,
        test_density,
        test_stitch_single_tile,
        test_png_writer,
        test_registration,
        test_version_consistency,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ALL PASS")


if __name__ == "__main__":
    main()
