import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_undo")
os.makedirs(OUT, exist_ok=True)
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "control"
state = {"tick": 0}


def log(*a):
    print("[UC]", *a)
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
            sp.node_tree = bpy.data.materials["M_Sel"].node_tree
            state.update(win=win, area=area, space=sp)
            return 0.5

        win, area, sp = state["win"], state["area"], state["space"]
        region = next(r for r in area.regions if r.type == "WINDOW")
        mat = bpy.data.materials["M_Sel"]
        nt = mat.node_tree

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
            bpy.ops.node.add_node(type="ShaderNodeMath", use_transform=False)
        redraw()
        sentinel = nt.nodes.active.name
        with bpy.context.temp_override(window=win, area=area, region=region):
            up = bpy.ops.ed.undo_push(message="USER_" + MODE)
        log("%s: sentinel %s, nodes %d, undo_push %s, mat users %d"
            % (MODE, sentinel, len(nt.nodes), up, mat.users))
        pre_area = sorted((a.type, a.x, a.y, a.width, a.height) for a in win.screen.areas)
        if MODE != "control":
            pre_tree = sp.node_tree
            tmp = None
            failure = None
            try:
                if MODE in ("nocopy", "copy"):
                    with bpy.context.temp_override(window=win, area=area, region=region):
                        bpy.ops.screen.screen_full_area(use_hide_panels=True)
                    with bpy.context.temp_override(window=win):
                        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
                    area = max(win.screen.areas, key=lambda a: a.width * a.height)
                    sp = area.spaces.active
                    region = next(r for r in area.regions if r.type == "WINDOW")
                    sp.show_region_ui = False
                    sp.show_region_toolbar = False
                    sp.show_region_header = False
                    sp.show_gizmo = False
                    sp.overlay.show_context_path = False
                    sp.show_backdrop = False
                    redraw()
                    if MODE == "copy":
                        tmp = nt.copy()
                        for n in list(tmp.nodes):
                            if n.label not in ("N1", "R1"):
                                tmp.nodes.remove(n)
                        sp.node_tree = tmp
                        redraw()
                        if MODE == "copyfail":
                            raise RuntimeError("induced failure after temp tree assignment")
                    with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                        bpy.ops.node.view_all()
                    with bpy.context.temp_override(window=win, area=area, region=region):
                        bpy.ops.view2d.pan(deltax=321, deltay=-123)
                    redraw()
                    mv = win.screenshot(region=((region.x, region.y),
                                                (region.x + region.width, region.y + region.height)))
                    arr = np.frombuffer(mv, dtype=np.uint8).reshape(region.height, region.width, 4).copy()
                    save(arr, "case_%s.png" % MODE)
            except Exception as e:
                failure = e
                log("%s: caught failure %s: %s" % (MODE, type(e).__name__, e))
            finally:
                sp.node_tree = pre_tree
                redraw()
                if tmp is not None:
                    try:
                        bpy.data.batch_remove([tmp])
                    except Exception as e:
                        log("%s: cleanup fail %s" % (MODE, e))
                # restore region visibility BEFORE leaving maximize; with hidden
                # regions an exception path can make screen_full_area fail
                sp.show_region_ui = True
                sp.show_region_toolbar = False
                sp.show_region_header = True
                sp.show_gizmo = True
                sp.overlay.show_context_path = True
                redraw()
                area = max(win.screen.areas, key=lambda a: a.width * a.height)
                sp = area.spaces.active
                region = next(r for r in area.regions if r.type == "WINDOW")
                with bpy.context.temp_override(window=win, area=area, region=region):
                    rleave = bpy.ops.screen.screen_full_area(use_hide_panels=True)
                with bpy.context.temp_override(window=win):
                    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
                log("%s: finally leave %s, areas now %d"
                    % (MODE, rleave, len(win.screen.areas)))
                if len(win.screen.areas) == 1:
                    fresh = win.screen.areas[0]
                    fresh_region = next(r for r in fresh.regions if r.type == "WINDOW")
                    with bpy.context.temp_override(window=win, area=fresh, region=fresh_region):
                        rleave2 = bpy.ops.screen.screen_full_area(use_hide_panels=True)
                    with bpy.context.temp_override(window=win):
                        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
                    log("%s: leave retry %s, areas now %d"
                        % (MODE, rleave2, len(win.screen.areas)))
                area = max(win.screen.areas, key=lambda a: a.width * a.height)
                sp = area.spaces.active
                region = next(r for r in area.regions if r.type == "WINDOW")
                redraw()

        # inspect before undo
        mat = bpy.data.materials.get("M_Sel")
        nt = mat.node_tree if mat else None
        cur_area = sorted((a.type, a.x, a.y, a.width, a.height) for a in win.screen.areas)
        log("%s: before undo tree %s, sentinel %s, nodes %s, areas_same %s"
            % (MODE, nt.name if nt else None,
               (sentinel in nt.nodes) if nt else None,
               len(nt.nodes) if nt else None,
               cur_area == pre_area))
        if cur_area != pre_area:
            log("%s: pre_area %s" % (MODE, pre_area))
            log("%s: cur_area %s" % (MODE, cur_area))

        with bpy.context.temp_override(window=win, area=area, region=region):
            res = bpy.ops.ed.undo()
        redraw()
        mat = bpy.data.materials.get("M_Sel")
        nt = mat.node_tree if mat else None
        exists = (sentinel in nt.nodes) if nt else None
        log("%s: undo %s -> tree %s, sentinel exists %s, nodes %s"
            % (MODE, res, nt.name if nt else None, exists,
               len(nt.nodes) if nt else None))
        with bpy.context.temp_override(window=win, area=area, region=region):
            rres = bpy.ops.ed.redo()
        redraw()
        mat = bpy.data.materials.get("M_Sel")
        nt = mat.node_tree if mat else None
        exists2 = (sentinel in nt.nodes) if nt else None
        log("%s: redo %s -> sentinel exists %s, nodes %s"
            % (MODE, rres, exists2, len(nt.nodes) if nt else None))
        log("%s: RESULT %s" % (MODE, "PASS" if (exists is False and exists2 is True) else "FAIL"))
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    return None


log("start")
bpy.app.timers.register(run, first_interval=0.5)
