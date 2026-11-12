# SPDX-License-Identifier: GPL-3.0-or-later
"""Cancel GUI test: start a large export, cancel during capture, verify restore."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_cancel_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "cancel.png")
state = {"ticks": 0, "cancelled": False, "stage": None}


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
        "header": bool(getattr(space, "show_region_header", False)),
        "ui": bool(getattr(space, "show_region_ui", False)),
        "toolbar": bool(getattr(space, "show_region_toolbar", False)),
        "gizmo": bool(getattr(space, "show_gizmo", False)),
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
    space.node_tree = bpy.data.materials["M_Uniq"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    tree = space.edit_tree
    for node in tree.nodes:
        node.select = False
    tree.nodes.active = None

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "cancel.png"
    prefs.output_dpi = 192  # D=2, enough tiles to cancel during capture
    prefs.padding = 20
    prefs.max_mp = 150.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot()


def tick():
    from node_atlas import operators

    state["ticks"] += 1
    job = operators._current_job
    if job is not None:
        state["stage"] = job.stage
        if job.stage == "capture" and not state["cancelled"]:
            area, region = node_area()
            window = bpy.context.window_manager.windows[0]
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.node_atlas.cancel_export()
            state["cancelled"] = True
            return 0.05
        if state["ticks"] > 1800:
            fail(f"timed out waiting for the job; stage={job.stage}")
        return 0.05

    if not state["cancelled"]:
        fail(f"export finished before it could be cancelled; last stage={state['stage']}")
    if os.path.exists(OUTPUT):
        fail("cancelled export still created the PNG")
    if snapshot() != state["before"]:
        fail(f"state mismatch after cancel: {state['before']} != {snapshot()}")
    print(json.dumps({
        "result": "PASS",
        "cancelled_stage": state["stage"],
        "output_created": False,
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


print("NodeAtlas cancel test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.05)
