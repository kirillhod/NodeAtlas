# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on keymaps shared by the export and cancel shortcuts.

Both shortcuts live in the add-on ``Node Editor`` keymap, so the get-or-create
and removal logic exists once instead of in ``__init__`` and ``job``.
"""

from __future__ import annotations

import bpy

_items: dict[str, list[tuple[object, object]]] = {}


def _node_editor_keymap():
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return None
    keymap = keyconfig.keymaps.get("Node Editor")
    if keymap is None:
        keymap = keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    return keymap


def add(owner: str, idname: str, key: str, **modifiers):
    """Add one shortcut under *owner*.

    Raises when Blender rejects the key or the modifiers; the caller decides
    whether to retry with a safe default.
    """
    keymap = _node_editor_keymap()
    if keymap is None:
        return None
    item = keymap.keymap_items.new(idname, key, "PRESS", **modifiers)
    _items.setdefault(owner, []).append((keymap, item))
    return item


def clear(owner: str) -> None:
    """Remove every shortcut registered under *owner*. Never raises."""
    for keymap, item in _items.pop(owner, ()):
        try:
            keymap.keymap_items.remove(item)
        except Exception:
            pass
