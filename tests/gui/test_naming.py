# SPDX-License-Identifier: GPL-3.0-or-later
"""Naming and DPI GUI test: owner-based filename and pHYs density."""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = tempfile.mkdtemp(prefix="nodeatlas_naming_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
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


def png_phys_dpi(path):
    with open(path, "rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("bad PNG signature")
        while True:
            header = handle.read(8)
            if len(header) < 8:
                return None
            length = struct.unpack(">I", header[:4])[0]
            tag = header[4:8]
            data = handle.read(length)
            handle.read(4)
            if tag == b"pHYs":
                ppu_x, ppu_y, unit = struct.unpack(">IIB", data)
                return ppu_x * 0.0254, ppu_y * 0.0254, unit
            if tag == b"eXIf":
                raise RuntimeError("EXIF block is still present")
            if tag == b"IEND":
                return None


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
    prefs.filename_pattern = "{tree}_{type}_{datablock}.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return space.edit_tree.name


def tick():
    from node_atlas import operators

    state["ticks"] += 1
    if os.path.exists(state["output"]):
        if state["found"] is None:
            state["found"] = state["ticks"]
        if state["ticks"] - state["found"] >= 5:
            try:
                result = operators.last_result
                if not result or not result["ok"]:
                    fail(f"export did not succeed: {result}")
                if result["path"] != state["output"]:
                    fail(f"unexpected path: {result['path']} != {state['output']}")
                dpi = png_phys_dpi(state["output"])
                if dpi is None:
                    fail("PNG has no pHYs chunk")
                if abs(dpi[0] - 96.0) > 0.1 or abs(dpi[1] - 96.0) > 0.1 or dpi[2] != 1:
                    fail(f"unexpected pHYs density: {dpi}")
                print(json.dumps({
                    "result": "PASS",
                    "file": os.path.basename(state["output"]),
                    "dpi": [round(dpi[0], 2), round(dpi[1], 2)],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the naming export")
    return 0.1


print("NodeAtlas naming test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    from node_atlas import operators

    tree_name = setup()
    expected = operators.render_filename(
        "{tree}_{type}_{datablock}.png",
        {
            "blend": "scene_both",
            "tree": operators._safe_name("M_Small"),
            "datablock": operators._safe_name(tree_name),
            "type": "Shader",
            "date": "20260101-000000",
        },
    )
    state["output"] = os.path.join(OUT, expected)
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the naming export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
