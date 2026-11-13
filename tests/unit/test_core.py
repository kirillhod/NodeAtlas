# SPDX-License-Identifier: GPL-3.0-or-later
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
    vm = bounds.measure_view(v2d, 2.5)
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
    upp, used, dpi_max = bounds.target_upp(96, 1.25)
    check(abs(upp - 1.25) < 1e-9, "D=1 upp")
    check(abs(used - 96) < 1e-9, "D=1 dpi")
    check(abs(dpi_max - (1.25 / 0.43311) * 96) < 1e-6, "Dmax")
    upp, used, _ = bounds.target_upp(10000, 1.25)
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
    tiles = {(0, 0): tile}
    image, holes = stitch.stitch_tiles(
        tiles, layout, region_w, region_h, padding
    )
    check(holes == 0, "holes")
    check(image.shape == (layout.final_h, layout.final_w, 4), "shape")
    check(image[0, 0, 0] == 10 and image[0, 0, 1] == 20 and image[0, 0, 2] == 30, "pixels")
    check((image[:, :, 3] == 255).all(), "alpha")

    spilled, spilled_holes = stitch.stitch_tiles(
        tiles, layout, region_w, region_h, padding, memory_limit=0
    )
    check(spilled_holes == 0, "memmap holes")
    check((spilled == image).all(), "memmap output")


def png_phys_dpi(path):
    import struct

    with open(path, "rb") as handle:
        check(handle.read(8) == b"\x89PNG\r\n\x1a\n", "png signature")
        while True:
            header = handle.read(8)
            if len(header) < 8:
                return None
            length = struct.unpack(">I", header[:4])[0]
            tag = header[4:8]
            data = handle.read(length)
            handle.read(4)
            if tag == b"pHYs":
                ppu_x, ppu_y, unit = struct.unpack(">IIB", data)
                check(ppu_x == ppu_y, "pHYs axes differ")
                return ppu_x * 0.0254, unit
            if tag == b"IEND":
                return None


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
        stitch._write_png_numpy(image, path, dpi=96)
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
        dpi, unit = png_phys_dpi(path)
        check(abs(dpi - 96.0) < 0.1 and unit == 1, "96 dpi pHYs")

        stitch.save_png(image, path, dpi=300)
        dpi, unit = png_phys_dpi(path)
        check(abs(dpi - 300.0) < 0.5 and unit == 1, "300 dpi pHYs")
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
        check(prefs.output_dpi == 128, "default dpi")
        check(prefs.padding == 20, "default padding")
        check(prefs.scope == "CURRENT", "default scope")
        check(os.path.isabs(prefs.default_dir), "default directory is absolute")
        check(os.path.isdir(prefs.default_dir), "default directory exists")
        check(prefs.enable_shortcut is False, "shortcut is off by default")
        advanced = getattr(bpy.types, "NODE_PT_node_atlas_advanced", None)
        check(advanced is not None, "advanced panel registered")
        check("DEFAULT_CLOSED" in advanced.bl_options, "advanced panel is collapsed")
        from node_atlas import operators

        check(hasattr(operators.NODE_ATLAS_OT_export_as, "draw"), "export dialog settings")
        check(hasattr(bpy.ops.node_atlas, "open_last_export"), "open-last-export operator")
        previous = operators.last_result
        operators.last_result = {"path": __file__}
        try:
            check(
                bpy.ops.node_atlas.open_last_export.poll(),
                "open-last-export poll",
            )
        finally:
            operators.last_result = previous
    finally:
        bpy.ops.preferences.addon_disable(module="node_atlas")


def test_shortcut_keymap():
    import bpy

    bpy.ops.preferences.addon_enable(module="node_atlas")
    prefs = None
    for key, addon in bpy.context.preferences.addons.items():
        if key == "node_atlas" or key.endswith(".node_atlas"):
            prefs = addon.preferences
            break
    check(prefs is not None, "preferences for shortcut test")
    try:
        prefs.enable_shortcut = True
        prefs.shortcut_key = "J"
        prefs.shortcut_ctrl = False
        prefs.shortcut_shift = True
        prefs.shortcut_alt = False
        keymap = bpy.context.window_manager.keyconfigs.addon.keymaps.get("Node Editor")
        check(keymap is not None, "node editor keymap")
        item = next(
            (i for i in keymap.keymap_items if i.idname == "node_atlas.export_png"),
            None,
        )
        check(item is not None, "shortcut item")
        check(item.type == "J", "shortcut key")
        check(not item.ctrl and item.shift and not item.alt, "shortcut modifiers")
        prefs.enable_shortcut = False
        item = next(
            (i for i in keymap.keymap_items if i.idname == "node_atlas.export_png"),
            None,
        )
        check(item is None, "shortcut removed when disabled")
    finally:
        prefs.enable_shortcut = False
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


def test_save_cleanup():
    import os
    import tempfile

    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[:, :, 3] = 255
    descriptor, path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    original_replace = stitch.os.replace
    try:
        def locked(*_args, **_kwargs):
            raise OSError("target is locked")

        stitch.os.replace = locked
        try:
            stitch.save_png(image, path)
        except stitch.OutputError as exc:
            check("target is locked" in str(exc), "save error message")
        else:
            check(False, "save_png should fail when the target is locked")
    finally:
        stitch.os.replace = original_replace
        check(not os.path.exists(path + ".tmp.png"), "temporary PNG was not cleaned up")
        if os.path.exists(path):
            os.remove(path)


def test_locked_target():
    import tempfile

    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[:, :, 3] = 255
    descriptor, path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    with open(path, "wb") as handle:
        handle.write(b"not a png")
    holder = open(path, "rb")
    try:
        try:
            stitch.save_png(image, path)
        except stitch.OutputError as exc:
            check("Cannot write" in str(exc), "locked target message")
        else:
            check(False, "save_png should fail when the target is locked")
    finally:
        holder.close()
        check(not os.path.exists(path + ".tmp.png"), "locked target temp PNG was not cleaned up")
        os.remove(path)


def test_long_output_path():
    import tempfile

    root = tempfile.mkdtemp(prefix="nodeatlas_long_")
    parts = ["segment-%02d-abcdefghij" % index for index in range(6)]
    directory = os.path.join(root, *parts)
    check(len(directory) > 150, "long path fixture is too short")
    target = os.path.join(directory, "export.png")
    stitch.check_output_path(target)
    check(os.path.isdir(directory), "long output directory was not created")


def test_output_preflight():
    import errno
    import tempfile

    root = tempfile.mkdtemp(prefix="nodeatlas_preflight_")
    target = os.path.join(root, "nested", "export.png")
    stitch.check_output_path(target)
    check(os.path.isdir(os.path.dirname(target)), "preflight creates the directory")
    check(
        not any(name.startswith(".nodeatlas_probe_") for name in os.listdir(os.path.dirname(target))),
        "preflight probe was removed",
    )

    original_open = stitch.os.open
    try:
        def denied(*_args, **_kwargs):
            raise OSError(errno.EACCES, "Permission denied")

        stitch.os.open = denied
        try:
            stitch.check_output_path(target)
        except stitch.OutputError as exc:
            check("not writable" in str(exc), "read-only directory message")
        else:
            check(False, "read-only directory was not rejected")
    finally:
        stitch.os.open = original_open

    blocker = os.path.join(root, "blocked")
    with open(blocker, "w", encoding="utf-8") as handle:
        handle.write("file")
    try:
        stitch.check_output_path(os.path.join(blocker, "export.png"))
    except stitch.OutputError as exc:
        check("Cannot create output directory" in str(exc), "blocked directory message")
    else:
        check(False, "a file in the directory path was not rejected")


def test_disk_full():
    import errno
    import tempfile

    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[:, :, 3] = 255
    descriptor, path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    original_replace = stitch.os.replace
    try:
        def full(*_args, **_kwargs):
            error = OSError(errno.ENOSPC, "No space left on device")
            error.winerror = 112
            raise error

        stitch.os.replace = full
        try:
            stitch.save_png(image, path)
        except stitch.OutputError as exc:
            check("Not enough free disk space" in str(exc), "disk-full message")
        else:
            check(False, "save_png should fail on a full disk")
    finally:
        stitch.os.replace = original_replace
        check(not os.path.exists(path + ".tmp.png"), "disk-full temp PNG was not cleaned up")
        if os.path.exists(path):
            os.remove(path)


def test_selected_node_names():
    class Node:
        def __init__(self, name, select=False, hide=False, kind="NODE", parent=None):
            self.name = name
            self.select = select
            self.hide = hide
            self.type = kind
            self.parent = parent

    class Tree:
        pass

    frame = Node("Frame", select=True, kind="FRAME")
    child = Node("Child", parent=frame)
    grandchild = Node("Grandchild", parent=child)
    selected = Node("Selected", select=True)
    hidden = Node("Hidden", select=True, hide=True)
    unrelated = Node("Unrelated")
    tree = Tree()
    tree.nodes = [frame, child, grandchild, selected, hidden, unrelated]
    check(
        bounds.selected_node_names(tree) == {"Frame", "Child", "Grandchild", "Selected"},
        "selected/frame descendants",
    )

    frame.select = False
    selected.select = False
    check(bounds.selected_node_names(tree) == set(), "empty selection")


def test_filename_sanitization():
    from node_atlas import operators

    check(operators._safe_name("Дерево 儀") == "Дерево_儀", "unicode filename")
    check(
        operators._safe_name("Shader  Nodetree") == "Shader_Nodetree",
        "whitespace to underscore",
    )
    check(
        operators._safe_name("  Material (copy)  ") == "Material_(copy)",
        "trim and collapse",
    )
    sanitized = operators._safe_name('a/b:c*?"<>|')
    check(not any(char in sanitized for char in '/\\:*?"<>|'), "invalid characters")
    check(operators._safe_name("...") == "export", "empty filename fallback")


def test_render_filename():
    from node_atlas import operators

    fields = {
        "blend": "scene",
        "tree": "Material",
        "datablock": "Shader Nodetree",
        "type": "Shader",
        "date": "20260101-000000",
    }
    check(
        operators.render_filename("{blend}_{tree}_{type}.png", fields)
        == "scene_Material_Shader.png",
        "owner and type tokens",
    )
    check(
        operators.render_filename("{datablock}_{date}", fields)
        == "Shader_Nodetree_20260101-000000.png",
        "datablock token and suffix",
    )
    check(
        operators.render_filename("{unknown}.png", fields)
        == "scene_Material_20260101-000000.png",
        "unknown token falls back",
    )


def test_tree_owner_name():
    import bpy

    from node_atlas import operators

    material = bpy.data.materials.new("Owner Material")
    material.use_nodes = True
    try:
        check(
            operators._tree_owner_name(material.node_tree) == "Owner Material",
            "material owner",
        )
    finally:
        bpy.data.materials.remove(material)
    check(operators._tree_owner_name(None) is None, "no tree")


def test_quick_filepath():
    import os
    import tempfile
    import types

    import bpy

    from node_atlas import operators

    empty = types.SimpleNamespace(default_dir="", filename_pattern="{tree}.png")
    check(operators.quick_filepath(bpy.context, empty) is None, "empty dir asks")

    folder = tempfile.mkdtemp(prefix="nodeatlas_path_")
    prefs = types.SimpleNamespace(
        default_dir=folder, filename_pattern="{tree}_{date}.png"
    )
    path = operators.quick_filepath(bpy.context, prefs)
    check(path is not None and os.path.dirname(path) == folder, "quick path")
    check(os.path.basename(path).endswith(".png"), "png suffix")


def main():
    tests = [
        test_view_metrics,
        test_rect_and_layout,
        test_density,
        test_stitch_single_tile,
        test_png_writer,
        test_save_cleanup,
        test_locked_target,
        test_long_output_path,
        test_output_preflight,
        test_disk_full,
        test_selected_node_names,
        test_filename_sanitization,
        test_render_filename,
        test_tree_owner_name,
        test_quick_filepath,
        test_registration,
        test_shortcut_keymap,
        test_version_consistency,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("ALL PASS")


if __name__ == "__main__":
    main()
