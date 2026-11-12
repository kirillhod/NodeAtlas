# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only output directory GUI test.

The destination is locked with a real ACL deny entry (``icacls``) so the
preflight must reject it before any capture work starts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = tempfile.mkdtemp(prefix="nodeatlas_readonly_")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "scene_both.blend")
LOCKED = os.path.join(OUT, "locked")
OUTPUT = os.path.join(LOCKED, "readonly.png")
state = {"ticks": 0}


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    if state.get("user"):
        try:
            unlock_directory(state["user"])
        except Exception:
            pass
    os._exit(1)


def run_icacls(*args):
    return subprocess.run(["icacls", *args], capture_output=True)


def node_area():
    window = bpy.context.window_manager.windows[0]
    areas = [area for area in window.screen.areas if area.type == "NODE_EDITOR"]
    if not areas:
        return None, None
    area = max(areas, key=lambda item: item.width * item.height)
    return area, next((item for item in area.regions if item.type == "WINDOW"), None)


def snapshot():
    area, _region = node_area()
    space = area.spaces.active
    tree = space.edit_tree
    return {
        "tree": tree.name if tree else None,
        "tree_type": space.tree_type,
        "pin": bool(space.pin),
        "selected": sorted(node.name for node in tree.nodes if node.select) if tree else [],
        "active": tree.nodes.active.name if tree and tree.nodes.active else None,
        "ui_scale": bpy.context.preferences.view.ui_scale,
        "smooth_view": bpy.context.preferences.view.smooth_view,
    }


def setup():
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    os.makedirs(LOCKED, exist_ok=True)
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    if area is None:
        area = max(window.screen.areas, key=lambda item: item.width * item.height)
        area.type = "NODE_EDITOR"
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    space.pin = True
    space.node_tree = bpy.data.materials["M_Small"].node_tree
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    prefs = bpy.context.preferences.addons["node_atlas"].preferences
    prefs.default_dir = LOCKED + os.sep
    prefs.filename_pattern = "readonly.png"
    prefs.output_dpi = 96
    prefs.padding = 20
    prefs.max_mp = 100.0
    prefs.scope = "CURRENT"
    prefs.hide_ui = True
    prefs.restore_ui = True
    prefs.deterministic = True
    return snapshot()


def lock_directory():
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if not user:
        fail("could not determine the current user for icacls")
    result = run_icacls(LOCKED, "/deny", f"{user}:(W)")
    if result.returncode != 0:
        fail(f"icacls deny failed: {result.stdout} {result.stderr}")
    probe = os.path.join(LOCKED, ".probe")
    try:
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("x")
    except OSError:
        return user
    finally:
        if os.path.exists(probe):
            try:
                os.remove(probe)
            except OSError:
                pass
    fail("the ACL deny entry did not make the directory read-only")


def unlock_directory(user):
    if not os.path.isdir(LOCKED):
        return
    run_icacls(LOCKED, "/remove:d", user)
    for name in os.listdir(LOCKED):
        try:
            os.remove(os.path.join(LOCKED, name))
        except OSError:
            pass


def tick():
    from node_atlas import operators

    state["ticks"] += 1
    if operators._current_job is not None:
        if state["ticks"] > 600:
            fail("timed out waiting for the read-only export to finish")
        return 0.05

    if os.path.exists(OUTPUT):
        fail("read-only export still created the PNG")
    if state.get("result") != "ERROR":
        fail(f"export did not fail on a read-only directory: {state.get('result')}")
    if "not writable" not in state.get("message", ""):
        fail(f"unexpected read-only error: {state.get('message')}")
    if operators.last_result is not None:
        fail(f"a job ran despite the read-only directory: {operators.last_result}")
    if snapshot() != state["before"]:
        fail(f"state mismatch after the read-only attempt: {state['before']} != {snapshot()}")
    unlock_directory(state["user"])
    print(json.dumps({
        "result": "PASS",
        "output_created": False,
        "job_started": False,
        "restored": True,
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


print("NodeAtlas read-only test output:", OUT, flush=True)
if sys.platform != "win32":
    print(json.dumps({"result": "SKIP", "reason": "icacls is Windows-only"}, indent=2))
    sys.stdout.flush()
    os._exit(0)
try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    state["before"] = setup()
    state["user"] = lock_directory()
    area, region = node_area()
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        try:
            state["result"] = bpy.ops.node_atlas.export_png()
        except RuntimeError as exc:
            state["result"] = "ERROR"
            state["message"] = str(exc)
except Exception:
    fail("could not start the read-only export:\n" + traceback.format_exc())

bpy.app.timers.register(tick, first_interval=0.05)
