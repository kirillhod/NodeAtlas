"""Repeatability GUI test: two deterministic exports must match pixel-for-pixel."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = tempfile.mkdtemp(prefix="nodeatlas_repeat_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
state = {"ticks": 0, "phase": 0, "found": None}


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
    space.node_tree = bpy.data.materials["M_Small"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "a.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return os.path.join(OUT, "a.png")


def start_export():
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()


def read_pixels(path):
    image = bpy.data.images.load(path, check_existing=False)
    try:
        image.colorspace_settings.name = "Non-Color"
        width, height = image.size
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        return np.clip(
            pixels.reshape(height, width, 4) * 255.0 + 0.5, 0, 255
        ).astype(np.uint8)
    finally:
        bpy.data.images.remove(image)


def tick():
    state["ticks"] += 1
    if state["phase"] == 0:
        path = os.path.join(OUT, "a.png")
        if os.path.exists(path):
            if state["found"] is None:
                state["found"] = state["ticks"]
            if state["ticks"] - state["found"] >= 5:
                state["first"] = read_pixels(path)
                prefs = bpy.context.preferences.addons["node_atlas"].preferences
                prefs.filename_pattern = "b.png"
                state["phase"] = 1
                state["found"] = None
                start_export()
                return 0.2
    else:
        path = os.path.join(OUT, "b.png")
        if os.path.exists(path):
            if state["found"] is None:
                state["found"] = state["ticks"]
            if state["ticks"] - state["found"] >= 5:
                second = read_pixels(path)
                first = state["first"]
                if first.shape != second.shape:
                    fail(f"shape mismatch: {first.shape} != {second.shape}")
                differing = int((first != second).any(axis=2).sum())
                if differing:
                    fail(f"{differing} pixels differ between deterministic exports")
                print(json.dumps({
                    "result": "PASS",
                    "size": [first.shape[1], first.shape[0]],
                    "differing_pixels": differing,
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
    if state["ticks"] > 1800:
        fail("timed out waiting for repeatability export")
    return 0.1


print("NodeAtlas repeatability test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["output"] = setup()
    start_export()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
