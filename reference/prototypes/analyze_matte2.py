import imbuf
import numpy as np
import os

BASE = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_matte")
CROP = 16


def load(name):
    img = imbuf.load(os.path.join(BASE, name))
    w, h = img.size
    with img.with_buffer() as b:
        a = np.frombuffer(b, dtype=np.uint8).reshape(h, w, 4).copy()
    img.free()
    return a[CROP:-CROP, CROP:-CROP, :3].astype(np.float32) / 255.0


def to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1 / 2.4)) - 0.055)


imgs = {n: load("bg_%s.png" % n) for n in ("black", "white", "magenta", "green", "cyan", "gray")}
H, W = imgs["black"].shape[:2]
print("cropped image", W, H)
B = {n: np.median(im[:20, :20].reshape(-1, 3), axis=0) for n, im in imgs.items()}
for n in imgs:
    print("bg %-8s median %s" % (n, np.round(B[n] * 255).astype(int)))


def alpha_pair(a_name, b_name, linear=False):
    ia, ib = imgs[a_name], imgs[b_name]
    ba, bb = B[a_name], B[b_name]
    if linear:
        ia, ib = to_lin(ia), to_lin(ib)
        ba, bb = to_lin(ba), to_lin(bb)
    diff = ba - bb
    valid = np.abs(diff) > 0.02
    a = 1.0 - (ia - ib) / np.where(valid, diff, 1.0)
    a = np.where(valid, a, np.nan)
    mean = np.nanmean(a, axis=2)
    std = np.nanstd(a, axis=2)
    return np.clip(mean, 0, 1), std, valid


print("\n== alpha consistency across two backgrounds ==")
results = []
for pair in (("black", "white"), ("black", "gray"), ("magenta", "green")):
    for lin in (False, True):
        a, std, valid = alpha_pair(pair[0], pair[1], lin)
        mid = (a > 0.02) & (a < 0.98) & np.isfinite(a) & (valid.sum() >= 2)
        results.append((pair[0] + "/" + pair[1], lin, float(np.nanmean(std[mid])),
                        float(np.nanmedian(std[mid])), int(mid.sum())))
        print("  %-16s %-6s mean std %.6f median %.6f n=%d"
              % (pair[0] + "/" + pair[1], "linear" if lin else "sRGB",
                 np.nanmean(std[mid]), np.nanmedian(std[mid]), mid.sum()))

best = min(results, key=lambda t: t[2])
print("BEST", best)
pair = best[0].split("/")
lin = best[1]
a_ref, _, _ = alpha_pair(pair[0], pair[1], lin)

# cross-check against another pair/model
a_x, _, _ = alpha_pair("magenta", "green", lin)
mid = (a_ref > 0.05) & (a_ref < 0.95) & np.isfinite(a_x)
print("cross-pair alpha on edges: mean |d| %.6f p99 %.6f"
      % (float(np.abs(a_ref[mid] - a_x[mid]).mean()),
         float(np.percentile(np.abs(a_ref[mid] - a_x[mid]), 99))))

# reference foreground from the black capture in the chosen space
i0 = to_lin(imgs["black"]) if lin else imgs["black"]
b0 = to_lin(B["black"]) if lin else B["black"]
F_ref = (i0 - (1 - a_ref[:, :, None]) * b0) / np.maximum(a_ref[:, :, None], 1e-3)
F_ref = np.clip(F_ref, 0, 1)
F_ref_srgb = to_srgb(F_ref) if lin else F_ref

bg = a_ref < 0.01
fg = a_ref > 0.99
edge = (a_ref > 0.05) & (a_ref < 0.95)
print("alpha: bg %.2f%%, fg %.2f%%, edge %.2f%% (%d px)"
      % (100 * bg.mean(), 100 * fg.mean(), 100 * edge.mean(), edge.sum()))
print("edge alpha percentiles", [round(float(v), 3) for v in np.percentile(a_ref[edge], [0, 10, 25, 50, 75, 90, 100])])
print("bg alpha mean/max %.6f/%.4f, fg mean/min %.6f/%.4f"
      % (a_ref[bg].mean(), a_ref[bg].max(), a_ref[fg].mean(), a_ref[fg].min()))


def smoothstep(d, t0, t1):
    x = np.clip((d - t0) / max(t1 - t0, 1e-6), 0, 1)
    return x * x * (3 - 2 * x)


# checkerboard for composites
yy, xx = np.mgrid[0:H, 0:W]
check = np.where(((yy // 16) + (xx // 16)) % 2 == 0, 0.30, 0.75).astype(np.float32)
comp_ref = a_ref[:, :, None] * F_ref_srgb + (1 - a_ref[:, :, None]) * check[:, :, None]

print("\n== chroma-key candidates (distance keyer, thresholds fitted as an upper bound) ==")
report = []
for key in ("magenta", "green", "cyan", "white", "gray"):
    I = to_lin(imgs[key]) if lin else imgs[key]
    Kp = to_lin(B[key]) if lin else B[key]
    d = np.sqrt(((I - Kp) ** 2).sum(axis=2)) / np.sqrt(3.0)
    Fd = np.sqrt(((F_ref - Kp) ** 2).sum(axis=2)) / np.sqrt(3.0)
    best_thr = None
    for t0 in (0.0, 0.01, 0.02, 0.04, 0.06):
        for t1 in np.linspace(0.08, 0.70, 32):
            ak = smoothstep(d, t0, t1)
            mae = float(np.abs(ak[edge] - a_ref[edge]).mean())
            if best_thr is None or mae < best_thr[0]:
                best_thr = (mae, t0, t1)
    mae, t0, t1 = best_thr
    ak = smoothstep(d, t0, t1)
    err = np.abs(ak - a_ref)[edge]

    # realistic composites
    simple = ak[:, :, None] * (to_srgb(imgs[key]) if lin else imgs[key]) + (1 - ak[:, :, None]) * check[:, :, None]
    Fk = (I - (1 - ak[:, :, None]) * Kp) / np.maximum(ak[:, :, None], 1e-3)
    Fk = np.clip(Fk, 0, 1)
    decon = ak[:, :, None] * (to_srgb(Fk) if lin else Fk) + (1 - ak[:, :, None]) * check[:, :, None]
    e_simple = np.abs(simple - comp_ref).mean(axis=2)[edge]
    e_decon = np.abs(decon - comp_ref).mean(axis=2)[edge]
    es_rgb = (simple - comp_ref)[edge].mean(axis=0) * 255
    ed_rgb = (decon - comp_ref)[edge].mean(axis=0) * 255

    rec = dict(key=key, mae_alpha=mae, p95=float(np.percentile(err, 95)),
               gt010=float((err > 0.10).mean()), gt025=float((err > 0.25).mean()),
               bg_false=float((ak[bg] > 0.10).mean()),
               fg_holes=float((ak[fg] < 0.90).mean()),
               comp_simple_mean=float(e_simple.mean() * 255),
               comp_simple_p95=float(np.percentile(e_simple, 95) * 255),
               comp_simple_max=float(e_simple.max() * 255),
               comp_decon_mean=float(e_decon.mean() * 255),
               comp_decon_p95=float(np.percentile(e_decon, 95) * 255),
               comp_decon_max=float(e_decon.max() * 255),
               err_simple_rgb=[float(v) for v in es_rgb],
               err_decon_rgb=[float(v) for v in ed_rgb],
               key_fg_min=float(Fd[fg].min()), key_fg_p1=float(np.percentile(Fd[fg], 1)),
               t0=t0, t1=t1)
    report.append(rec)
    print("  %-8s aMAE %.3f p95 %.3f >.1 %.2f%% >.25 %.2f%% | bgF %.5f fgH %.5f | "
          "comp simple %.2f/%.1f/max%.0f decon %.2f/%.1f/max%.0f | "
          "dRGB simple %s decon %s | fgdist min %.3f p1 %.3f"
          % (key, rec["mae_alpha"], rec["p95"], 100 * rec["gt010"], 100 * rec["gt025"],
             rec["bg_false"], rec["fg_holes"], rec["comp_simple_mean"], rec["comp_simple_p95"],
             rec["comp_simple_max"], rec["comp_decon_mean"], rec["comp_decon_p95"],
             rec["comp_decon_max"], np.round(es_rgb, 1), np.round(ed_rgb, 1),
             rec["key_fg_min"], rec["key_fg_p1"]))

best_key = min(report, key=lambda r: r["mae_alpha"] + 2 * r["fg_holes"] + r["comp_simple_mean"] / 255)
print("BEST KEY", best_key["key"])


def save(a, name):
    if a.ndim == 2:
        a = np.dstack([a] * 3)
    if a.shape[2] == 3:
        a = np.dstack([a, np.full(a.shape[:2], 255, dtype=np.float32)])
    a = np.ascontiguousarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    hh, ww, cc = a.shape
    im = imbuf.new((ww, hh), planes=32, buffer_type="BYTE")
    with im.with_buffer(write=True) as b:
        np.frombuffer(b, dtype=np.uint8).reshape(hh, ww, cc)[:] = a
    imbuf.write(im, filepath=os.path.join(BASE, name))
    im.free()


save(np.dstack([a_ref * 255] * 3), "c_alpha_ref.png")
save(comp_ref * 255, "c_comp_ref.png")
for rec in report:
    key = rec["key"]
    I = to_lin(imgs[key]) if lin else imgs[key]
    Kp = to_lin(B[key]) if lin else B[key]
    d = np.sqrt(((I - Kp) ** 2).sum(axis=2)) / np.sqrt(3.0)
    ak = smoothstep(d, rec["t0"], rec["t1"])
    simple = ak[:, :, None] * (to_srgb(imgs[key]) if lin else imgs[key]) + (1 - ak[:, :, None]) * check[:, :, None]
    Fk = (I - (1 - ak[:, :, None]) * Kp) / np.maximum(ak[:, :, None], 1e-3)
    Fk = np.clip(Fk, 0, 1)
    decon = ak[:, :, None] * (to_srgb(Fk) if lin else Fk) + (1 - ak[:, :, None]) * check[:, :, None]
    save(ak * 255, "c_alpha_%s.png" % key)
    save(simple * 255, "c_simple_%s.png" % key)
    save(decon * 255, "c_decon_%s.png" % key)

# choose a crop around the leftmost node's header/text
m = a_ref > 0.8
cols = np.nonzero(m.sum(axis=0) > 20)[0]
rows = np.nonzero(m.sum(axis=1) > 20)[0]
x0 = int(cols.min())
ys = np.nonzero(m[:, x0:x0 + 260].sum(axis=1) > 20)[0]
y1 = int(ys.max())
cx = max(0, min(W - 380, x0 - 20))
cy = max(0, min(H - 300, y1 - 250))
print("crop around leftmost node: x=%d y=%d" % (cx, cy))
save(comp_ref[cy:cy + 300, cx:cx + 380] * 255, "z_ref.png")
for rec in report:
    key = rec["key"]
    I = to_lin(imgs[key]) if lin else imgs[key]
    Kp = to_lin(B[key]) if lin else B[key]
    d = np.sqrt(((I - Kp) ** 2).sum(axis=2)) / np.sqrt(3.0)
    ak = smoothstep(d, rec["t0"], rec["t1"])
    simple = ak[:, :, None] * (to_srgb(imgs[key]) if lin else imgs[key]) + (1 - ak[:, :, None]) * check[:, :, None]
    Fk = (I - (1 - ak[:, :, None]) * Kp) / np.maximum(ak[:, :, None], 1e-3)
    Fk = np.clip(Fk, 0, 1)
    decon = ak[:, :, None] * (to_srgb(Fk) if lin else Fk) + (1 - ak[:, :, None]) * check[:, :, None]
    save(simple[cy:cy + 300, cx:cx + 380] * 255, "z_simple_%s.png" % key)
    save(decon[cy:cy + 300, cx:cx + 380] * 255, "z_decon_%s.png" % key)
    save(np.dstack([ak[cy:cy + 300, cx:cx + 380] * 255] * 3), "z_alpha_%s.png" % key)

with open(os.path.join(BASE, "report2.txt"), "w", encoding="utf-8") as f:
    f.write("model=%s pair=%s crop=%d\n" % ("linear" if lin else "sRGB", "/".join(pair), CROP))
    f.write("edge=%d\n" % int(edge.sum()))
    for rec in report:
        f.write(str(rec) + "\n")
print("DONE")
