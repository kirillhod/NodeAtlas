# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture-area preview GUI test.

Exports the same tree twice, with the overlay on and off, and requires the
pixels to match: the preview must never reach a tile. The label must describe
the PNG that the export actually writes, and the overlay suppression must be
cleared after the run.
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
from node_atlas import capture, preview  # noqa: E402

OUT = tempfile.mkdtemp(prefix="nodeatlas_preview_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
PADDING = 20
PADDING_PX = PADDING  # 96 DPI: 1 unit == 1 final pixel
state = {"ticks": 0, "phase": 0, "found": None, "cursor": None}


def fail(message):
    png_content.restore_cursor(state["cursor"])
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
    prefs.filename_pattern = "preview_on.png"
    prefs.output_dpi = 96
    prefs.padding = PADDING
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.show_capture_area = True


def effective_scale():
    return float(bpy.context.preferences.system.ui_scale)


def current_union(est, area, region):
    """Return the live graph bounds used by the draw handler."""
    from node_atlas import bounds, preview

    metrics = bounds.measure_view(region.view2d, effective_scale())
    view_scale = bpy.context.preferences.view.ui_scale
    tree = area.spaces.active.edit_tree
    names = set(est.names) if est.names is not None else None
    nodes = (
        tree.nodes if names is None
        else [node for node in tree.nodes if node.name in names]
    )
    return preview.live_union(nodes, metrics, view_scale)


def current_rect(est, area, region):
    """Return the preview rectangle exactly as the draw handler computes it."""
    return preview.screen_rect(current_union(est, area, region), est)


def start_export():
    # Park the pointer: a hover highlight on a node row would land in one of the
    # two comparison exports and break the pixel equality check. Restored as soon
    # as the file exists.
    state["cursor"] = png_content.park_cursor()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()


def force_redraw():
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


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


def region_pixels():
    """Screenshot the WINDOW region, overlay included, on every version.

    ``screenshot_area`` captures the whole area (header above, sidebar right);
    the WINDOW region is its bottom-left rectangle. Using the operator directly
    keeps the test independent of ``capture_tile``, which expects a maximised
    export area with the sidebar hidden.
    """
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    settings = bpy.context.scene.render.image_settings
    old_format = settings.file_format
    old_mode = settings.color_mode
    descriptor, path = tempfile.mkstemp(prefix="nodeatlas_preview_", suffix=".png")
    os.close(descriptor)
    try:
        settings.file_format = "PNG"
        settings.color_mode = "RGBA"
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.screenshot_area(filepath=path)
        image = bpy.data.images.load(path, check_existing=False)
        try:
            image.colorspace_settings.name = "Non-Color"
            width, height = image.size
            buffer = np.empty(width * height * 4, dtype=np.float32)
            image.pixels.foreach_get(buffer)
            pixels = np.clip(
                buffer.reshape(height, width, 4) * 255.0 + 0.5, 0, 255
            ).astype(np.uint8)
        finally:
            bpy.data.images.remove(image)
    finally:
        settings.file_format = old_format
        settings.color_mode = old_mode
        try:
            os.remove(path)
        except OSError:
            pass
    if width < region.width or height < region.height:
        fail(f"screenshot {width}x{height} is smaller than the region")
    return pixels[0:region.height, 0:region.width]


def frame_mask(shape, rect, band=5):
    """Band around each of the four frame lines, in bottom-up region rows."""
    height, width = shape
    left, top, right, bottom = rect
    xs = np.arange(width)[None, :]
    ys = np.arange(height)[:, None]
    near_x = (np.abs(xs - left) <= band) | (np.abs(xs - right) <= band)
    near_y = (np.abs(ys - bottom) <= band) | (np.abs(ys - top) <= band)
    span_y = (ys >= bottom - band) & (ys <= top + band)
    span_x = (xs >= left - band) & (xs <= right + band)
    return (near_x & span_y) | (near_y & span_x)


def orange_count(pixels, mask):
    rgb = pixels[:, :, :3].astype(np.int16)
    orange = (
        (rgb[:, :, 0] > 170) & (rgb[:, :, 1] > 80)
        & (rgb[:, :, 1] < 205) & (rgb[:, :, 2] < 100)
    )
    return int((orange & mask).sum())


def fit_frame(est):
    """Zoom out until the whole export rectangle is inside the region."""
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    space = area.spaces.active
    height = capture.effective_height(region, capture.bottom_ui_height(area))
    needed = max(
        est.final_w * est.upp / max(region.width, 1),
        est.final_h * est.upp / max(height, 1),
    )
    capture.set_zoom(
        window, area, region, space, needed * 1.2, region.width, height
    )


def check_overlay(pixels):
    import node_atlas

    if preview._handle is None:
        fail("preview handler is missing while the add-on is enabled")
    if preview.suppress:
        fail("overlay suppression was not cleared after the export")

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    est = node_atlas._estimate(bpy.context, prefs)
    if est is None:
        fail("the panel estimate is unavailable after the export")
    if tuple(pixels.shape[1::-1]) != (est.final_w, est.final_h):
        delta = max(
            abs(pixels.shape[1] - est.final_w), abs(pixels.shape[0] - est.final_h)
        )
        if delta > 3:
            fail(
                f"PNG {pixels.shape[1::-1]} does not match the estimate "
                f"{(est.final_w, est.final_h)}"
            )
    text = preview.label(est, prefs)
    if f"{est.final_w} × {est.final_h} px" not in text:
        fail(f"label does not name the PNG size: {text}")
    if f"padding {est.padding_px} px" not in text:
        fail(f"label does not name the padding: {text}")
    if est.padding_px != PADDING_PX:
        fail(f"padding {est.padding_px} != {PADDING_PX}")

    area, region = node_area()
    rect = current_rect(est, area, region)
    if not preview.intersects(rect, region.width, region.height):
        fail(f"frame {rect} is outside {region.width}x{region.height} after restore")
    width, height = rect[2] - rect[0], rect[1] - rect[3]
    if width <= 0 or height <= 0:
        fail(f"outline is empty: {rect}")
    aspect = width / height
    expected = est.final_w / est.final_h
    if abs(aspect - expected) > 0.01 * expected:
        fail(f"outline aspect {aspect:.4f} != PNG aspect {expected:.4f}")
    return text


def tick():
    state["ticks"] += 1
    path = os.path.join(OUT, "preview_on.png" if state["phase"] == 0 else "preview_off.png")
    if not os.path.exists(path):
        if state["ticks"] > 1800:
            fail("timed out waiting for the export")
        return 0.1
    if state["cursor"] is not None:
        png_content.restore_cursor(state["cursor"])
        state["cursor"] = None
    if state["found"] is None:
        state["found"] = state["ticks"]
    if state["ticks"] - state["found"] < 5:
        return 0.1

    if state["phase"] == 0:
        try:
            first = read_pixels(path)
            png_content.check_capture(path, PADDING_PX)
            state["label"] = check_overlay(first)
        except Exception:
            fail("post-export checks failed:\n" + traceback.format_exc())
        state["first"] = first
        prefs = bpy.context.preferences.addons["node_atlas"].preferences
        prefs.show_capture_area = False
        prefs.filename_pattern = "preview_off.png"
        state["phase"] = 1
        state["found"] = None
        start_export()
        return 0.2

    try:
        second = read_pixels(path)
        first = state["first"]
        if first.shape != second.shape:
            fail(f"shape mismatch: {first.shape} != {second.shape}")
        differing = int((first != second).any(axis=2).sum())
        if differing:
            fail(f"{differing} pixels differ with the overlay on and off")
        if preview.suppress:
            fail("overlay suppression is still set after the second export")
    except Exception:
        fail("comparison failed:\n" + traceback.format_exc())
    print(json.dumps({
        "result": "PASS",
        "size": [first.shape[1], first.shape[0]],
        "differing_pixels": differing,
        "frame_pixels": state["visible"],
        "frame_pixels_off": state["hidden"],
        "changed_pixels": state["changed"],
        "changed_pixels_in_frame_band": state["changed_band"],
        "label": state["label"],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


print("NodeAtlas preview test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    setup()
    import node_atlas

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    est = node_atlas._estimate(bpy.context, prefs)
    if est is None:
        fail("the panel estimate is unavailable")

    # The fixture opens at a zoom where the export rectangle can be bigger
    # than the window; zoom out so the frame is visible and testable.
    fit_frame(est)
    force_redraw()
    if preview._frame["count"] == 0:
        fail(f"the overlay did not draw: {preview._frame['error']}")

    area, region = node_area()
    expected = current_rect(est, area, region)
    if not preview.intersects(expected, region.width, region.height):
        fail(f"frame {expected} is outside {region.width}x{region.height}")
    if not preview.top_edge_visible(expected, region.height):
        fail(f"frame top {expected[1]:.1f} is above the region; the label must hide")
    if (
        expected[0] < -1 or expected[2] > region.width + 1
        or expected[3] < -1 or expected[1] > region.height + 1
    ):
        fail(f"frame {expected} does not fit {region.width}x{region.height}")

    drawn = preview._frame["rects"].get(area.as_pointer())
    if drawn is None:
        fail("the overlay geometry is unavailable")
    if any(abs(a - b) > 1e-6 for a, b in zip(drawn, expected)):
        fail(f"drawn outline {drawn} != computed bounds {expected}")

    # Equal padding on all four sides is the visual invariant the user sees.
    union = current_union(est, area, region)
    pads = (
        union.left - expected[0],
        expected[1] - union.top,
        expected[2] - union.right,
        union.bottom - expected[3],
    )
    if min(pads) <= 0:
        fail(f"frame {expected} does not enclose the graph {union}: pads {pads}")
    if max(pads) - min(pads) > 1.0:
        fail(f"padding is not symmetric around the graph {union}: {pads}")
    want_pad = est.padding_px * (union.width / est.content.width)
    if abs(pads[0] - want_pad) > 1.0:
        fail(f"padding {pads[0]:.2f} != export padding {want_pad:.2f}")

    # The frame must be real pixels, not just a submitted batch.
    mask = frame_mask((region.height, region.width), expected)
    on_pixels = region_pixels()
    visible = orange_count(on_pixels, mask)

    prefs.show_capture_area = False
    force_redraw()
    count = preview._frame["count"]
    force_redraw()
    if preview._frame["count"] != count:
        fail("the overlay still draws when the toggle is off")
    off_pixels = region_pixels()
    hidden = orange_count(off_pixels, mask)
    changed_mask = (on_pixels != off_pixels).any(axis=2)
    changed = int(changed_mask.sum())
    changed_band = int((changed_mask & mask).sum())
    if changed:
        ys, xs = np.nonzero(changed_mask)
        bbox = [int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())]
    else:
        bbox = None
    if visible < 200:
        fail(
            f"the frame is not visible: orange={visible}, changed={changed}, "
            f"changed_in_band={changed_band}, bbox={bbox}, "
            f"rect={expected}, region={region.width}x{region.height}, "
            f"error={preview._frame['error']}"
        )
    if hidden > visible * 0.2:
        fail(f"the frame is still visible with the toggle off: {hidden} px")
    if changed_band < 500:
        fail(
            f"the frame is not on its computed edges: {changed_band} changed px; "
            f"rect={expected}, bbox={bbox}, changed={changed}"
        )

    prefs.show_capture_area = True
    force_redraw()
    state["visible"] = visible
    state["hidden"] = hidden
    state["changed"] = changed
    state["changed_band"] = changed_band
    start_export()
except Exception:
    fail("could not start the export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.2)
