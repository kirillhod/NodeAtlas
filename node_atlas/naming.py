# SPDX-License-Identifier: GPL-3.0-or-later
"""Output folder and filename helpers for NodeAtlas."""

from __future__ import annotations

import os
import re
from datetime import datetime

import bpy

from . import capture, stitch

_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*]+')
_WHITESPACE = re.compile(r"\s+")
_MULTI_UNDERSCORE = re.compile(r"_{2,}")
_TREE_TYPE_LABELS = {
    "ShaderNodeTree": "Shader",
    "GeometryNodeTree": "Geometry Nodes",
    "CompositorNodeTree": "Compositor",
    "TextureNodeTree": "Texture",
}


def safe_name(value: str) -> str:
    value = _INVALID_FILENAME.sub("_", str(value))
    value = _WHITESPACE.sub("_", value)
    value = _MULTI_UNDERSCORE.sub("_", value)
    return value.strip(" ._") or "export"


def tree_owner_name(tree):
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
    owner = tree_owner_name(tree)
    return {
        "blend": safe_name(blend),
        "tree": safe_name(owner or (tree.name if tree else "tree")),
        "datablock": safe_name(tree.name if tree else "tree"),
        "type": safe_name(_TREE_TYPE_LABELS.get(tree_type, tree_type or "Tree")),
        "date": datetime.now().strftime("%Y%m%d-%H%M%S"),
    }


def render_filename(pattern: str, fields: dict) -> str:
    try:
        name = pattern.format(**fields)
    except (KeyError, ValueError):
        name = "{blend}_{tree}_{date}.png".format(**fields)
    if not name.lower().endswith(".png"):
        name += ".png"
    return safe_name(name)


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
    base = stitch.resolve_path(default_dir)
    pattern = prefs.filename_pattern or "{blend}_{tree}_{date}.png"
    name = render_filename(pattern, _filename_fields(context))
    return _unique_path(os.path.join(base, name))
