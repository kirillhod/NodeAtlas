# SPDX-License-Identifier: GPL-3.0-or-later
"""Long-link GUI test: a connection crossing a middle tile must not fade.

Blender dims a link to 5 % when the nearer of its two sockets is about a tenth
of the view width away from the view (report §5 item 17). A connection that
spans three tiles therefore fades across the middle tile. The add-on selects
the nodes outside each tile, which exempts their links from that fade, and
mutes the selected-link tint so the colour stays unchanged.

Run from the repository root in a visible Blender window:

blender --factory-startup --python tests/gui/test_longlink.py

Also checks that selection, the theme alpha and undo are untouched.
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

import numpy as np

import png_content
from node_atlas import bounds

OUT = tempfile.mkdtemp(prefix="nodeatlas_longlink_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
OUTPUT = os.path.join(OUT, "longlink.png")
PADDING = 20
DPI = int(os.environ.get("NODEATLAS_TEST_DPI", "96"))
SPAN = int(os.environ.get("NODEATLAS_TEST_SPAN", "12000"))
MIN_WIDTH = 9000
state = {"ticks": 0, "found": None, "before": None, "tree": None}


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


def highlight_alpha():
    color = getattr(
        bpy.context.preferences.themes[0].node_editor, "wire_select", None
    )
    return None if color is None else float(color[3])


def build_tree():
    # Reuse a fixture material: a material created here would disappear on the
    # undo below (the first step restores the file as opened), taking its tree
    # with it and invalidating the references this test checks afterwards.
    material = bpy.data.materials["M_Small"]
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    value = tree.nodes.new("ShaderNodeValue")
    value.location = (0.0, 0.0)
    value.label = "SRC"
    math = tree.nodes.new("ShaderNodeMath")
    math.location = (SPAN, 0.0)
    math.operation = "ADD"
    math.label = "DST"
    tree.links.new(value.outputs[0], math.inputs[0])

    sentinel = tree.nodes.new("ShaderNodeMath")
    sentinel.label = "UNDO_SENTINEL"
    sentinel.location = (0.0, -400.0)
    sentinel.select = True
    math.select = True
    tree.nodes.active = sentinel
    return tree, value, math


def setup():
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    window = bpy.context.window_manager.windows[0]
    area, region = node_area()
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"

    tree, value, math = build_tree()
    space.pin = True
    space.node_tree = tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        bpy.ops.ed.undo_push(message="nodeatlas sentinel")

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = "longlink.png"
    prefs.output_dpi = DPI
    prefs.padding = PADDING
    prefs.max_mp = 200.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True

    state["tree"] = tree
    return {
        "selected": sorted(node.name for node in tree.nodes if node.select),
        "active": tree.nodes.active.name if tree.nodes.active else None,
        "highlight_alpha": highlight_alpha(),
        "value": value.name,
        "math": math.name,
    }


def measure():
    tree = state["tree"]
    value = tree.nodes[state["before"]["value"]]
    math = tree.nodes[state["before"]["math"]]
    pixels = png_content.read_rgba(OUTPUT)
    height, width, _channels = pixels.shape
    background = pixels[0, 0, :3].astype(np.int16)

    left = min(bounds.absolute_location(node)[0] for node in tree.nodes)
    right = max(
        bounds.absolute_location(node)[0] + node.dimensions.x
        for node in tree.nodes
    )
    padding_px = round(PADDING * DPI / 96.0)
    upp = (width - 2 * padding_px) / max(1.0, right - left)

    def column_dev(px):
        band = pixels[:, px, :3].astype(np.int16)
        return np.abs(band - background).max(axis=1)

    def link_row(x_unit):
        px = int(round((x_unit - left) * upp + padding_px))
        dev = column_dev(px)
        dev[: max(0, padding_px - 2)] = 0
        dev[height - padding_px :] = 0
        return int(dev.argmax())

    start = bounds.absolute_location(value)[0] + value.dimensions.x + 40.0
    end = bounds.absolute_location(math)[0] - 40.0
    row_a = link_row(start + (end - start) * 0.01)
    row_b = link_row(start + (end - start) * 0.99)
    row_lo = max(0, min(row_a, row_b) - 6)
    row_hi = min(height, max(row_a, row_b) + 7)

    samples = []
    for index in range(21):
        fraction = 0.02 + 0.96 * index / 20
        px = int(
            round((start + (end - start) * fraction - left) * upp + padding_px)
        )
        band = pixels[row_lo:row_hi, px, :3].astype(np.int16)
        samples.append(int(np.abs(band - background).max(axis=1).max()))

    peak = max(samples)
    trough = min(samples)
    median = float(np.median(samples))
    return {
        "size": [width, height],
        "upp": round(upp, 4),
        "span_units": round(right - left, 1),
        "samples": samples,
        "peak": peak,
        "trough": trough,
        "median": median,
        "ratio": round(trough / peak, 3) if peak else 0.0,
        "median_ratio": round(median / peak, 3) if peak else 0.0,
    }


def check_capture(result):
    width = result["size"][0]
    minimum = MIN_WIDTH * DPI // 96
    if width < minimum:
        fail(
            f"graph is {width} px wide, expected at least {minimum}: "
            "the export did not span several tiles"
        )
    if result["peak"] < 80:
        fail(f"link is not visible: peak deviation {result['peak']}")
    # A fade covers most of the link, so the median catches it with a wide
    # margin. The trough alone is weaker evidence: on 4.2/4.5 a 1-px link
    # varies by up to 16% from sub-pixel anti-aliasing, which is not a fade.
    if result["median_ratio"] < 0.9:
        fail(
            "the link fades across the middle tiles: "
            f"median/peak = {result['median_ratio']} ({result['samples']})"
        )
    if result["ratio"] < 0.75:
        fail(
            "the link drops out somewhere along its length: "
            f"trough/peak = {result['ratio']} ({result['samples']})"
        )


def check_state():
    tree = state["tree"]
    selected = sorted(node.name for node in tree.nodes if node.select)
    active = tree.nodes.active.name if tree.nodes.active else None
    if selected != state["before"]["selected"]:
        fail(f"selection: before={state['before']['selected']} after={selected}")
    if active != state["before"]["active"]:
        fail(f"active node: before={state['before']['active']} after={active}")
    alpha = highlight_alpha()
    if alpha != state["before"]["highlight_alpha"]:
        fail(
            "theme wire_select alpha was not restored: "
            f"before={state['before']['highlight_alpha']} after={alpha}"
        )


def check_undo():
    def has_sentinel():
        # Undo recreates the datablocks, so re-resolve the tree each time.
        tree = bpy.data.materials["M_Small"].node_tree
        return any(node.label == "UNDO_SENTINEL" for node in tree.nodes)

    if not has_sentinel():
        fail("sentinel is missing before undo")
    window = bpy.context.window_manager.windows[0]
    area, region = node_area()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.ed.undo()
    if has_sentinel():
        fail("undo did not remove the sentinel (pipeline pushed an undo step)")
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.ed.redo()
    if not has_sentinel():
        fail("redo did not restore the sentinel")


def finish():
    result = measure()
    check_capture(result)
    check_state()
    check_undo()
    print(json.dumps({"result": "PASS", "path": OUTPUT, **result}, indent=2))
    sys.stdout.flush()
    os._exit(0)


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
        fail("timed out waiting for the export")
    return 0.1


print("NodeAtlas long-link test output:", OUT)
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
