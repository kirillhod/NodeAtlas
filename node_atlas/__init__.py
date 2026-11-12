"""NodeAtlas — export any Blender node tree as one high-resolution PNG."""

from __future__ import annotations

import bpy

from . import bounds, capture, operators, preferences

__version__ = "0.5.0"
__author__ = "kirillhod"

bl_info = {
    "name": "Node Atlas",
    "author": "kirillhod",
    "version": (0, 5, 0),
    "blender": (5, 2, 0),
    "location": "Node Editor > Sidebar > Node Atlas",
    "description": "Export any node tree as one high-resolution PNG",
    "category": "Node",
}

_get_prefs = preferences.get_prefs
_keymaps: list[tuple[object, object]] = []


def _estimate(context, prefs):
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
        metrics = bounds.measure_view(
            region.view2d, context.preferences.system.ui_scale,
            context.preferences.view.ui_scale,
        )
        rects = bounds.collect_rects(tree.nodes, metrics)
        content = bounds.union_rects(rects)
        return bounds.compute_layout(
            content, region.width, height, prefs.padding,
            context.preferences.view.ui_scale,
        )
    except (ValueError, RuntimeError):
        return None


class NODE_PT_node_atlas(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Node Atlas"
    bl_label = "Node Atlas"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            not bpy.app.background
            and space is not None
            and space.type == "NODE_EDITOR"
            and space.edit_tree is not None
        )

    def draw(self, context):
        layout = self.layout
        prefs = _get_prefs(context)
        if prefs is None:
            layout.label(text="Node Atlas preferences are unavailable", icon="ERROR")
            return

        layout.operator("node_atlas.export_png", text="Export Current Tree", icon="IMAGE_DATA")
        layout.operator("node_atlas.export_as", text="Export As…", icon="FILE_TICK")
        if operators._current_job is not None:
            layout.operator("node_atlas.cancel_export", text="Cancel Export", icon="CANCEL")
            layout.label(text="Export in progress…", icon="TIME")

        box = layout.box()
        box.label(text="Settings")
        box.prop(prefs, "output_dpi")
        box.prop(prefs, "padding")
        box.prop(prefs, "max_mp")
        box.prop(prefs, "scope", expand=True)

        parts = capture.get_node_context(context)
        if parts is not None:
            tree = parts[2].edit_tree
            if prefs.scope == "SELECTED":
                selected = sum(1 for node in tree.nodes if node.select and not node.hide)
                box.label(
                    text=f"Selected nodes: {selected}",
                    icon="INFO" if selected else "ERROR",
                )
            estimated = _estimate(context, prefs)
            if estimated is not None:
                box.label(
                    text=f"Estimated: {estimated.final_w} × {estimated.final_h} px "
                         f"({estimated.megapixels:.1f} MP)"
                )
            system = context.preferences.system.ui_scale
            view = context.preferences.view.ui_scale
            dpi_max = (system * view) / bounds.UPP_MIN * 96.0
            if prefs.output_dpi > dpi_max:
                box.label(
                    text=f"Max DPI at this UI scale: {dpi_max:.0f}",
                    icon="ERROR",
                )

        advanced = layout.box()
        advanced.label(text="Advanced")
        advanced.prop(prefs, "hide_ui")
        advanced.prop(prefs, "restore_ui")
        advanced.prop(prefs, "deterministic")
        advanced.prop(prefs, "default_dir")
        advanced.prop(prefs, "filename_pattern")
        advanced.prop(prefs, "show_header_button")
        advanced.prop(prefs, "show_keymap")


def _draw_menu(self, context):
    self.layout.operator("node_atlas.export_png", text="Export Node Graph as PNG")
    self.layout.operator("node_atlas.export_as", text="Export Node Graph as PNG…")


def _draw_header(self, context):
    prefs = _get_prefs(context)
    if prefs is not None and prefs.show_header_button:
        self.layout.operator(
            "node_atlas.export_png",
            text="",
            icon="IMAGE_DATA",
        )


def _register_keymap():
    prefs = _get_prefs(bpy.context)
    if prefs is not None and not prefs.show_keymap:
        return
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.get("Node Editor")
    if keymap is None:
        keymap = keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    item = keymap.keymap_items.new(
        "node_atlas.export_png", "E", "PRESS", ctrl=True, shift=True
    )
    _keymaps.append((keymap, item))


def _unregister_keymap():
    for keymap, item in _keymaps:
        try:
            keymap.keymap_items.remove(item)
        except Exception:
            pass
    _keymaps.clear()


classes = (
    preferences.NodeAtlasPreferences,
    operators.NODE_ATLAS_OT_export_png,
    operators.NODE_ATLAS_OT_export_as,
    operators.NODE_ATLAS_OT_cancel_export,
    NODE_PT_node_atlas,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_view.append(_draw_menu)
    bpy.types.NODE_MT_context_menu.append(_draw_menu)
    bpy.types.TOPBAR_MT_file_export.append(_draw_menu)
    bpy.types.NODE_HT_header.append(_draw_header)
    _register_keymap()


def unregister():
    _unregister_keymap()
    bpy.types.NODE_HT_header.remove(_draw_header)
    bpy.types.TOPBAR_MT_file_export.remove(_draw_menu)
    bpy.types.NODE_MT_context_menu.remove(_draw_menu)
    bpy.types.NODE_MT_view.remove(_draw_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
