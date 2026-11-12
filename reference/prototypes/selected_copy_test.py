import bpy
import imbuf
import numpy as np
import os
import sys
import traceback

OUT = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "nodeatlas_ref", "out_selected")
os.makedirs(OUT, exist_ok=True)
state = {"tick": 0}


def log(*a):
    print("[SC]", *a)
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
            sp.show_region_ui = False
            sp.show_region_toolbar = False
            sp.show_region_header = False
            sp.show_gizmo = False
            sp.overlay.show_context_path = False
            state.update(win=win, area=area, space=sp, nt=sp.node_tree)
            return 0.5

        win, area, sp, nt = state["win"], state["area"], state["space"], state["nt"]
        region = next(r for r in area.regions if r.type == "WINDOW")
        tw, th = region.width, region.height

        def redraw():
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        def shot(name):
            redraw()
            mv = win.screenshot(region=((region.x, region.y),
                                        (region.x + tw, region.y + th)))
            arr = np.frombuffer(mv, dtype=np.uint8).reshape(th, tw, 4).copy()
            save(arr, name)
            log("shot", name, arr.shape)

        def case(tag, labels):
            # duplicate and filter
            tmp = nt.copy()
            by_label = {n.label: n for n in tmp.nodes}
            keep = set(labels)
            # if a frame is selected, keep its descendants
            for n in list(tmp.nodes):
                if n.label in keep and n.type == "FRAME":
                    for m in tmp.nodes:
                        p = m.parent
                        while p is not None:
                            if p.label == n.label:
                                keep.add(m.label)
                                break
                            p = p.parent
            log("%s: original selected %s -> keep %s" % (tag, labels, sorted(keep)))
            # unparent kept nodes whose parent is not kept, preserving absolute position
            for n in list(tmp.nodes):
                if n.label in keep and n.parent is not None and n.parent.label not in keep:
                    abs_loc = n.location_absolute
                    n.parent = None
                    n.location = abs_loc
            # remove the rest
            for n in list(tmp.nodes):
                if n.label not in keep:
                    tmp.nodes.remove(n)
            # report
            log("%s: tmp nodes %s" % (tag, [(n.label, tuple(n.location_absolute)) for n in tmp.nodes]))
            log("%s: tmp links %s" % (tag, [(l.from_node.label, l.to_node.label) for l in tmp.links]))
            sp.pin = True
            sp.node_tree = tmp
            redraw()
            log("%s: editor tree %s, dims %d/%d" % (tag,
                sp.edit_tree.name if sp.edit_tree else None,
                sum(1 for n in tmp.nodes if n.dimensions.x > 0), len(tmp.nodes)))
            redraw()
            with bpy.context.temp_override(window=win, area=area, region=region, space_data=sp):
                bpy.ops.node.view_all()
            redraw()
            shot("copy_%s.png" % tag)
            # restore original, remove temp
            sp.node_tree = nt
            try:
                bpy.data.batch_remove([tmp])
                log("%s: tmp removed" % tag)
            except Exception as e:
                log("%s: tmp remove FAIL %s %s" % (tag, type(e).__name__, e))
            redraw()
            log("%s: editor tree restored %s" % (tag, sp.node_tree.name if sp.node_tree else None))

        case("N1_R1", ["N1", "R1"])
        case("F1_frame", ["F1"])
        case("C3_child", ["C3_selected_in_F2"])
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
