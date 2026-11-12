import bpy
import os
import sys
import traceback

state = {"tick": 0}


def log(*a):
    print("[Z2]", *a)
    sys.stdout.flush()


def run():
    try:
        state["tick"] += 1
        if state["tick"] == 1:
            bpy.context.preferences.view.smooth_view = 0
            win = bpy.context.window_manager.windows[0]
            area = max(win.screen.areas, key=lambda a: a.width * a.height)
            area.type = "NODE_EDITOR"
            sp = area.spaces.active
            sp.show_region_ui = False
            sp.show_region_toolbar = False
            sp.show_gizmo = False
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

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def upp():
            redraw()
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        def reset():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            redraw()

        def op(name, **kw):
            try:
                with bpy.context.temp_override(window=win, area=area, region=region):
                    getattr(bpy.ops.view2d, name)(**kw)
            except Exception as e:
                return "FAIL %s" % e
            return ""

        def case(tag, name, **kw):
            reset()
            u0 = upp()
            err = op(name, **kw)
            u1 = upp()
            log("%-34s upp %.5f -> %.5f (x%.3f) %s" % (tag, u0, u1, u1 / u0, err))

        case("zoom_in() defaults", "zoom_in")
        case("zoom_out() defaults", "zoom_out")
        case("zoom_in(1.1)", "zoom_in", zoomfacx=1.1, zoomfacy=1.1)
        case("zoom_in(1.5)", "zoom_in", zoomfacx=1.5, zoomfacy=1.5)
        case("zoom_out(1.1)", "zoom_out", zoomfacx=1.1, zoomfacy=1.1)
        case("zoom_out(1.5)", "zoom_out", zoomfacx=1.5, zoomfacy=1.5)
        case("zoom(dy=10)", "zoom", deltax=0.0, deltay=10.0, use_cursor_init=False)
        case("zoom(dy=-10)", "zoom", deltax=0.0, deltay=-10.0, use_cursor_init=False)
        case("zoom(dy=1)", "zoom", deltax=0.0, deltay=1.0, use_cursor_init=False)
        case("zoom(dy=-1)", "zoom", deltax=0.0, deltay=-1.0, use_cursor_init=False)

        for r in (0.9, 0.7, 0.5, 0.45, 0.44, 0.43, 0.4, 0.3):
            reset()
            u0 = upp()
            op("zoom_border", xmin=int(tw / 2 - tw * r / 2), xmax=int(tw / 2 + tw * r / 2),
               ymin=int(th / 2 - th * r / 2), ymax=int(th / 2 + th * r / 2), wait_for_input=False)
            u1 = upp()
            log("zoom_border r=%.2f  upp %.5f -> %.5f (x%.3f)" % (r, u0, u1, u1 / u0))

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
