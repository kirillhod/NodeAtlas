# SPDX-License-Identifier: GPL-3.0-or-later
"""Timer-driven export job: stages, cancellation and the last result."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import traceback
from dataclasses import dataclass

import bpy
import numpy as np

from . import bounds, capture, keymap, preview, recovery, stitch
from .log import get_logger
from .preferences import get_prefs

log = get_logger()
_current_job = None
last_result = None

# Stage name -> method on ExportJob. A class-level table avoids rebuilding the
# dispatch dict on every timer tick.
_STAGE_METHODS = {
    "prepare": "_prepare",
    "measure": "_measure",
    "capture": "_capture_one",
    "stitch": "_stitch",
    "save": "_save",
    "restore": "_restore",
}


@dataclass
class ExportSettings:
    filepath: str | None
    output_dpi: int
    padding: int
    max_mp: float
    scope: str
    hide_ui: bool
    copy_only: bool = False
    keep_links: bool = False
    transparent: bool = False


def settings_from_prefs(prefs, filepath, copy_only: bool = False) -> ExportSettings:
    return ExportSettings(
        filepath=filepath,
        output_dpi=int(prefs.output_dpi),
        padding=int(prefs.padding),
        max_mp=float(prefs.max_mp),
        scope=prefs.scope,
        hide_ui=bool(prefs.hide_ui),
        copy_only=copy_only,
        keep_links=bool(prefs.keep_links),
        transparent=bool(prefs.transparent),
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
        self.content = None
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
        self.recovery_written = False
        self.message = ""
        self.started = time.perf_counter()
        self.elapsed = 0.0
        self.transparent_pass = 0
        self.dark_dir = None
        self.dark_paths = {}
        self.matte_step = None
        self.anchor = None

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
                region = capture.window_region(area)
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
        if self.initial is not None:
            initial = self.initial
            area = capture.find_node_area(initial.window) or initial.area
            if area is not None:
                initial.area = area
                initial.space = area.spaces.active
                initial.region = capture.window_region(area)
            if initial.space is not None and initial.region is not None:
                try:
                    capture.apply_tree_path(initial)
                    if initial.region is not None:
                        parts = (
                            initial.window,
                            initial.area,
                            initial.space,
                            initial.region,
                        )
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

        # Write the appearance before the first change, so a normal quit during
        # the export can be undone on the next start. An older marker wins: it
        # holds the values from before the interrupted run.
        if recovery.pending() is None and recovery.save(recovery.current()):
            self.recovery_written = True

        if self.settings.transparent:
            # The grid would not cancel out between the two backgrounds: it keeps
            # its own colour, so matting would turn it opaque.
            capture.set_theme_grid_levels(0)
            # The first pass is written here, not held in RAM: a large graph holds
            # one whole image worth of tiles, and doubling that would break the
            # memory limit the stitcher already spills to keep.
            self.dark_dir = tempfile.mkdtemp(prefix="nodeatlas_alpha_")

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

        was_maximized = len(window.screen.areas) == 1
        window, area, space, region = capture.maximize(window, area, region)
        self.snapshot.maximized = not was_maximized
        self.window, self.area, self.space, self.region = window, area, space, region
        if self.settings.hide_ui:
            # Only after maximizing: screen_full_area rebuilds the regions, so a
            # flag set on the old space would not survive.
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

        # Always prime with View All: view2d.reset() keeps the current center, so
        # the rasterization phase drifts between exports (report §11.10).
        achieved = capture.set_zoom(
            window, area, region, space, target, region.width, height,
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

        anchored = capture.anchor_first_tile(
            window, area, region, space, self.tree, layout, effective_scale, vis,
            nodes=nodes,
        )
        # The second background pass repeats the same view, so keep what the
        # anchor and the capture loop need to reach it again.
        self.anchor = (target, effective_scale, vis, nodes)
        self.layout = layout
        self.region_width = region.width
        self.region_height = height
        # The per-tile selection box must use the same origin and factors as
        # node_rect: drawable nodes only, positions by s (UI scale), sizes by k
        # (report §4.3). "anchor_first_tile" aligns this union.
        origin_left, origin_top = bounds.content_origin(nodes)
        self.content = bounds.ContentFrame(
            left=origin_left,
            top=origin_top,
            s=anchored.s,
            k=anchored.k,
            margin_px=layout.pad + bounds.visual_margin(view_scale),
        )
        self.tiles = {}
        self.index = 0
        self.current_tile = (0, 0)
        self.stage = "capture"

    def _capture_tile(self):
        return capture.capture_tile(
            self.window, self.area, self.region,
            self.region_width, self.region_height, self.bottom_ui, self.layout.pad,
        )

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
                self.content,
                self.layout,
                (i, j),
                self.region_width,
                self.region_height,
            )
        if self.settings.transparent:
            self._capture_transparent(i, j, total)
        else:
            self._status(f"NodeAtlas: capturing tile {self.index + 1}/{total}…")
            self.tiles[(i, j)] = self._capture_tile()

        self.index += 1
        if self.index >= total:
            if self.settings.transparent and self.transparent_pass == 0:
                self._start_second_pass()
            else:
                self.stage = "stitch"

    def _capture_transparent(self, i: int, j: int, total: int) -> None:
        """Capture one tile for the current background pass.

        The dark pass is written to a temporary file and read back in the light
        pass: the export already holds one full image worth of tiles, and two
        passes in RAM at once would double the peak.
        """
        if self.transparent_pass == 0:
            self._status(f"NodeAtlas: dark pass, tile {self.index + 1}/{total}…")
            if self.index == 0:
                capture.set_theme_backdrop(capture.DARK_BACKDROP)
            path = os.path.join(self.dark_dir, f"tile_{i}_{j}.npy")
            np.save(path, self._capture_tile())
            self.dark_paths[(i, j)] = path
            return

        self._status(f"NodeAtlas: light pass, tile {self.index + 1}/{total}…")
        dark = np.load(self.dark_paths.pop((i, j)))
        light = self._capture_tile()
        if self.matte_step is None:
            self.matte_step = stitch.matte_step(dark, light)
        self.tiles[(i, j)] = stitch.matte_from_pair(dark, light, step=self.matte_step)

    def _start_second_pass(self) -> None:
        """Switch the background once and replay the same tile views.

        The background changes twice per export, not twice per tile: a per-tile
        alternation would flash the whole editor at tile rate.
        """
        capture.set_theme_backdrop(capture.LIGHT_BACKDROP)
        target, effective_scale, vis, nodes = self.anchor
        capture.set_zoom(
            self.window, self.area, self.region, self.space, target,
            self.region.width, self.region_height,
            prime=True,
        )
        capture.anchor_first_tile(
            self.window, self.area, self.region, self.space, self.tree,
            self.layout, effective_scale, vis, nodes=nodes,
        )
        self.current_tile = (0, 0)
        self.index = 0
        self.transparent_pass = 1
        self._status("NodeAtlas: light pass…")

    def _stitch(self) -> None:
        self._status("NodeAtlas: stitching…")
        self.final = stitch.stitch_tiles(
            self.tiles, self.layout, self.region_width, self.region_height,
            transparent=self.settings.transparent,
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
            # Preferences were restored in the snapshot's finally, so the
            # recovery marker has done its job even when the area was lost.
            if self.recovery_written:
                recovery.clear()
                self.recovery_written = False
        if self.dark_dir is not None:
            # The first background pass lives on disk until the second one reads
            # it; a failed or cancelled export must not leave it behind.
            shutil.rmtree(self.dark_dir, ignore_errors=True)
            self.dark_dir = None
        self.dark_paths = {}
        self.final = None
        self.stage = "done"

    def cancel(self) -> None:
        if self.stage in {"done", "restore"}:
            return
        self.cancelled = True
        self.stage = "restore" if self.snapshot is not None else "done"

    def step(self) -> bool:
        if self.stage == "done":
            return True
        try:
            method = _STAGE_METHODS.get(self.stage)
            if method is None:
                raise RuntimeError(f"Unknown export stage {self.stage!r}")
            log.debug("stage %s", self.stage)
            getattr(self, method)()
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


def pending_recovery():
    """Return the appearance of an export that never restored, or None."""
    if _current_job is not None:
        return None
    return recovery.pending()


def restore_pending_recovery():
    """Apply the recovery marker. Returns ``(errors, warnings)`` or None."""
    appearance = pending_recovery()
    if appearance is None:
        return None
    errors, warnings = recovery.apply(appearance)
    if not errors:
        recovery.clear()
    return errors, warnings


def cancel_current() -> bool:
    """Cancel the running job. Returns False when nothing is running."""
    if _current_job is None:
        return False
    _current_job.cancel()
    return True


# -- timer-driven job runner ------------------------------------------------

def _register_cancel_keymap() -> None:
    keymap.add("cancel", "node_atlas.cancel_export", "ESC")


def _unregister_cancel_keymap() -> None:
    keymap.clear("cancel")


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

    editor = capture.EditorRef.capture(context)
    if editor is None:
        if operator is not None:
            operator.report({"ERROR"}, "Open a Node Editor with an active node tree")
        return False

    job = ExportJob(
        context, settings_from_prefs(prefs, filepath, copy_only=copy_only), editor
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
