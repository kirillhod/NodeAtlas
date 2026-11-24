# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless core tests. Run with:

blender --background --factory-startup --python tests/unit/test_core.py
"""

from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile

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


def test_padding_unit():
    check(bounds.padding_px(20, 96) == 20, "padding at 96 dpi")
    check(bounds.padding_px(20, 192) == 40, "padding at 192 dpi")
    check(bounds.padding_px(20, 48) == 10, "padding at 48 dpi")
    check(bounds.padding_px(20, 128) == 27, "padding at 128 dpi")
    check(bounds.padding_px(0, 192) == 0, "zero padding")


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
    image = stitch.stitch_tiles(
        tiles, layout, region_w, region_h
    )
    check(image.shape == (layout.final_h, layout.final_w, 4), "shape")
    check(image[0, 0, 0] == 10 and image[0, 0, 1] == 20 and image[0, 0, 2] == 30, "pixels")
    check((image[:, :, 3] == 255).all(), "alpha")

    spilled = stitch.stitch_tiles(
        tiles, layout, region_w, region_h, memory_limit=0
    )
    check((spilled == image).all(), "memmap output")


def test_transparent_stitch():
    region_w, region_h, pad, padding = 200, 100, 16, 10
    tile_w, tile_h = region_w - 2 * pad, region_h - 2 * pad
    layout = bounds.Layout(
        pad=pad, overlap=120, margin=padding + pad,
        grid_x=1, grid_y=1, step_x=region_w - 120, step_y=region_h - 120,
        canvas_w=region_w, canvas_h=region_h,
        final_w=math.ceil(region_w - 2 * (padding + pad)) + 2 * padding,
        final_h=math.ceil(region_h - 2 * (padding + pad)) + 2 * padding,
    )
    tile = np.zeros((tile_h, tile_w, 4), dtype=np.uint8)
    tile[:, :, 0] = 200
    # The left half is a semi-transparent node pixel, the right half is empty.
    tile[:, : tile_w // 2, 3] = 128
    tiles = {(0, 0): tile}
    image = stitch.stitch_tiles(tiles, layout, region_w, region_h, transparent=True)
    check(image.shape == (layout.final_h, layout.final_w, 4), "transparent shape")
    check(image[0, 0, 3] in (127, 128), "semi-transparent alpha survives")
    check(image[0, -1, 3] == 0, "empty background is transparent")
    check(abs(int(image[0, 0, 0]) - 200) <= 2, "straight colour after premultiplied stitch")

    spilled = stitch.stitch_tiles(
        tiles, layout, region_w, region_h, memory_limit=0, transparent=True
    )
    check((spilled == image).all(), "transparent memmap output")


def test_matte_pair():
    # Background over black and white: no foreground, so alpha is zero.
    dark = np.zeros((2, 2, 4), dtype=np.uint8)
    light = np.full((2, 2, 4), 255, dtype=np.uint8)
    image = stitch.matte_from_pair(dark, light)
    check((image[:, :, 3] == 0).all(), "background alpha")
    check((image[:, :, :3] == 0).all(), "background colour")

    # Opaque red is identical over both backgrounds.
    dark = np.zeros((1, 1, 4), dtype=np.uint8)
    light = np.zeros((1, 1, 4), dtype=np.uint8)
    dark[0, 0] = (255, 0, 0, 255)
    light[0, 0] = (255, 0, 0, 255)
    image = stitch.matte_from_pair(dark, light)
    check(image[0, 0, 3] == 255, "opaque alpha")
    check(tuple(image[0, 0, :3]) == (255, 0, 0), "opaque colour")

    # Half coverage: 127 of the 254 steps between the backgrounds.
    dark = np.zeros((1, 1, 4), dtype=np.uint8)
    light = np.zeros((1, 1, 4), dtype=np.uint8)
    dark[0, 0] = (64, 64, 64, 255)
    light[0, 0] = (191, 191, 191, 255)
    image = stitch.matte_from_pair(dark, light)
    check(abs(int(image[0, 0, 3]) - 128) <= 1, "half alpha")
    check(abs(int(image[0, 0, 0]) - 128) <= 2, "half colour unpremultiplied")


def test_matte_step():
    # The bottom-left block of the first tile is background: 100 bytes apart.
    dark = np.zeros((16, 16, 4), dtype=np.uint8)
    light = np.zeros((16, 16, 4), dtype=np.uint8)
    light[:, :, :3] = 100
    # An opaque node in the middle does not change the corner sample.
    dark[8:, 8:, :3] = 40
    light[8:, 8:, :3] = 40
    check(abs(stitch.matte_step(dark, light) - 100.0) < 1e-6, "measured step")

    # A corner covered by content falls back to the whole tile.
    dark[:] = 0
    light[:] = 0
    dark[4:, 4:, 0] = 0
    light[4:, 4:, 0] = 60
    check(abs(stitch.matte_step(dark, light) - 60.0) < 20.0, "fallback step")

    flat = np.zeros((8, 8, 4), dtype=np.uint8)
    try:
        stitch.matte_step(flat, flat)
    except stitch.StitchError:
        pass
    else:
        check(False, "a flat pair must not produce a step")


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
        check(prefs.show_advanced is False, "advanced section is collapsed")
        check(
            prefs.show_capture_area is False,
            "capture-area preview is off by default",
        )
        from node_atlas import operators, job

        check(hasattr(operators.NODE_ATLAS_OT_export_as, "draw"), "export dialog settings")
        check(hasattr(bpy.ops.node_atlas, "open_last_export"), "open-last-export operator")
        previous = job.last_result
        job.last_result = {"path": __file__}
        try:
            check(
                bpy.ops.node_atlas.open_last_export.poll(),
                "open-last-export poll",
            )
        finally:
            job.last_result = previous
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

    # Linux and macOS report an exhausted quota instead of ENOSPC.
    descriptor, path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    original_replace = stitch.os.replace
    try:
        def quota(*_args, **_kwargs):
            raise OSError(getattr(errno, "EDQUOT", errno.ENOSPC), "Disk quota exceeded")

        stitch.os.replace = quota
        try:
            stitch.save_png(image, path)
        except stitch.OutputError as exc:
            check("Not enough free disk space" in str(exc), "quota message")
        else:
            check(False, "save_png should fail on an exhausted quota")
    finally:
        stitch.os.replace = original_replace
        check(not os.path.exists(path + ".tmp.png"), "quota temp PNG was not cleaned up")
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
    from node_atlas import naming

    check(naming.safe_name("Дерево 儀") == "Дерево_儀", "unicode filename")
    check(
        naming.safe_name("Shader  Nodetree") == "Shader_Nodetree",
        "whitespace to underscore",
    )
    check(
        naming.safe_name("  Material (copy)  ") == "Material_(copy)",
        "trim and collapse",
    )
    sanitized = naming.safe_name('a/b:c*?"<>|')
    check(not any(char in sanitized for char in '/\\:*?"<>|'), "invalid characters")
    check(naming.safe_name("...") == "export", "empty filename fallback")


def test_render_filename():
    from node_atlas import naming

    fields = {
        "blend": "scene",
        "tree": "Material",
        "datablock": "Shader Nodetree",
        "type": "Shader",
        "date": "20260101-000000",
    }
    check(
        naming.render_filename("{blend}_{tree}_{type}.png", fields)
        == "scene_Material_Shader.png",
        "owner and type tokens",
    )
    check(
        naming.render_filename("{datablock}_{date}", fields)
        == "Shader_Nodetree_20260101-000000.png",
        "datablock token and suffix",
    )
    check(
        naming.render_filename("{unknown}.png", fields)
        == "scene_Material_20260101-000000.png",
        "unknown token falls back",
    )


def test_tree_owner_name():
    import bpy

    from node_atlas import naming

    material = bpy.data.materials.new("Owner Material")
    material.use_nodes = True
    try:
        check(
            naming.tree_owner_name(material.node_tree) == "Owner Material",
            "material owner",
        )
    finally:
        bpy.data.materials.remove(material)
    check(naming.tree_owner_name(None) is None, "no tree")


def test_quick_filepath():
    import os
    import tempfile
    import types

    import bpy

    from node_atlas import naming

    empty = types.SimpleNamespace(default_dir="", filename_pattern="{tree}.png")
    check(naming.quick_filepath(bpy.context, empty) is None, "empty dir asks")

    folder = tempfile.mkdtemp(prefix="nodeatlas_path_")
    prefs = types.SimpleNamespace(
        default_dir=folder, filename_pattern="{tree}_{date}.png"
    )
    path = naming.quick_filepath(bpy.context, prefs)
    check(path is not None and os.path.dirname(path) == folder, "quick path")
    check(os.path.basename(path).endswith(".png"), "png suffix")

    # bpy.path.abspath leaves "~" alone, so the folder must be expanded separately.
    home = os.path.expanduser("~")
    tilde = types.SimpleNamespace(
        default_dir=os.path.join("~", "NodeAtlasTildeTest"),
        filename_pattern="{tree}.png",
    )
    path = naming.quick_filepath(bpy.context, tilde)
    check(
        path is not None
        and os.path.dirname(path) == os.path.join(home, "NodeAtlasTildeTest"),
        "quick path expands the home shorthand",
    )


def test_resolve_path():
    home = os.path.expanduser("~")
    check(
        stitch.resolve_path(os.path.join("~", "Pictures", "x.png"))
        == os.path.join(home, "Pictures", "x.png"),
        "resolve_path expands the home shorthand",
    )
    check(os.path.isabs(stitch.resolve_path("relative.png")), "resolve_path is absolute")


def test_link_neighbour_names():
    class Node:
        def __init__(self, name):
            self.name = name

    class Link:
        def __init__(self, a, b):
            self.from_node = a
            self.to_node = b

    class Tree:
        pass

    selected = Node("Selected")
    neighbour = Node("Neighbour")
    far = Node("Far")
    tree = Tree()
    tree.links = [Link(selected, neighbour), Link(neighbour, far)]

    check(
        bounds.link_neighbour_names(tree, {"Selected"}) == {"Neighbour"},
        "direct neighbour only",
    )
    check(
        bounds.link_neighbour_names(tree, {"Selected", "Neighbour"}) == {"Far"},
        "growing keep set",
    )
    check(
        bounds.link_neighbour_names(tree, set()) == set(),
        "empty keep set",
    )


def test_select_outside_tiles():
    from types import SimpleNamespace

    from node_atlas import capture

    class Dim:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    class Node:
        def __init__(self, name, x, y, width=100, height=50):
            self.name = name
            self.location = (x, y)
            self.parent = None
            self.dimensions = Dim(width, height)
            self.select = False

    class Tree:
        pass

    tree = Tree()
    inside = Node("inside", 0, 0)
    near = Node("near", -120, 0)
    far = Node("far", -300, 0)
    low = Node("low", 0, -900)
    tree.nodes = [inside, near, far, low]
    layout = SimpleNamespace(margin=20, step_x=800, step_y=600)

    capture.select_outside_view(tree, 0.0, 0.0, 1.0, 1.0, layout, (0, 0), 1000, 800, 20)
    check(not inside.select, "node inside the first tile stays unselected")
    check(not near.select, "node within the margin stays unselected")
    check(far.select, "node beyond the margin is selected")
    check(low.select, "node below the first tile is selected")

    tree.nodes = [Node("inside", 0, 0), Node("visible", 900, -900)]
    capture.select_outside_view(tree, 0.0, 0.0, 1.0, 1.0, layout, (1, 1), 1000, 800, 20)
    check(tree.nodes[0].select, "top node is outside the lower-right tile")
    check(not tree.nodes[1].select, "lower-right node is inside its tile")

    # Effective UI scale 2: positions use s, sizes use k (report §4.3). The
    # node sits 120 px into the second tile with s = 2, while k = 1 would put
    # its right edge at -230 px and select it inside the captured tile.
    tree.nodes = [Node("scaled", 450, 0)]
    capture.select_outside_view(tree, 0.0, 0.0, 2.0, 1.0, layout, (1, 0), 1000, 800, 20)
    check(not tree.nodes[0].select, "positions use s, not k")


def test_content_origin():
    from types import SimpleNamespace

    from node_atlas import bounds

    class Dim:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    def node(x, y, width=100, height=50):
        return SimpleNamespace(
            location=(x, y), parent=None, dimensions=Dim(width, height)
        )

    nodes = [node(0, 0), node(400, 300), node(-900, 800, 0, 0)]
    check(
        bounds.content_origin(nodes) == (0.0, 300.0),
        "nodes without dimensions are ignored by the content origin",
    )


def test_preview_geometry():
    from node_atlas import bounds, preview

    content = bounds.Rect(left=0, top=500, right=1000, bottom=0)

    def estimate(padding):
        layout = bounds.compute_layout(content, 800, 600, padding, 1.0)
        return preview.Estimate(
            content=content, layout=layout, used_dpi=48.0, nodes=1,
            scope="CURRENT", upp=1.25,
        )

    # The frame is the on-screen graph bounds widened by the export padding:
    # 500 screen px of a 1000 px export is half scale, so 20 px becomes 10.
    union = bounds.Rect(left=100, top=600, right=600, bottom=100)
    rect = preview.screen_rect(union, estimate(20))
    check(rect == (90, 610, 610, 90), f"padded rect {rect}")
    check(rect[0] - union.left == union.right - rect[2], "horizontal padding")
    check(rect[1] - union.top == union.bottom - rect[3], "vertical padding")
    check(union.left - rect[0] == 10, "padding follows the screen scale")

    # live_union uses the same rects and visual margin as the export.
    metrics = bounds.ViewMetrics(upp=1.0, k=1.0, s=1.0, ox=10, oy=20)
    nodes = [FakeNode(0, 0, 100, 50), FakeNode(300, 200, 100, 50)]
    union = preview.live_union(nodes, metrics, 1.0)
    check(union == bounds.Rect(7, 223, 413, -33), f"live union {union}")

    # The label is only drawn while the frame top is inside the view.
    check(preview.intersects((10, 10, 100, 0), 200, 100), "rect inside")
    check(not preview.intersects((-200, 10, -10, 0), 200, 100), "rect left of view")
    check(not preview.intersects((0, 300, 100, 200), 200, 100), "rect above view")
    check(preview.top_edge_visible((0, 100, 100, 0), 100), "top on the border")
    check(not preview.top_edge_visible((0, 100.5, 100, 0), 100), "top outside")


def test_preview_dashes_and_label():
    from types import SimpleNamespace

    from node_atlas import bounds, preview

    dashes = preview.dash_quads((0, 100, 100, 0), dash=10, gap=5, width=2)
    solid = preview.dash_quads((0, 100, 100, 0), dash=1000, gap=0, width=2)
    check(len(dashes) % 6 == 0, "each dash is two triangles")
    check(len(solid) % 6 == 0, "solid quads are triangles too")
    check(len(dashes) == 28 * 6, f"dash count for 400 px perimeter: {len(dashes)}")
    check(len(solid) < len(dashes), "gaps create more quads than a solid edge")
    check(all(vertex[2] == 0.0 for vertex in dashes), "flat overlay geometry")
    xs = [vertex[0] for vertex in dashes]
    ys = [vertex[1] for vertex in dashes]
    check(min(xs) >= -1 and max(xs) <= 101, "x stays on the outline")
    check(min(ys) >= -1 and max(ys) <= 101, "y stays on the outline")

    content = bounds.Rect(left=0, top=500, right=1000, bottom=0)
    layout = bounds.compute_layout(content, 800, 600, 20, 1.0)
    base = preview.Estimate(
        content=content, layout=layout, used_dpi=48.0, nodes=7,
        scope="CURRENT", upp=0.5,
    )
    prefs = SimpleNamespace(output_dpi=48, scope="CURRENT")
    check(
        preview.label(base, prefs)
        == "≈ 1040 × 540 px · 0.6 MP · 48 DPI · padding 20 px",
        "label numbers come from the layout",
    )
    check(
        preview.size_text(base) == "1040 × 540 px · 0.6 MP", "size fragment"
    )

    clamped = preview.Estimate(
        content=content, layout=bounds.compute_layout(content, 800, 600, 0, 1.0),
        used_dpi=48.0, nodes=7, scope="SELECTED", upp=0.5,
    )
    prefs = SimpleNamespace(output_dpi=128, scope="SELECTED")
    check(
        preview.label(clamped, prefs)
        == "≈ 1000 × 500 px · 0.5 MP · 48 DPI (clamped) · 7 nodes",
        "clamped DPI and the selected count are shown",
    )
    clamped_one = preview.Estimate(
        content=content, layout=clamped.layout, used_dpi=96.0, nodes=1,
        scope="SELECTED", upp=0.5,
    )
    check(
        preview.label(clamped_one, SimpleNamespace(output_dpi=96, scope="SELECTED"))
        == "≈ 1000 × 500 px · 0.5 MP · 96 DPI · 1 node",
        "singular node count",
    )


def test_preview_registration():
    import bpy

    from node_atlas import bounds, preview

    check(preview._handle is None, "no handler before enable")
    bpy.ops.preferences.addon_enable(module="node_atlas")
    try:
        check(preview._handle is not None, "preview handler registered")
        content = bounds.Rect(0, 10, 10, 0)
        est = preview.Estimate(
            content=content,
            layout=bounds.compute_layout(content, 800, 600, 0, 1.0),
            used_dpi=96.0, nodes=0, scope="CURRENT", upp=1.0,
        )
        check(
            preview.screen_rect(bounds.Rect(0, 10, 10, 0), est) is not None,
            "geometry works without a view",
        )
    finally:
        bpy.ops.preferences.addon_disable(module="node_atlas")
    check(preview._handle is None, "preview handler removed on disable")


def test_recovery_file():
    from node_atlas import recovery

    folder = tempfile.mkdtemp(prefix="nodeatlas_recovery_unit_")
    target = os.path.join(folder, "pending.json")
    previous = os.environ.get("NODEATLAS_RECOVERY_FILE")
    os.environ["NODEATLAS_RECOVERY_FILE"] = target
    try:
        appearance = recovery.Appearance(
            theme="Default",
            backdrop=(0.1, 0.2, 0.3),
            grid_levels=2,
            link_alpha=0.5,
            ui_scale=1.25,
            smooth_view=200,
        )
        check(recovery.save(appearance), "recovery save")
        check(os.path.exists(target), "recovery file exists")
        loaded = recovery.load()
        check(loaded is not None, "recovery load")
        check(loaded.theme == "Default", "recovery theme")
        check(loaded.grid_levels == 2, "recovery grid")
        check(
            loaded.backdrop is not None
            and all(abs(a - b) < 1e-6 for a, b in zip(loaded.backdrop, (0.1, 0.2, 0.3))),
            "recovery backdrop",
        )
        check(abs(loaded.ui_scale - 1.25) < 1e-6, "recovery ui_scale")
        check(loaded.smooth_view == 200, "recovery smooth_view")

        with open(target, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        check(recovery.load() is None, "broken json is ignored")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write('{"version": 99}')
        check(recovery.load() is None, "unknown version is ignored")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write('{"version": 1, "ui_scale": NaN, "smooth_view": 1}')
        check(recovery.load() is None, "non-finite numbers are ignored")

        recovery.clear()
        check(not os.path.exists(target), "recovery file cleared")
    finally:
        if previous is None:
            os.environ.pop("NODEATLAS_RECOVERY_FILE", None)
        else:
            os.environ["NODEATLAS_RECOVERY_FILE"] = previous
        shutil.rmtree(folder, ignore_errors=True)


def main():
    tests = [
        test_view_metrics,
        test_rect_and_layout,
        test_padding_unit,
        test_density,
        test_stitch_single_tile,
        test_transparent_stitch,
        test_matte_pair,
        test_matte_step,
        test_png_writer,
        test_save_cleanup,
        test_locked_target,
        test_long_output_path,
        test_output_preflight,
        test_disk_full,
        test_selected_node_names,
        test_link_neighbour_names,
        test_select_outside_tiles,
        test_content_origin,
        test_preview_geometry,
        test_preview_dashes_and_label,
        test_filename_sanitization,
        test_render_filename,
        test_tree_owner_name,
        test_quick_filepath,
        test_resolve_path,
        test_preview_registration,
        test_recovery_file,
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
