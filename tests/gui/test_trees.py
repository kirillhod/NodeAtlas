"""Geometry Nodes + Compositor GUI test using scene_graphs.blend."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_trees_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_graphs.blend")
state = {"ticks": 0, "case": 0, "found": None, "sizes": {}}


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
    return area, next((item for item in area.regions if item.type == "WINDOW"), None)


def snapshot():
    area, _region = node_area()
    space = area.spaces.active
    tree = space.edit_tree
    return {
        "tree": tree.name if tree else None,
        "tree_type": space.tree_type,
        "pin": bool(space.pin),
        "backdrop": bool(getattr(space, "show_backdrop", False)),
        "header": bool(getattr(space, "show_region_header", False)),
        "ui": bool(getattr(space, "show_region_ui", False)),
        "toolbar": bool(getattr(space, "show_region_toolbar", False)),
        "gizmo": bool(getattr(space, "show_gizmo", False)),
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "smooth_view": bpy.context.preferences.view.smooth_view,
    }


def configure_tree(kind):
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    if kind == "gn":
        space.tree_type = "GeometryNodeTree"
        space.pin = True
        space.node_tree = bpy.data.node_groups["GN_Test"]
        name = "gn.png"
    else:
        space.tree_type = "CompositorNodeTree"
        space.show_backdrop = False
        space.pin = True
        space.node_tree = bpy.data.node_groups["COMP_Test"]
        name = "comp.png"
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = name
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot(), os.path.join(OUT, name)


def start_export():
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()


def image_size(path):
    image = bpy.data.images.load(path, check_existing=False)
    try:
        return tuple(image.size)
    finally:
        bpy.data.images.remove(image)


def finish_case(path):
    if not os.path.isfile(path):
        fail(f"missing output {path}")
    size = image_size(path)
    if size[0] <= 0 or size[1] <= 0:
        fail(f"empty output {path}")
    if size[0] < 500:
        fail(f"suspiciously narrow output {size}")
    state["sizes"][os.path.basename(path)] = size
    after = snapshot()
    if after != state["before"]:
        fail(f"state mismatch after {path}: {state['before']} != {after}")


def tick():
    state["ticks"] += 1
    path = state.get("output")
    if path and os.path.exists(path):
        if state["found"] is None:
            state["found"] = state["ticks"]
        if state["ticks"] - state["found"] >= 5:
            try:
                finish_case(path)
                state["case"] += 1
                state["found"] = None
                if state["case"] == 1:
                    state["before"], state["output"] = configure_tree("comp")
                    start_export()
                    return 0.2
                print(json.dumps({
                    "result": "PASS",
                    "sizes": state["sizes"],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1800:
        fail("timed out waiting for GN/Compositor exports")
    return 0.1


print("NodeAtlas GN/Compositor test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    state["before"], state["output"] = configure_tree("gn")
    start_export()
except Exception:
    fail("could not start GN export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
