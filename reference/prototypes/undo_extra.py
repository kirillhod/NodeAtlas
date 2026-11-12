import bpy
import os
import sys
import traceback

MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "uiscale"
state = {"tick": 0}


def log(*a):
    print("[UE]", *a)
    sys.stdout.flush()


def run():
    try:
        state["tick"] += 1
        if state["tick"] == 1:
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
            bpy.ops.ed.undo_push(message="USER_" + MODE)
        log("%s: sentinel %s, nodes %d" % (MODE, sentinel, len(nt.nodes)))

        if MODE == "uiscale":
            old = bpy.context.preferences.view.ui_scale
            bpy.context.preferences.view.ui_scale = 1.5
            redraw()
            bpy.context.preferences.view.ui_scale = old
            redraw()
            log("%s: ui_scale changed to 1.5 and restored to %s" % (MODE, old))
        elif MODE == "theme":
            theme = bpy.context.preferences.themes[0].node_editor
            old = tuple(theme.space.back)
            theme.space.back = (0.0, 0.0, 0.0)
            redraw()
            theme.space.back = (1.0, 1.0, 1.0)
            redraw()
            theme.space.back = old
            redraw()
            log("%s: theme background changed and restored to %s" % (MODE, old))
        elif MODE == "selection":
            sel = [(n.name, n.select) for n in nt.nodes]
            for n in nt.nodes:
                n.select = False
            nt.nodes.active = None
            redraw()
            for n in nt.nodes:
                n.select = dict(sel)[n.name]
            redraw()
            log("%s: selection cleared and restored" % MODE)

        with bpy.context.temp_override(window=win, area=area, region=region):
            res = bpy.ops.ed.undo()
        redraw()
        mat = bpy.data.materials.get("M_Sel")
        nt = mat.node_tree if mat else None
        exists = (sentinel in nt.nodes) if nt else None
        with bpy.context.temp_override(window=win, area=area, region=region):
            rres = bpy.ops.ed.redo()
        redraw()
        mat = bpy.data.materials.get("M_Sel")
        nt = mat.node_tree if mat else None
        exists2 = (sentinel in nt.nodes) if nt else None
        log("%s: undo %s exists %s, redo %s exists %s" % (MODE, res, exists, rres, exists2))
        log("%s: RESULT %s" % (MODE, "PASS" if exists is False and exists2 is True else "FAIL"))
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    return None


log("start")
bpy.app.timers.register(run, first_interval=0.5)
