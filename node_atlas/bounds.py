"""Geometry, layout and selection helpers for NodeAtlas.

Pure functions operate on objects exposing the Blender Node/View2D attributes;
`build_selected_copy` is the only function that needs ``bpy``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

UPP_MIN = 0.43311
UPP_MAX = 20.00953


class EmptySelection(RuntimeError):
    """Raised when selected-only export has nothing to export."""


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom


@dataclass(frozen=True)
class ViewMetrics:
    upp: float
    k: float       # px per node unit for sizes
    s: float       # px per node unit for positions
    ox: float
    oy: float


@dataclass(frozen=True)
class Layout:
    pad: int
    overlap: int
    margin: int
    content_w: float
    content_h: float
    grid_x: int
    grid_y: int
    step_x: int
    step_y: int
    canvas_w: int
    canvas_h: int
    final_w: int
    final_h: int

    @property
    def megapixels(self) -> float:
        return (self.final_w * self.final_h) / 1_000_000.0


def measure_upp(v2d) -> float:
    """Return units per pixel at the current zoom (report §4.3)."""
    delta = v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]
    if delta <= 0:
        raise RuntimeError("Could not measure the node editor zoom")
    return delta / 100.0


def measure_view(v2d, ui_scale: float) -> ViewMetrics:
    """Measure the view; *ui_scale* is the effective (system × resolution) scale."""
    upp = measure_upp(v2d)
    k = 1.0 / upp
    s = ui_scale * k
    ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
    return ViewMetrics(upp=upp, k=k, s=s, ox=ox, oy=oy)


def absolute_location(node):
    """Return frame-aware node position across Blender versions."""
    location = getattr(node, "location_absolute", None)
    if location is not None:
        return location.x, location.y
    x, y = node.location
    parent = node.parent
    while parent is not None:
        x += parent.location.x
        y += parent.location.y
        parent = parent.parent
    return x, y


def node_rect(node, metrics: ViewMetrics) -> Rect:
    width = node.dimensions.x
    height = node.dimensions.y
    absolute_x, absolute_y = absolute_location(node)
    left = metrics.ox + metrics.s * absolute_x
    top = metrics.oy + metrics.s * absolute_y
    return Rect(
        left=left,
        top=top,
        right=left + width * metrics.k,
        bottom=top - height * metrics.k,
    )


def collect_rects(nodes, metrics: ViewMetrics) -> list[Rect]:
    rects = []
    for node in nodes:
        if node.dimensions.x <= 0 or node.dimensions.y <= 0:
            continue
        rects.append(node_rect(node, metrics))
    return rects


def union_rects(rects) -> Rect:
    rects = list(rects)
    if not rects:
        raise ValueError("No drawable nodes in the tree")
    return Rect(
        left=min(r.left for r in rects),
        top=max(r.top for r in rects),
        right=max(r.right for r in rects),
        bottom=min(r.bottom for r in rects),
    )


def target_upp(output_dpi: float, ui_scale: float):
    """Return (upp, clamped_dpi, dpi_max) for the requested density.

    *ui_scale* is the effective UI scale (``system.ui_scale`` after the UI has
    refreshed; it already includes the Resolution Scale).
    """
    density = max(float(output_dpi), 0.001) / 96.0
    dpi_max = ui_scale / UPP_MIN
    dpi_min = ui_scale / UPP_MAX
    clamped = min(max(density, dpi_min), dpi_max)
    return ui_scale / clamped, clamped * 96.0, dpi_max * 96.0


def compute_layout(
    content: Rect,
    region_w: int,
    region_h: int,
    padding: int,
    view_ui_scale: float,
) -> Layout:
    if content.width <= 0 or content.height <= 0:
        raise ValueError("Graph content has no size")
    if region_w <= 0 or region_h <= 0:
        raise ValueError("Node editor region has no size")

    short_side = max(1, min(region_w, region_h))
    pad = max(16, math.ceil(8 * view_ui_scale))
    pad = min(pad, max(1, short_side // 4))
    overlap = max(120, 2 * pad + 32)
    overlap = min(overlap, max(1, short_side // 2))
    step_x = max(1, region_w - overlap)
    step_y = max(1, region_h - overlap)

    margin = int(padding) + pad
    capture_w = content.width + 2 * margin
    capture_h = content.height + 2 * margin
    grid_x = max(1, math.ceil((capture_w - overlap) / step_x))
    grid_y = max(1, math.ceil((capture_h - overlap) / step_y))

    canvas_w = (grid_x - 1) * step_x + region_w
    canvas_h = (grid_y - 1) * step_y + region_h
    final_w = math.ceil(content.width) + 2 * int(padding)
    final_h = math.ceil(content.height) + 2 * int(padding)

    return Layout(
        pad=pad,
        overlap=overlap,
        margin=margin,
        content_w=content.width,
        content_h=content.height,
        grid_x=grid_x,
        grid_y=grid_y,
        step_x=step_x,
        step_y=step_y,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        final_w=final_w,
        final_h=final_h,
    )


def build_selected_copy(tree):
    """Return a filtered orphan/group copy of *tree* and kept node count.

    The original tree is never modified. Selected frames include descendants;
    kept nodes inside unselected frames are unparented with their absolute
    position preserved. Hidden selected nodes are skipped.
    """
    import bpy  # local import keeps the rest of this module testable

    tmp = tree.copy()
    keep = {node.name for node in tmp.nodes if node.select and not node.hide}

    # A selected frame keeps every descendant.
    for node in list(tmp.nodes):
        if node.name not in keep or node.type != "FRAME":
            continue
        for child in tmp.nodes:
            parent = child.parent
            while parent is not None:
                if parent.name in keep:
                    keep.add(child.name)
                    break
                parent = parent.parent

    # Preserve absolute placement when the parent frame is not kept.
    for node in tmp.nodes:
        if node.name in keep and node.parent is not None and node.parent.name not in keep:
            absolute = absolute_location(node)
            node.parent = None
            node.location = absolute

    for node in list(tmp.nodes):
        if node.name not in keep:
            tmp.nodes.remove(node)

    if not tmp.nodes:
        bpy.data.batch_remove([tmp])
        raise EmptySelection("Select at least one node to export")

    try:
        tmp.nodes.active = None
    except Exception:
        pass
    return tmp, len(tmp.nodes)
