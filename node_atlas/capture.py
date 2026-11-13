# SPDX-License-Identifier: GPL-3.0-or-later
"""Editor state, view control, tiled capture and restoration."""

from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass, field

import bpy
import numpy as np

from .bounds import Layout, ViewMetrics, measure_upp, measure_view, node_rect
from .log import get_logger

log = get_logger()


@dataclass
class EditorSnapshot:
    window: object
    tree: object | None
    tree_type: str
    pin: bool
    header: bool
    ui: bool
    toolbar: bool
    gizmo: bool
    context_path: bool
    backdrop: bool
    selected: tuple[str, ...]
    active: str | None
    ui_scale: float
    smooth_view: int
    upp: float
    center: tuple[float, float]
    area_signature: tuple
    area_count: int
    area_bbox: tuple
    root_tree: object | None
    path_trees: tuple
    maximized: bool = False
    temp_tree: object | None = None
    warnings: list[str] = field(default_factory=list)


def find_node_area(window):
    candidates = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    if not candidates:
        return None
    return max(candidates, key=lambda area: area.width * area.height)


def find_area_by_bbox(window, snapshot: EditorSnapshot | None):
    if snapshot is None or snapshot.area_bbox is None:
        return None
    for area in window.screen.areas:
        if area.type == "NODE_EDITOR" and (
            area.x, area.y, area.width, area.height
        ) == tuple(snapshot.area_bbox):
            return area
    return None


def fresh_node_area(window):
    area = find_node_area(window)
    if area is None and window.screen.areas:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
    if area is None:
        return None, None, None
    space = area.spaces.active
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    return area, space, region


def get_node_context(context):
    """Return (window, area, space, region) for the Node Editor, or None."""
    window = context.window
    if window is None:
        windows = context.window_manager.windows
        window = windows[0] if windows else None
    if window is None or window.screen is None:
        return None

    area = context.area
    if area is None or area.type != "NODE_EDITOR":
        area = find_node_area(window)
    if area is None:
        return None
    space = area.spaces.active
    if space is None or space.type != "NODE_EDITOR" or space.edit_tree is None:
        return None
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None:
        return None
    return window, area, space, region


def current_tree(space):
    return space.edit_tree or space.node_tree


def take_snapshot(window, area, space, region, tree) -> EditorSnapshot:
    v2d = region.view2d
    prefs = bpy.context.preferences
    return EditorSnapshot(
        window=window,
        tree=tree,
        tree_type=space.tree_type,
        pin=space.pin,
        header=getattr(space, "show_region_header", False),
        ui=getattr(space, "show_region_ui", False),
        toolbar=getattr(space, "show_region_toolbar", False),
        gizmo=getattr(space, "show_gizmo", False),
        context_path=getattr(getattr(space, "overlay", None), "show_context_path", False),
        backdrop=getattr(space, "show_backdrop", False),
        selected=tuple(sorted(node.name for node in tree.nodes if node.select)),
        active=tree.nodes.active.name if tree.nodes.active else None,
        ui_scale=prefs.view.ui_scale,
        smooth_view=prefs.view.smooth_view,
        upp=measure_upp(v2d),
        center=tuple(v2d.region_to_view(region.width / 2, region.height / 2)),
        area_signature=tuple(
            sorted((item.type, item.x, item.y, item.width, item.height)
                   for item in window.screen.areas)
        ),
        area_count=len(window.screen.areas),
        area_bbox=(area.x, area.y, area.width, area.height),
        root_tree=space.node_tree,
        path_trees=tuple(
            item.node_tree for item in getattr(space, "path", ())
            if item.node_tree is not None
        ),
    )


def assign_tree(space, tree, tree_type: str) -> None:
    space.pin = False
    space.tree_type = tree_type
    if hasattr(space, "show_backdrop"):
        space.show_backdrop = False
    space.pin = True
    space.node_tree = tree


def hide_ui(space) -> None:
    for attr in ("show_region_header", "show_region_toolbar", "show_region_ui", "show_gizmo"):
        if hasattr(space, attr):
            setattr(space, attr, False)
    overlay = getattr(space, "overlay", None)
    if overlay is not None and hasattr(overlay, "show_context_path"):
        overlay.show_context_path = False
    if hasattr(space, "show_backdrop"):
        space.show_backdrop = False


def clear_selection(tree) -> None:
    for node in tree.nodes:
        node.select = False
    try:
        tree.nodes.active = None
    except Exception:
        pass


def bottom_ui_height(area) -> int:
    return sum(
        region.height
        for region in area.regions
        if region.type in {"ASSET_SHELF", "ASSET_SHELF_HEADER"}
    )


def effective_height(region, bottom_ui: int) -> int:
    return region.height - bottom_ui


def redraw(window, area, region) -> None:
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


def view_op(window, area, region, name: str, **kwargs):
    with bpy.context.temp_override(window=window, area=area, region=region):
        result = getattr(bpy.ops.view2d, name)(**kwargs)
    redraw(window, area, region)
    return result


def node_view_all(window, area, region, space) -> None:
    with bpy.context.temp_override(
        window=window, area=area, region=region, space_data=space
    ):
        bpy.ops.node.view_all()
    redraw(window, area, region)


def set_zoom(
    window, area, region, space, target_upp: float, width: int, height: int,
    prime: bool = True,
) -> float:
    if prime:
        node_view_all(window, area, region, space)
    for _ in range(60):
        current = measure_upp(region.view2d)
        if abs(current / target_upp - 1.0) < 0.002:
            return current
        if current > target_upp:
            factor = target_upp / current
            if 0.46 <= factor < 1.0:
                rect_w = max(1, int(width * factor))
                rect_h = max(1, int(height * factor))
                view_op(
                    window, area, region, "zoom_border",
                    xmin=max(0, width // 2 - rect_w // 2),
                    xmax=min(width, width // 2 + rect_w // 2),
                    ymin=max(0, height // 2 - rect_h // 2),
                    ymax=min(height, height // 2 + rect_h // 2),
                    wait_for_input=False,
                )
            else:
                view_op(window, area, region, "zoom_in")
        else:
            view_op(window, area, region, "zoom_out")
    return measure_upp(region.view2d)


def pan(window, area, region, dx: int, dy: int) -> None:
    if dx or dy:
        view_op(window, area, region, "pan", deltax=int(dx), deltay=int(dy))


def maximize(window, area, region):
    # screen_full_area toggles: calling it on an already-maximized area would
    # restore the old layout and capture the wrong region.
    if len(window.screen.areas) > 1:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
    area = find_node_area(window)
    if area is None:
        raise RuntimeError("Node Editor area disappeared after maximizing")
    space = area.spaces.active
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None:
        raise RuntimeError("Node Editor WINDOW region disappeared after maximizing")
    redraw(window, area, region)
    return window, area, space, region


def leave_maximize(window, snapshot: EditorSnapshot):
    # Already back in the saved layout (e.g. the user left maximize manually).
    restored_area = find_area_by_bbox(window, snapshot)
    if restored_area is not None and len(window.screen.areas) == snapshot.area_count:
        area, space, region = fresh_node_area(window)
        return (area, space, region) if area is not None and region is not None else None

    for _attempt in range(2):
        area = find_area_by_bbox(window, snapshot) or find_node_area(window)
        if area is None and window.screen.areas:
            area = max(window.screen.areas, key=lambda item: item.width * item.height)
        if area is None:
            return None
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
        if region is None:
            return None
        try:
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.screen.screen_full_area(use_hide_panels=True)
        except Exception as exc:
            log.warning("screen_full_area failed: %s", exc)

        # The layout changed: every previous area/region reference is now stale.
        area, space, region = fresh_node_area(window)
        if area is None or region is None:
            return None
        try:
            redraw(window, area, region)
        except Exception as exc:
            log.warning("redraw after leaving maximize failed: %s", exc)

        if len(window.screen.areas) == snapshot.area_count and find_area_by_bbox(window, snapshot):
            break

    area, space, region = fresh_node_area(window)
    if area is None or region is None:
        return None
    if snapshot.area_count > 1 and len(window.screen.areas) == 1:
        snapshot.warnings.append("area stayed maximized after restore")
    return area, space, region


def anchor_first_tile(
    window, area, region, space, tree, layout: Layout,
    ui_scale: float,
) -> ViewMetrics:
    for _ in range(12):
        metrics = measure_view(region.view2d, ui_scale)
        rects = [node_rect(node, metrics) for node in tree.nodes
                 if node.dimensions.x > 0 and node.dimensions.y > 0]
        if not rects:
            raise RuntimeError("No drawable nodes after view normalization")
        left = min(rect.left for rect in rects)
        top = max(rect.top for rect in rects)
        dx = int(round(left - layout.margin))
        dy = int(round(top - (region.height - layout.margin)))
        if dx == 0 and dy == 0:
            break
        pan(window, area, region, dx, dy)
    return measure_view(region.view2d, ui_scale)


def can_capture_raw(window) -> bool:
    """True on Blender 5.2+, unless the legacy path is forced for testing."""
    return hasattr(window, "screenshot") and os.environ.get(
        "NODEATLAS_FORCE_LEGACY"
    ) != "1"


def capture_tile(window, area, region, width: int, height: int, bottom_ui: int, pad: int):
    redraw(window, area, region)
    if not can_capture_raw(window):
        return _capture_tile_legacy(window, area, region, width, height, bottom_ui, pad)

    full_height = region.height
    bottom = region.y + bottom_ui
    top = region.y + full_height
    screenshot = window.screenshot(
        region=((region.x, bottom), (region.x + width, top))
    )
    array = np.frombuffer(screenshot, dtype=np.uint8)
    expected = width * height * 4
    if array.size != expected:
        raise RuntimeError(
            f"Screenshot has {array.size} bytes, expected {expected} "
            f"({width}x{height}); is the window visible?"
        )
    tile = array.reshape(height, width, 4)
    cropped = tile[pad:height - pad, pad:width - pad, :].copy()
    if cropped.shape[0] <= 0 or cropped.shape[1] <= 0:
        raise RuntimeError("PAD is larger than the captured tile")
    return cropped


def _capture_tile_legacy(
    window, area, region, width: int, height: int, bottom_ui: int, pad: int,
):
    """Blender 4.2–5.1: screenshot_area into a temporary PNG and crop it."""
    settings = bpy.context.scene.render.image_settings
    old_format = settings.file_format
    old_mode = settings.color_mode
    descriptor, path = tempfile.mkstemp(prefix="nodeatlas_", suffix=".png")
    os.close(descriptor)
    try:
        settings.file_format = "PNG"
        settings.color_mode = "RGBA"
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.screenshot_area(filepath=path)

        image = bpy.data.images.load(path, check_existing=False)
        try:
            image.colorspace_settings.name = "Non-Color"
            image_width, image_height = image.size
            if image_width != width:
                raise RuntimeError(
                    f"screenshot_area width {image_width} != WINDOW width {width}"
                )
            if image_height < region.height:
                raise RuntimeError(
                    f"screenshot_area height {image_height} < WINDOW height {region.height}"
                )
            pixels = np.empty(image_width * image_height * 4, dtype=np.float32)
            image.pixels.foreach_get(pixels)
            array = np.clip(
                pixels.reshape(image_height, image_width, 4) * 255.0 + 0.5, 0, 255
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

    # imbuf rows are bottom-up. The WINDOW region is at the bottom of the area;
    # the header sits above it, and the asset shelf overlays the bottom rows.
    start = bottom_ui
    end = start + height
    if end > image_height:
        raise RuntimeError("screenshot_area does not contain the whole WINDOW region")
    tile = array[start:end, 0:width, :]
    cropped = tile[pad:height - pad, pad:width - pad, :].copy()
    if cropped.shape[0] <= 0 or cropped.shape[1] <= 0:
        raise RuntimeError("PAD is larger than the captured tile")
    return cropped


def restore_view(window, snapshot: EditorSnapshot):
    area = find_area_by_bbox(window, snapshot) or find_node_area(window)
    if area is None:
        return None, None
    space = area.spaces.active
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None:
        return None, None

    bottom_ui = bottom_ui_height(area)
    height = effective_height(region, bottom_ui)
    node_view_all(window, area, region, space)
    # view_all can reset the node-group path; re-enter before restoring zoom.
    _restore_tree_path(space, snapshot, window, area, region)
    set_zoom(
        window, area, region, space, snapshot.upp, region.width, height,
        prime=False,
    )

    center_x, center_y = snapshot.center
    for _ in range(8):
        px, py = region.view2d.view_to_region(center_x, center_y, clip=False)
        dx = int(round(px - region.width / 2))
        dy = int(round(py - region.height / 2))
        if dx == 0 and dy == 0:
            break
        pan(window, area, region, dx, dy)

    achieved_upp = measure_upp(region.view2d)
    achieved_center = tuple(
        region.view2d.region_to_view(region.width / 2, region.height / 2)
    )
    return achieved_upp, achieved_center


def _restore_attr(obj, attr: str, value) -> None:
    if hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except Exception as exc:
            log.warning("Could not restore %s: %s", attr, exc)


def apply_tree_path(
    space, root_tree, path_trees, pin, tree, tree_type,
    window=None, area=None, region=None,
) -> None:
    """Set the root tree, pin flag and nested group edit path."""
    space.pin = False
    space.tree_type = tree_type
    root = root_tree or tree
    if root is not None:
        space.node_tree = root
    groups = [group for group in path_trees if group is not root]
    if groups and window is not None and area is not None and region is not None:
        # Enter groups through the operator so Blender records the full edit
        # path; a bare space.path.append() is dropped on the next redraw.
        space.pin = True
        current_tree = root
        for group in groups:
            node = next(
                (
                    item for item in current_tree.nodes
                    if item.type == "GROUP"
                    and getattr(item, "node_tree", None) is group
                ),
                None,
            )
            if node is None:
                break
            current_tree.nodes.active = node
            node.select = True
            try:
                with bpy.context.temp_override(
                    window=window, area=area, region=region
                ):
                    bpy.ops.node.group_edit(exit=False)
            except Exception:
                break
            current_tree = space.edit_tree or group
        # Pinning keeps a programmatically restored group path valid across
        # redraws; an unpinned edit path is dropped by Blender.
        space.pin = True
    elif groups:
        for group in groups:
            space.path.append(group)
        space.pin = True
    else:
        space.pin = pin
    if pin and space.edit_tree is not tree:
        space.node_tree = tree


def _restore_tree_path(
    space, snapshot: EditorSnapshot, window=None, area=None, region=None,
) -> None:
    """Restore the root tree, pin flag and the nested group edit path."""
    current_path = tuple(
        item.node_tree for item in getattr(space, "path", ())
        if item.node_tree is not None
    )
    if (
        space.node_tree is snapshot.root_tree
        and current_path == snapshot.path_trees
        and space.edit_tree is snapshot.tree
    ):
        space.pin = True if len(snapshot.path_trees) > 1 else snapshot.pin
        return
    apply_tree_path(
        space,
        snapshot.root_tree,
        snapshot.path_trees,
        snapshot.pin,
        snapshot.tree,
        snapshot.tree_type,
        window=window,
        area=area,
        region=region,
    )


def restore_snapshot(snapshot: EditorSnapshot, restore_ui: bool = True):
    """Best-effort restoration. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = list(snapshot.warnings)
    window = snapshot.window
    area = find_area_by_bbox(window, snapshot) or find_node_area(window)
    if area is None:
        return ["Node Editor area is no longer available"], warnings

    space = area.spaces.active
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if space is None or region is None:
        return ["Node Editor space/region is no longer available"], warnings

    try:
        _restore_tree_path(space, snapshot, window, area, region)
    except Exception as exc:
        errors.append(f"tree/pin restore failed: {exc}")

    def restore_ui_state(target_space):
        if not restore_ui:
            return
        with bpy.context.temp_override(window=snapshot.window):
            _restore_attr(target_space, "show_region_header", snapshot.header)
            _restore_attr(target_space, "show_region_ui", snapshot.ui)
            _restore_attr(target_space, "show_region_toolbar", snapshot.toolbar)
            _restore_attr(target_space, "show_gizmo", snapshot.gizmo)
            _restore_attr(target_space.overlay, "show_context_path", snapshot.context_path)
            _restore_attr(target_space, "show_backdrop", snapshot.backdrop)

    def restore_selection():
        if not restore_ui or snapshot.tree is None:
            return
        try:
            for node in snapshot.tree.nodes:
                node.select = node.name in snapshot.selected
            snapshot.tree.nodes.active = (
                snapshot.tree.nodes.get(snapshot.active) if snapshot.active else None
            )
        except Exception as exc:
            errors.append(f"selection restore failed: {exc}")

    restore_ui_state(space)

    prefs = bpy.context.preferences
    try:
        prefs.view.ui_scale = snapshot.ui_scale
        prefs.view.smooth_view = 0
    except Exception as exc:
        errors.append(f"preferences restore failed: {exc}")

    # Tree/region changes can rebuild area.regions; re-acquire before the redraw.
    area, space, region = fresh_node_area(window)
    if area is None or region is None:
        errors.append("Node Editor disappeared before restore redraw")
    else:
        try:
            redraw(window, area, region)
        except Exception as exc:
            warnings.append(f"redraw before leaving maximize failed: {exc}")

    try:
        if snapshot.maximized:
            restored = leave_maximize(window, snapshot)
            if restored is None:
                errors.append("could not leave the maximized area")
            else:
                area, space, region = restored
        else:
            area, space, region = fresh_node_area(window)
    except Exception as exc:
        errors.append(f"leaving maximize failed: {exc}")

    # screen_full_area may reset per-space flags and the node path; apply both
    # on the final space, then re-apply the path once more because UI flag
    # updates can rebuild the area.
    if space is not None:
        try:
            _restore_tree_path(space, snapshot, window, area, region)
        except Exception as exc:
            errors.append(f"tree/pin restore after maximize failed: {exc}")
        restore_ui_state(space)
        # Region visibility updates can rebuild the area and invalidate the
        # space reference; re-acquire before re-applying the node path.
        area, space, region = fresh_node_area(window)
        if space is not None:
            try:
                _restore_tree_path(space, snapshot, window, area, region)
            except Exception as exc:
                errors.append(f"tree/pin restore after UI flags failed: {exc}")
        restore_selection()

    if region is not None:
        try:
            restore_view(window, snapshot)
        except Exception as exc:
            errors.append(f"view restore failed: {exc}")

    # View operators can reset the node path; leave the user in the same tree.
    area = find_node_area(window)
    if area is not None:
        space = area.spaces.active
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
        if space is not None and region is not None:
            try:
                _restore_tree_path(space, snapshot, window, area, region)
                restore_selection()
            except Exception as exc:
                errors.append(f"final tree/pin restore failed: {exc}")

    try:
        prefs.view.smooth_view = snapshot.smooth_view
    except Exception as exc:
        errors.append(f"smooth_view restore failed: {exc}")

    if snapshot.temp_tree is not None:
        try:
            bpy.data.batch_remove([snapshot.temp_tree])
        except Exception as exc:
            errors.append(f"temporary tree cleanup failed: {exc}")
        snapshot.temp_tree = None

    signature = tuple(
        sorted((item.type, item.x, item.y, item.width, item.height)
               for item in window.screen.areas)
    )
    if signature != snapshot.area_signature:
        warnings.append("area layout differs from the saved snapshot")

    return errors, warnings
