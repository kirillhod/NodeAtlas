# SPDX-License-Identifier: GPL-3.0-or-later
"""NodeAtlas operators, menus and the Export As dialog."""

from __future__ import annotations

import os

import bpy
from bpy_extras.io_utils import ExportHelper

from . import capture, job, naming, stitch
from .preferences import get_prefs


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
        path = naming.quick_filepath(context, prefs)
        if path is None:
            return bpy.ops.node_atlas.export_as("INVOKE_DEFAULT")
        return {"FINISHED"} if job.start_job(context, path, self) else {"CANCELLED"}

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "NodeAtlas preferences are unavailable")
            return {"CANCELLED"}
        path = naming.quick_filepath(context, prefs)
        if path is None:
            self.report(
                {"ERROR"},
                "NodeAtlas: set a Default Directory or use Export As…",
            )
            return {"CANCELLED"}
        return {"FINISHED"} if job.start_job(context, path, self) else {"CANCELLED"}


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
            if job.start_job(context, None, self, copy_only=True)
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
            self.filepath = naming.quick_filepath(context, prefs) or ""
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
        box.prop(prefs, "deterministic")

    def execute(self, context):
        if not self.filepath.strip():
            self.report({"ERROR"}, "NodeAtlas: choose an output file")
            return {"CANCELLED"}
        path = stitch.resolve_path(self.filepath)
        return {"FINISHED"} if job.start_job(context, path, self) else {"CANCELLED"}


class NODE_ATLAS_OT_cancel_export(bpy.types.Operator):
    bl_idname = "node_atlas.cancel_export"
    bl_label = "Cancel NodeAtlas Export"
    bl_description = "Cancel the running NodeAtlas export and restore the UI"

    @classmethod
    def poll(cls, context):
        return job.current_job() is not None

    def execute(self, context):
        if job.cancel_current():
            self.report({"WARNING"}, "Cancelling NodeAtlas export…")
        return {"FINISHED"}


class NODE_ATLAS_OT_open_last_export(bpy.types.Operator):
    bl_idname = "node_atlas.open_last_export"
    bl_label = "Open Last Export"
    bl_description = "Open the last saved PNG in the default image viewer"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        result = job.last_result
        return bool(
            result
            and result.get("path")
            and os.path.exists(result["path"])
        )

    def execute(self, context):
        path = job.last_result["path"] if job.last_result else None
        if not path or not os.path.exists(path):
            self.report({"ERROR"}, "The last export is no longer available")
            return {"CANCELLED"}
        result = bpy.ops.wm.path_open(filepath=path)
        if "FINISHED" not in result:
            # No xdg-open on a bare Linux install, or no default handler.
            self.report({"ERROR"}, f"NodeAtlas: no application could open {path}")
            return {"CANCELLED"}
        return {"FINISHED"}
