# SPDX-License-Identifier: GPL-3.0-or-later
"""Live GUI test for the transparent-background export.

Run from the repository root in a visible Blender window:

blender --factory-startup --python tests/gui/test_transparent.py

It opens tests/fixtures/scene_both.blend, exports M_Small with Transparent
Background on, and requires transparent padding, opaque nodes, partial alpha on
node shadows, and an exactly restored theme background and grid setting.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import numpy as np

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import png_content

OUT = tempfile.mkdtemp(prefix="nodeatlas_transparent_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
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
        return None, None
    area = max(areas, key=lambda item: item.width * item.height)
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    return area, region


def theme_values():
    theme = bpy.context.preferences.themes[0].node_editor
    return (
        tuple(round(channel, 6) for channel in theme.space.back),
        int(theme.grid_levels),
    )


def snapshot():
    area, _region = node_area()
    if area is None:
        return None
    space = area.spaces.active
    tree = space.edit_tree
    return {
        "area_type": area.type,
        "tree": tree.name if tree else None,
        "pin": bool(space.pin),
        "ui": bool(getattr(space, "show_region_ui", False)),
        "header": bool(getattr(space, "show_region_header", False)),
        "selected": sorted(node.name for node in tree.nodes if node.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "theme": theme_values(),
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
    prefs.filename_pattern = "test_transparent.png"
    prefs.output_dpi = 96
    prefs.padding = PADDING
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.transparent = True
    state["output"] = os.path.join(OUT, "test_transparent.png")
    return snapshot()


def check_state(before):
    after = snapshot()
    for key in ("area_type", "tree", "pin", "ui", "header", "selected", "active",
                "ui_scale", "theme"):
        if before.get(key) != after.get(key):
            fail(f"state {key}: before={before.get(key)!r} after={after.get(key)!r}")


def check_alpha(path):
    pixels = png_content.read_rgba(path)
    height, width, channels = pixels.shape
    if channels != 4:
        fail(f"PNG has {channels} channels, expected RGBA")
    alpha = pixels[:, :, 3]

    border = np.concatenate(
        (
            alpha[:2, :].reshape(-1),
            alpha[-2:, :].reshape(-1),
            alpha[:, :2].reshape(-1),
            alpha[:, -2:].reshape(-1),
        )
    )
    if border.size and int(border.max()) > 2:
        fail(f"outer border is not transparent: max alpha {int(border.max())}")

    if PADDING:
        # A node shadow can reach into the inner half of the padding band, as it
        # does in the opaque capture; the background itself must be clear in the
        # outer half, where no shadow or glow can reach.
        half = max(1, PADDING // 2)
        outer_bands = (
            alpha[:half, :],
            alpha[-half:, :],
            alpha[:, :half],
            alpha[:, -half:],
        )
        for band in outer_bands:
            leaked = float((band > 2).mean())
            if leaked > 0.02:
                fail(
                    f"outer padding is {leaked:.1%} non-transparent; "
                    "the background leaked"
                )

    total = alpha.size
    transparent = int((alpha == 0).sum())
    opaque = int((alpha >= 250).sum())
    partial = int(((alpha > 0) & (alpha < 250)).sum())
    if transparent < total // 10:
        fail(f"only {transparent}/{total} transparent pixels; background was not removed")
    if opaque < total // 200:
        fail(f"only {opaque}/{total} opaque pixels; the graph is missing")
    if partial < 50:
        fail(f"only {partial} partial-alpha pixels; node shadows were flattened")

    content = alpha[PADDING:height - PADDING, PADDING:width - PADDING]
    if content.size and int(content.max()) < 250:
        fail("no opaque node pixel inside the padding")

    return {
        "size": [width, height],
        "transparent": transparent,
        "opaque": opaque,
        "partial": partial,
    }


def finish():
    stats = check_alpha(state["output"])
    check_state(state["before"])
    print(json.dumps({"result": "PASS", "path": state["output"], "alpha": stats}, indent=2))
    sys.stdout.flush()
    os._exit(0)


def tick():
    state["ticks"] += 1
    if os.path.exists(state.get("output", "")):
        if state.get("found_tick") is None:
            state["found_tick"] = state["ticks"]
        if state["ticks"] - state["found_tick"] >= 5:
            try:
                finish()
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the transparent export")
    return 0.1


print("NodeAtlas transparent test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not start the transparent export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
