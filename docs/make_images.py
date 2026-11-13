# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the README screenshots with a demo shader graph.

Run on a GUI Blender 5.x:
    blender --factory-startup --python docs/make_images.py
"""

from __future__ import annotations

import os
import sys
import traceback

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

IMAGES = os.path.join(ROOT, "docs", "images")
EXAMPLE = os.path.join(IMAGES, "example-export.png")
PANEL = os.path.join(IMAGES, "panel.png")
state = {"phase": "export", "ticks": 0, "found": None}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def node_area():
    window = bpy.context.window_manager.windows[0]
    areas = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    if not areas:
        return window, None, None
    area = max(areas, key=lambda item: item.width * item.height)
    return window, area, next((item for item in area.regions if item.type == "WINDOW"), None)


def add(nodes, kind, x, y, label=None):
    node = nodes.new(kind)
    node.location = (x, y)
    if label:
        node.label = label
    return node


def make_material():
    material = bpy.data.materials.get("Node Atlas Demo")
    if material is None:
        material = bpy.data.materials.new("Node Atlas Demo")
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()

    tex = add(tree.nodes, "ShaderNodeTexCoord", -1180, 160, "Coordinates")
    mapping = add(tree.nodes, "ShaderNodeMapping", -940, 160, "Mapping")
    noise = add(tree.nodes, "ShaderNodeTexNoise", -660, 220, "Large Noise")
    ramp = add(tree.nodes, "ShaderNodeValToRGB", -380, 220, "Color Ramp")
    bsdf = add(tree.nodes, "ShaderNodeBsdfPrincipled", 60, 220, "Metal")
    output = add(tree.nodes, "ShaderNodeOutputMaterial", 420, 220, "Output")
    detail = add(tree.nodes, "ShaderNodeTexNoise", -660, -160, "Fine Noise")
    bump = add(tree.nodes, "ShaderNodeBump", -380, -160, "Surface Bump")

    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.55
    detail.inputs["Scale"].default_value = 34.0
    detail.inputs["Detail"].default_value = 4.0
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.12
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.32

    elements = ramp.color_ramp.elements
    elements[0].position = 0.25
    elements[0].color = (0.015, 0.03, 0.11, 1.0)
    elements[1].position = 0.75
    elements[1].color = (1.0, 0.42, 0.08, 1.0)
    middle = elements.new(0.5)
    middle.color = (0.16, 0.35, 0.8, 1.0)

    links = tree.links
    links.new(tex.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(mapping.outputs["Vector"], detail.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(detail.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    obj = bpy.data.objects.get("Cube")
    if obj is not None:
        obj.data.materials.clear()
        obj.data.materials.append(material)
        obj.active_material = material
    return tree


def setup():
    os.makedirs(IMAGES, exist_ok=True)
    for path in (EXAMPLE, PANEL):
        if os.path.exists(path):
            os.remove(path)

    tree = make_material()
    window, area, region = node_area()
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    space.pin = True
    space.node_tree = tree
    from node_atlas import capture

    capture.node_view_all(window, area, region, space)
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = IMAGES + os.sep
    prefs.filename_pattern = "example-export.png"
    prefs.output_dpi = 96
    prefs.padding = 48
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True


def save_panel():
    window, area, region = node_area()
    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = ""
    prefs.filename_pattern = "{blend}_{tree}_{date}.png"
    prefs.output_dpi = 128
    prefs.padding = 20
    prefs.max_mp = 200.0
    prefs.scope = "CURRENT"
    prefs.enable_shortcut = False
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)
    window, area, region = node_area()
    space = area.spaces.active
    space.show_region_ui = True
    space.show_gizmo = False
    if hasattr(space, "show_region_toolbar"):
        space.show_region_toolbar = False
    overlay = getattr(space, "overlay", None)
    if overlay is not None:
        overlay.show_context_path = False
    from node_atlas import capture

    capture.redraw(window, area, region)
    bpy.context.preferences.view.ui_scale = 1.0
    capture.node_view_all(window, area, region, space)
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    ui_region = next((item for item in area.regions if item.type == "UI"), None)
    if ui_region is None:
        fail("the Node Atlas sidebar did not open")
    ui_region.active_panel_category = "Node Atlas"
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)

    width, height = window.width, window.height
    from node_atlas import operators
    operators.last_result = {"ok": True, "path": EXAMPLE}
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    shot = window.screenshot(region=((0, 0), (width, height)))
    array = np.frombuffer(shot, dtype=np.uint8)
    if array.size != width * height * 4:
        fail(f"unexpected panel screenshot size: {array.size}")

    # Bottom-up screenshot: keep the top of the window and the Node Atlas
    # sidebar at native resolution so the controls stay legible in the README.
    left = max(0, ui_region.x - 10)
    right = min(width, ui_region.x + ui_region.width)
    top = height
    bottom = max(0, height - 620)
    crop = array.reshape(height, width, 4)[bottom:top, left:right]
    from node_atlas import stitch

    stitch._write_png_numpy(crop, PANEL)
    print(f"panel crop: {left},{bottom} .. {right},{top}")


def tick():
    state["ticks"] += 1
    if state["phase"] == "export":
        if os.path.exists(EXAMPLE):
            if state["found"] is None:
                state["found"] = state["ticks"]
            if state["ticks"] - state["found"] >= 3:
                state["phase"] = "panel"
                save_panel()
                print("Saved", EXAMPLE)
                print("Saved", PANEL)
                sys.stdout.flush()
                os._exit(0)
        elif state["ticks"] > 900:
            fail("timed out waiting for the example export")
        return 0.1
    return None


print("NodeAtlas docs images output:", IMAGES)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    setup()
    area, region = node_area()[1:]
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.node_atlas.export_png()
except Exception:
    fail("could not generate the docs images:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.1)
