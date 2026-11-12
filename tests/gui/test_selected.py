# SPDX-License-Identifier: GPL-3.0-or-later
"""Selected-only GUI test: export two selected nodes from scene_selected.blend."""

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

from node_atlas import bounds  # noqa: E402

OUT = tempfile.mkdtemp(prefix="nodeatlas_selected_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_selected.blend")
OUTPUT = os.path.join(OUT, "selected.png")
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


def tree_state(tree):
    return {
        "nodes": sorted(node.name for node in tree.nodes),
        "links": sorted((link.from_node.name, link.to_node.name) for link in tree.links),
        "selected": sorted(node.name for node in tree.nodes if node.select),
        "active": tree.nodes.active.name if tree.nodes.active else None,
        "locations": {
            node.name: tuple(bounds.absolute_location(node)) for node in tree.nodes
        },
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
    keep = {"N1", "R1"}
    for node in tree.nodes:
        node.select = node.label in keep
        if node.label in keep:
            tree.nodes.active = node
    before = tree_state(tree)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "selected.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "SELECTED"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return tree, before


def tick():
    state["ticks"] += 1
    if os.path.exists(OUTPUT):
        if state["found"] is None:
            state["found"] = state["ticks"]
        if state["ticks"] - state["found"] >= 5:
            try:
                finish()
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 900:
        fail("timed out waiting for the selected-only export")
    return 0.1


def finish():
    image = bpy.data.images.load(OUTPUT, check_existing=False)
    try:
        width, height = image.size
    finally:
        bpy.data.images.remove(image)
    if width <= 0 or height <= 0:
        fail("selected-only PNG has zero size")
    if width > 1400:
        fail(f"selected-only PNG is unexpectedly wide: {width}px")

    area, _region = node_area()
    tree = area.spaces.active.edit_tree
    if tree is None:
        fail("original tree was not restored")
    after = tree_state(tree)
    if after != state["before"]:
        fail("selected-only export changed the original tree")

    print(json.dumps({
        "result": "PASS",
        "path": OUTPUT,
        "size": [width, height],
        "nodes": len(after["nodes"]),
        "selected": after["selected"],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


print("NodeAtlas selected-only test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    tree, before = setup()
    state["before"] = before
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
