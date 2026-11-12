# SPDX-License-Identifier: GPL-3.0-or-later
"""Scaling GUI test: the same graph exports at the same size across UI scales.

The effective UI scale is the OS scale times ``view.ui_scale`` (Resolution Scale).
Four effective scales are exercised in one session; each export must restore the view
and produce the same pixel size.
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

OUT = tempfile.mkdtemp(prefix="nodeatlas_scaling_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_one.blend")
EFFECTIVE = (1.0, 1.25, 1.5, 2.0)
state = {"ticks": 0, "index": 0, "waiting": False, "sizes": []}


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
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    state["os_scale"] = bpy.context.preferences.system.ui_scale
    return snapshot()


def start_next(output):
    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    effective = EFFECTIVE[state["index"]]
    view_scale = min(4.0, max(0.5, effective / state["os_scale"]))
    bpy.context.preferences.view.ui_scale = view_scale
    state["view_before"] = view_scale
    prefs.filename_pattern = os.path.basename(output)
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
    state["waiting"] = True


def finish():
    prefs = bpy.context.preferences
    prefs.view.ui_scale = state["before"]["ui_scale"]
    after = snapshot()
    if after != state["before"]:
        fail(f"state mismatch after scaling runs: {state['before']} != {after}")
    widths = [size[0] for _scale, size in state["sizes"]]
    heights = [size[1] for _scale, size in state["sizes"]]
    spread_w = max(widths) - min(widths)
    spread_h = max(heights) - min(heights)
    # Node layout is quantized in UI pixels, so the content size drifts a little
    # between scales. A scale bug would be 2x-4x, not a few percent.
    if spread_w > max(8, 0.1 * min(widths)) or spread_h > max(8, 0.1 * min(heights)):
        fail(f"output size depends on the UI scale: {state['sizes']}")
    print(json.dumps({
        "result": "PASS",
        "sizes": [
            {"effective_scale": scale, "size": list(size)}
            for scale, size in state["sizes"]
        ],
        "spread": [spread_w, spread_h],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


def tick():
    from node_atlas import operators

    state["ticks"] += 1
    if operators._current_job is not None:
        if state["ticks"] > 3600:
            fail("timed out waiting for a scaling export")
        return 0.1

    if not state["waiting"]:
        if state["index"] >= len(EFFECTIVE):
            finish()
            return None
        state["output"] = os.path.join(OUT, f"scale_{state['index']}.png")
        start_next(state["output"])
        return 0.1

    if not os.path.exists(state["output"]):
        if state["ticks"] > 3600:
            fail("timed out waiting for the scaling PNG")
        return 0.1

    result = operators.last_result
    if not result or not result["ok"]:
        fail(f"scaling export failed: {result}")
    expected_view = state["view_before"]
    if abs(bpy.context.preferences.view.ui_scale - expected_view) > 1e-6:
        fail(f"view.ui_scale was not restored: {bpy.context.preferences.view.ui_scale}")
    image = bpy.data.images.load(state["output"], check_existing=False)
    try:
        size = tuple(image.size)
    finally:
        bpy.data.images.remove(image)
    scale = EFFECTIVE[state["index"]]
    state["sizes"].append((scale, size))
    state["index"] += 1
    state["waiting"] = False
    return 0.1


print("NodeAtlas scaling test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
except Exception:
    fail("could not prepare the scaling test:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
