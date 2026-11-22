# SPDX-License-Identifier: GPL-3.0-or-later
"""Padding unit test: 20 units must become 40 final pixels at 192 DPI.

The preference is density-independent, so the band keeps the same proportion
to the graph. A regression to final-image pixels would leave content in the
outer 40 px and fail ``png_content``.
"""

from __future__ import annotations

import json
import math
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

OUT = tempfile.mkdtemp(prefix="nodeatlas_padding_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "padding.png")
UNITS = 20
DPI = 192
PADDING_PX = round(UNITS * DPI / 96)
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


def estimate():
    import node_atlas

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    layout = node_atlas._estimate(bpy.context, prefs)
    if layout is None:
        fail("the panel estimate is unavailable")
    return (layout.final_w, layout.final_h)


def snapshot():
    area, _region, _window = node_area()
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
    area, region, window = node_area()
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
    prefs.filename_pattern = "padding.png"
    prefs.output_dpi = DPI
    prefs.padding = UNITS
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    return snapshot(), estimate()


def finish(before, expected):
    result = job.last_result
    if result is None:
        fail("export never finished")
    if not result["ok"]:
        fail(f"padding export failed: {result['error']}")
    path = result["path"] or OUTPUT
    if not os.path.isfile(path):
        fail(f"missing output {path}")
    image = bpy.data.images.load(path, check_existing=False)
    try:
        size = tuple(image.size)
    finally:
        bpy.data.images.remove(image)
    # The band must really be 40 px of background at D=2.
    content = png_content.check_capture(path, PADDING_PX)
    # The estimate assumes the target upp, while set_zoom stops within 0.2 %
    # of it (report 4.3), so a high DPI image can differ by a few pixels. The
    # padding band itself was checked exactly above.
    slack = max(3, math.ceil(max(expected) * 0.003))
    if any(abs(a - b) > slack for a, b in zip(size, expected)):
        fail(f"estimate {expected} does not match the PNG {size} (slack {slack})")
    if snapshot() != before:
        fail(f"state mismatch: {before} != {snapshot()}")
    if estimate() != expected:
        fail(f"estimate changed after restore: {estimate()} != {expected}")
    print(json.dumps({
        "result": "PASS",
        "dpi": DPI,
        "units": UNITS,
        "padding_px": PADDING_PX,
        "size": list(size),
        "content_pixels": content["content_pixels"],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


def tick():
    state["ticks"] += 1
    if job.last_result is not None:
        try:
            finish(state["before"], state["expected"])
        except Exception:
            fail("post-export checks failed:\n" + traceback.format_exc())
    if state["ticks"] > 900:
        fail("timed out waiting for the export")
    return 0.1


print("NodeAtlas padding test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"], state["expected"] = setup()
    area, region, window = node_area()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
