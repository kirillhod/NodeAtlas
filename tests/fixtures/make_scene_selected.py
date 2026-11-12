import bpy
import os

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=False)

obj = bpy.data.objects["Cube"]
obj.data.materials.clear()
mat = bpy.data.materials.new("M_Sel")
obj.data.materials.append(mat)
obj.active_material = mat
if mat.node_tree is None:
    mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()

n1 = nt.nodes.new("ShaderNodeTexNoise"); n1.location = (0, 0); n1.label = "N1"
r1 = nt.nodes.new("ShaderNodeValToRGB"); r1.location = (500, 100); r1.label = "R1"
b1 = nt.nodes.new("ShaderNodeBsdfPrincipled"); b1.location = (1000, 0); b1.label = "B1"
o1 = nt.nodes.new("ShaderNodeOutputMaterial"); o1.location = (1600, 0); o1.label = "O1"
u1 = nt.nodes.new("ShaderNodeMapRange"); u1.location = (300, -100); u1.label = "U1_inside_bbox"

nt.links.new(n1.outputs["Fac"], r1.inputs["Fac"])
nt.links.new(r1.outputs["Color"], b1.inputs["Base Color"])
nt.links.new(b1.outputs["BSDF"], o1.inputs["Surface"])

# frame F1 with children C1, C2
f1 = nt.nodes.new("NodeFrame"); f1.location = (0, -800); f1.label = "F1"
c1 = nt.nodes.new("ShaderNodeTexNoise"); c1.parent = f1; c1.location = (50, -50); c1.label = "C1_child_of_F1"
c2 = nt.nodes.new("ShaderNodeValToRGB"); c2.parent = f1; c2.location = (350, -50); c2.label = "C2_child_of_F1"

# frame F2 with selected C3 and unselected C4
f2 = nt.nodes.new("NodeFrame"); f2.location = (2000, 0); f2.label = "F2"
c3 = nt.nodes.new("ShaderNodeBsdfPrincipled"); c3.parent = f2; c3.location = (50, -50); c3.label = "C3_selected_in_F2"
c4 = nt.nodes.new("ShaderNodeOutputMaterial"); c4.parent = f2; c4.location = (350, -50); c4.label = "C4_unselected_in_F2"

path = os.path.join(OUT, "scene_selected.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path)
for n in nt.nodes:
    print("NODE", n.label, n.name, "parent", n.parent.label if n.parent else None,
          "loc", tuple(n.location), "abs", tuple(n.location_absolute))
