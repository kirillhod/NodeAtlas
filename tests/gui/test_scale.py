# SPDX-License-Identifier: GPL-3.0-or-later
"""UI-scale GUI test: the per-tile selection must stay outside the captured tile.

At effective UI scale 1.25 node *positions* scale by ``s`` while node *sizes*
scale by ``k`` (report §4.3). A selection box that used ``k`` for both put a
visible node outside its assumed tile position, selected it, and captured its
selection outline and frame tint in the PNG. The probe measures every selected
node with the same ``node_rect`` the anchor uses, after the redraw and before
the screenshot is returned.
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
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import png_content  # noqa: E402

OUT = tempfile.mkdtemp(prefix="nodeatlas_scale_")
PATH = os.path.join(OUT, "scale.png")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
PADDING = 40  # 20 units at 192 DPI
state = {"ticks": 0, "tiles": 0, "violations": []}


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


def install_probe():
    from node_atlas import bounds, capture, job

    original = capture.capture_tile

    def wrapped(window, area, region, width, height, bottom_ui, pad):
        shot = original(window, area, region, width, height, bottom_ui, pad)
        state["tiles"] += 1
        current = job.current_job()
        if current is None or not current.link_selection_fix:
            return shot
        # Measured after the redraw inside capture_tile, so the view is current.
        metrics = bounds.measure_view(region.view2d, current.anchor[1])
        vis = current.anchor[2]
        for node in current.tree.nodes:
            if not node.select:
                continue
            rect = bounds.node_rect(node, metrics, vis)
            if (
                rect.right > pad + 2
                and rect.left < width - pad - 2
                and rect.top > bottom_ui + pad + 2
                and rect.bottom < region.height - pad - 2
            ):
                state["violations"].append(node.name)
        return shot

    capture.capture_tile = wrapped


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
    prefs.filename_pattern = "scale.png"
    prefs.output_dpi = 192
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.transparent = False
    # The export snapshots and restores this value.
    bpy.context.preferences.view.ui_scale = 1.25
    return window, area, region


def start_export(parts):
    window, area, region = parts
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()


def tick():
    state["ticks"] += 1
    from node_atlas import job as jobmod

    if os.path.exists(PATH) and jobmod.current_job() is None:
        if state["tiles"] < 2:
            fail(f"only {state['tiles']} tile(s) captured; the test needs a tiled export")
        if state["violations"]:
            names = ", ".join(sorted(set(state["violations"])))
            fail(f"selected nodes intersect the captured tiles: {names}")
        info = png_content.check_capture(PATH, PADDING)
        print(json.dumps({
            "result": "PASS",
            "size": info["size"],
            "tiles": state["tiles"],
            "selected_outside": 0,
        }, indent=2))
        sys.stdout.flush()
        os._exit(0)
    if state["ticks"] > 1800:
        fail("timed out waiting for the UI-scale export")
    return 0.1


print("NodeAtlas UI-scale test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    install_probe()
    parts = setup()
    start_export(parts)
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
