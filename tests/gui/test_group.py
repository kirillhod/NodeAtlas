# SPDX-License-Identifier: GPL-3.0-or-later
"""Group-edit GUI test: export must leave the user inside nested node groups."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_group_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "group.png")
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


def group_state(space):
    return {
        "root": space.node_tree.name if space.node_tree else None,
        "edit": space.edit_tree.name if space.edit_tree else None,
        "pin": bool(space.pin),
        "path": [item.node_tree.name for item in space.path if item.node_tree],
        "selected": sorted(
            node.name for node in space.edit_tree.nodes if node.select
        ) if space.edit_tree else [],
        "active": (
            space.edit_tree.nodes.active.name
            if space.edit_tree and space.edit_tree.nodes.active else None
        ),
    }


def enter_group(space, tree, node_tree):
    node_tree.nodes.active = tree
    tree.select = True
    window, area, region = node_area()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node.group_edit(exit=False)


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
    material = bpy.data.materials["M_Small"]
    space.node_tree = material.node_tree

    group1 = bpy.data.node_groups.new("Group1", "ShaderNodeTree")
    group1.nodes.clear()
    group2 = bpy.data.node_groups.new("Group2", "ShaderNodeTree")
    group2.nodes.clear()
    noise = group2.nodes.new("ShaderNodeTexNoise")
    noise.location = (0, 0)
    outer = material.node_tree.nodes.new("ShaderNodeGroup")
    outer.node_tree = group1
    inner = group1.nodes.new("ShaderNodeGroup")
    inner.node_tree = group2
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    enter_group(space, outer, material.node_tree)
    enter_group(space, inner, group1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "group.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return group_state(space)


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
                window, area, _region = node_area()
                space = area.spaces.active
                after = group_state(space)
                if after != state["before"]:
                    fail(f"group state mismatch: {state['before']} != {after}")
                result = operators.last_result
                if not result or not result["ok"]:
                    fail(f"export did not succeed: {result}")
                print(json.dumps({
                    "result": "PASS",
                    "size": size,
                    "path": after["path"],
                    "edit": after["edit"],
                    "pin": after["pin"],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the group export")
    return 0.1


print("NodeAtlas group-edit test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    window, area, region = node_area()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the group export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
