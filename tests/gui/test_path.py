# SPDX-License-Identifier: GPL-3.0-or-later
"""Path GUI test: an empty Default Directory must not fall back to a temp folder."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_path_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_one.blend")
OUTPUT = os.path.join(OUT, "path.png")
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
    prefs.default_dir = ""
    prefs.filename_pattern = "path.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return prefs


def tick():
    from node_atlas import operators

    state["ticks"] += 1
    if os.path.exists(OUTPUT):
        if state["found"] is None:
            state["found"] = state["ticks"]
        if state["ticks"] - state["found"] >= 5:
            result = operators.last_result
            if not result or not result["ok"]:
                fail(f"export with a directory did not succeed: {result}")
            print(json.dumps({"result": "PASS", "path": result["path"]}, indent=2))
            sys.stdout.flush()
            os._exit(0)
    if state["ticks"] > 1200:
        fail("timed out waiting for the path export")
    return 0.1


print("NodeAtlas path test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    prefs = setup()
    from node_atlas import operators

    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        try:
            bpy.ops.node_atlas.export_png()
        except RuntimeError as exc:
            message = str(exc)
        else:
            fail("an empty Default Directory did not stop the export")
    if "Default Directory" not in message:
        fail(f"unexpected empty-directory error: {message}")
    if operators._current_job is not None or operators.last_result is not None:
        fail("a job started despite the empty Default Directory")
    if os.path.exists(OUTPUT):
        fail("the empty-directory attempt created a PNG")

    prefs.default_dir = OUT + os.sep
    with bpy.context.temp_override(window=window, area=area, region=region):
        result = bpy.ops.node_atlas.export_png()
    if "FINISHED" not in result:
        fail(f"export with a directory was not started: {result}")
except Exception:
    fail("could not run the path test:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
