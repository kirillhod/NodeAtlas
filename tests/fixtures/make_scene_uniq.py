# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import os

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=False)

obj = bpy.data.objects["Cube"]
obj.data.materials.clear()
mat = bpy.data.materials.new("M_Uniq")
obj.data.materials.append(mat)
obj.active_material = mat
if mat.node_tree is None:
    mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()

rows = [1600, 0, -1600]
chains = [-2200, 400]


def add(kind, x, y, label=None):
    n = nt.nodes.new(kind)
    n.location = (x, y)
    if label:
        n.label = label
    return n


specs = [
    # chain builder id, y, x
    ("texnoise", "ramp", "bsdf"),
    ("texvoronoi", "bump", "bsdf"),
    ("texwave", "mix", "emission"),
    ("texmagic", "maprange", "bsdf"),
    ("texbrick", "huesat", "diffuse"),
    ("texgradient", "curve", "emission"),
]

idx = 0
for y in rows:
    for x in chains:
        a, b, c = specs[idx]
        idx += 1
        n1 = add("ShaderNodeTex" + {"texnoise": "Noise", "texvoronoi": "Voronoi",
                                    "texwave": "Wave", "texmagic": "Magic",
                                    "texbrick": "Brick", "texgradient": "Gradient"}[a],
                 x, y, label="C%d_%s" % (idx, a))
        n2kind = {"ramp": "ShaderNodeValToRGB", "bump": "ShaderNodeBump",
                  "mix": "ShaderNodeMix", "maprange": "ShaderNodeMapRange",
                  "huesat": "ShaderNodeHueSaturation",
                  "curve": "ShaderNodeRGBCurve"}[b]
        n2 = add(n2kind, x + 480, y, label="C%d_%s" % (idx, b))
        n3kind = {"bsdf": "ShaderNodeBsdfPrincipled", "emission": "ShaderNodeEmission",
                  "diffuse": "ShaderNodeBsdfDiffuse"}[c]
        n3 = add(n3kind, x + 980, y, label="C%d_%s" % (idx, c))
        out = add("ShaderNodeOutputMaterial", x + 1500, y, label="C%d_out" % idx)

        # wire something plausible, ignore socket mismatches
        try:
            for o in n1.outputs:
                if o.enabled:
                    for i in n2.inputs:
                        if i.enabled and i.type == o.type:
                            nt.links.new(o, i)
                            raise StopIteration
        except StopIteration:
            pass
        try:
            for o in n2.outputs:
                if o.enabled:
                    for i in n3.inputs:
                        if i.enabled and i.type == o.type:
                            nt.links.new(o, i)
                            raise StopIteration
        except StopIteration:
            pass
        try:
            nt.links.new(n3.outputs[0], out.inputs["Surface"])
        except Exception:
            pass

# make sizes differ a bit
for n in nt.nodes:
    pass

path = os.path.join(OUT, "scene_uniq.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path, "nodes", len(nt.nodes))
