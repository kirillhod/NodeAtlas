# SPDX-License-Identifier: GPL-3.0-or-later
"""Selected-only compositor test.

Blender 4.2/4.5 cannot pin a compositor tree (native crash) and the scene tree
is read-only, so a filtered copy cannot be displayed: the add-on must refuse
with a clear error and restore the editor. 5.1+ exports the selection.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for extra in (ROOT, os.path.dirname(os.path.abspath(__file__))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import png_content  # noqa: E402
from node_atlas import job  # noqa: E402

OUT = tempfile.mkdtemp(prefix="nodeatlas_selected_comp_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_graphs.blend")
OUTPUT = os.path.join(OUT, "selected_comp.png")
PADDING = 20
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
        return None, None, window
    area = max(areas, key=lambda item: item.width * item.height)
    return area, next((item for item in area.regions if item.type == "WINDOW"), None), window


def snapshot():
    area, _region, _window = node_area()
    if area is None:
        return None
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
    area, region, window = node_area()
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    scene = window.scene
    tree = getattr(scene, "compositing_node_group", None) or scene.node_tree
    space.pin = False
    space.tree_type = "CompositorNodeTree"
    if hasattr(space, "show_backdrop"):
        space.show_backdrop = False
    space.pin = bpy.app.version >= (5, 1, 0)
    space.node_tree = tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    if space.edit_tree is not tree:
        fail("compositor tree is not displayed")

    keep = {"C_layers", "C_glare"}
    for node in tree.nodes:
        node.select = node.label in keep
        if node.select:
            tree.nodes.active = node
    if not any(node.select for node in tree.nodes):
        fail("fixture selection is empty")

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "selected_comp.png"
    prefs.output_dpi = 96
    prefs.padding = PADDING
    prefs.max_mp = 100.0
    prefs.scope = "SELECTED"
    prefs.hide_ui = True
    return snapshot()


def finish(before):
    result = job.last_result
    if result is None:
        fail("export never finished")
    after = snapshot()
    if after != before:
        fail(f"state mismatch after export: {before} != {after}")

    if bpy.app.version < (5, 1, 0):
        if result["ok"]:
            fail("selected-only compositor export should be refused below 5.1")
        message = result["message"] or ""
        if "5.1 or newer" not in message:
            fail(f"unexpected refusal message: {message!r}")
        if os.path.exists(OUTPUT):
            fail("refused export still wrote a file")
        print(json.dumps({
            "result": "PASS",
            "version": bpy.app.version_string,
            "mode": "refused",
            "message": message,
        }, indent=2))
        sys.stdout.flush()
        os._exit(0)

    if not result["ok"]:
        fail(f"selected-only compositor export failed: {result['error']}")
    if not os.path.isfile(OUTPUT):
        fail("missing output file")
    image = bpy.data.images.load(OUTPUT, check_existing=False)
    try:
        width, height = image.size
    finally:
        bpy.data.images.remove(image)
    png_content.check_capture(OUTPUT, PADDING)
    if width <= 0 or height <= 0:
        fail("empty PNG")
    if width > 1500:
        fail(f"selection was not filtered: {width}x{height}")
    print(json.dumps({
        "result": "PASS",
        "version": bpy.app.version_string,
        "mode": "exported",
        "size": [width, height],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


def tick():
    state["ticks"] += 1
    if job.last_result is not None:
        try:
            finish(state["before"])
        except Exception:
            fail("post-export checks failed:\n" + traceback.format_exc())
    if state["ticks"] > 900:
        fail("timed out waiting for the export")
    return 0.1


print("NodeAtlas selected compositor output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region, window = node_area()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
