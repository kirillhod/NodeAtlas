# SPDX-License-Identifier: GPL-3.0-or-later
"""Hide UI option GUI test.

Two cases in one session: ``hide_ui=False`` and ``hide_ui=True``. Both must
restore the editor flags, selection, active node, tree and view; the second
case must also call ``capture.hide_ui`` at least once.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import png_content

OUT = tempfile.mkdtemp(prefix="nodeatlas_ui_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
PADDING = 20
state = {"ticks": 0, "case": 0, "before": None, "output": None, "found": None,
         "hide_calls": 0, "expect_hide": False, "results": {}}


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
        "areas": len(bpy.context.window_manager.windows[0].screen.areas),
        "tree": tree.name if tree else None,
        "tree_type": space.tree_type,
        "pin": bool(space.pin),
        "header": bool(getattr(space, "show_region_header", False)),
        "ui": bool(getattr(space, "show_region_ui", False)),
        "toolbar": bool(getattr(space, "show_region_toolbar", False)),
        "gizmo": bool(getattr(space, "show_gizmo", False)),
        "context_path": bool(getattr(getattr(space, "overlay", None), "show_context_path", False)),
        "backdrop": bool(getattr(space, "show_backdrop", False)),
        "selected": sorted(node.name for node in tree.nodes if node.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "smooth_view": bpy.context.preferences.view.smooth_view,
    }


def set_ui(space):
    """A visible overlay state; region-visibility setters are avoided.

    Changing ``show_region_header`` from a script without a fully initialized
    area can crash Blender 5.3, and the add-on itself hides those regions. The
    overlay flags are enough to prove that hide/restore acts on the UI state.
    """
    if hasattr(space, "show_gizmo") and not space.show_gizmo:
        space.show_gizmo = True
    overlay = getattr(space, "overlay", None)
    if overlay is not None and hasattr(overlay, "show_context_path"):
        overlay.show_context_path = True
    if hasattr(space, "show_backdrop") and not space.show_backdrop:
        space.show_backdrop = True


def configure(hide_ui, name):
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
    tree = space.edit_tree
    sentinel = tree.nodes.get("UI_SENTINEL")
    if sentinel is None:
        sentinel = tree.nodes.new("ShaderNodeMath")
        sentinel.label = "UI_SENTINEL"
        sentinel.name = "UI_SENTINEL"
        sentinel.location = (0, -1400)
    for node in tree.nodes:
        node.select = node is sentinel
    tree.nodes.active = sentinel
    set_ui(space)
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = OUT + os.sep
    prefs.filename_pattern = name
    prefs.output_dpi = 96
    prefs.padding = PADDING
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = hide_ui
    state["expect_hide"] = hide_ui
    state["hide_calls"] = 0
    return snapshot(), os.path.join(OUT, name)


def start_export():
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()


def image_size(path):
    image = bpy.data.images.load(path, check_existing=False)
    try:
        return tuple(image.size)
    finally:
        bpy.data.images.remove(image)


def finish_case():
    path = state["output"]
    if not os.path.isfile(path):
        fail(f"missing output {path}")
    size = image_size(path)
    if size[0] <= 0 or size[1] <= 0:
        fail(f"empty output {path}")
    png_content.check_capture(path, PADDING)
    if state["expect_hide"] and state["hide_calls"] < 1:
        fail("hide_ui=True never called capture.hide_ui")
    if not state["expect_hide"] and state["hide_calls"] != 0:
        fail(f"hide_ui=False still called capture.hide_ui {state['hide_calls']} times")
    after = snapshot()
    before = state["before"]
    if after != before:
        fail(
            f"hide_ui={state['expect_hide']} changed the editor state: "
            f"{before} != {after}"
        )
    key = "hidden" if state["expect_hide"] else "visible"
    state["results"][key] = {"size": size, "state": "restored"}
    return state["case"]


def tick():
    state["ticks"] += 1
    path = state["output"]
    if path and os.path.exists(path):
        if state["found"] is None:
            state["found"] = state["ticks"]
        if state["ticks"] - state["found"] >= 5:
            try:
                finish_case()
                state["case"] += 1
                state["found"] = None
                if state["case"] == 1:
                    state["before"], state["output"] = configure(
                        True, "ui_hidden.png"
                    )
                    start_export()
                    return 0.1
                print(json.dumps({
                    "result": "PASS",
                    "padding": PADDING,
                    "cases": state["results"],
                }, indent=2))
                sys.stdout.flush()
                os._exit(0)
            except Exception:
                fail("post-export checks failed:\n" + traceback.format_exc())
            return None
    if state["ticks"] > 1800:
        fail("timed out waiting for UI option exports")
    return 0.1


print("NodeAtlas UI option test output:", OUT)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    from node_atlas import capture
    original_hide_ui = capture.hide_ui
    state["original_hide_ui"] = original_hide_ui

    def tracked_hide_ui(space):
        state["hide_calls"] += 1
        return original_hide_ui(space)

    capture.hide_ui = tracked_hide_ui
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    state["before"], state["output"] = configure(False, "ui_visible.png")
    start_export()
except Exception:
    fail("could not start the hide_ui=False export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
