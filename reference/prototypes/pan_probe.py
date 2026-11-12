import bpy
import sys
import traceback

state = {"tick": 0}


def log(*a):
    print("[PAN]", *a)
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

        def pan(dx, dy):
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.pan(deltax=int(dx), deltay=int(dy))
            redraw()

        def pos():
            # screen position (window px, bottom-left origin) of model (0,0)
            return v2d.view_to_region(0.0, 0.0, clip=False)

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        for amt in (100, 500, 1000, 1500, 2000, 3000, -1000, -2500):
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            redraw()
            p0 = pos()
            pan(amt, 0)
            p1 = pos()
            pan(0, amt)
            p2 = pos()
            log("request dx=%5d  actual dx=%7.1f  upp=%.5f | request dy=%5d actual dy=%7.1f"
                % (amt, p1[0] - p0[0], upp(), amt, p2[1] - p1[1]))

        # zoomed in (0.43) and out (2.5) linearity
        for ztag in ("in", "out"):
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.reset()
            redraw()
            for _ in range(6):
                with bpy.context.temp_override(window=win, area=area, region=region):
                    (bpy.ops.view2d.zoom_in if ztag == "in" else bpy.ops.view2d.zoom_out)()
            redraw()
            p0 = pos()
            pan(1000, 700)
            p1 = pos()
            log("zoom %s upp=%.4f request (1000,700) actual (%.1f,%.1f)"
                % (ztag, upp(), p1[0] - p0[0], p1[1] - p0[1]))

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
