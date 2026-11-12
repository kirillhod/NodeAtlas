import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_maximize")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}


def log(*a):
    print("[MX]", *a)
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
            state.update(win=win, area=area, region=region, space=sp)
            log("before: win %dx%d area %dx%d region %dx%d x=%d y=%d"
                % (win.width, win.height, area.width, area.height,
                   region.width, region.height, region.x, region.y))
            return 0.5

        win = state["win"]
        area = state["area"]
        region = state["region"]

        # maximize the hovered area (Ctrl+Space equivalent)
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
        with bpy.context.temp_override(window=win):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        areas = list(win.screen.areas)
        log("after maximize: %d areas" % len(areas))
        area = max(areas, key=lambda a: a.width * a.height)
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        sp = area.spaces.active
        log("area type %s size %dx%d, region %s size %s x=%s y=%s, window %dx%d"
            % (area.type, area.width, area.height,
               region.type if region else None,
               (region.width, region.height) if region else None,
               region.x if region else None, region.y if region else None,
               win.width, win.height))
        if region is None:
            raise RuntimeError("no WINDOW region after maximize")
        v2d = region.view2d
        tw, th = region.width, region.height

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def upp():
            return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

        def prime():
            with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                bpy.ops.node.view_all()
            redraw()

        redraw()
        log("after maximize: upp=%.5f nodesdims=%s"
            % (upp(), [(n.label or n.name, round(n.dimensions.x), round(n.dimensions.y))
                       for n in bpy.data.materials["M_Small"].node_tree.nodes]))
        mv = win.screenshot(region=((region.x, region.y), (region.x + tw, region.y + th)))
        arr = np.frombuffer(mv, dtype=np.uint8)
        log("screenshot size %d = %dx%dx4? %s" % (arr.size, tw, th, arr.size == tw * th * 4))

        # zoom limit with maximize
        prime()
        prev = upp()
        for k in range(40):
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.zoom_in()
            redraw()
            u = upp()
            if abs(u - prev) < 1e-5:
                break
            prev = u
        eff = bpy.context.preferences.system.ui_scale * bpy.context.preferences.view.ui_scale
        log("maximize zoom limit upp=%.5f eff=%.3f D_max=%.3f" % (prev, eff, eff / prev))

        # restore (toggle)
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
        with bpy.context.temp_override(window=win):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        areas = list(win.screen.areas)
        area = max(areas, key=lambda a: a.width * a.height)
        region = next(r for r in area.regions if r.type == "WINDOW")
        log("restored: %d areas, area %dx%d region %dx%d"
            % (len(areas), area.width, area.height, region.width, region.height))

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
