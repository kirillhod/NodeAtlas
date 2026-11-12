# SPDX-License-Identifier: GPL-3.0-or-later
"""Artifact smoke test: export with the installed add-on/extension module.

The module key differs between a classic install (``node_atlas``) and an
extension (``bl_ext.<repo>.node_atlas``), so it is discovered at runtime.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = tempfile.mkdtemp(prefix="nodeatlas_artifact_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "artifact.png")
state = {"ticks": 0, "found": None, "module": None}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def addon_key():
    keys = [
        key for key in bpy.context.preferences.addons.keys()
        if key == "node_atlas" or key.endswith(".node_atlas")
    ]
    if not keys:
        try:
            bpy.ops.preferences.addon_enable(module="node_atlas")
        except Exception:
            pass
        keys = [
            key for key in bpy.context.preferences.addons.keys()
            if key == "node_atlas" or key.endswith(".node_atlas")
        ]
    if not keys:
        fail("NodeAtlas is neither installed nor enabled in this profile")
    return keys[0]


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


def setup(module):
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

    prefs = bpy.context.preferences.addons[module].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "artifact.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot()


def tick():
    package = sys.modules.get(state["module"])
    if package is None or not hasattr(package, "operators"):
        fail(f"module {state['module']} has not been imported")
    operators = package.operators

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
                if snapshot() != state["before"]:
                    fail(f"state mismatch: {state['before']} != {snapshot()}")
                if not operators.last_result or not operators.last_result["ok"]:
                    fail(f"export did not succeed: {operators.last_result}")
                print(json.dumps({
                    "result": "PASS",
                    "module": state["module"],
                    "size": size,
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the artifact export")
    return 0.1


print("NodeAtlas artifact test output:", OUT, flush=True)
try:
    state["module"] = addon_key()
    print("module:", state["module"], flush=True)
    state["before"] = setup(state["module"])
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the artifact export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
