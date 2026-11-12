# NodeAtlas QA report

**Version:** 0.7.0
**Date:** 12 November 2026  
**Platforms:** Windows, GUI sessions only

## Environment

| Blender | OS | Role |
|---|---|---|
| 5.3.0 | Windows | Primary development, raw `Window.screenshot` path |
| 5.2.4 LTS | Windows | Raw `Window.screenshot` path |
| 5.1.2 | Windows | Legacy `screenshot_area` path |
| 4.5.9 LTS | Windows | Legacy `screenshot_area` path |
| 4.2.23 LTS | Windows | Legacy `screenshot_area` path |

Fixtures are generated locally by `tests/fixtures/make_scene_*.py` with Blender 4.2.23
so the resulting `.blend` files open in all tested versions. Generated fixtures are
ignored by Git.

## Headless tests

Command:

```powershell
blender --background --factory-startup --python tests/unit/test_core.py
```

| Check | 5.3.0 | 5.2.4 | 5.1.2 | 4.5.9 | 4.2.23 |
|---|---|---|---|---|---|
| View metrics | PASS | PASS | PASS | PASS | PASS |
| Rect/layout math | PASS | PASS | PASS | PASS | PASS |
| Density limits | PASS | PASS | PASS | PASS | PASS |
| Single-tile stitching | PASS | PASS | PASS | PASS | PASS |
| Memmap spill path | PASS | PASS | PASS | PASS | PASS |
| NumPy PNG writer round-trip | PASS | PASS | PASS | PASS | PASS |
| Failed-save temp cleanup | PASS | PASS | PASS | PASS | PASS |
| Locked target error + cleanup | PASS | PASS | PASS | PASS | PASS |
| Long output path (180+ chars) | PASS | PASS | PASS | PASS | PASS |
| Output preflight (read-only/missing) | PASS | PASS | PASS | PASS | PASS |
| Disk-full error mapping | PASS | PASS | PASS | PASS | PASS |
| Filename sanitization / Unicode | PASS | PASS | PASS | PASS | PASS |
| Registration/preferences | PASS | PASS | PASS | PASS | PASS |
| Manifest/`__version__` consistency | PASS | PASS | PASS | PASS | PASS |

Result: **13/13 PASS on all five versions.** The memmap spill is a sub-case of the
single-tile stitching test.

## GUI tests

Commands are listed in [`README.md`](README.md). Each test starts a visible Blender
window, exports a fixture, validates the PNG and editor restoration, then exits.

| Test | 5.3.0 | 5.2.4 | 5.1.2 | 4.5.9 | 4.2.23 |
|---|---|---|---|---|---|
| `test_export.py` | PASS, 2232×1631 | PASS, 2231×1638 | PASS, 2231×1638 | PASS, 2232×1639 | PASS, 2232×1639 |
| `test_legacy.py` | PASS, forced | raw path | native path | native path | native path |
| `test_selected.py` | PASS, 781×413 | PASS, 780×419 | PASS, 780×419 | PASS, 780×419 | PASS, 780×419 |
| `test_trees.py` | PASS, GN + Compositor | PASS, GN + Compositor | PASS, GN; Compositor skipped | PASS, GN; Compositor skipped | PASS, GN; Compositor skipped |
| `test_texture.py` | PASS | PASS | PASS | PASS | PASS |
| `test_repeat.py` | PASS, 0 differing px | PASS, 0 differing px | PASS, 0 differing px | PASS, 0 differing px | PASS, 0 differing px |
| `test_cancel.py` | PASS, capture stage | PASS | PASS | PASS | PASS |
| `test_fail.py` | PASS | PASS | PASS | PASS | PASS |
| `test_large.py` | PASS, 6017×3131, 1.87 s | PASS, 6013×3132, 1.69 s | PASS, 6013×3132, 2.71 s | PASS, 6016×3133, 3.18 s | PASS, 6016×3133, 3.25 s |
| `test_maxmp.py` | PASS | PASS | PASS | PASS | PASS |
| `test_density.py` | PASS, 4382×1198 | PASS, 4382×1198 | PASS, 4384×1156 | PASS, 4378×1154 | PASS, 4383×1129 |
| `test_extreme.py` | PASS, 2465×4825, 11.9 MP | PASS, 2465×4943, 12.2 MP | PASS, 2465×4943, 12.2 MP | PASS, 2465×4943, 12.2 MP | PASS, 1657×3294, 5.5 MP |
| `test_multiarea.py` | PASS, 2230×643 | PASS, 2230×643 | PASS, 2231×622 | PASS, 2229×621 | PASS, 2229×610 |
| `test_multiwindow.py` | PASS, 2230×643 | PASS, 2230×643 | PASS, 2231×622 | PASS, 2229×621 | PASS, 2229×610 |
| `test_1000.py` | PASS, 12579×6013, 8.29 s | PASS, 12591×6026, 7.51 s | PASS, 12591×6026, 11.56 s | PASS, 12581×6021, 12.52 s | PASS, 12581×6021, 13.95 s |
| `test_1000.py` @120 dpi | PASS, 15724×7511, 118.1 MP | PASS, 15713×7514, 118.1 MP | PASS, 15713×7514, 118.1 MP | PASS, 15727×7521, 118.3 MP | PASS, 15727×7521, 118.3 MP |
| `test_limits.py` | PASS, 249×257, D_min + padding 120 | PASS | PASS | PASS | PASS, 249×258 |
| `test_readonly.py` | PASS, real ACL deny | PASS | PASS | PASS | PASS |
| `test_diskfull.py` | PASS, injected ENOSPC | PASS | PASS | PASS | PASS |
| `test_arealost.py` | PASS, lost area after snapshot | PASS | PASS | PASS | PASS |

All GUI tests validate that the editor state is restored and that failed/cancelled
exports leave no PNG. The 1000-node test forces the memmap path and ~75.8 MP (118 MP at
120 dpi); the density test uses D=2, zero padding and `view.ui_scale = 2.0`; the extreme
test runs at D_max with `view.ui_scale = 6` (4.0 max on 4.2); the limits test clamps D_min
and uses 120 px padding; the multi-area/multi-window tests keep the other editor/window
untouched; the max-MP test uses a 1 MP limit. The read-only test applies a real Windows
ACL deny entry, and the disk-full test injects ENOSPC at the save boundary.

## Packaging

- `blender --command extension validate node_atlas`: PASS.
- `blender --command extension build --source-dir node_atlas --output-dir dist`:
  produces `node_atlas-0.7.0.zip` with the manifest and package modules.
- Classic add-on clean-profile install: PASS on Blender 4.2.23, 4.5.9, 5.1.2, 5.2.4
  and 5.3.0 in isolated `BLENDER_USER_SCRIPTS/scripts/addons` profiles (0.6.1); the
  0.6.2 package was re-validated on 5.3.0, and the 0.7.0 package is re-validated on
  5.3.0.
- Extension clean-profile install: PASS across the same five versions with 0.6.1; the
  0.6.2 zip was installed into an isolated 5.3.0 repository with
  `install-file --enable`, loading `bl_ext.nodeatlas_test.node_atlas` version 0.6.2.
  The 0.7.0 zip is re-validated the same way.
- Linux/macOS QA is still pending.

## Runtime guards

- The destination directory is created and probed with a private file before any
  capture work starts. Denied directories, full disks and path errors stop the export
  with `OutputError` and no job is started.
- Writing probes uses `os.open` rather than `tempfile.mkstemp`: on Windows, `mkstemp`
  retries forever when an ACL denies writes but `os.access` still reports the directory
  as writable. This was reproduced on Python 3.11 and fixed in 0.7.0.
- Write failures are mapped to `OutputError`; ENOSPC reports "Not enough free disk space"
  and the temporary `*.tmp.png` is removed.
- A snapshot is taken before mutation and restored in `finally`; a lost area after the
  snapshot is reported as a failure with the UI restored.

## Known issues

1. **Compositor on Blender 4.2–5.1.** Native Blender crashes with
   `EXCEPTION_ACCESS_VIOLATION` during capture. NodeAtlas detects the version/tree type
   and raises a clear error instead of risking a crash. Use Blender 5.2+ for the
   Compositor.
2. **macOS/Retina and Linux/X11** were not tested.
3. View restoration is nearest-pixel (`View2D.cur` is not exposed); UI/tree/selection
   restoration is exact.
4. Long links may fade; Blender exposes no public setting to disable link LOD.
5. Per-run setting overrides and transparent background are not in 0.7.0.
6. If Blender hard-crashes mid-export, the in-memory `view.ui_scale` cannot be restored
   by the add-on. Blender saves preferences only on a normal quit; NodeAtlas never calls
   `save_userpref`.

## Not in scope for 1.0.0

Batch export of all groups, transparent background, SVG/JSON/HTML, headless capture
and AI upscaling are deferred; see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).
