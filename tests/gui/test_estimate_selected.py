# SPDX-License-Identifier: GPL-3.0-or-later
"""Selected-estimate GUI test: the panel must use the selected subgraph."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_estimate_selected_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_selected.blend")
OUTPUT = os.path.join(OUT, "estimate_selected.png")
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


def estimate():
    import node_atlas

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    layout = node_atlas._estimate(bpy.context, prefs)
    if layout is None:
        fail("the panel estimate is unavailable")
    return (layout.final_w, layout.final_h)


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
    space.node_tree = bpy.data.materials["M_Sel"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    tree = space.edit_tree
    for node in tree.nodes:
        node.select = node.label in {"N1", "R1"}
        if node.select:
            tree.nodes.active = node
    before = snapshot()

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "estimate_selected.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return before


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
                expected = state["selected"]
                if any(abs(a - b) > 3 for a, b in zip(size, expected)):
                    fail(f"selected estimate {expected} does not match the PNG {size}")
                if snapshot() != state["before"]:
                    fail(f"state mismatch: {state['before']} != {snapshot()}")
                print(json.dumps({
                    "result": "PASS",
                    "full": list(state["full"]),
                    "selected": list(expected),
                    "actual": list(size),
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the selected estimate export")
    return 0.1


print("NodeAtlas selected-estimate test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    state["full"] = estimate()
    bpy.context.preferences.addons["node_atlas"].preferences.scope = "SELECTED"
    state["selected"] = estimate()
    if state["selected"] == state["full"]:
        fail("selected estimate equals the full-tree estimate")
    if state["selected"][0] > state["full"][0] or state["selected"][1] > state["full"][1]:
        fail(f"selected estimate is not smaller: {state['selected']} vs {state['full']}")
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the selected estimate export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
