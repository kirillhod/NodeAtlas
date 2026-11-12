"""1000-node GUI test: exercises the memmap stitching path."""

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

OUT = tempfile.mkdtemp(prefix="nodeatlas_1000_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
DPI = int(os.environ.get("NODEATLAS_TEST_DPI", "96"))
OUTPUT = os.path.join(OUT, "thousand.png")
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
        "node_count": len(tree.nodes) if tree else 0,
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
    tree = space.edit_tree

    for index in range(976):
        node = tree.nodes.new("ShaderNodeMath")
        node.label = f"T{index:04d}"
        node.location = (4000 + (index % 32) * 200, 4000 - (index // 32) * 150)
        node.select = False
    tree.nodes.active = None
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "thousand.png"
    prefs.output_dpi = DPI
    prefs.padding = 20
    prefs.max_mp = 200.0 if DPI > 96 else 150.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot()


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
                if DPI > 96 and size[0] * size[1] < 100_000_000:
                    fail(f"expected a 100+ MP output at {DPI} dpi: {size}")
                after = snapshot()
                if after != state["before"]:
                    fail(f"state mismatch: {state['before']} != {after}")
                print(json.dumps({
                    "result": "PASS",
                    "size": size,
                    "nodes": after["node_count"],
                    "dpi": DPI,
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 3600:
        fail("timed out waiting for the 1000-node export")
    return 0.2


print("NodeAtlas 1000-node test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
