"""Limit GUI test: minimum density with the largest allowed padding."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_limits_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_one.blend")
OUTPUT = os.path.join(OUT, "limits.png")
PADDING = 120
state = {"ticks": 0, "found": None}


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
    space.node_tree = bpy.data.materials["M_One"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "limits.png"
    prefs.output_dpi = 1  # below D_min: must clamp up
    prefs.padding = PADDING
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot()


def tick():
    from node_atlas import operators

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
                if size[0] <= 2 * PADDING or size[1] <= 2 * PADDING:
                    fail(f"output is too small for padding {PADDING}: {size}")
                result = operators.last_result
                if not result or not result["ok"]:
                    fail(f"export did not succeed: {result}")
                if not any("DPI clamped" in item for item in result["warnings"]):
                    fail(f"D_min clamp was not reported: {result['warnings']}")
                after = snapshot()
                if after != state["before"]:
                    fail(f"state mismatch: {state['before']} != {after}")
                print(json.dumps({
                    "result": "PASS",
                    "size": size,
                    "padding": PADDING,
                    "warnings": result["warnings"],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the limits export")
    return 0.1


print("NodeAtlas limits test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
