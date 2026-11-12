import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

state = {"tick": 0}
OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_repro")
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print("[RI]", *a)
    sys.stdout.flush()


def save(arr, name):
    h, w, c = arr.shape
    img = imbuf.new((w, h), planes=32, buffer_type="BYTE")
    with img.with_buffer(write=True) as b:
        np.frombuffer(b, dtype=np.uint8).reshape(h, w, c)[:] = arr
    imbuf.write(img, filepath=os.path.join(OUT, name))
    img.free()


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
            state.update(win=win, area=area, region=region, space=sp)
            return 0.5

        win, area, region, sp = state["win"], state["area"], state["region"], state["space"]
        v2d = region.view2d
        tw, th = region.width, region.height
        nt = bpy.data.materials["M_Small"].node_tree
        sp.node_tree = nt
        bpy.data.objects["Cube"].active_material = bpy.data.materials["M_Small"]

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def view_op(name, **kw):
            with bpy.context.temp_override(window=win, area=area, region=region):
                getattr(bpy.ops.view2d, name)(**kw)
            redraw()

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        def zoom_to(target):
            for it in range(60):
                u = upp()
                r = u / target
                if abs(r - 1.0) < 0.002:
                    return it, u
                if r > 1.0:
                    f = target / u
                    if 0.46 <= f < 1.0:
                        rw = int(tw * f)
                        rh = int(th * f)
                        view_op("zoom_border",
                                xmin=int(tw / 2 - rw / 2), xmax=int(tw / 2 + rw / 2),
                                ymin=int(th / 2 - rh / 2), ymax=int(th / 2 + rh / 2),
                                wait_for_input=False)
                    else:
                        view_op("zoom_in")
                else:
                    view_op("zoom_out")
            return -1, upp()

        def view_all():
            with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                bpy.ops.node.view_all()
            redraw()

        def shot(name):
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            arr = np.frombuffer(mv, dtype=np.uint8).reshape(th, tw, 4).copy()
            ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
            log("%s upp=%.6f ox=%.4f oy=%.4f" % (name, upp(), ox, oy))
            save(arr, "inproc_%s.png" % name)

        redraw()
        target = 1.25025

        view_all()
        zoom_to(target)
        shot("1")

        view_all()
        zoom_to(target)
        shot("2")

        # emulate a previous export: random-ish view, then view_all again
        view_op("zoom_in")
        view_op("pan", deltax=357, deltay=-211)
        view_op("zoom_out")
        view_all()
        zoom_to(target)
        shot("3")

        # without view_all: reset only
        view_op("reset")
        zoom_to(target)
        shot("4")
        view_op("reset")
        zoom_to(target)
        shot("5")

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
