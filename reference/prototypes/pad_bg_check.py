import imbuf
import numpy as np
import os

BASE = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_dpi3")


def load(name):
    img = imbuf.load(os.path.join(BASE, name))
    w, h = img.size
    with img.with_buffer() as b:
        a = np.frombuffer(b, dtype=np.uint8).reshape(h, w, 4).copy()
    img.free()
    return a


def save(a, name):
    a = np.ascontiguousarray(a)
    hh, ww, cc = a.shape
    im = imbuf.new((ww, hh), planes=32, buffer_type="BYTE")
    with im.with_buffer(write=True) as b:
        np.frombuffer(b, dtype=np.uint8).reshape(hh, ww, cc)[:] = a
    imbuf.write(im, filepath=os.path.join(BASE, name))
    im.free()


a = load("final_big_d100_p40_v1.png")
h, w = a.shape[:2]
pad = 40
g = a[:, :, :3].astype(np.float32).mean(axis=2)

print("image", w, h)
# orientation-correct corner crops (PNG top-left = array high rows)
save(a[-220:, :320][::-1].copy(), "corner_tl_1to1.png")
save(a[:220, :320].copy(), "corner_bl_1to1.png")
save(a[-220:, -320:][::-1].copy(), "corner_tr_1to1.png")

# background stats in the four padding bands vs a known-empty interior strip
top = g[-pad:, pad:-pad]
bot = g[:pad, pad:-pad]
left = g[pad:-pad, :pad]
right = g[pad:-pad, -pad:]

# interior empty strip: between content rows, pick rows where overall row std is low
inner = g[1300:1340, 1500:1900]   # between chains, few wires expected
print("padding stats:")
for name, b in (("top", top), ("bottom", bot), ("left", left), ("right", right), ("interior", inner)):
    print("  %-8s mean %.3f std %.3f min %.0f max %.0f" % (name, b.mean(), b.std(), b.min(), b.max()))

print("edge purity (no frame/scrollbar):")
for name, v in (("row0(bottom)", g[0]), ("rowN(top)", g[-1]),
                ("col0(left)", g[:, 0]), ("colN(right)", g[:, -1])):
    print("  %-12s mean %.3f max %.0f p99 %.0f" % (name, v.mean(), v.max(), np.percentile(v, 99)))

# grid dots: local maxima above local median, count and spacing in top band
def dots(b):
    med = np.median(b)
    m = (b > med + 0.8) & (b < med + 4)
    # count 2x2 local maxima
    from numpy.lib.stride_tricks import sliding_window_view
    if b.shape[0] >= 3 and b.shape[1] >= 3:
        win = sliding_window_view(b, (3, 3))
        c = win[1:-1, 1:-1]
        peaks = (c >= win.max(axis=(2, 3)) - 1e-6) & (c > med + 0.8) & (c < med + 4)
        return int(peaks.sum()), med
    return 0, med


n, med = dots(top)
print("top band: median %.1f, local maxima %d" % (med, n))
n2, med2 = dots(inner)
print("interior: median %.1f, local maxima %d" % (med2, n2))
