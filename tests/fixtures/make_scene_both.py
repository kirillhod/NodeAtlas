import bpy
import os

BASE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(BASE, "scene_uniq.blend"))

with bpy.data.libraries.load(os.path.join(BASE, "scene_small.blend")) as (src, dst):
    dst.materials = ["M_Small"]

small = bpy.data.materials["M_Small"]
cube = bpy.data.objects["Cube"]
uniq = cube.data.materials[0]
print("cube material before:", uniq.name)

mesh2 = cube.data.copy()
mesh2.name = "MeshSmall"
mesh2.materials.clear()
mesh2.materials.append(small)

obj2 = bpy.data.objects.new("CubeSmall", mesh2)
bpy.context.scene.collection.objects.link(obj2)
obj2.active_material = small
print("cube material after:", cube.data.materials[0].name)

path = os.path.join(BASE, "scene_both.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("saved", path, "materials", [m.name for m in bpy.data.materials])
