import bpy
import imbuf
import math
import os
import sys
import time
import traceback
import numpy as np

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_dpi3")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}

OVERLAP = 120
PAD = 16
FILL_PADDING = False   # True = заливать поля; False = сохранять настоящий фон графа

RUNS = [
    # tag, scene material, D (px per node unit), padding, start view, view.ui_scale
    ("small_d100_p20_r1", "M_Small", 1.00, 20, "reset", 1.0),
    ("small_d100_p20_r2", "M_Small", 1.00, 20, "reset", 1.0),
    ("small_d100_p20_v2", "M_Small", 1.00, 20, "reset", 2.0),
    ("small_d400_p20_v2", "M_Small", 4.00, 20, "reset", 2.0),
    ("big_d100_p40_v1", "M_Uniq", 1.00, 40, "reset", 1.0),
    ("big_d100_p40_v2", "M_Uniq", 1.00, 40, "reset", 2.0),
    ("small_d100_p20_r3", "M_Small", 1.00, 20, "reset", 1.0),
]


def log(*a):
    print("[T6]", *a)
    sys.stdout.flush()


def save_rgba(arr, path):
    h, w, c = arr.shape
    img = imbuf.new((w, h), planes=32, buffer_type="BYTE")
    with img.with_buffer(write=True) as buf:
        np.frombuffer(buf, dtype=np.uint8).reshape(h, w, c)[:] = arr
    tmp = path + ".tmp.png"
    imbuf.write(img, filepath=tmp)
    img.free()
    os.replace(tmp, path)


def ramp(n, ov, lo, hi):
    w = np.ones(n, dtype=np.float32)
    if ov > 0:
        r = (np.arange(ov, dtype=np.float32) + 0.5) / ov
        if lo:
            w[:ov] = r
        if hi:
            w[n - ov:] = r[::-1]
    return w


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
            sp.overlay.show_context_path = False
            region = next(r for r in area.regions if r.type == "WINDOW")
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            state.update(win=win, area=area, region=region, space=sp,
                         initial_view_scale=bpy.context.preferences.view.ui_scale)
            return 0.5

        win, area, region = state["win"], state["area"], state["region"]
        v2d = region.view2d
        tw, th = region.width, region.height
        uiscale = bpy.context.preferences.system.ui_scale
        viewscale = bpy.context.preferences.view
        eff_scale = uiscale * viewscale.ui_scale

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        def view_op(name, **kw):
            with bpy.context.temp_override(window=win, area=area, region=region):
                getattr(bpy.ops.view2d, name)(**kw)
            redraw()

        def reset_view():
            view_op("reset")

        def prime():
            # детерминированная база: view_all вычисляется из границ нод,
            # а не из текущего (дробного) центра вида, как reset
            with bpy.context.temp_override(window=win, area=area, region=region,
                                           space_data=state["space"]):
                bpy.ops.node.view_all()
            redraw()

        def pan(dx, dy):
            if dx or dy:
                view_op("pan", deltax=int(dx), deltay=int(dy))

        def set_zoom(target):
            prime()
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

        def start_view(kind):
            reset_view()
            if kind in ("random1", "random3"):
                view_op("zoom_in")
                view_op("zoom_in")
                pan(420, -260)
            if kind in ("random2", "random3"):
                pan(-700, 380)
                view_op("zoom_out")

        def geom():
            u = upp()
            k = 1.0 / u
            s = eff_scale * k
            ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
            return k, s, ox, oy

        def shot():
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            arr = np.frombuffer(mv, dtype=np.uint8)
            if arr.size != th * tw * 4:
                raise RuntimeError("screenshot size %d" % arr.size)
            return arr.reshape(th, tw, 4).copy()

        results = []
        for tag, matname, D, padding, sv, vus in RUNS:
            viewscale.ui_scale = vus
            eff_scale = uiscale * vus
            nt = bpy.data.materials[matname].node_tree
            sp = state["space"]
            # снять выделение/активность: контур активной ноды выходит за
            # Node.dimensions и съедает padding (масштабируется с ui_scale)
            sel = [(n, n.select) for n in nt.nodes]
            act = nt.nodes.active
            for n in nt.nodes:
                n.select = False
            try:
                nt.nodes.active = None
            except Exception:
                pass
            try:
                sp.node_tree = nt
            except Exception as e:
                log("node_tree set failed: %s" % e)
            obj = bpy.data.objects["Cube"]
            obj.active_material = bpy.data.materials[matname]
            redraw()
            dims_ok = sum(1 for n in nt.nodes if n.dimensions.x > 0)
            log("%s: tree %s, nodes with dims %d/%d, region %dx%d"
                % (tag, nt.name, dims_ok, len(nt.nodes), tw, th))
            start_view(sv)
            it, u_ach = set_zoom(eff_scale / D)
            g = geom()
            k, s, ox, oy = g
            log("%s: D=%.2f pad=%d view=%.2f eff=%.3f -> upp=%.5f (iters %d), s=%.5f"
                % (tag, D, padding, vus, eff_scale, upp(), it, s))

            def node_rects(g=None):
                g = g or geom()
                k, s, ox, oy = g
                rects = []
                for n in nt.nodes:
                    w, h = n.dimensions
                    if w <= 0 or h <= 0:
                        continue
                    l = ox + s * n.location_absolute.x
                    t = oy + s * n.location_absolute.y
                    rects.append((n.name, l, t, l + w * k, t - h * k))
                return rects

            rects = node_rects()
            L = min(r[1] for r in rects)
            B = min(r[4] for r in rects)
            R = max(r[3] for r in rects)
            T = max(r[2] for r in rects)
            cw, chh = R - L, T - B
            M = padding + PAD
            Lc, Bc = L - M, B - M
            Wc, Hc = cw + 2 * M, chh + 2 * M

            step_x = tw - OVERLAP
            step_y = th - OVERLAP
            nx = max(1, int(math.ceil((Wc - OVERLAP) / step_x)))
            ny = max(1, int(math.ceil((Hc - OVERLAP) / step_y)))

            # place tile 0 top-left at region (0, th); then model Lc is at screen 0
            for _ in range(8):
                r0 = node_rects()
                cl = min(r[1] for r in r0)
                ct = max(r[2] for r in r0)
                dx = int(round(cl - M))
                dy = int(round(ct - (th - M)))
                if dx == 0 and dy == 0:
                    break
                pan(dx, dy)
            redraw()

            g0 = geom()
            t0 = time.perf_counter()
            raw = {}
            cur = (0, 0)
            for j in range(ny):
                for i in range(nx):
                    if (i, j) != (0, 0):
                        pan((i - cur[0]) * step_x, (cur[1] - j) * step_y)
                        cur = (i, j)
                    raw[(i, j)] = shot()
            t_cap = time.perf_counter() - t0

            UW = (nx - 1) * step_x + tw
            UH = (ny - 1) * step_y + th
            cwid = tw - 2 * PAD
            chgt = th - 2 * PAD
            ovx = OVERLAP - 2 * PAD
            acc = np.zeros((UH, UW, 3), dtype=np.float32)
            wsum = np.zeros((UH, UW), dtype=np.float32)
            for j in range(ny):
                for i in range(nx):
                    tile = raw[(i, j)][PAD:th - PAD, PAD:tw - PAD, :3].astype(np.float32)
                    wx = ramp(cwid, ovx, lo=(i > 0), hi=(i < nx - 1))
                    wy = ramp(chgt, ovx, lo=(j > 0), hi=(j < ny - 1))
                    w = np.outer(wy, wx)
                    x = i * step_x + PAD
                    y = UH - th - j * step_y + PAD
                    acc[y:y + chgt, x:x + cwid] += tile * w[:, :, None]
                    wsum[y:y + chgt, x:x + cwid] += w
            img = acc / np.maximum(wsum, 1e-6)[:, :, None]
            t_asm = time.perf_counter() - t0 - t_cap

            fw = int(math.ceil(cw)) + 2 * padding
            fh = int(math.ceil(chh)) + 2 * padding
            c0 = UH - fh - PAD
            holes = int((wsum[c0:c0 + fh, PAD:PAD + fw] <= 0).sum())

            del acc
            wsum = None

            img8 = np.clip(img + 0.5, 0, 255).astype(np.uint8)
            del img
            rgba = np.empty((UH, UW, 4), dtype=np.uint8)
            rgba[:, :, :3] = img8
            rgba[:, :, 3] = 255
            del img8

            final = rgba[c0:c0 + fh, PAD:PAD + fw].copy()

            # чистые поля: заливаем внешнюю рамку цветом фона (отключаемо)
            if padding > 0 and FILL_PADDING:
                s = max(2, min(8, padding // 2))
                bgc = np.median(final[2:2 + s, 2:2 + s, :3].reshape(-1, 3), axis=0)
                bgc = bgc.astype(np.uint8)
                final[:padding, :, :3] = bgc
                final[-padding:, :, :3] = bgc
                final[:, :padding, :3] = bgc
                final[:, -padding:, :3] = bgc

            save_rgba(final, os.path.join(OUT, "final_%s.png" % tag))

            # exact padding check via content bbox (threshold 15 to skip grid dots)
            bg = np.median(final[:6, :6, :3].reshape(-1, 3), axis=0)
            d = np.abs(final[:, :, :3].astype(np.int16) - bg.astype(np.int16)).max(axis=2)
            mask = d > 15
            colcnt = mask.sum(axis=0)
            rowcnt = mask.sum(axis=1)
            xs = np.nonzero(colcnt >= 2)[0]
            ys = np.nonzero(rowcnt >= 2)[0]
            log("  final %dx%d, margins l/b/r/t = %d/%d/%d/%d (target %d)"
                % (final.shape[1], final.shape[0], xs.min(), ys.min(),
                   final.shape[1] - 1 - xs.max(), final.shape[0] - 1 - ys.max(), padding))

            # статистика полей: настоящий фон с сеткой, а не заливка
            fstat = []
            if padding > 0:
                bands = [final[:padding, padding:-padding, :3],
                         final[-padding:, padding:-padding, :3]]
                if padding * 2 < final.shape[1]:
                    bands += [final[padding:-padding, :padding, :3],
                              final[padding:-padding, -padding:, :3]]
                for b in bands:
                    fstat.append((float(b.std()), float(b.mean())))
            log("  holes %d; padding bands std/mean %s"
                % (holes, [("%.2f/%.1f" % (s, m)) for s, m in fstat]))

            # node top-left detection in final coords
            sat = (final[:, :, :3].max(axis=2).astype(np.int16)
                   - final[:, :, :3].min(axis=2).astype(np.int16))
            fh_img, fw_img = final.shape[:2]
            devs = []
            k0, s0, ox0, oy0 = g0
            for n in nt.nodes:
                if n.dimensions.x <= 0:
                    continue
                mx = ox0 + s0 * n.location_absolute.x
                my = oy0 + s0 * n.location_absolute.y
                exi = int(round(mx - PAD))
                eyi = int(round(my - th + UH - c0))
                if not (30 <= exi < fw_img - 90 and 26 <= eyi < fh_img - 12):
                    continue
                band = sat[eyi - 12:eyi + 12, exi + 6:exi + 24].mean(axis=1)
                j1 = np.diff(band)
                band2 = sat[eyi - 24:eyi - 6, exi - 10:exi + 10].mean(axis=0)
                j2 = np.diff(band2)
                ay = eyi - 12 + int(np.argmax(j1)) + 1
                ax = exi - 10 + int(np.argmax(j2)) + 1
                if j1.max() > 20 and j2.max() > 20:
                    devs.append((ax - exi, ay - eyi))
            if devs:
                log("  node placement: n=%d dx %d..%d dy %d..%d"
                    % (len(devs), min(d[0] for d in devs), max(d[0] for d in devs),
                       min(d[1] for d in devs), max(d[1] for d in devs)))

            results.append((tag, D, padding, final.shape[1], final.shape[0], cw, chh,
                            t_cap, t_asm, nx, ny))
            log("  grid %dx%d capture %.2fs assembly %.2fs" % (nx, ny, t_cap, t_asm))

        log("=== summary ===")
        for r in results:
            log("%s D=%.2f pad=%d -> %dx%d (content %.1fx%.1f) tiles %dx%d cap %.2fs asm %.2fs"
                % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[9], r[10], r[7], r[8]))

        viewscale.ui_scale = state.get("initial_view_scale", 1.0)
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
