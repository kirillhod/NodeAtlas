# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import os

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=False)

# --- shader material (already validated) ---
cube = bpy.data.objects["Cube"]
cube.data.materials.clear()
mat = bpy.data.materials.new("M_Small")
cube.data.materials.append(mat)
cube.active_material = mat
if mat.node_tree is None:
    mat.use_nodes = True
mt = mat.node_tree
mt.nodes.clear()
n = mt.nodes.new("ShaderNodeTexNoise"); n.location = (0, 0); n.label = "S_noise"
n = mt.nodes.new("ShaderNodeValToRGB"); n.location = (650, 250); n.label = "S_ramp"
n = mt.nodes.new("ShaderNodeBsdfPrincipled"); n.location = (1350, 0); n.label = "S_bsdf"
n = mt.nodes.new("ShaderNodeOutputMaterial"); n.location = (2050, -150); n.label = "S_out"

# --- geometry nodes tree ---
gn = bpy.data.node_groups.new("GN_Test", "GeometryNodeTree")
gn.nodes.clear()
specs = [
    ("NodeGroupInput", -400, 0, "GN_in"),
    ("GeometryNodeInputPosition", 0, 0, "GN_pos"),
    ("GeometryNodeSetPosition", 650, 0, "GN_setpos"),
    ("GeometryNodeTransform", 1300, 0, "GN_xform"),
    ("GeometryNodeRealizeInstances", 0, -900, "GN_realize"),
    ("GeometryNodeJoinGeometry", 650, -900, "GN_join"),
    ("GeometryNodeSetShadeSmooth", 1300, -900, "GN_smooth"),
    ("NodeGroupOutput", 1950, -450, "GN_out"),
]
made = []
for kind, x, y, label in specs:
    try:
        nd = gn.nodes.new(kind)
        nd.location = (x, y)
        nd.label = label
        made.append((kind, nd.name))
    except Exception as e:
        print("GN node FAIL", kind, e)

# connect something plausible
try:
    gn.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    gn.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gn.links.new(gn.nodes["Group Input"].outputs[0], gn.nodes["Set Position"].inputs["Geometry"])
    gn.links.new(gn.nodes["Position"].outputs[0], gn.nodes["Set Position"].inputs["Position"])
    gn.links.new(gn.nodes["Set Position"].outputs[0], gn.nodes["Transform Geometry"].inputs["Geometry"])
    gn.links.new(gn.nodes["Transform Geometry"].outputs[0], gn.nodes["Group Output"].inputs[0])
except Exception as e:
    print("GN link", type(e).__name__, e)

obj = bpy.data.objects["Cube"]
mod = obj.modifiers.new("GN", "NODES")
mod.node_group = gn

# --- compositor tree (5.3: scene.compositing_node_group; 4.2–5.1: scene.node_tree) ---
scene = bpy.context.scene
if hasattr(scene, "compositing_node_group"):
    comp = bpy.data.node_groups.new("COMP_Test", "CompositorNodeTree")
    comp.nodes.clear()
else:
    scene.use_nodes = True
    comp = scene.node_tree
    comp.nodes.clear()
cspecs = [
    ("CompositorNodeRLayers", -200, 0, "C_layers"),
    ("CompositorNodeGlare", 500, 200, "C_glare"),
    ("CompositorNodeLensdist", 500, -500, "C_lens"),
    ("CompositorNodeViewer", 1200, 0, "C_viewer"),
    ("NodeGroupOutput", 1750, -300, "C_out"),
]
c_made = []
for kind, x, y, label in cspecs:
    try:
        nd = comp.nodes.new(kind)
        nd.location = (x, y)
        nd.label = label
        c_made.append((kind, nd.name))
    except Exception as e:
        print("COMP node FAIL", kind, e)

try:
    comp.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    comp.links.new(comp.nodes["Render Layers"].outputs["Image"], comp.nodes["Glare"].inputs["Image"])
    comp.links.new(comp.nodes["Glare"].outputs["Image"], comp.nodes["Viewer"].inputs["Image"])
    comp.links.new(comp.nodes["Glare"].outputs["Image"], comp.nodes["Group Output"].inputs[0])
except Exception as e:
    print("COMP link", type(e).__name__, e)

try:
    if hasattr(scene, "compositing_node_group"):
        scene.compositing_node_group = comp
        print("scene.compositing_node_group ->", scene.compositing_node_group)
    else:
        print("scene.node_tree (legacy compositor) ->", comp)
except Exception as e:
    print("assign compositor tree FAIL", type(e).__name__, e)

path = os.path.join(OUT, "scene_graphs.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path)
print("nodes GN:", [n.name for n in gn.nodes])
print("nodes COMP:", [n.name for n in comp.nodes])
print("GN interface:", [(i.name, i.in_out) for i in gn.interface.items_tree])
print("COMP interface:", [(i.name, i.in_out) for i in comp.interface.items_tree])
