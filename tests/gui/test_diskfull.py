# SPDX-License-Identifier: GPL-3.0-or-later
"""Disk-full GUI test: the writer boundary raises ENOSPC.

The per-run save function fails after writing a partial temporary file, so the
job must report the error, clean up and restore the UI without leaving a PNG.
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

OUT = tempfile.mkdtemp(prefix="nodeatlas_diskfull_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "diskfull.png")
state = {"ticks": 0}


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
    space.node_tree = bpy.data.materials["M_Small"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "diskfull.png"
    prefs.output_dpi = 96
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
    if operators._current_job is not None:
        if state["ticks"] > 1200:
            fail("timed out waiting for the disk-full export to finish")
        return 0.05

    result = operators.last_result
    if result is None:
        fail("the disk-full job never reported a result")
    if result["ok"]:
        fail(f"disk-full export reported success: {result}")
    if os.path.exists(OUTPUT):
        fail("disk-full export still created the PNG")
    if os.path.exists(OUTPUT + ".tmp.png"):
        fail("disk-full export left a temporary PNG")
    if "Not enough free disk space" not in (result["error"] or ""):
        fail(f"unexpected disk-full error: {result['error']}")
    if "UI restored" not in result["message"]:
        fail(f"UI restoration was not reported: {result['message']}")
    if snapshot() != state["before"]:
        fail(f"state mismatch after the disk-full failure: {state['before']} != {snapshot()}")
    print(json.dumps({
        "result": "PASS",
        "output_created": False,
        "temporary_removed": True,
        "restored": True,
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


print("NodeAtlas disk-full test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    from node_atlas import stitch

    def disk_full(image, filepath, dpi=None):
        path = os.path.abspath(filepath)
        temp_path = path + ".tmp.png"
        with open(temp_path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\npartial")
        try:
            raise stitch.OutputError(f"Not enough free disk space to save {path}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    stitch.save_png = disk_full
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the disk-full export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.05)
