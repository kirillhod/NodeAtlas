import bpy
import sys
import traceback

state = {"tick": 0}


def log(*a):
    print("[ZL]", *a)
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
            sp.tree_type = "ShaderNodeTree"
            region = next(r for r in area.regions if r.type == "WINDOW")
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            state.update(win=win, area=area, region=region)
            return 0.5

        win, area, region = state["win"], state["area"], state["region"]
        v2d = region.view2d

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        def op(name):
            with bpy.context.temp_override(window=win, area=area, region=region):
                getattr(bpy.ops.view2d, name)()
            redraw()

        def reset():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            redraw()

        reset()
        prev = upp()
        log("reset upp %.5f" % prev)
        for k in range(1, 81):
            op("zoom_in")
            u = upp()
            if abs(u - prev) < 1e-5:
                log("zoom_in limit at call %d: upp %.5f" % (k, u))
                break
            prev = u
        log("max magnification upp=%.5f -> max D=%.3f (ui_scale=%.3f)"
            % (prev, bpy.context.preferences.system.ui_scale / prev,
               bpy.context.preferences.system.ui_scale))

        reset()
        prev = upp()
        for k in range(1, 81):
            op("zoom_out")
            u = upp()
            if abs(u - prev) < 1e-5:
                log("zoom_out limit at call %d: upp %.5f" % (k, u))
                break
            prev = u
        log("max zoom-out upp=%.5f -> min D=%.3f"
            % (prev, bpy.context.preferences.system.ui_scale / prev))

        log("DONE")
        sys.stdout.flush()
        import os
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        import os
        os._exit(1)
    return None


log("start")
bpy.app.timers.register(run, first_interval=0.5)
