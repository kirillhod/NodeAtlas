# SPDX-License-Identifier: GPL-3.0-or-later
"""Timer-driven export job: stages, cancellation and the last result."""

from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass

import bpy

from . import bounds, capture, preview, stitch
from .log import get_logger
from .preferences import get_prefs

log = get_logger()
_current_job = None
last_result = None


@dataclass
class ExportSettings:
    filepath: str | None
    output_dpi: int
    padding: int
    max_mp: float
    scope: str
    hide_ui: bool
    deterministic: bool
    copy_only: bool = False
    keep_links: bool = False


def settings_from_prefs(prefs, filepath, copy_only: bool = False) -> ExportSettings:
    return ExportSettings(
        filepath=filepath,
        output_dpi=int(prefs.output_dpi),
        padding=int(prefs.padding),
        max_mp=float(prefs.max_mp),
        scope=prefs.scope,
        hide_ui=bool(prefs.hide_ui),
        deterministic=bool(prefs.deterministic),
        copy_only=copy_only,
        keep_links=bool(prefs.keep_links),
    )


def _copy_to_clipboard(filepath: str) -> None:
    """Copy a saved PNG to the OS clipboard through Blender's image operator."""
    if not hasattr(bpy.ops.image, "clipboard_copy"):
        raise RuntimeError("this Blender build has no image clipboard support")
    image = bpy.data.images.load(filepath, check_existing=False)
    try:
        with bpy.context.temp_override(edit_image=image):
            result = bpy.ops.image.clipboard_copy()
        if "FINISHED" not in result:
            raise RuntimeError(f"clipboard copy returned {result}")
    finally:
        bpy.data.images.remove(image)


def _copy_result(image, dpi: float) -> None:
    """Write the stitched image to a temporary PNG and copy it to the clipboard."""
    import tempfile

    descriptor, path = tempfile.mkstemp(prefix="nodeatlas_clipboard_", suffix=".png")
    os.close(descriptor)
    try:
        stitch.save_png(image, path, dpi=dpi)
        _copy_to_clipboard(path)
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


class ExportJob:
    """One export, advanced one stage at a time by the operator's modal timer."""

    def __init__(self, context, settings: ExportSettings, initial=None):
        self.context = context
        self.settings = settings
        self.initial = initial
        self.stage = "prepare"
        self.snapshot = None
        self.window = None
        self.area = None
        self.space = None
        self.region = None
        self.tree = None
        self.content_names = None
        self.tree_type = ""
        self.bottom_ui = 0
        self.region_width = 0
        self.region_height = 0
        self.selection_margin_px = 0.0
        self.content_left = 0.0
        self.content_top = 0.0
        self.content_k = 1.0
        self.link_selection_fix = False
        self.layout = None
        self.tiles = {}
        self.index = 0
        self.current_tile = (0, 0)
        self.final = None
        self.output_size = (0, 0)
        self.saved_path = None
        self.used_dpi = float(settings.output_dpi)
        self.padding_px = int(settings.padding)
        self.error = None
        self.warnings = []
        self.cancelled = False
        self.message = ""
        self.started = time.perf_counter()
        self.elapsed = 0.0

    # -- status ---------------------------------------------------------
    def _status(self, text: str | None) -> None:
        workspace = getattr(self.context, "workspace", None)
        if workspace is None:
            workspace = bpy.context.workspace
        if workspace is not None:
            try:
                workspace.status_text_set(text)
            except Exception:
                pass

    def _parts(self):
        if self.window is not None:
            area = capture.find_node_area(self.window)
            if area is not None:
                space = area.spaces.active
                region = next((item for item in area.regions if item.type == "WINDOW"), None)
                if space is not None and region is not None:
                    return self.window, area, space, region
        return capture.get_node_context(self.context)

    # -- stages ---------------------------------------------------------
    def _prepare(self) -> None:
        # The overlay is drawn into the region and would be captured with the
        # tiles; hide it before the first redraw and restore it after.
        preview.suppress = True
        self._status("NodeAtlas: preparing…")
        parts = None
        if self.initial:
            initial = self.initial
            window = initial["window"]
            area = capture.find_node_area(window) or initial["area"]
            space = area.spaces.active if area is not None else initial["space"]
            region = next(
                (item for item in area.regions if item.type == "WINDOW"), None
            ) if area is not None else initial["region"]
            if space is not None and region is not None:
                try:
                    capture.apply_tree_path(
                        space,
                        initial["root_tree"],
                        initial["path_trees"],
                        initial["pin"],
                        initial["tree"],
                        initial["tree_type"],
                        window=window,
                        area=area,
                        region=region,
                    )
                    parts = (window, area, space, region)
                except Exception:
                    log.warning("Could not restore the captured node path", exc_info=True)
        parts = parts or capture.get_node_context(self.context)
        if parts is None:
            raise RuntimeError("Open a Node Editor with an active node tree")
        window, area, space, region = parts
        tree = capture.current_tree(space)
        if tree is None:
            raise RuntimeError("The Node Editor has no tree to export")

        self.window = window
        self.snapshot = capture.take_snapshot(window, area, space, region, tree)
        self.tree_type = space.tree_type
        self.tree = tree

        # Selected-only needs a pinned temporary tree; pinning a compositor
        # tree crashes Blender 4.2/4.5 and the scene tree is read-only there.
        if (
            self.settings.scope == "SELECTED"
            and self.tree_type == "CompositorNodeTree"
            and bpy.app.version < (5, 1, 0)
        ):
            raise RuntimeError(
                "Selected-only compositor export requires Blender 5.1 or newer; "
                "export the whole compositor tree instead"
            )

        if self.settings.scope == "SELECTED":
            self.tree, self.content_names = bounds.build_selected_copy(
                tree, keep_links=self.settings.keep_links
            )
            self.snapshot.temp_tree = self.tree
            text = f"Exporting {len(self.content_names)} selected nodes"
            extra = len(self.tree.nodes) - len(self.content_names)
            if extra:
                text += f" and {extra} linked node{'s' if extra != 1 else ''}"
            self.warnings.append(text)
        capture.assign_tree(space, self.tree, self.tree_type)
        capture.clear_selection(self.tree)
        self.link_selection_fix = capture.mute_link_highlight()
        bpy.context.preferences.view.smooth_view = 0
        if self.settings.hide_ui:
            capture.hide_ui(space)

        was_maximized = len(window.screen.areas) == 1
        window, area, space, region = capture.maximize(window, area, region)
        self.snapshot.maximized = not was_maximized
        self.window, self.area, self.space, self.region = window, area, space, region
        if self.settings.hide_ui:
            capture.hide_ui(space)
        capture.redraw(window, area, region)
        self.stage = "measure"

    def _measure(self) -> None:
        self._status("NodeAtlas: measuring graph…")
        parts = self._parts()
        if parts is None:
            raise RuntimeError("Node Editor disappeared during export")
        self.window, self.area, self.space, self.region = parts
        window, area, space, region = parts
        capture.redraw(window, area, region)
        self.bottom_ui = capture.bottom_ui_height(area)
        height = capture.effective_height(region, self.bottom_ui)
        if height < 64 or region.width < 64:
            raise RuntimeError("Node Editor is too small for export")

        prefs = bpy.context.preferences
        # After a redraw, system.ui_scale already includes view.ui_scale.
        effective_scale = prefs.system.ui_scale
        view_scale = prefs.view.ui_scale
        ui_prop = prefs.view.bl_rna.properties["ui_scale"]
        max_view = float(getattr(ui_prop, "hard_max", 6.0))
        planned, new_view, max_effective = bounds.planned_scale(
            self.settings.output_dpi, effective_scale, view_scale, max_view
        )
        if new_view > view_scale + 1e-6:
            prefs.view.ui_scale = new_view
            capture.redraw(window, area, region)
            effective_scale = prefs.system.ui_scale
            view_scale = prefs.view.ui_scale
        target, used_dpi, dpi_max = bounds.target_upp(
            self.settings.output_dpi, effective_scale
        )
        self.used_dpi = used_dpi
        self.padding_px = bounds.padding_px(self.settings.padding, used_dpi)
        if abs(used_dpi - self.settings.output_dpi) > 0.5:
            self.warnings.append(
                f"DPI clamped from {self.settings.output_dpi:g} to {used_dpi:.0f} "
                f"(limit {dpi_max:.0f})"
            )

        if not self.settings.deterministic:
            capture.view_op(window, area, region, "reset")
        achieved = capture.set_zoom(
            window, area, region, space, target, region.width, height,
            prime=self.settings.deterministic,
        )
        if abs(achieved / target - 1.0) > 0.01:
            self.warnings.append(f"Zoom error {abs(achieved / target - 1.0) * 100:.2f}%")

        metrics = bounds.measure_view(region.view2d, effective_scale)
        vis = bounds.visual_margin(view_scale)
        nodes = self.tree.nodes
        if self.content_names is not None:
            nodes = [node for node in nodes if node.name in self.content_names]
        rects = bounds.collect_rects(nodes, metrics, vis)
        content = bounds.union_rects(rects)
        layout = bounds.compute_layout(
            content, region.width, height, self.padding_px, view_scale
        )
        if layout.megapixels > self.settings.max_mp:
            raise RuntimeError(
                f"Output would be {layout.final_w}×{layout.final_h} "
                f"({layout.megapixels:.1f} MP), above the {self.settings.max_mp:.0f} MP limit"
            )

        capture.anchor_first_tile(
            window, area, region, space, self.tree, layout, effective_scale, vis,
            nodes=nodes,
        )
        self.layout = layout
        self.region_width = region.width
        self.region_height = height
        self.content_left = min(bounds.absolute_location(node)[0] for node in nodes)
        self.content_top = max(bounds.absolute_location(node)[1] for node in nodes)
        self.content_k = metrics.k
        self.selection_margin_px = layout.pad + bounds.visual_margin(view_scale)
        self.tiles = {}
        self.index = 0
        self.current_tile = (0, 0)
        self.stage = "capture"

    def _capture_one(self) -> None:
        layout = self.layout
        total = layout.grid_x * layout.grid_y
        i = self.index % layout.grid_x
        j = self.index // layout.grid_x
        if (i, j) != (0, 0):
            dx = (i - self.current_tile[0]) * layout.step_x
            dy = (self.current_tile[1] - j) * layout.step_y
            capture.pan(self.window, self.area, self.region, dx, dy)
            self.current_tile = (i, j)
        if self.link_selection_fix:
            capture.select_outside_view(
                self.tree,
                self.content_left,
                self.content_top,
                self.content_k,
                self.layout,
                (i, j),
                self.region_width,
                self.region_height,
                self.selection_margin_px,
            )
        self._status(f"NodeAtlas: capturing tile {self.index + 1}/{total}…")
        self.tiles[(i, j)] = capture.capture_tile(
            self.window, self.area, self.region,
            self.region_width, self.region_height, self.bottom_ui, layout.pad,
        )
        self.index += 1
        if self.index >= total:
            self.stage = "stitch"

    def _stitch(self) -> None:
        self._status("NodeAtlas: stitching…")
        self.final = stitch.stitch_tiles(
            self.tiles, self.layout, self.region_width, self.region_height,
        )
        self.output_size = (self.final.shape[1], self.final.shape[0])
        self.tiles = {}
        self.stage = "save"

    def _save(self) -> None:
        if self.settings.copy_only:
            self._status("NodeAtlas: copying to clipboard…")
            _copy_result(self.final, self.used_dpi)
            self.saved_path = None
        else:
            self._status("NodeAtlas: saving…")
            stitch.save_png(self.final, self.settings.filepath, dpi=self.used_dpi)
            self.saved_path = self.settings.filepath
        self.elapsed = time.perf_counter() - self.started
        self.stage = "restore"

    def _restore(self) -> None:
        self._status("NodeAtlas: restoring UI…")
        if self.snapshot is not None:
            snapshot = self.snapshot
            # Clear the per-tile selection first; restore_snapshot then
            # reapplies the saved selection.
            try:
                capture.clear_selection(self.tree)
            except Exception:
                log.warning("Could not clear the capture selection", exc_info=True)
            errors, warnings = capture.restore_snapshot(snapshot)
            self.warnings.extend(warnings)
            if errors:
                self.error = (self.error + "\n" if self.error else "") + "\n".join(errors)
            self.snapshot = None
        self.final = None
        self.stage = "done"

    def cancel(self) -> None:
        if self.stage in {"done", "restore"}:
            return
        self.cancelled = True
        self.stage = "restore" if self.snapshot is not None else "done"

    def step(self) -> bool:
        handlers = {
            "prepare": self._prepare,
            "measure": self._measure,
            "capture": self._capture_one,
            "stitch": self._stitch,
            "save": self._save,
            "restore": self._restore,
        }
        if self.stage == "done":
            return True
        try:
            handler = handlers.get(self.stage)
            if handler is None:
                raise RuntimeError(f"Unknown export stage {self.stage!r}")
            log.debug("stage %s", self.stage)
            handler()
            log.debug("stage %s done", self.stage)
        except Exception:
            self.error = traceback.format_exc()
            log.exception("Export failed in stage %s", self.stage)
            if self.snapshot is not None and self.stage not in {"restore", "done"}:
                self.stage = "restore"
            else:
                self.stage = "done"
        if self.stage == "done":
            # Also covers a failure before the snapshot exists, where there is
            # no restore stage to clear the overlay suppression.
            preview.suppress = False
        return self.stage == "done"

    def finish(self) -> bool:
        self._status(None)
        if self.error:
            last = self.error.strip().splitlines()[-1] if self.error.strip() else "unknown error"
            suffix = "UI restored." if self.snapshot is None else "UI restoration failed."
            self.message = f"NodeAtlas failed: {last}. {suffix}"
            level = "ERROR"
            ok = False
        elif self.cancelled:
            self.message = "NodeAtlas export cancelled; UI restored."
            level = "WARNING"
            ok = False
        else:
            width, height = self.output_size
            mp = (width * height) / 1_000_000.0
            if self.settings.copy_only:
                action = "Copied to clipboard"
            else:
                action = f"Saved {self.saved_path}"
            self.message = (
                f"{action} ({width}×{height} px, {mp:.1f} MP) "
                f"in {self.elapsed:.2f}s"
            )
            level = "WARNING" if self.warnings else "INFO"
            if self.warnings:
                self.message += ". " + "; ".join(self.warnings)
            ok = True

        if level == "ERROR":
            log.error("%s", self.message)
        elif level == "WARNING":
            log.warning("%s", self.message)
        else:
            log.info("%s", self.message)
        self._status(self.message)
        return ok


# -- job accessors ----------------------------------------------------------


def current_job():
    """Return the running job, or None."""
    return _current_job


def cancel_current() -> bool:
    """Cancel the running job. Returns False when nothing is running."""
    if _current_job is None:
        return False
    _current_job.cancel()
    return True


# -- timer-driven job runner ------------------------------------------------

_cancel_keymaps: list[tuple[object, object]] = []


def _register_cancel_keymap() -> None:
    if _cancel_keymaps:
        return
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.get("Node Editor")
    if keymap is None:
        keymap = keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    item = keymap.keymap_items.new("node_atlas.cancel_export", "ESC", "PRESS")
    _cancel_keymaps.append((keymap, item))


def _unregister_cancel_keymap() -> None:
    for keymap, item in _cancel_keymaps:
        try:
            keymap.keymap_items.remove(item)
        except Exception:
            pass
    _cancel_keymaps.clear()


def _job_tick():
    global _current_job, last_result
    job = _current_job
    if job is None:
        return None
    if not job.step():
        return 0.01

    try:
        ok = job.finish()
    except Exception:
        log.exception("Could not finish NodeAtlas job")
        ok = False
        job.message = "NodeAtlas failed while finishing; see the console."
    last_result = {
        "ok": ok,
        "cancelled": job.cancelled,
        "path": job.saved_path,
        "copy_only": job.settings.copy_only,
        "error": job.error,
        "warnings": list(job.warnings),
        "size": tuple(job.output_size),
        "dpi": job.used_dpi,
        "elapsed": job.elapsed,
        "message": job.message,
    }
    _current_job = None
    _unregister_cancel_keymap()
    return None


def start_job(context, filepath, operator=None, copy_only: bool = False) -> bool:
    """Create a job and start it from Blender's application timer."""
    global _current_job, last_result
    if bpy.app.background:
        if operator is not None:
            operator.report({"ERROR"}, "NodeAtlas requires a GUI Blender session")
        return False
    if _current_job is not None:
        if operator is not None:
            operator.report({"WARNING"}, "A NodeAtlas export is already running")
        return False
    prefs = get_prefs(context)
    if prefs is None:
        if operator is not None:
            operator.report({"ERROR"}, "NodeAtlas preferences are unavailable")
        return False
    if not copy_only:
        if not filepath:
            if operator is not None:
                operator.report({"ERROR"}, "NodeAtlas: no output path was chosen")
            return False

        try:
            stitch.check_output_path(filepath)
        except stitch.OutputError as exc:
            log.error("Output path rejected: %s", exc)
            if operator is not None:
                operator.report({"ERROR"}, f"NodeAtlas: {exc}")
            return False

    parts = capture.get_node_context(context)
    if parts is None:
        if operator is not None:
            operator.report({"ERROR"}, "Open a Node Editor with an active node tree")
        return False
    window, area, space, region = parts
    initial = {
        "window": window,
        "area": area,
        "space": space,
        "region": region,
        "tree": capture.current_tree(space),
        "tree_type": space.tree_type,
        "root_tree": space.node_tree,
        "path_trees": tuple(
            item.node_tree for item in getattr(space, "path", ())
            if item.node_tree is not None
        ),
        "pin": space.pin,
    }

    job = ExportJob(
        context, settings_from_prefs(prefs, filepath, copy_only=copy_only), initial
    )
    _current_job = job
    last_result = None
    try:
        _register_cancel_keymap()
    except Exception:
        log.warning("Could not register the Esc cancel shortcut", exc_info=True)
    bpy.app.timers.register(_job_tick, first_interval=0.01)
    log.info("export started: %s", "clipboard" if copy_only else filepath)
    return True
