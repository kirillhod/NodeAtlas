# SPDX-License-Identifier: GPL-3.0-or-later
"""Clipboard GUI test: a successful export also lands on the clipboard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = tempfile.mkdtemp(prefix="nodeatlas_clipboard_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
state = {"ticks": 0, "found": None}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def node_area():
    window = bpy.context.window_manager.windows[0]
    areas = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    if not areas:
        return None, None
    area = max(areas, key=lambda item: item.width * item.height)
    return area, next((item for item in area.regions if item.type == "WINDOW"), None)


def snapshot():
    area, _region = node_area()
    space = area.spaces.active
    tree = space.edit_tree
    return {
        "tree": tree.name if tree else None,
        "tree_type": space.tree_type,
        "pin": bool(space.pin),
        "selected": sorted(node.name for node in tree.nodes if node.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "smooth_view": bpy.context.preferences.view.smooth_view,
    }


def setup():
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    space.pin = True
    space.node_tree = bpy.data.materials["M_Small"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = ""
    prefs.filename_pattern = "clipboard.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot()


def clipboard_size():
    """Read the OS clipboard image size on Windows via PowerShell."""
    command = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$img=[System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($null -eq $img) { 'none' } else { '{0}x{1}' -f $img.Width, $img.Height }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = result.stdout.strip()
    if not text or text == "none":
        return None
    width, height = text.split("x", 1)
    return (int(width), int(height))


def tick():
    from node_atlas import operators

    state["ticks"] += 1
    if operators._current_job is not None:
        if state["ticks"] > 1200:
            fail("timed out waiting for the clipboard export")
        return 0.1
    result = operators.last_result
    if result is None:
        if state["ticks"] > 1200:
            fail("the clipboard job never reported a result")
        return 0.1
    try:
        if not result["ok"]:
            fail(f"clipboard export did not succeed: {result}")
        if not result.get("copy_only"):
            fail(f"the job was not a clipboard export: {result}")
        if result["path"] is not None:
            fail(f"clipboard export wrote a file: {result['path']}")
        if "Copied to clipboard" not in result["message"]:
            fail(f"unexpected result message: {result['message']}")
        if os.listdir(OUT):
            fail(f"clipboard export left files in the output folder: {os.listdir(OUT)}")
        size = tuple(result["size"])
        if snapshot() != state["before"]:
            fail(f"state mismatch: {state['before']} != {snapshot()}")
        if sys.platform == "win32":
            pasted = clipboard_size()
            if pasted != size:
                fail(f"clipboard image is {pasted}, expected {size}")
        else:
            pasted = None
        print(json.dumps({
            "result": "PASS",
            "size": list(size),
            "clipboard": list(pasted) if pasted else "not verified",
        }, indent=2))
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        fail("post-export checks failed:\n" + traceback.format_exc())


print("NodeAtlas clipboard test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.copy_png()
except Exception:
    fail("could not start the clipboard export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
