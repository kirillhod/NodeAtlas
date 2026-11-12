# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import os

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=False)

obj = bpy.data.objects["Cube"]
obj.data.materials.clear()
mat = bpy.data.materials.new("M_Small")
obj.data.materials.append(mat)
obj.active_material = mat
if mat.node_tree is None:
    mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()

noise = nt.nodes.new("ShaderNodeTexNoise")
noise.location = (0, 0)
noise.label = "S_noise"
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.location = (650, 250)
ramp.label = "S_ramp"
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (1350, 0)
bsdf.label = "S_bsdf"
out = nt.nodes.new("ShaderNodeOutputMaterial")
out.location = (2050, -150)
out.label = "S_out"

nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

path = os.path.join(OUT, "scene_small.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path, "nodes", len(nt.nodes))
