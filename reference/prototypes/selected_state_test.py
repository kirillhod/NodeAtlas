import bpy
import os
import sys
import traceback

state = {"tick": 0}


def log(*a):
    print("[SS]", *a)
    sys.stdout.flush()


def snapshot(nt):
    return {
        "tree": nt.name,
        "users": nt.users,
        "fake": nt.use_fake_user,
        "nodes": sorted(
            (n.label, n.name, tuple(round(v, 4) for v in n.location_absolute),
             tuple(round(v, 4) for v in n.dimensions),
             n.parent.label if n.parent else None, n.select, n.hide)
            for n in nt.nodes),
        "links": sorted((l.from_node.label, l.from_socket.name,
                         l.to_node.label, l.to_socket.name) for l in nt.links),
    }


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
            sp.show_region_ui = False
            sp.show_region_toolbar = False
            sp.show_region_header = False
            sp.show_gizmo = False
            sp.overlay.show_context_path = False
            state.update(win=win, area=area, space=sp, nt=sp.node_tree)
            return 0.5

        win, area, sp, nt = state["win"], state["area"], state["space"], state["nt"]
        region = next(r for r in area.regions if r.type == "WINDOW")

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
            bpy.ops.node.view_all()
        redraw()
        before = snapshot(nt)
        log("before: tree %s users %d nodes %d links %d"
            % (before["tree"], before["users"], len(before["nodes"]), len(before["links"])))

        def case(tag, labels):
            tmp = nt.copy()
            by_label = {n.label: n for n in tmp.nodes}
            keep = set(labels)
            for n in list(tmp.nodes):
                if n.label in keep and n.type == "FRAME":
                    for m in tmp.nodes:
                        p = m.parent
                        while p is not None:
                            if p.label == n.label:
                                keep.add(m.label)
                                break
                            p = p.parent
            for n in list(tmp.nodes):
                if n.label in keep and n.parent is not None and n.parent.label not in keep:
                    loc = n.location_absolute
                    n.parent = None
                    n.location = loc
            for n in list(tmp.nodes):
                if n.label not in keep:
                    tmp.nodes.remove(n)
            log("%s: keep %s -> tmp nodes %s links %s"
                % (tag, sorted(keep), [n.label for n in tmp.nodes],
                   [(l.from_node.label, l.to_node.label) for l in tmp.links]))
            sp.node_tree = tmp
            redraw()
            log("%s: editor %s dims %d/%d"
                % (tag, sp.edit_tree.name if sp.edit_tree else None,
                   sum(1 for n in tmp.nodes if n.dimensions.x > 0), len(tmp.nodes)))
            sp.node_tree = nt
            redraw()
            try:
                bpy.data.batch_remove([tmp])
            except Exception as e:
                log("%s: cleanup FAIL %s" % (tag, e))
            after = snapshot(nt)
            ok = before == after
            log("%s: restore %s (tree %s, nodes %d, links %d)"
                % (tag, "OK" if ok else "DIFF", after["tree"],
                   len(after["nodes"]), len(after["links"])))
            if not ok:
                for k in before:
                    if before[k] != after[k]:
                        log("  DIFF", k)
                        log("    before", before[k])
                        log("    after ", after[k])
            return ok

        all_ok = True
        all_ok &= case("N1_R1", ["N1", "R1"])
        all_ok &= case("F1_frame", ["F1"])
        all_ok &= case("C3_child", ["C3_selected_in_F2"])
        log("RESULT", "PASS" if all_ok else "FAIL")
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
