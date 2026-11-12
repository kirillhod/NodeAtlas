import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_uiscale")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}


def log(*a):
    print("[US]", *a)
    sys.stdout.flush()


def save_rgba(arr, path):
    h, w, c = arr.shape
    img = imbuf.new((w, h), planes=32, buffer_type="BYTE")
    with img.with_buffer(write=True) as buf:
        np.frombuffer(buf, dtype=np.uint8).reshape(h, w, c)[:] = arr
    imbuf.write(img, filepath=path)
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
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            return 0.5

        win, area, region, sp = state["win"], state["area"], state["region"], state["space"]
        v2d = region.view2d
        tw, th = region.width, region.height
        prefs = bpy.context.preferences
        sysp = prefs.system
        viewp = prefs.view
        nt = bpy.data.materials["M_Small"].node_tree
        sp.node_tree = nt
        bpy.data.objects["Cube"].active_material = bpy.data.materials["M_Small"]

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def reset():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            redraw()

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        def shot():
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            return np.frombuffer(mv, dtype=np.uint8).reshape(th, tw, 4).copy()

        def header_bbox(arr):
            rgb = arr[:, :, :3].astype(np.int16)
            sat = rgb.max(axis=2) - rgb.min(axis=2)
            m = sat > 90
            rows = m.sum(axis=1)
            ys = np.nonzero(rows > 20)[0]
            if len(ys) == 0:
                return None
            # groups of rows
            grp = []
            s = p = ys[0]
            for v in ys[1:]:
                if v - p > 4:
                    grp.append((s, p))
                    s = v
                p = v
            grp.append((s, p))
            # take group with max width, lowest (headers near node tops)
            best = None
            for (s, e) in grp:
                y0 = max(0, s - 2)
                y1 = min(th, e + 3)
                cols = m[y0:y1].sum(axis=0)
                xs = np.nonzero(cols > 0)[0]
                if len(xs) == 0:
                    continue
                w = xs.max() - xs.min()
                if best is None or w > best[0]:
                    best = (int(w), int(xs.min()), int(xs.max()), int(s), int(e))
            return best

        log("system.ui_scale=%.3f dpi=%d view.ui_scale=%.3f"
            % (sysp.ui_scale, sysp.dpi, viewp.ui_scale))

        for vus in (1.0, 1.25, 1.5, 2.0, 3.0):
            try:
                viewp.ui_scale = vus
            except Exception as e:
                log("set view.ui_scale=%.2f FAIL %s" % (vus, e))
                continue
            reset()
            u = upp()
            dims = [(n.label or n.name, round(n.dimensions.x, 2), round(n.dimensions.y, 2))
                    for n in nt.nodes]
            arr = shot()
            hb = header_bbox(arr)
            save_rgba(arr, os.path.join(OUT, "uiscale_%.2f.png" % vus))
            # screen pos of graph origin and of node (0,0)
            ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
            # node at (0,0): noise
            n0 = next(n for n in nt.nodes if n.label == "S_noise")
            nx, ny = v2d.view_to_region(n0.location.x, n0.location.y, clip=False)
            log("view.ui_scale=%.2f eff_system=%.3f upp=%.5f ox=%.2f oy=%.2f"
                % (vus, sysp.ui_scale, u, ox, oy))
            log("   dims=%s" % dims)
            log("   view_to_region(node 0,0 top-left)=(%.2f,%.2f)  delta from origin=(%.2f,%.2f)"
                % (nx, ny, nx - ox, ny - oy))
            log("   header bbox=%s" % (hb,))

            # max magnification
            reset()
            prev = upp()
            for k in range(30):
                with bpy.context.temp_override(window=win, area=area, region=region):
                    bpy.ops.view2d.zoom_in()
                redraw()
                u2 = upp()
                if abs(u2 - prev) < 1e-5:
                    break
                prev = u2
            log("   zoom_in limit upp=%.5f -> D_max(if scale used)=%.3f, D_max(system only)=%.3f"
                % (prev, (sysp.ui_scale * vus) / prev, sysp.ui_scale / prev))

        viewp.ui_scale = 1.0
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
