# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import os

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=False)

obj = bpy.data.objects["Cube"]
obj.data.materials.clear()
mat = bpy.data.materials.new("M_One")
obj.data.materials.append(mat)
obj.active_material = mat
if mat.node_tree is None:
    mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
n = nt.nodes.new("ShaderNodeTexNoise")
n.location = (0, 0)
n.label = "One_noise"

path = os.path.join(OUT, "scene_one.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path, "nodes", [x.name for x in nt.nodes])
