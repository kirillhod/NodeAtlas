# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture-area preview: a dashed outline and a size label in the Node Editor.

The outline is the live graph bounds from the same ``collect_rects`` /
``measure_view`` pair the export uses, expanded by the export padding, so it
cannot drift from the nodes. The label reads the same estimate as the sidebar.
A screenshot captures draw handlers as well, so the export sets
:data:`suppress` before it switches trees and redraws: the preview never
reaches a tile (report §5 item 39).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import bpy

from . import bounds, capture
from .log import get_logger
from .preferences import get_prefs

log = get_logger()

DASH = 6.0          # px, at 100 % UI scale
GAP = 4.0           # px, at 100 % UI scale
THICKNESS = 1.5     # px, at 100 % UI scale
MARGIN = 6.0        # px between the outline and the label
TEXT_SIZE = 11.0    # points

OUTLINE_COLOR = (1.0, 0.62, 0.15, 0.95)
TEXT_COLOR = (1.0, 0.84, 0.45, 0.95)
SHADOW_COLOR = (0.0, 0.0, 0.0, 0.8)

suppress = False
_handle = None
_blf_dpi = True
_frame = {"count": 0, "rects": {}, "error": None}


@dataclass(frozen=True)
class Estimate:
    """What the panel and the overlay label show, computed from the prefs.

    ``content`` and the metrics are in export image pixels: ``final_w`` is
    ``ceil(content.width) + 2 * padding`` (report §4.5). The outline also uses
    ``content.width`` to convert the padding to screen pixels, but its
    position comes from the live graph bounds.
    """

    content: bounds.Rect
    layout: bounds.Layout
    used_dpi: float
    nodes: int
    scope: str
    upp: float      # export units per pixel
    names: tuple[str, ...] | None = None  # None: every node (whole tree)

    @property
    def final_w(self) -> int:
        return self.layout.final_w

    @property
    def final_h(self) -> int:
        return self.layout.final_h

    @property
    def megapixels(self) -> float:
        return self.layout.megapixels

    @property
    def padding_px(self) -> int:
        return self.layout.margin - self.layout.pad


def estimate(context, prefs, area=None, space=None, region=None) -> Estimate | None:
    """Return the export estimate for the current editor, or ``None``.

    The panel calls this without editor parts; the overlay passes the area it
    is drawing into, so the two never describe a different node editor.
    """
    if area is None:
        parts = capture.get_node_context(context)
        if parts is None:
            return None
        _window, area, space, region = parts
    tree = space.edit_tree
    if tree is None:
        return None
    bottom = capture.bottom_ui_height(area)
    height = capture.effective_height(region, bottom)
    if height < 64:
        return None
    try:
        system = context.preferences.system.ui_scale
        view = context.preferences.view.ui_scale
        ui_prop = context.preferences.view.bl_rna.properties["ui_scale"]
        max_view = float(getattr(ui_prop, "hard_max", 6.0))
        effective, planned_view, _max_effective = bounds.planned_scale(
            prefs.output_dpi, system, view, max_view
        )
        target, used_dpi, _dpi_max = bounds.target_upp(prefs.output_dpi, effective)
        metrics = bounds.ViewMetrics(
            upp=target, k=1.0 / target, s=effective / target, ox=0.0, oy=0.0
        )
        nodes = tree.nodes
        names = None
        if prefs.scope == "SELECTED":
            keep = bounds.selected_node_names(tree)
            names = tuple(sorted(keep))
            nodes = [node for node in tree.nodes if node.name in keep]
        rects = bounds.collect_rects(nodes, metrics, bounds.visual_margin(planned_view))
        content = bounds.union_rects(rects)
        layout = bounds.compute_layout(
            content, region.width, height,
            bounds.padding_px(prefs.padding, used_dpi),
            view,
        )
        return Estimate(
            content=content,
            layout=layout,
            used_dpi=used_dpi,
            nodes=len(nodes),
            scope=prefs.scope,
            upp=target,
            names=names,
        )
    except (ValueError, RuntimeError):
        return None


def size_text(est: Estimate) -> str:
    """Return the shared size fragment: ``6003 × 3117 px · 18.7 MP``."""
    return (
        f"{est.final_w} × {est.final_h} px · {est.megapixels:.1f} MP"
    )


def label(est: Estimate, prefs) -> str:
    """Return the overlay label, for example ``≈ 6003 × 3117 px · …``."""
    parts = [f"≈ {size_text(est)}"]
    if abs(float(est.used_dpi) - float(prefs.output_dpi)) > 0.5:
        parts.append(f"{est.used_dpi:.0f} DPI (clamped)")
    else:
        parts.append(f"{est.used_dpi:.0f} DPI")
    if est.padding_px > 0:
        parts.append(f"padding {est.padding_px} px")
    if est.scope == "SELECTED":
        suffix = "" if est.nodes == 1 else "s"
        parts.append(f"{est.nodes} node{suffix}")
    return " · ".join(parts)


def live_union(nodes, metrics, view_scale: float):
    """Return the on-screen bounds of the captured nodes.

    ``metrics`` comes from :func:`bounds.measure_view` for the live view, so
    this is the same rectangle the export would capture, without padding.
    """
    return bounds.union_rects(
        bounds.collect_rects(nodes, metrics, bounds.visual_margin(view_scale))
    )


def screen_rect(union, est: Estimate):
    """Expand the on-screen graph bounds by the export padding.

    ``union`` is in region pixels from :func:`live_union`; padding is in
    final-image pixels. The union width is the same content at the current
    zoom, so their ratio converts padding to region pixels. Keeping the frame
    on the live union means the position scaling of report §4.3 is applied by
    the same code that computes the export bounds.
    """
    pad = est.padding_px * (union.width / est.content.width)
    return (union.left - pad, union.top + pad, union.right + pad, union.bottom - pad)


def intersects(rect, width: int, height: int) -> bool:
    """True when any part of the region rectangle is inside the view."""
    left, top, right, bottom = rect
    return right > 0 and left < width and top > 0 and bottom < height


def top_edge_visible(rect, height: int) -> bool:
    """True when the frame top, the label's anchor, is inside the view."""
    return 0.0 <= rect[1] <= height


def dash_quads(
    rect, dash: float = DASH, gap: float = GAP, width: float = THICKNESS,
):
    """Return triangle vertices for a dashed rectangle.

    Each dash is a quad, not a ``LINE_STRIP``: GPU line width and smoothing
    differ between backends (and are capped on macOS), while quads keep the
    thickness exact. The dash pattern restarts at every corner, so corners
    always carry a dash.
    """
    left, top, right, bottom = rect
    x0, x1 = sorted((left, right))
    y0, y1 = sorted((top, bottom))
    dash = max(float(dash), 0.1)
    gap = max(float(gap), 0.0)
    half = max(float(width), 0.5) * 0.5

    edges = (
        (x0, y0, x1, y0),
        (x1, y0, x1, y1),
        (x1, y1, x0, y1),
        (x0, y1, x0, y0),
    )
    vertices: list[tuple[float, float, float]] = []
    for ax, ay, bx, by in edges:
        length = math.hypot(bx - ax, by - ay)
        if length <= 0:
            continue
        ux, uy = (bx - ax) / length, (by - ay) / length
        nx, ny = -uy * half, ux * half
        start = 0.0
        while start < length:
            end = min(start + dash, length)
            p0x, p0y = ax + ux * start, ay + uy * start
            p1x, p1y = ax + ux * end, ay + uy * end
            # One tuple per vertex: batch_for_shader derives the attribute
            # length from the first element, so a flat float list becomes a
            # scalar attribute and every dash collapses to a point.
            vertices.extend((
                (p0x + nx, p0y + ny, 0.0),
                (p0x - nx, p0y - ny, 0.0),
                (p1x + nx, p1y + ny, 0.0),
                (p1x + nx, p1y + ny, 0.0),
                (p0x - nx, p0y - ny, 0.0),
                (p1x - nx, p1y - ny, 0.0),
            ))
            start = end + gap
    return vertices


def _effective(context) -> float:
    """Effective UI scale after a redraw (system × resolution)."""
    return max(1e-6, float(context.preferences.system.ui_scale))


def _set_font_size(font: int, size: float) -> None:
    """Set the overlay font size across the ``blf.size`` signatures.

    Blender 5.x dropped the ``dpi`` argument that 4.2 accepts; probe once and
    keep the working form.
    """
    global _blf_dpi
    import blf

    if _blf_dpi:
        try:
            blf.size(font, size, 72)
            return
        except TypeError:
            _blf_dpi = False
    blf.size(font, size)


def _fit_text(font: int, text: str, max_width: float) -> str:
    import blf

    if blf.dimensions(font, text)[0] <= max_width:
        return text
    cut = text
    while cut and blf.dimensions(font, cut + "…")[0] > max_width:
        cut = cut[:-1]
    return (cut + "…") if cut else ""


def _draw_label(font: int, text: str, rect, size: float, region_width: int,
                region_height: int, scale: float) -> None:
    import blf

    _set_font_size(font, size)
    max_width = max(40.0, region_width - 2.0 * MARGIN * scale)
    text = _fit_text(font, text, max_width)
    if not text:
        return
    text_width, text_height = blf.dimensions(font, text)
    x = rect[0]
    y = rect[1] + MARGIN * scale
    if y + text_height > region_height - 2.0:
        # No room above the visible top edge: sit inside the frame instead of
        # floating at the far side of a region the frame may not reach.
        y = rect[1] - MARGIN * scale - text_height
    x = min(
        max(x, MARGIN * scale),
        max(MARGIN * scale, region_width - MARGIN * scale - text_width),
    )
    y = min(
        max(y, MARGIN * scale),
        max(MARGIN * scale, region_height - MARGIN * scale - text_height),
    )

    blf.color(font, *SHADOW_COLOR)
    blf.position(font, x + 1.0, y - 1.0, 0)
    blf.draw(font, text)
    blf.color(font, *TEXT_COLOR)
    blf.position(font, x, y, 0)
    blf.draw(font, text)


def _draw_shape(rect, context, est, prefs) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader

    region = context.region
    scale = max(1.0, _effective(context))
    vertices = dash_quads(
        rect, DASH * scale, GAP * scale, THICKNESS * scale
    )
    if vertices:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices})
        # The node editor leaves GPU state behind; a 2D overlay must not be
        # depth-tested or culled, or the dashes silently disappear.
        gpu.state.depth_test_set("NONE")
        gpu.state.face_culling_set("NONE")
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", OUTLINE_COLOR)
        batch.draw(shader)

    # The label is part of the frame, not a free-floating caption: when the top
    # edge is outside the view it stays hidden.
    if top_edge_visible(rect, region.height):
        _draw_label(
            0, label(est, prefs), rect, max(9.0, TEXT_SIZE * scale),
            region.width, region.height, scale,
        )


def _draw() -> None:
    if suppress:
        return
    context = bpy.context
    area = context.area
    region = context.region
    space = context.space_data
    if area is None or region is None or space is None:
        return
    if area.type != "NODE_EDITOR" or region.type != "WINDOW":
        return
    prefs = get_prefs(context)
    if prefs is None or not prefs.show_capture_area:
        return
    try:
        est = estimate(context, prefs, area=area, space=space, region=region)
        if est is None:
            return
        tree = space.edit_tree
        metrics = bounds.measure_view(region.view2d, _effective(context))
        view_scale = context.preferences.view.ui_scale
        names = set(est.names) if est.names is not None else None
        nodes = (
            tree.nodes if names is None
            else [node for node in tree.nodes if node.name in names]
        )
        union = live_union(nodes, metrics, view_scale)
        rect = screen_rect(union, est)
        if not intersects(rect, region.width, region.height):
            return
        _draw_shape(rect, context, est, prefs)
        _frame["count"] += 1
        _frame["rects"][area.as_pointer()] = rect
        _frame["error"] = None
    except Exception as exc:  # a draw handler must never break the editor
        _frame["error"] = repr(exc)
        log.debug("Preview draw failed", exc_info=True)


def register() -> None:
    global _handle
    if _handle is not None:
        return
    # POST_PIXEL carries the region's pixel-space matrix. POST_VIEW inherits
    # the node canvas transform, which scales and offsets the outline like a
    # node instead of placing it at screen pixels.
    _handle = bpy.types.SpaceNodeEditor.draw_handler_add(
        _draw, (), "WINDOW", "POST_PIXEL"
    )


def unregister() -> None:
    global _handle
    if _handle is None:
        return
    try:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_handle, "WINDOW")
    except Exception:
        log.warning("Could not remove the preview handler", exc_info=True)
    _handle = None
