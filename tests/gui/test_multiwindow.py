"""Multi-window GUI test: export from one window, leave the other untouched."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_multiwindow_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "multiwindow.png")
state = {"ticks": 0, "found": None}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def node_area(window):
    areas = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    if not areas:
        return None, None
    area = max(areas, key=lambda item: item.width * item.height)
    return area, next((item for item in area.regions if item.type == "WINDOW"), None)


def snapshot(window):
    area, _region = node_area(window)
    if area is None:
        return {"window": window.screen.name, "tree": None}
    space = area.spaces.active
    tree = space.edit_tree
    return {
        "window": window.screen.name,
        "tree": tree.name if tree else None,
        "tree_type": space.tree_type,
        "pin": bool(space.pin),
        "header": bool(getattr(space, "show_region_header", False)),
        "ui": bool(getattr(space, "show_region_ui", False)),
        "toolbar": bool(getattr(space, "show_region_toolbar", False)),
        "gizmo": bool(getattr(space, "show_gizmo", False)),
        "selected": sorted(node.name for node in tree.nodes if node.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "smooth_view": bpy.context.preferences.view.smooth_view,
    }


def configure(window, material_name):
    area, region = node_area(window)
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    space.pin = True
    space.node_tree = bpy.data.materials[material_name].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    return area, region


def setup():
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    windows = bpy.context.window_manager.windows
    first = windows[0]
    configure(first, "M_Small")
    area, region = node_area(first)
    with bpy.context.temp_override(window=first, area=area, region=region):
        bpy.ops.wm.window_new()
    windows = bpy.context.window_manager.windows
    if len(windows) != 2:
        fail(f"window_new produced {len(windows)} windows")
    second = [window for window in windows if window != first][0]
    configure(second, "M_Uniq")

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "multiwindow.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return first, [snapshot(first), snapshot(second)]


def tick():
    state["ticks"] += 1
    if os.path.exists(OUTPUT):
        if state["found"] is None:
            state["found"] = state["ticks"]
        if state["ticks"] - state["found"] >= 5:
            try:
                image = bpy.data.images.load(OUTPUT, check_existing=False)
                try:
                    size = tuple(image.size)
                finally:
                    bpy.data.images.remove(image)
                windows = list(bpy.context.window_manager.windows)
                if len(windows) != 2:
                    fail(f"expected 2 windows after restore, got {len(windows)}")
                after = sorted((snapshot(window) for window in windows),
                               key=lambda item: item["window"])
                before = sorted(state["before"], key=lambda item: item["window"])
                if after != before:
                    fail(f"state mismatch: {before} != {after}")
                print(json.dumps({
                    "result": "PASS",
                    "size": size,
                    "windows": [item["tree"] for item in after],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1800:
        fail("timed out waiting for the multi-window export")
    return 0.1


print("NodeAtlas multi-window test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    first, state["before"] = setup()
    area, region = node_area(first)
    with bpy.context.temp_override(window=first, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
