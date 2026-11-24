# SPDX-License-Identifier: GPL-3.0-or-later
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


@dataclass(frozen=True)
class ContentFrame:
    """The anchored graph corner and pixel factors of one capture (report 4.3)."""

    left: float       # node-unit x of the content corner
    top: float        # node-unit y of the content corner
    s: float          # px per node unit for positions
    k: float          # px per node unit for sizes
    margin_px: float  # PAD and the outline drawn outside Node.dimensions


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
    """Return the frame-aware node position across Blender versions.

    ``location_absolute`` is missing on some 4.2 node types, so derive the
    position from ``location`` and the parent chain there (report §4.3).
    """
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


def padding_px(units: float, used_dpi: float) -> int:
    """Convert the padding preference to final-image pixels.

    The stored value is density-independent (1 unit = 1 px at 96 DPI), so the
    band keeps the same proportion to the graph at any Output DPI: content
    scales with ``D = used_dpi / 96``, therefore so must the margin (report
    11.21). Using ``k`` here would shrink the margin on high-UI-scale screens.
    """
    return max(0, int(round(float(units) * max(float(used_dpi), 0.0) / 96.0)))


def visual_margin(view_ui_scale: float) -> float:
    """Pixels drawn outside ``Node.dimensions`` (outline, glow).

    Report 5.6: ``VIS = ceil(2.5 * view.ui_scale)``. Measured on the
    selected-only compositor path, where the node outline otherwise lands in
    the padding band.
    """
    return float(math.ceil(2.5 * max(float(view_ui_scale), 0.0)))


def node_rect(node, metrics: ViewMetrics, vis: float = 0.0) -> Rect:
    width = node.dimensions.x
    height = node.dimensions.y
    absolute_x, absolute_y = absolute_location(node)
    left = metrics.ox + metrics.s * absolute_x
    top = metrics.oy + metrics.s * absolute_y
    return Rect(
        left=left - vis,
        top=top + vis,
        right=left + width * metrics.k + vis,
        bottom=top - height * metrics.k - vis,
    )


def collect_rects(nodes, metrics: ViewMetrics, vis: float = 0.0) -> list[Rect]:
    rects = []
    for node in nodes:
        if node.dimensions.x <= 0 or node.dimensions.y <= 0:
            continue
        rects.append(node_rect(node, metrics, vis))
    return rects


def content_origin(nodes) -> tuple[float, float]:
    """Return the node-unit corner the anchored layout aligns to.

    ``anchor_first_tile`` aligns the union of :func:`collect_rects`, which
    skips nodes without positive dimensions. Such a node must not move that
    origin: using every node shifted the per-tile selection box relative to
    the drawn content, so nodes that were visible could be selected.
    """
    usable = [
        node for node in nodes
        if node.dimensions.x > 0 and node.dimensions.y > 0
    ]
    if not usable:
        raise ValueError("No drawable nodes in the tree")
    return (
        min(absolute_location(node)[0] for node in usable),
        max(absolute_location(node)[1] for node in usable),
    )


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


def planned_scale(
    output_dpi: float, system_scale: float, view_scale: float, max_view: float,
):
    """Return (effective_scale, view_scale, max_effective_scale).

    Resolution Scale (``view.ui_scale``) can be raised temporarily so that a
    requested DPI above the current ``D_max`` is still achievable.
    """
    system_scale = max(float(system_scale), 1e-6)
    view_scale = max(float(view_scale), 1e-6)
    base = system_scale / view_scale
    max_effective = base * max(float(max_view), view_scale)
    required = (max(float(output_dpi), 0.001) / 96.0) * UPP_MIN * 1.01
    effective = min(max(system_scale, required), max_effective)
    new_view = view_scale * effective / system_scale
    return effective, new_view, max_effective


@dataclass(frozen=True)
class DensityPlan:
    """Scale and density one export would use (report section 4.3)."""

    effective: float   # effective UI scale after a Resolution Scale raise
    view_scale: float  # view.ui_scale to apply (may be raised)
    upp: float         # export units per pixel
    used_dpi: float    # density after the UPP clamp
    max_dpi: float     # highest density reachable by raising Resolution Scale


def plan_density(
    output_dpi: float, system_scale: float, view_scale: float, max_view: float,
) -> DensityPlan:
    """Return the projected scale and density for *output_dpi*.

    The panel, the preview and the export read one object instead of unpacking
    the scale tuples at every call site.
    """
    effective, new_view, max_effective = planned_scale(
        output_dpi, system_scale, view_scale, max_view
    )
    upp, used_dpi, _current_max = target_upp(output_dpi, effective)
    return DensityPlan(
        effective=effective,
        view_scale=new_view,
        upp=upp,
        used_dpi=used_dpi,
        max_dpi=max_effective / UPP_MIN * 96.0,
    )


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
        grid_x=grid_x,
        grid_y=grid_y,
        step_x=step_x,
        step_y=step_y,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        final_w=final_w,
        final_h=final_h,
    )


def selected_node_names(tree) -> set[str]:
    """Names kept by selected-only export: selection plus selected-frame children."""
    keep = {node.name for node in tree.nodes if node.select and not node.hide}
    for node in tree.nodes:
        if node.name not in keep or node.type != "FRAME":
            continue
        for child in tree.nodes:
            parent = child.parent
            while parent is not None:
                if parent.name in keep:
                    keep.add(child.name)
                    break
                parent = parent.parent
    return keep


def link_neighbour_names(tree, keep: set[str]) -> set[str]:
    """Names of nodes directly linked to a kept node.

    Blender stores a link together with both endpoint nodes, so the far node has
    to stay in the temporary copy or the connection disappears. Hidden nodes are
    kept too: the editor still draws them as collapsed blocks, so their links
    exist (report 5 item 32).
    """
    names = set()
    for link in tree.links:
        for near, far in (
            (link.from_node, link.to_node),
            (link.to_node, link.from_node),
        ):
            if near.name in keep and far.name not in keep:
                names.add(far.name)
    return names


def build_selected_copy(tree, keep_links: bool = False):
    """Return a filtered orphan/group copy of *tree* and the frame node names.

    The original tree is never modified. Selected frames include descendants;
    kept nodes inside unselected frames are unparented with their absolute
    position preserved. Hidden selected nodes are skipped.

    With *keep_links*, the nodes directly linked to the selection stay in the
    copy so their connections keep an endpoint and stay visible when the far
    node is cropped by the export area. They are not part of the returned names:
    the captured rectangle still covers the selection only.
    """
    import bpy  # local import keeps the rest of this module testable

    tmp = tree.copy()
    selected = selected_node_names(tmp)
    keep = selected
    if keep_links:
        keep = selected | link_neighbour_names(tmp, selected)

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
    return tmp, selected
