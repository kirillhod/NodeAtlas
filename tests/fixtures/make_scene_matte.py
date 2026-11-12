# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import os

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=False)

obj = bpy.data.objects["Cube"]
obj.data.materials.clear()
mat = bpy.data.materials.new("M_Matte")
obj.data.materials.append(mat)
obj.active_material = mat
if mat.node_tree is None:
    mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()

noise = nt.nodes.new("ShaderNodeTexNoise"); noise.location = (0, 0); noise.label = "M_noise"
ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (500, 150); ramp.label = "M_ramp"
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (1000, 0); bsdf.label = "M_bsdf"
out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (1600, -100); out.label = "M_out"

# make the ramp colorful (test key-color conflicts)
cr = ramp.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (0.0, 0.0, 0.0, 1.0)
cr.elements[1].position = 1.0
cr.elements[1].color = (1.0, 0.0, 1.0, 1.0)
mid = cr.elements.new(0.5)
mid.color = (0.0, 1.0, 1.0, 1.0)

nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

path = os.path.join(OUT, "scene_matte.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path, "nodes", len(nt.nodes))
