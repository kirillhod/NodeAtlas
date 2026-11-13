# SPDX-License-Identifier: GPL-3.0-or-later
"""Export operators and the timer-driven export job."""

from __future__ import annotations

import os
import re
import time
import traceback
from dataclasses import dataclass
from datetime import datetime

import bpy
from bpy_extras.io_utils import ExportHelper

from . import bounds, capture, stitch
from .log import get_logger
from .preferences import get_prefs

log = get_logger()
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*]+')
_WHITESPACE = re.compile(r"\s+")
_MULTI_UNDERSCORE = re.compile(r"_{2,}")
_TREE_TYPE_LABELS = {
    "ShaderNodeTree": "Shader",
    "GeometryNodeTree": "Geometry Nodes",
    "CompositorNodeTree": "Compositor",
    "TextureNodeTree": "Texture",
}
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
    restore_ui: bool
    deterministic: bool
    copy_only: bool = False


def _safe_name(value: str) -> str:
    value = _INVALID_FILENAME.sub("_", str(value))
    value = _WHITESPACE.sub("_", value)
    value = _MULTI_UNDERSCORE.sub("_", value)
    return value.strip(" ._") or "export"


def _tree_owner_name(tree):
    """Return the material/world/object/scene/texture that owns *tree*."""
    if tree is None:
        return None
    for material in bpy.data.materials:
        if material.node_tree is tree:
            return material.name
    for world in bpy.data.worlds:
        if getattr(world, "node_tree", None) is tree:
            return world.name
    for light in bpy.data.lights:
        if getattr(light, "node_tree", None) is tree:
            return light.name
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if getattr(modifier, "node_group", None) is tree:
                return obj.name
    for scene in bpy.data.scenes:
        if getattr(scene, "compositing_node_group", None) is tree:
            return scene.name
        if getattr(scene, "node_tree", None) is tree:
            return scene.name
    for texture in bpy.data.textures:
        if getattr(texture, "node_tree", None) is tree:
            return texture.name
    return None


def _filename_fields(context) -> dict:
    blend = os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "untitled"
    parts = capture.get_node_context(context)
    tree = parts[2].edit_tree if parts else None
    tree_type = parts[2].tree_type if parts else ""
    owner = _tree_owner_name(tree)
    return {
        "blend": _safe_name(blend),
        "tree": _safe_name(owner or (tree.name if tree else "tree")),
        "datablock": _safe_name(tree.name if tree else "tree"),
        "type": _safe_name(_TREE_TYPE_LABELS.get(tree_type, tree_type or "Tree")),
        "date": datetime.now().strftime("%Y%m%d-%H%M%S"),
    }


def render_filename(pattern: str, fields: dict) -> str:
    try:
        name = pattern.format(**fields)
    except (KeyError, ValueError):
        name = "{blend}_{tree}_{date}.png".format(**fields)
    if not name.lower().endswith(".png"):
        name += ".png"
    return _safe_name(name)


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    index = 1
    while True:
        candidate = f"{stem}-{index:03d}{ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def quick_filepath(context, prefs) -> str | None:
    """Return an automatic path, or None when the user must choose one."""
    default_dir = prefs.default_dir.strip() if prefs.default_dir else ""
    if not default_dir:
        return None
    base = bpy.path.abspath(default_dir)
    pattern = prefs.filename_pattern or "{blend}_{tree}_{date}.png"
    name = render_filename(pattern, _filename_fields(context))
    return _unique_path(os.path.join(base, name))


def settings_from_prefs(prefs, filepath, copy_only: bool = False) -> ExportSettings:
    return ExportSettings(
        filepath=filepath,
        output_dpi=int(prefs.output_dpi),
        padding=int(prefs.padding),
        max_mp=float(prefs.max_mp),
        scope=prefs.scope,
        hide_ui=bool(prefs.hide_ui),
        restore_ui=bool(prefs.restore_ui),
        deterministic=bool(prefs.deterministic),
        copy_only=copy_only,
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

    def __init__(self, context, settings: ExportSettings):
        self.context = context
        self.settings = settings
        self.stage = "prepare"
        self.snapshot = None
        self.window = None
        self.area = None
        self.space = None
        self.region = None
        self.tree = None
        self.tree_type = ""
        self.bottom_ui = 0
        self.region_width = 0
        self.region_height = 0
        self.layout = None
        self.tiles = {}
        self.index = 0
        self.current_tile = (0, 0)
        self.final = None
        self.output_size = (0, 0)
        self.saved_path = None
        self.used_dpi = float(settings.output_dpi)
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
        self._status("NodeAtlas: preparing…")
        parts = capture.get_node_context(self.context)
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
        if self.tree_type == "CompositorNodeTree" and bpy.app.version < (5, 2, 0):
            raise RuntimeError(
                "Compositor export on Blender 4.2–5.1 is not supported yet; "
                "use Blender 5.2+ or export a Shader/Geometry Nodes tree"
            )

        if self.settings.scope == "SELECTED":
            self.tree, count = bounds.build_selected_copy(tree)
            self.snapshot.temp_tree = self.tree
            self.warnings.append(f"Exporting {count} selected nodes")

        capture.assign_tree(space, self.tree, self.tree_type)
        capture.clear_selection(self.tree)
        bpy.context.preferences.view.smooth_view = 0
        if self.settings.hide_ui:
            capture.hide_ui(space)

        window, area, space, region = capture.maximize(window, area, region)
        self.snapshot.maximized = True
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
        target, used_dpi, dpi_max = bounds.target_upp(
            self.settings.output_dpi, effective_scale
        )
        self.used_dpi = used_dpi
        if abs(used_dpi - self.settings.output_dpi) > 0.5:
            self.warnings.append(
                f"DPI clamped from {self.settings.output_dpi:g} to {used_dpi:.0f} "
                f"(limit {dpi_max:.0f})"
            )

        if self.settings.deterministic:
            pass  # set_zoom primes with View All
        else:
            capture.view_op(window, area, region, "reset")
        achieved = capture.set_zoom(
            window, area, region, space, target, region.width, height,
            prime=self.settings.deterministic,
        )
        if abs(achieved / target - 1.0) > 0.01:
            self.warnings.append(f"Zoom error {abs(achieved / target - 1.0) * 100:.2f}%")

        metrics = bounds.measure_view(region.view2d, effective_scale)
        rects = bounds.collect_rects(self.tree.nodes, metrics)
        content = bounds.union_rects(rects)
        layout = bounds.compute_layout(
            content, region.width, height, self.settings.padding, view_scale
        )
        if layout.megapixels > self.settings.max_mp:
            raise RuntimeError(
                f"Output would be {layout.final_w}×{layout.final_h} "
                f"({layout.megapixels:.1f} MP), above the {self.settings.max_mp:.0f} MP limit"
            )

        capture.anchor_first_tile(
            window, area, region, space, self.tree, layout, effective_scale
        )
        self.layout = layout
        self.region_width = region.width
        self.region_height = height
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
        self.final, _holes = stitch.stitch_tiles(
            self.tiles, self.layout, self.region_width, self.region_height,
            self.settings.padding,
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
            errors, warnings = capture.restore_snapshot(
                self.snapshot, restore_ui=self.settings.restore_ui
            )
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

    def fail(self, text: str) -> None:
        self.error = text
        if self.snapshot is not None and self.stage not in {"restore", "done"}:
            self.stage = "restore"
        elif self.stage not in {"restore", "done"}:
            self.stage = "done"

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
        return self.stage == "done"

    def finish(self, operator=None) -> bool:
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

        if operator is not None:
            operator.report({level}, self.message)
        if level == "ERROR":
            log.error("%s", self.message)
        elif level == "WARNING":
            log.warning("%s", self.message)
        else:
            log.info("%s", self.message)
        self._status(self.message)
        return ok


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
    try:
        done = job.step()
    except Exception:
        job.fail(traceback.format_exc())
        done = job.step()
    if not done:
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

    job = ExportJob(context, settings_from_prefs(prefs, filepath, copy_only=copy_only))
    _current_job = job
    last_result = None
    try:
        _register_cancel_keymap()
    except Exception:
        log.warning("Could not register the Esc cancel shortcut", exc_info=True)
    bpy.app.timers.register(_job_tick, first_interval=0.01)
    log.info("export started: %s", "clipboard" if copy_only else filepath)
    return True


class NODE_ATLAS_OT_export_png(bpy.types.Operator):
    bl_idname = "node_atlas.export_png"
    bl_label = "Export Node Graph as PNG"
    bl_description = (
        "Export the current node tree to the Default Directory set in Advanced "
        "(asks for a path if it is empty)"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and capture.get_node_context(context) is not None

    def invoke(self, context, event):
        prefs = get_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "NodeAtlas preferences are unavailable")
            return {"CANCELLED"}
        if not prefs.default_dir.strip():
            return bpy.ops.node_atlas.export_as("INVOKE_DEFAULT")
        path = quick_filepath(context, prefs)
        if path is None:
            return bpy.ops.node_atlas.export_as("INVOKE_DEFAULT")
        return {"FINISHED"} if start_job(context, path, self) else {"CANCELLED"}

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "NodeAtlas preferences are unavailable")
            return {"CANCELLED"}
        path = quick_filepath(context, prefs)
        if path is None:
            self.report(
                {"ERROR"},
                "NodeAtlas: set a Default Directory or use Export As…",
            )
            return {"CANCELLED"}
        return {"FINISHED"} if start_job(context, path, self) else {"CANCELLED"}


class NODE_ATLAS_OT_copy_png(bpy.types.Operator):
    bl_idname = "node_atlas.copy_png"
    bl_label = "Copy Node Graph to Clipboard"
    bl_description = "Export the current node tree and copy it to the system clipboard"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and capture.get_node_context(context) is not None

    def _run(self, context):
        return (
            {"FINISHED"}
            if start_job(context, None, self, copy_only=True)
            else {"CANCELLED"}
        )

    def invoke(self, context, event):
        return self._run(context)

    def execute(self, context):
        return self._run(context)


class NODE_ATLAS_OT_export_as(bpy.types.Operator, ExportHelper):
    bl_idname = "node_atlas.export_as"
    bl_label = "Export Node Graph as PNG…"
    bl_description = "Choose a filename and export the current node tree as PNG"
    bl_options = {"REGISTER"}

    filename_ext = ".png"
    filter_glob = "*.png"

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and capture.get_node_context(context) is not None

    def invoke(self, context, event):
        prefs = get_prefs(context)
        if prefs is not None:
            self.filepath = quick_filepath(context, prefs) or ""
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        prefs = get_prefs(context)
        layout = self.layout
        layout.label(text="Node Atlas Settings", icon="IMAGE_DATA")
        if prefs is None:
            layout.label(text="Preferences are unavailable", icon="ERROR")
            return
        box = layout.box()
        box.prop(prefs, "output_dpi")
        box.prop(prefs, "padding")
        box.prop(prefs, "max_mp")
        box.prop(prefs, "scope", expand=True)
        box.prop(prefs, "hide_ui")
        box.prop(prefs, "restore_ui")
        box.prop(prefs, "deterministic")

    def execute(self, context):
        if not self.filepath.strip():
            self.report({"ERROR"}, "NodeAtlas: choose an output file")
            return {"CANCELLED"}
        path = bpy.path.abspath(self.filepath)
        return {"FINISHED"} if start_job(context, path, self) else {"CANCELLED"}


class NODE_ATLAS_OT_cancel_export(bpy.types.Operator):
    bl_idname = "node_atlas.cancel_export"
    bl_label = "Cancel NodeAtlas Export"
    bl_description = "Cancel the running NodeAtlas export and restore the UI"

    @classmethod
    def poll(cls, context):
        return _current_job is not None

    def execute(self, context):
        if _current_job is not None:
            _current_job.cancel()
            self.report({"WARNING"}, "Cancelling NodeAtlas export…")
        return {"FINISHED"}

