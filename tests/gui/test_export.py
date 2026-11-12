# SPDX-License-Identifier: GPL-3.0-or-later
"""Live GUI smoke test for the NodeAtlas MVP.

Run from the repository root in a visible Blender window:

blender --factory-startup --python tests/gui/test_export.py

It opens tests/fixtures/scene_both.blend, exports M_Small, checks the PNG, the
restored editor state and undo neutrality, then exits.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = tempfile.mkdtemp(prefix="nodeatlas_gui_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
state = {"ticks": 0, "started": False, "error": None}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def node_area():
    window = bpy.context.window_manager.windows[0]
    areas = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    if not areas:
        return None, None
    area = max(areas, key=lambda item: item.width * item.height)
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    return area, region


def snapshot():
    area, _region = node_area()
    if area is None:
        return None
    space = area.spaces.active
    tree = space.edit_tree
    return {
        "area_type": area.type,
        "tree": tree.name if tree else None,
        "tree_type": space.tree_type,
        "pin": bool(space.pin),
        "header": bool(getattr(space, "show_region_header", False)),
        "ui": bool(getattr(space, "show_region_ui", False)),
        "toolbar": bool(getattr(space, "show_region_toolbar", False)),
        "gizmo": bool(getattr(space, "show_gizmo", False)),
        "context_path": bool(getattr(getattr(space, "overlay", None), "show_context_path", False)),
        "backdrop": bool(getattr(space, "show_backdrop", False)),
        "selected": sorted(node.name for node in tree.nodes if node.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "smooth_view": bpy.context.preferences.view.smooth_view,
    }


def setup():
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    space.pin = True
    space.node_tree = bpy.data.materials["M_Small"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    tree = space.edit_tree
    sentinel = tree.nodes.new("ShaderNodeMath")
    sentinel.label = "UNDO_SENTINEL"
    sentinel.location = (0, -1200)
    sentinel.select = True
    tree.nodes.active = sentinel
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.ed.undo_push(message="nodeatlas sentinel")

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "test_export.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    state["output"] = os.path.join(OUT, "test_export.png")
    return snapshot()


def check_png():
    path = state.get("output")
    if not path or not os.path.isfile(path):
        fail(f"PNG was not created: {path!r}")
    image = bpy.data.images.load(path, check_existing=False)
    try:
        width, height = image.size
        if width <= 0 or height <= 0:
            fail("PNG has zero size")
        return width, height
    finally:
        bpy.data.images.remove(image)


def check_state(before, result):
    after = snapshot()
    for key in (
        "area_type", "tree", "tree_type", "pin", "header", "ui", "toolbar",
        "gizmo", "context_path", "backdrop", "selected", "active",
        "ui_scale", "smooth_view",
    ):
        if before.get(key) != after.get(key):
            fail(f"state {key}: before={before.get(key)!r} after={after.get(key)!r}")
    area, _region = node_area()
    if area is None or area.type != "NODE_EDITOR":
        fail("Node Editor was not restored")


def check_undo():
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]

    def tree_now():
        current = area.spaces.active.edit_tree
        return current if current is not None else bpy.data.materials["M_Small"].node_tree

    tree = tree_now()
    if not any(node.label == "UNDO_SENTINEL" for node in tree.nodes):
        fail("sentinel is missing before undo")
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.ed.undo()
    tree = tree_now()
    if any(node.label == "UNDO_SENTINEL" for node in tree.nodes):
        fail("undo did not remove the sentinel (pipeline pushed an undo step)")
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.ed.redo()
    tree = tree_now()
    if not any(node.label == "UNDO_SENTINEL" for node in tree.nodes):
        fail("redo did not restore the sentinel")


def finish():
    width, height = check_png()
    check_state(state["before"], None)
    check_undo()
    print(json.dumps({
        "result": "PASS",
        "path": state.get("output"),
        "size": [width, height],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


def tick():
    state["ticks"] += 1
    if os.path.exists(state.get("output", "")):
        if state.get("found_tick") is None:
            state["found_tick"] = state["ticks"]
        if state["ticks"] - state["found_tick"] >= 5:
            try:
                finish()
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 900:
        fail("timed out waiting for the export")
    return 0.1


print("NodeAtlas GUI test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

# Register the polling timer only after open_mainfile/addon_enable: both can
# clear non-persistent application timers.
bpy.app.timers.register(tick, first_interval=0.2)
