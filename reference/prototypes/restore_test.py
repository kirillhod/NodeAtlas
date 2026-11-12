import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_restore")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "success"


def log(*a):
    print("[RT]", *a)
    sys.stdout.flush()


def area_sig(win):
    return sorted((a.type, a.x, a.y, a.width, a.height) for a in win.screen.areas)


def find_node_area(win):
    for a in win.screen.areas:
        if a.type == "NODE_EDITOR":
            return a
    return None


def node_snapshot(win):
    a = find_node_area(win)
    if a is None:
        return None
    sp = a.spaces.active
    r = next((x for x in a.regions if x.type == "WINDOW"), None)
    if r is None:
        return None
    v2d = r.view2d
    upp = (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0
    center = v2d.region_to_view(r.width / 2, r.height / 2)
    tree = sp.node_tree
    return {
        "tree_type": sp.tree_type,
        "tree": tree.name if tree else None,
        "edit_tree": sp.edit_tree.name if sp.edit_tree else None,
        "pin": sp.pin,
        "region": (r.x, r.y, r.width, r.height),
        "upp": upp,
        "center": center,
        "sel": sorted(n.name for n in tree.nodes if n.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "header": sp.show_region_header,
        "ui": sp.show_region_ui,
        "toolbar": sp.show_region_toolbar,
        "gizmo": sp.show_gizmo,
        "context_path": sp.overlay.show_context_path,
        "backdrop": sp.show_backdrop,
    }


def full_snapshot(win):
    prefs = bpy.context.preferences
    return {
        "window": (win.width, win.height),
        "areas": area_sig(win),
        "node": node_snapshot(win),
        "ui_scale": prefs.view.ui_scale,
        "smooth": prefs.view.smooth_view,
    }


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
            state.update(win=win, area=area, orig_type=area.type)
            return 0.5

        win = state["win"]
        area = state["area"]
        orig_type = state["orig_type"]
        prefs = bpy.context.preferences

        # --- setup a node editor in the chosen area ---
        pre_layout = full_snapshot(win)
        area.type = "NODE_EDITOR"
        if MODE in ("success", "fail"):
            state["orig_type"] = "NODE_EDITOR"
            orig_type = "NODE_EDITOR"
        sp = area.spaces.active
        sp.tree_type = "ShaderNodeTree"
        sp.pin = True
        sp.node_tree = bpy.data.materials["M_Small"].node_tree
        region = next(r for r in area.regions if r.type == "WINDOW")

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        redraw()
        pre = full_snapshot(win)
        state["pre_tree"] = sp.node_tree
        log("mode=%s orig area type=%s pre areas=%s node=%s"
            % (MODE, orig_type, pre["areas"], "yes" if pre["node"] else "no"))

        # pre screenshot (only when the original area is a node editor)
        pre_img = None
        if orig_type == "NODE_EDITOR" and pre["node"]:
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + region.width, region.y + region.height)))
            pre_img = np.frombuffer(mv, dtype=np.uint8).reshape(region.height, region.width, 4).copy()
            save(pre_img, "pre.png")

        # --- simulate export mutations ---
        mutated = {"done": False}
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.screen.screen_full_area(use_hide_panels=True)
            with bpy.context.temp_override(window=win):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            win = bpy.context.window_manager.windows[0]
            area = find_node_area(win)
            if area is None:
                raise RuntimeError("no node area after maximize")
            sp = area.spaces.active
            region = next(r for r in area.regions if r.type == "WINDOW")
            sp.show_region_header = False
            sp.show_region_ui = False
            sp.show_region_toolbar = False
            sp.show_gizmo = False
            sp.overlay.show_context_path = False
            sp.show_backdrop = False
            sp.pin = False
            sp.tree_type = "ShaderNodeTree"
            sp.pin = True
            sp.node_tree = bpy.data.materials["M_Uniq"].node_tree
            prefs.view.ui_scale = 1.5
            redraw()
            for n in sp.node_tree.nodes:
                n.select = False
            sp.node_tree.nodes.active = None
            with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                bpy.ops.node.view_all()
            redraw()
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view2d.pan(deltax=321, deltay=-123)
            redraw()
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + region.width, region.y + region.height)))
            arr = np.frombuffer(mv, dtype=np.uint8).reshape(region.height, region.width, 4)
            log("mutation done: area %dx%d region %dx%d upp=%.4f"
                % (area.width, area.height, region.width, region.height,
                   (region.view2d.region_to_view(100, 0)[0] - region.view2d.region_to_view(0, 0)[0]) / 100.0))
            mutated["done"] = True
            if MODE == "fail":
                raise RuntimeError("induced failure after mutations")
        except Exception:
            log("caught during export:")
            traceback.print_exc()
        finally:
            # --- restore everything ---
            win = bpy.context.window_manager.windows[0]
            area = find_node_area(win)
            if area is not None:
                sp = area.spaces.active
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                # tree & pin
                sp.pin = False
                sp.tree_type = pre["node"]["tree_type"]
                sp.pin = pre["node"]["pin"]
                tree = state.get("pre_tree")
                if tree is not None:
                    sp.node_tree = tree
                # regions/gizmo/context/backdrop
                sp.show_region_header = pre["node"]["header"]
                sp.show_region_ui = pre["node"]["ui"]
                sp.show_region_toolbar = pre["node"]["toolbar"]
                sp.show_gizmo = pre["node"]["gizmo"]
                sp.overlay.show_context_path = pre["node"]["context_path"]
                sp.show_backdrop = pre["node"]["backdrop"]
                # selection/active
                if tree is not None:
                    for n in tree.nodes:
                        n.select = n.name in pre["node"]["sel"]
                    act = tree.nodes.get(pre["node"]["active"]) if pre["node"]["active"] else None
                    try:
                        tree.nodes.active = act
                    except Exception:
                        pass
                # ui scale / smooth
                prefs.view.ui_scale = pre["ui_scale"]
                prefs.view.smooth_view = pre["smooth"]
                redraw()
                # leave maximization first: the restored area has a different
                # region size, so the view must be restored on the final region
                with bpy.context.temp_override(window=win, area=area, region=region):
                    bpy.ops.screen.screen_full_area(use_hide_panels=True)
                with bpy.context.temp_override(window=win):
                    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
                win = bpy.context.window_manager.windows[0]
                area = find_node_area(win)
                if area is None:
                    area = max(win.screen.areas, key=lambda a: a.width * a.height)
                sp = area.spaces.active
                region = next(r for r in area.regions if r.type == "WINDOW")
                redraw()
                # restore view: zoom + center on the final region
                v2d = region.view2d
                tw, th = region.width, region.height

                def upp():
                    return (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0

                target = pre["node"]["upp"]
                with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                    bpy.ops.node.view_all()
                redraw()
                for it in range(60):
                    u = upp()
                    r = u / target
                    if abs(r - 1.0) < 0.002:
                        break
                    if r > 1.0:
                        f = target / u
                        if 0.46 <= f < 1.0:
                            rw = int(tw * f)
                            rh = int(th * f)
                            with bpy.context.temp_override(window=win, area=area, region=region):
                                bpy.ops.view2d.zoom_border(
                                    xmin=int(tw / 2 - rw / 2), xmax=int(tw / 2 + rw / 2),
                                    ymin=int(th / 2 - rh / 2), ymax=int(th / 2 + rh / 2),
                                    wait_for_input=False)
                        else:
                            with bpy.context.temp_override(window=win, area=area, region=region):
                                bpy.ops.view2d.zoom_in()
                    else:
                        with bpy.context.temp_override(window=win, area=area, region=region):
                            bpy.ops.view2d.zoom_out()
                    redraw()
                cx, cy = pre["node"]["center"]
                for _ in range(8):
                    px, py = v2d.view_to_region(cx, cy, clip=False)
                    dx = int(round(px - tw / 2))
                    dy = int(round(py - th / 2))
                    if dx == 0 and dy == 0:
                        break
                    with bpy.context.temp_override(window=win, area=area, region=region):
                        bpy.ops.view2d.pan(deltax=dx, deltay=dy)
                    redraw()
                if orig_type != "NODE_EDITOR":
                    area.type = orig_type
                with bpy.context.temp_override(window=win):
                    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        post = full_snapshot(win)
        log("post areas=%s node=%s" % (post["areas"], "yes" if post["node"] else "no"))

        # --- compare ---
        def cmp(tag, a, b, tol=1e-6):
            ok = a == b
            log("  %-18s %s  pre=%r post=%r" % (tag, "OK" if ok else "DIFF", a, b))
            return ok

        ok_all = True
        ref = pre_layout if MODE == "areatype" else pre
        ok_all &= cmp("areas", ref["areas"], post["areas"])
        ok_all &= cmp("window", ref["window"], post["window"])
        ok_all &= cmp("ui_scale", round(ref["ui_scale"], 4), round(post["ui_scale"], 4))
        ok_all &= cmp("smooth", ref["smooth"], post["smooth"])
        if MODE != "areatype" and pre["node"] and post["node"]:
            for key in ("tree_type", "tree", "edit_tree", "pin", "region", "sel", "active",
                        "header", "ui", "toolbar", "gizmo", "context_path", "backdrop"):
                ok_all &= cmp(key, pre["node"][key], post["node"][key])
            du = abs(pre["node"]["upp"] - post["node"]["upp"])
            cx, cy = pre["node"]["center"]
            px, py = post["node"]["center"]
            log("  %-18s pre=(%.2f,%.2f) post=(%.2f,%.2f)  upp diff %.6f"
                % ("view", cx, cy, px, py, du))
        if pre_img is not None and post["node"] and orig_type == "NODE_EDITOR":
            area = find_node_area(win)
            region = next(r for r in area.regions if r.type == "WINDOW")
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + region.width, region.y + region.height)))
            post_img = np.frombuffer(mv, dtype=np.uint8).reshape(region.height, region.width, 4).copy()
            save(post_img, "post.png")
            if pre_img.shape == post_img.shape:
                d = np.abs(pre_img[:, :, :3].astype(np.int16) - post_img[:, :, :3].astype(np.int16))
                log("  %-18s mean %.6f max %d pixels>0 %d"
                    % ("pixels", float(d.mean()), int(d.max()), int((d.max(axis=2) > 0).sum())))
            else:
                log("  pixels: shape mismatch", pre_img.shape, post_img.shape)

        log("RESULT", "PASS" if ok_all else "FAIL", "mode", MODE)
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    return None


log("start")
bpy.app.timers.register(run, first_interval=0.5)
