# SPDX-License-Identifier: GPL-3.0-or-later
"""Restore test: a lost area must still return the global preferences.

Two cases that the normal export cannot exercise:

* the Node Editor disappears before ``restore_snapshot`` finds it, so the
  early return must not skip ``ui_scale`` and ``smooth_view``;
* an export never reached its restore stage, so the on-disk marker offers the
  **Restore Editor Settings** button on the next start.

The theme, the selected-link tint, ``ui_scale`` and ``smooth_view`` are
preferences; Blender saves them on a normal exit, so a leak survives a restart.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = tempfile.mkdtemp(prefix="nodeatlas_recovery_")
RECOVERY_FILE = os.path.join(OUT, "pending.json")
os.environ["NODEATLAS_RECOVERY_FILE"] = RECOVERY_FILE


def fail(message):
    print("FAIL:", message)
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)


def check(condition, message):
    if not condition:
        fail(message)


def close(a, b, tol=1e-4):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def theme_state(capture):
    prefs = bpy.context.preferences
    color = capture.link_highlight_color()
    return {
        "backdrop": capture.current_theme_backdrop(),
        "grid": capture.current_theme_grid_levels(),
        "alpha": float(color[3]) if color is not None else None,
        "ui_scale": float(prefs.view.ui_scale),
        "smooth_view": int(prefs.view.smooth_view),
    }


def state_equal(now, expected, key):
    a, b = now[key], expected[key]
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        return close(a, b)
    return a == b


def same_state(capture, expected):
    now = theme_state(capture)
    keys = ("backdrop", "grid", "alpha", "ui_scale", "smooth_view")
    check(
        all(state_equal(now, expected, key) for key in keys),
        f"preferences were not restored: {expected} != {now}",
    )


def damage(capture):
    capture.set_theme_backdrop((0.0, 0.0, 0.0))
    capture.set_theme_grid_levels(0)
    color = capture.link_highlight_color()
    if color is not None:
        color[3] = 0.0
    bpy.context.preferences.view.ui_scale = 1.25
    bpy.context.preferences.view.smooth_view = 0


def fake_snapshot(capture, expected):
    return capture.EditorSnapshot(
        window=None,
        tree=None,
        tree_type="ShaderNodeTree",
        pin=False,
        header=True,
        ui=True,
        toolbar=False,
        gizmo=False,
        context_path=False,
        backdrop=False,
        selected=(),
        active=None,
        ui_scale=expected["ui_scale"],
        smooth_view=expected["smooth_view"],
        upp=1.0,
        center=(0.0, 0.0),
        area_signature=(),
        area_count=0,
        area_bbox=None,
        root_tree=None,
        path_trees=(),
        link_highlight_alpha=expected["alpha"],
        theme_backdrop=expected["backdrop"],
        theme_grid_levels=expected["grid"],
    )


def run():
    from node_atlas import capture, job, recovery

    original = theme_state(capture)

    # 1. Lost area: both early returns used to skip the preferences.
    damage(capture)
    find_bbox, find_area = capture.find_area_by_bbox, capture.find_node_area
    capture.find_area_by_bbox = lambda *args, **kwargs: None
    capture.find_node_area = lambda *args, **kwargs: None
    try:
        errors, _warnings = capture.restore_snapshot(fake_snapshot(capture, original))
    finally:
        capture.find_area_by_bbox = find_bbox
        capture.find_node_area = find_area
    check(any("area is no longer available" in error for error in errors), errors)
    same_state(capture, original)
    print("PASS lost-area preferences")

    # 2. An unexpected exception during restore must not skip them either.
    damage(capture)

    def boom(*args, **kwargs):
        raise RuntimeError("injected area lookup")

    capture.find_area_by_bbox = boom
    try:
        errors, _warnings = capture.restore_snapshot(fake_snapshot(capture, original))
    finally:
        capture.find_area_by_bbox = find_bbox
    check(any("restore failed" in error for error in errors), errors)
    same_state(capture, original)
    print("PASS exception preferences")

    # 3. An answer written before the capture is offered after a restart.
    appearance = recovery.current()
    damage(capture)
    check(recovery.save(appearance), "could not write the recovery marker")
    recovery.reset_cache()
    check(job.pending_recovery() is not None, "the marker was not offered")
    check(job.pending_recovery() is not None, "the marker was not offered")
    result = bpy.ops.node_atlas.restore_editor()
    check("FINISHED" in result, f"restore operator returned {result}")
    same_state(capture, original)
    check(not os.path.exists(RECOVERY_FILE), "the marker was not cleared")
    check(job.pending_recovery() is None, "the marker is still pending")
    print("PASS interrupted-export marker")

    # 4. A marker whose values already match is not offered.
    check(recovery.save(recovery.current()), "could not write the stale marker")
    recovery.reset_cache()
    check(job.pending_recovery() is None, "a matching marker was offered")
    recovery.clear()
    check(not os.path.exists(RECOVERY_FILE), "the stale marker was not removed")
    print("PASS stale marker")

    print(json.dumps({
        "result": "PASS",
        "cases": ["lost-area", "exception", "marker", "stale"],
    }, indent=2))
    sys.stdout.flush()
    os._exit(0)


try:
    bpy.ops.preferences.addon_enable(module="node_atlas")
    run()
except Exception:
    fail("recovery test failed:\n" + traceback.format_exc())
