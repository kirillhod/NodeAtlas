# SPDX-License-Identifier: GPL-3.0-or-later
"""Global NodeAtlas preferences."""

from __future__ import annotations

import os
import sys

import bpy


def default_output_dir() -> str:
    """Return the user's Desktop when it exists, otherwise the home folder.

    Handles XDG on Linux and OneDrive-redirected Desktops on Windows.
    """
    home = os.path.expanduser("~")
    candidates = []
    if sys.platform.startswith("linux"):
        config = os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config"))
        user_dirs = os.path.join(config, "user-dirs.dirs")
        try:
            with open(user_dirs, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("XDG_DESKTOP_DIR="):
                        value = line.split("=", 1)[1].strip().strip('"')
                        candidates.append(value.replace("$HOME", home))
                        break
        except OSError:
            pass
    if sys.platform == "win32":
        one_drive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        if one_drive:
            candidates.append(os.path.join(one_drive, "Desktop"))
    candidates.append(os.path.join(home, "Desktop"))
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(home)


def _shortcut_updated(self, context):
    from . import refresh_keymap

    refresh_keymap()


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
        description="Output density; 96 = 1:1 pixels per node unit, 128 is 33% larger",
        default=128,
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
        description=(
            "Safety limit: stop before capturing when the image would exceed this "
            "many megapixels (200 MP is about 16000x12500 px)"
        ),
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
        description="Folder for quick exports; clear it to ask for a path every time",
        subtype="DIR_PATH",
        default=default_output_dir(),
    )
    filename_pattern: bpy.props.StringProperty(
        name="Filename Pattern",
        description=(
            "Fields: {blend}, {tree} (owner name), {datablock} (tree name), "
            "{type}, {date}"
        ),
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
        name="Header Buttons",
        description="Show the export buttons in the Node Editor header",
        default=True,
    )
    show_advanced: bpy.props.BoolProperty(
        name="Advanced",
        description="Show folder, filename, UI and shortcut options",
        default=False,
    )
    enable_shortcut: bpy.props.BoolProperty(
        name="Enable Shortcut",
        description="Enable a quick-export shortcut; off by default to avoid conflicts",
        default=False,
        update=_shortcut_updated,
    )
    shortcut_key: bpy.props.StringProperty(
        name="Key",
        description="Key for the quick export, for example E or F5",
        default="E",
        maxlen=4,
        update=_shortcut_updated,
    )
    shortcut_ctrl: bpy.props.BoolProperty(
        name="Ctrl",
        description="Require Ctrl",
        default=True,
        update=_shortcut_updated,
    )
    shortcut_shift: bpy.props.BoolProperty(
        name="Shift",
        description="Require Shift",
        default=True,
        update=_shortcut_updated,
    )
    shortcut_alt: bpy.props.BoolProperty(
        name="Alt",
        description="Require Alt",
        default=False,
        update=_shortcut_updated,
    )
