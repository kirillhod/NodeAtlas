# SPDX-License-Identifier: GPL-3.0-or-later
"""Selected-only GUI test: keep links to connected nodes.

Exports the same selection twice, with and without ``keep_links``. The frame
must cover the selected nodes in both runs; with the option on, the link to the
unselected neighbour has to reach the padding band instead of ending at the
selection.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for extra in (ROOT, os.path.dirname(os.path.abspath(__file__))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import png_content  # noqa: E402
from node_atlas import bounds  # noqa: E402
from node_atlas import operators  # noqa: E402

OUT = tempfile.mkdtemp(prefix="nodeatlas_selected_links_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_selected.blend")
PADDING = 60
state = {"ticks": 0, "phase": 0, "before": None, "started": None}


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
    prefs.filename_pattern = "links_off.png"
    prefs.output_dpi = 96
    prefs.padding = PADDING
    prefs.max_mp = 100.0
    prefs.scope = "SELECTED"
    prefs.keep_links = False
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return tree, before


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
        buffer = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(buffer)
        return np.clip(
            buffer.reshape(height, width, 4) * 255.0 + 0.5, 0, 255
        ).astype(np.uint8)
    finally:
        bpy.data.images.remove(image)


def band_bright(pixels, background, tolerance=60):
    """Pixels that stand out like a link in the right padding band.

    The first four columns are skipped: the node outline at the content edge
    legitimately lands on the band boundary by a pixel of rounding.
    """
    band = pixels[:, -(PADDING - 4):, :3].astype(np.int16)
    deviation = np.abs(band - background.astype(np.int16)).max(axis=2)
    return int(np.count_nonzero(deviation > tolerance))


def finish():
    result = operators.last_result
    if result is None or not result["ok"]:
        fail(f"export failed: {result and result.get('error')}")

    off_path = os.path.join(OUT, "links_off.png")
    on_path = os.path.join(OUT, "links_on.png")
    for name, path in (("links_off", off_path), ("links_on", on_path)):
        try:
            png_content.check_capture(path, PADDING)
        except AssertionError as exc:
            fail(f"{name} violates the capture invariants: {exc}")

    off = read_pixels(off_path)
    on = read_pixels(on_path)
    if any(abs(a - b) > 2 for a, b in zip(off.shape, on.shape)):
        fail(f"frame changed with keep_links: {off.shape} != {on.shape}")
    width = off.shape[1]
    height = off.shape[0]
    # B1 sits 1000 node units to the right of N1 at 96 DPI; the selected
    # content is about 750 px wide, so a frame that pulled the neighbour in
    # would be far wider than this.
    if max(width, on.shape[1]) >= 900:
        fail(f"export frame includes the linked neighbour: {width}px wide")

    def background_of(pixels):
        return np.round(
            np.median(pixels[:PADDING:2, ::2, :3].reshape(-1, 3), axis=0)
        ).astype(np.uint8)

    off_bright = band_bright(off, background_of(off))
    on_bright = band_bright(on, background_of(on))
    minimum = 40
    if off_bright > minimum // 2:
        fail(f"links_off already has a link in the right padding: {off_bright} px")
    if on_bright < minimum:
        fail(
            f"keep_links did not draw the link into the right padding: "
            f"{on_bright} px, need {minimum}"
        )

    area, _region = node_area()
    tree = area.spaces.active.edit_tree
    if tree is None:
        fail("original tree was not restored")
    after = tree_state(tree)
    if after != state["before"]:
        fail("selected-only export changed the original tree")

    print(json.dumps({
        "result": "PASS",
        "size": [width, height],
        "padding": PADDING,
        "off_bright": off_bright,
        "on_bright": on_bright,
        "nodes": len(after["nodes"]),
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


def tick():
    state["ticks"] += 1
    result = operators.last_result
    if state["phase"] == 0:
        if result is not None:
            if state["started"] is None:
                state["started"] = state["ticks"]
            elif state["ticks"] - state["started"] >= 5:
                if not result["ok"]:
                    fail(f"links_off export failed: {result.get('error')}")
                state["phase"] = 1
                prefs = bpy.context.preferences.addons["node_atlas"].preferences
                prefs.keep_links = True
                prefs.filename_pattern = "links_on.png"
                state["started"] = None
                start_export()
                return 0.2
    elif result is not None:
        try:
            finish()
        except Exception:
            fail("post-export checks failed:\n" + traceback.format_exc())
        return None
    if state["ticks"] > 1200:
        fail("timed out waiting for the selected-links export")
    return 0.1


print("NodeAtlas selected links test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    tree, before = setup()
    state["before"] = before
    start_export()
except Exception:
    fail("could not start export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
