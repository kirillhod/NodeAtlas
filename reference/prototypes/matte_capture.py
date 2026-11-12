import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_matte")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}

BACKGROUNDS = {
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
    "magenta": (1.0, 0.0, 1.0),
    "green": (0.0, 1.0, 0.0),
    "cyan": (0.0, 1.0, 1.0),
    "gray": (0.5, 0.5, 0.5),
}


def log(*a):
    print("[MT]", *a)
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
            sp.pin = True
            sp.node_tree = bpy.data.materials["M_Matte"].node_tree
            sp.show_region_ui = False
            sp.show_region_toolbar = False
            sp.show_region_header = False
            sp.show_gizmo = False
            sp.overlay.show_context_path = False
            sp.show_backdrop = False
            theme = bpy.context.preferences.themes[0]
            ne = theme.node_editor
            state.update(win=win, area=area, space=sp, theme=theme, ne=ne,
                         old_back=tuple(ne.space.back), old_grid=ne.grid_levels)
            ne.grid_levels = 0
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            return 0.5

        win, area, sp, ne = state["win"], state["area"], state["space"], state["ne"]
        region = next(r for r in area.regions if r.type == "WINDOW")
        v2d = region.view2d
        tw, th = region.width, region.height

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        for name, rgb in BACKGROUNDS.items():
            ne.space.back = rgb
            ne.grid_levels = 0
            with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                bpy.ops.node.view_all()
            redraw()
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            arr = np.frombuffer(mv, dtype=np.uint8).reshape(th, tw, 4).copy()
            save(arr, "bg_%s.png" % name)
            cx, cy = v2d.region_to_view(tw / 2, th / 2)
            log("%-8s bg=%s sample=%s upp=%.6f center=(%.4f,%.4f)"
                % (name, rgb, arr[5, 5, :3], upp(), cx, cy))

        ne.space.back = state["old_back"]
        ne.grid_levels = state["old_grid"]
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
