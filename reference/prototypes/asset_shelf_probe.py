import bpy
import os
import sys

win = bpy.context.window_manager.windows[0]
area = max(win.screen.areas, key=lambda a: a.width * a.height)
area.type = "NODE_EDITOR"
sp = area.spaces.active

for tt in ("ShaderNodeTree", "GeometryNodeTree", "CompositorNodeTree"):
    try:
        sp.tree_type = tt
        p = sp.bl_rna.properties["show_region_asset_shelf"]
        print("TT", tt, "is_readonly", p.is_readonly, "value", sp.show_region_asset_shelf)
        try:
            sp.show_region_asset_shelf = False
            print("  set False OK ->", sp.show_region_asset_shelf)
        except Exception as e:
            print("  set False FAIL", type(e).__name__, e)
    except Exception as e:
        print("TT", tt, "ERR", e)

print("PREF VIEW asset props:")
for p in bpy.context.preferences.view.bl_rna.properties:
    if "asset" in p.identifier or "shelf" in p.identifier:
        try:
            v = getattr(bpy.context.preferences.view, p.identifier)
        except Exception as e:
            v = e
        print("  ", p.identifier, p.is_readonly, p.type, "->", v)

print("SCREEN OPS:")
for name in dir(bpy.ops.screen):
    if "region" in name or "shelf" in name or "asset" in name:
        print("  screen.", name)
print("ASSET OPS:")
if hasattr(bpy.ops, "asset_shelf"):
    for name in dir(bpy.ops.asset_shelf):
        print("  asset_shelf.", name)

# region toggle properties
try:
    rna = bpy.ops.screen.region_toggle.get_rna_type()
    print("REGION_TOGGLE", [(p.identifier, p.type) for p in rna.properties])
except Exception as e:
    print("REGION_TOGGLE ERR", e)
sys.stdout.flush()
os._exit(0)
