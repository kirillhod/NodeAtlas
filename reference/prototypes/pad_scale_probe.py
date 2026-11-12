import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_padscale")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}


def log(*a):
    print("[PS]", *a)
    sys.stdout.flush()


def save(a, name):
    hh, ww, cc = a.shape
    im = imbuf.new((ww, hh), planes=32, buffer_type="BYTE")
    with im.with_buffer(write=True) as b:
        np.frombuffer(b, dtype=np.uint8).reshape(hh, ww, cc)[:] = a
    imbuf.write(im, filepath=os.path.join(OUT, name))
    im.free()


def run():
    try:
        state["tick"] += 1
        if state["tick"] == 1:
            bpy.context.preferences.view.smooth_view = 0
            win = bpy.context.window_manager.windows[0]
            area = max(win.screen.areas, key=lambda a: a.width * a.height)
            area.type = "NODE_EDITOR"
            sp = area.spaces.active
            sp.tree_type = "ShaderNodeTree"
            sp.show_region_ui = False
            sp.show_region_toolbar = False
            sp.show_gizmo = False
            region = next(r for r in area.regions if r.type == "WINDOW")
            state.update(win=win, area=area, region=region, space=sp,
                         ini=bpy.context.preferences.view.ui_scale)
            return 0.5

        win, area, region, sp = state["win"], state["area"], state["region"], state["space"]
        v2d = region.view2d
        tw, th = region.width, region.height
        nt = bpy.data.materials["M_One"].node_tree
        sp.node_tree = nt
        bpy.data.objects["Cube"].active_material = bpy.data.materials["M_One"]
        for n in nt.nodes:
            n.select = False

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def caps(vus):
            bpy.context.preferences.view.ui_scale = vus
            redraw()
            with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                bpy.ops.node.view_all()
            redraw()
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            arr = np.frombuffer(mv, dtype=np.uint8).reshape(th, tw, 4).copy()
            save(arr, "raw_v%.1f.png" % vus)
            g = arr[:, :, :3].astype(np.float32).mean(axis=2)
            bg = float(np.median(g[th // 2 - 20:th // 2 + 20, tw // 2 - 20:tw // 2 + 20]))
            log("view=%.1f bg=%.1f edge profiles:" % (vus, bg))
            log("  left  %s" % [round(float(v), 1) for v in g[:, :40].mean(axis=0)])
            log("  right %s" % [round(float(v), 1) for v in g[:, -40:].mean(axis=0)])
            log("  bottom %s" % [round(float(v), 1) for v in g[:40].mean(axis=1)])
            log("  top    %s" % [round(float(v), 1) for v in g[-40:].mean(axis=1)])

        for vus in (1.0, 2.0, 6.0):
            caps(vus)
        bpy.context.preferences.view.ui_scale = state["ini"]
        log("DONE")
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    return None


log("start")
bpy.app.timers.register(run, first_interval=0.5)
