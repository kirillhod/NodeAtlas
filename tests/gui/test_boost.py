# SPDX-License-Identifier: GPL-3.0-or-later
"""DPI GUI test: a high DPI raises Resolution Scale temporarily and restores it."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_boost_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_one.blend")
OUTPUT = os.path.join(OUT, "boost.png")
DPI = 300
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
        return window, None, None
    area = max(areas, key=lambda item: item.width * item.height)
    return window, area, next((item for item in area.regions if item.type == "WINDOW"), None)


def snapshot():
    _window, area, _region = node_area()
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
    window, area, region = node_area()
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

    bpy.context.preferences.view.ui_scale = 1.0
    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "boost.png"
    prefs.output_dpi = DPI
    prefs.padding = 20
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
                result = operators.last_result
                if not result or not result["ok"]:
                    fail(f"export did not succeed: {result}")
                if any("DPI clamped" in item for item in result["warnings"]):
                    fail(f"DPI was still clamped: {result['warnings']}")
                if snapshot() != state["before"]:
                    fail(f"state mismatch: {state['before']} != {snapshot()}")
                if abs(bpy.context.preferences.view.ui_scale - 1.0) > 1e-6:
                    fail(f"view.ui_scale was not restored: {bpy.context.preferences.view.ui_scale}")
                print(json.dumps({"result": "PASS", "size": size, "dpi": DPI}, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the boosted-DPI export")
    return 0.1


print("NodeAtlas DPI boost test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    window, area, region = node_area()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the boosted-DPI export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
