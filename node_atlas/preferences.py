# SPDX-License-Identifier: GPL-3.0-or-later
"""Global NodeAtlas preferences."""

from __future__ import annotations

import bpy


def get_prefs(context):
    """Return NodeAtlasPreferences, also when installed as an extension."""
    for key, addon in context.preferences.addons.items():
        if key == __package__ or key.endswith(".node_atlas"):
            return addon.preferences
    return None


class NodeAtlasPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    output_dpi: bpy.props.IntProperty(
        name="Output DPI",
        description="Output density; 96 = 1:1 pixels per node unit",
        default=96,
        min=1,
        max=2000,
    )
    padding: bpy.props.IntProperty(
        name="Padding (px)",
        description="Margin around the graph in final-image pixels; real background is captured",
        default=20,
        min=0,
        max=4000,
    )
    max_mp: bpy.props.FloatProperty(
        name="Max Megapixels",
        description="Abort before capturing when the output would exceed this size",
        default=200.0,
        min=1.0,
        max=100000.0,
    )
    scope: bpy.props.EnumProperty(
        name="Scope",
        items=(
            ("CURRENT", "Current Tree", "Export the tree displayed in the editor"),
            ("SELECTED", "Selected Nodes", "Export selected nodes using a temporary filtered copy"),
        ),
        default="CURRENT",
    )
    background: bpy.props.EnumProperty(
        name="Background",
        items=(("THEME", "Theme", "Keep the current editor background"),),
        default="THEME",
    )
    default_dir: bpy.props.StringProperty(
        name="Default Directory",
        description="Directory for quick exports; empty uses the .blend folder",
        subtype="DIR_PATH",
        default="",
    )
    filename_pattern: bpy.props.StringProperty(
        name="Filename Pattern",
        description="Available fields: {blend}, {tree}, {date}",
        default="{blend}_{tree}_{date}.png",
    )
    hide_ui: bpy.props.BoolProperty(
        name="Hide UI During Export",
        description="Hide headers, toolbars, gizmos and the context path",
        default=True,
    )
    restore_ui: bpy.props.BoolProperty(
        name="Restore UI",
        description="Restore the editor state after export (recommended)",
        default=True,
    )
    deterministic: bpy.props.BoolProperty(
        name="Deterministic View",
        description="Prime the view with View All before zooming; makes repeated exports identical",
        default=True,
    )
    show_header_button: bpy.props.BoolProperty(
        name="Header Button",
        description="Show the quick export button in the Node Editor header",
        default=True,
    )
    show_keymap: bpy.props.BoolProperty(
        name="Ctrl+Shift+E",
        description="Enable the quick export shortcut in the Node Editor",
        default=True,
    )
