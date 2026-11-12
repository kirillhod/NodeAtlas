import bpy
import imbuf
import math
import os
import sys
import time
import traceback
import numpy as np

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_tiles5")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}

MARGIN = 40
OVERLAP = 120
PAD = 16          # срезаем рамку/скроллбары по краям каждого тайла


def log(*a):
    print("[T5]", *a)
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


def offset_err(A, B, dx, dy):
    """mean abs diff between A and B placed at offset (dx, dy)."""
    ah, aw = A.shape[:2]
    bh, bw = B.shape[:2]
    x0 = max(0, dx)
    x1 = min(aw, bw + dx)
    y0 = max(0, dy)
    y1 = min(ah, bh + dy)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 1e9
    d = np.abs(A[y0:y1, x0:x1, :3].astype(np.int16) - B[y0 - dy:y1 - dy, x0 - dx:x1 - dx, :3].astype(np.int16))
    return float(d.mean())


def best_offset(A, B, ex, ey, rng=4):
    best = (1e18, 0, 0)
    for dy in range(ey - rng, ey + rng + 1):
        for dx in range(ex - rng, ex + rng + 1):
            v = offset_err(A, B, dx, dy)
            if v < best[0]:
                best = (v, dx, dy)
    return best


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
            space = area.spaces.active
            space.tree_type = "ShaderNodeTree"
            space.show_region_ui = False
            space.show_region_toolbar = False
            space.show_gizmo = False
            space.overlay.show_context_path = False
            region = next(r for r in area.regions if r.type == "WINDOW")
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            state.update(win=win, area=area, region=region)
            return 0.5

        win, area, region = state["win"], state["area"], state["region"]
        v2d = region.view2d
        tw, th = region.width, region.height
        nt = bpy.data.materials["M_Uniq"].node_tree

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def geom():
            upp = (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0
            k = 1.0 / upp
            s = bpy.context.preferences.system.ui_scale * k
            ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
            return k, s, ox, oy

        def bounds(g):
            k, s, ox, oy = g
            L = R = B = T = None
            for n in nt.nodes:
                w, h = n.dimensions
                if w <= 0 or h <= 0:
                    continue
                lx, ly = n.location_absolute.x, n.location_absolute.y
                l = ox + s * lx
                r = l + w * k
                t = oy + s * ly
                b = t - h * k
                L = l if L is None else min(L, l)
                R = r if R is None else max(R, r)
                B = b if B is None else min(B, b)
                T = t if T is None else max(T, t)
            return L - MARGIN, B - MARGIN, R + MARGIN, T + MARGIN

        def pan(dx, dy):
            if dx == 0 and dy == 0:
                return
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.pan(deltax=int(dx), deltay=int(dy))
            redraw()

        def place_top_left(tx, ty):
            for _ in range(8):
                L, B, R, T = bounds(geom())
                dx = int(round(L - tx))
                dy = int(round(T - ty))
                if dx == 0 and dy == 0:
                    break
                pan(dx, dy)

        def shot():
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            arr = np.frombuffer(mv, dtype=np.uint8)
            if arr.size != th * tw * 4:
                raise RuntimeError("unexpected screenshot size %d" % arr.size)
            return arr.reshape(th, tw, 4).copy()

        redraw()
        g = geom()
        L, B, R, T = bounds(g)
        W = int(math.ceil(R - L))
        H = int(math.ceil(T - B))
        step_x = tw - OVERLAP
        step_y = th - OVERLAP
        nx = max(1, int(math.ceil((W - OVERLAP) / step_x)))
        ny = max(1, int(math.ceil((H - OVERLAP) / step_y)))
        log("k %.5f s %.5f W %d H %d tiles %dx%d pad %d" % (g[0], g[1], W, H, nx, ny, PAD))

        place_top_left(0, th)
        redraw()
        g0 = geom()
        ox_, oy_, s_ = g0[2], g0[3], g0[1]
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
        log("capture %.2fs (%d tiles, %.1f ms/tile)" % (t_cap, nx * ny, 1000 * t_cap / (nx * ny)))

        # verify each pair against its nominal offset on clean (padded) content
        for i in range(nx - 1):
            a = raw[(i, 0)][PAD:th - PAD, PAD:tw - PAD]
            b = raw[(i + 1, 0)][PAD:th - PAD, PAD:tw - PAD]
            e, dx, dy = best_offset(a[:, :, :3], b[:, :, :3], step_x, 0)
            log("pair x %d nominal %d best %d,%d err %.4f | err@nominal %.4f"
                % (i, step_x, dx, dy, e, offset_err(a[:, :, :3], b[:, :, :3], step_x, 0)))
        for j in range(ny - 1):
            a = raw[(0, j)][PAD:th - PAD, PAD:tw - PAD]
            b = raw[(0, j + 1)][PAD:th - PAD, PAD:tw - PAD]
            e, dx, dy = best_offset(a[:, :, :3], b[:, :, :3], 0, -step_y)
            log("pair y %d nominal %d best %d,%d err %.4f | err@nominal %.4f"
                % (j, -step_y, dx, dy, e, offset_err(a[:, :, :3], b[:, :, :3], 0, -step_y)))

        UW = (nx - 1) * step_x + tw
        UH = (ny - 1) * step_y + th
        cw = tw - 2 * PAD
        ch = th - 2 * PAD
        ov_x = OVERLAP - 2 * PAD
        ov_y = OVERLAP - 2 * PAD

        acc = np.zeros((UH, UW, 3), dtype=np.float32)
        wsum = np.zeros((UH, UW), dtype=np.float32)
        for j in range(ny):
            for i in range(nx):
                tile = raw[(i, j)][PAD:th - PAD, PAD:tw - PAD, :3].astype(np.float32)
                wx = ramp(cw, ov_x, lo=(i > 0), hi=(i < nx - 1))
                wy = ramp(ch, ov_y, lo=(j > 0), hi=(j < ny - 1))
                w = np.outer(wy, wx)
                x = i * step_x + PAD
                y = UH - th - j * step_y + PAD
                acc[y:y + ch, x:x + cw] += tile * w[:, :, None]
                wsum[y:y + ch, x:x + cw] += w
        img = acc / np.maximum(wsum, 1e-6)[:, :, None]
        log("assembly %.2fs" % (time.perf_counter() - t0 - t_cap))

        # uncovered pixels (should be none inside the crop)
        holes = int((wsum[UH - H + PAD:UH - PAD, PAD:W - PAD] <= 0).sum())
        log("holes in crop", holes)

        img8 = np.clip(img + 0.5, 0, 255).astype(np.uint8)
        rgba = np.empty((UH, UW, 4), dtype=np.uint8)
        rgba[:, :, :3] = img8
        rgba[:, :, 3] = 255

        canvas = rgba.copy()
        save_rgba(canvas, os.path.join(OUT, "canvas.png"))
        # PAD-полосы по краю холста не покрыты (мы их срезали у тайлов),
        # поэтому финальный кроп начинается/заканчивается на PAD.
        final = rgba[UH - H + PAD:UH - PAD, PAD:W - PAD].copy()
        save_rgba(final, os.path.join(OUT, "final.png"))
        fh, fw = final.shape[:2]
        log("final", fw, fh)
        holes2 = int((wsum[UH - H + PAD:UH - PAD, PAD:W - PAD] <= 0).sum())
        log("holes in final crop", holes2)

        gr = final[:, :, :3].astype(np.float32).mean(axis=2)
        cold = np.abs(np.diff(gr, axis=1)).mean(axis=0)
        rowd = np.abs(np.diff(gr, axis=0)).mean(axis=1)
        log("col diff median %.4f p99 %.4f max %.4f" %
            (float(np.median(cold)), float(np.percentile(cold, 99)), float(cold.max())))
        log("row diff median %.4f p99 %.4f max %.4f" %
            (float(np.median(rowd)), float(np.percentile(rowd, 99)), float(rowd.max())))

        # seam coordinates in the final (bottom-up), final starts at canvas PAD
        for i in range(1, nx):
            x = i * step_x
            if 1 <= x < fw:
                log("seam col", x, "diff %.4f (neighbors %.4f %.4f)"
                    % (float(cold[x - 1]), float(cold[x - 2]), float(cold[x])))
        for j in range(1, ny):
            y = H - th - j * step_y
            if 1 <= y < fh:
                log("seam row", y, "diff %.4f (neighbors %.4f %.4f)"
                    % (float(rowd[y - 1]), float(rowd[y - 2]), float(rowd[y])))

        # content bbox against corner background
        bg = np.median(final[:8, :8, :3].reshape(-1, 3), axis=0)
        d = np.abs(final[:, :, :3].astype(np.int16) - bg.astype(np.int16)).max(axis=2)
        m = d > 6
        ys, xs = np.nonzero(m)
        log("content bbox", int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()),
            "margins l/b/r/t",
            int(xs.min()), int(ys.min()), int(fw - 1 - xs.max()), int(fh - 1 - ys.max()))

        # is there any leftover scrollbar? check the same edge bands in final
        fg = final[:, :, :3].astype(np.float32).mean(axis=2)
        log("final right cols", [round(float(v), 1) for v in fg[:, -12:].mean(axis=0)])
        log("final bottom rows", [round(float(v), 1) for v in fg[:12, :].mean(axis=1)])

        # --- проверка позиций нод в готовом изображении ---
        # model_x -> final_x = screen_x - PAD
        # model_y -> final_row(bottom-up) = screen_y - th + H - PAD
        fh_off = H - PAD
        sat = (final[:, :, :3].max(axis=2).astype(np.int16)
               - final[:, :, :3].min(axis=2).astype(np.int16))
        devs = []
        for n in nt.nodes:
            if n.dimensions.x <= 0:
                continue
            mx = ox_ + s_ * n.location_absolute.x
            my = oy_ + s_ * n.location_absolute.y
            exi = int(round(mx - PAD))
            eyi = int(round(my - th + H - PAD))
            if not (30 <= exi < fw - 160 and 30 <= eyi < fh - 30):
                continue
            # верхняя граница: резкий переход фон->цветной заголовок
            band = sat[eyi - 14:eyi + 14, exi + 8:exi + 28].mean(axis=1)
            jump = np.diff(band)
            ay = eyi - 14 + int(np.argmax(jump)) + 1
            # левая граница: переход фон->заголовок по горизонтали
            band2 = sat[eyi - 28:eyi - 8, exi - 12:exi + 12].mean(axis=0)
            jump2 = np.diff(band2)
            ax = exi - 12 + int(np.argmax(jump2)) + 1
            if jump.max() > 20 and jump2.max() > 20:
                devs.append((n.name, ax - exi, ay - eyi, round(float(jump.max()), 1),
                             round(float(jump2.max()), 1)))
        if devs:
            dxs = [d[1] for d in devs]
            dys = [d[2] for d in devs]
            log("node check: %d nodes, dx min/max %d/%d, dy min/max %d/%d, mean|dx| %.2f mean|dy| %.2f"
                % (len(devs), min(dxs), max(dxs), min(dys), max(dys),
                   float(np.mean(np.abs(dxs))), float(np.mean(np.abs(dys)))))
            log("node deviations", devs)

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
