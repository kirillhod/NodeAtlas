# SPDX-License-Identifier: GPL-3.0-or-later
"""Multi-area GUI test: two Node Editors, export from one, restore both."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_multiarea_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "multiarea.png")
state = {"ticks": 0, "found": None}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def node_areas(window=None):
    window = window or bpy.context.window_manager.windows[0]
    areas = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    return sorted(areas, key=lambda area: (area.x, area.y))


def area_snapshot(area):
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
    window = bpy.context.window_manager.windows[0]
    area = max(window.screen.areas, key=lambda item: item.width * item.height)
    area.type = "NODE_EDITOR"
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    space.pin = True
    space.node_tree = bpy.data.materials["M_Small"].node_tree
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.5)

    areas = node_areas(window)
    if len(areas) != 2:
        fail(f"area split produced {len(areas)} node editors")
    left, right = areas
    left.spaces.active.tree_type = "ShaderNodeTree"
    left.spaces.active.pin = True
    left.spaces.active.node_tree = bpy.data.materials["M_Small"].node_tree
    right.spaces.active.tree_type = "ShaderNodeTree"
    right.spaces.active.pin = True
    right.spaces.active.node_tree = bpy.data.materials["M_Uniq"].node_tree

    for target in (left, right):
        target_region = next(
            (item for item in target.regions if item.type == "WINDOW"), None
        )
        with bpy.context.temp_override(window=window, area=target, region=target_region):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "multiarea.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return [area_snapshot(item) for item in (left, right)]


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
                areas = node_areas()
                if len(areas) != 2:
                    fail(f"expected 2 node editors after restore, got {len(areas)}")
                after = [area_snapshot(item) for item in areas]
                if after != state["before"]:
                    fail(f"state mismatch: {state['before']} != {after}")
                print(json.dumps({
                    "result": "PASS",
                    "size": size,
                    "areas": [item["tree"] for item in after],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1800:
        fail("timed out waiting for the multi-area export")
    return 0.1


print("NodeAtlas multi-area test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area = node_areas()[0]
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
