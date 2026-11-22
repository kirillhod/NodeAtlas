# NodeAtlas QA report

**Version:** 1.6.1<br>
**Date:** 22 November 2026<br>
**Platforms:** Windows, GUI sessions only

> **1.6.1.** Patch release for the cross-platform audit: `~` is expanded in output
> folders, an exhausted quota maps to the disk-full message, the shortcut uses Cmd on
> macOS, **Open Last Export** reports a missing handler, the Linux `user-dirs.dirs` parser
> accepts `${HOME}` and escaped spaces, and **Restore UI** is gone because every export now
> restores the editor UI and selection.
>
> Full source matrix for 1.6.1: not re-run. The patch was verified on Blender 5.3.0 with
> **25/25 unit tests**, the **8/8 smoke tier** and the affected path, I/O and state tests;
> the 1.6.0 numbers below are the last five-version matrix. `test_artifact.py` results and
> the artifact hash are in [Packaging](#packaging).
>
> The detailed tables below are the 1.3.6 baseline; 1.4.0 changed sizes only by the
> `VIS` margin and the padding unit, and later versions added cases.

## Environment

| Blender | OS | Role |
|---|---|---|
| 5.3.0 | Windows 10 22H2 | Primary development, raw `Window.screenshot` path |
| 5.2.4 LTS | Windows 10 22H2 | Raw `Window.screenshot` path |
| 5.1.2 | Windows 10 22H2 | Legacy `screenshot_area` path |
| 4.5.9 LTS | Windows 10 22H2 | Legacy `screenshot_area` path |
| 4.2.23 LTS | Windows 10 22H2 | Legacy `screenshot_area` path |

The host has two 2048×1152 displays at a 125% OS scale. GUI tests run on the primary
display; physical second-monitor placement is not scripted. Effective UI scales
1.0/1.25/1.5/2.0 are covered by changing `view.ui_scale` (Resolution Scale), because
`system.ui_scale` is read-only and follows the OS.

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
| Single-tile stitching (memmap sub-case) | PASS | PASS | PASS | PASS | PASS |
| PNG writer round-trip + pHYs | PASS | PASS | PASS | PASS | PASS |
| Failed-save temp cleanup | PASS | PASS | PASS | PASS | PASS |
| Locked target error + cleanup | PASS | PASS | PASS | PASS | PASS |
| Long output path (150+ chars) | PASS | PASS | PASS | PASS | PASS |
| Output preflight (read-only/missing) | PASS | PASS | PASS | PASS | PASS |
| Disk-full error mapping | PASS | PASS | PASS | PASS | PASS |
| Selected-node filter | PASS | PASS | PASS | PASS | PASS |
| Filename sanitization / Unicode | PASS | PASS | PASS | PASS | PASS |
| Filename tokens / fallback | PASS | PASS | PASS | PASS | PASS |
| Tree owner names | PASS | PASS | PASS | PASS | PASS |
| Quick path / empty directory | PASS | PASS | PASS | PASS | PASS |
| Registration/preferences | PASS | PASS | PASS | PASS | PASS |
| Shortcut keymap / customization | PASS | PASS | PASS | PASS | PASS |
| Manifest/`__version__` consistency | PASS | PASS | PASS | PASS | PASS |

Result: **18/18 categories PASS on all five versions** (1.3.6 baseline; the 1.6.1 suite is
25/25 on 5.3.0, see the version notes above).

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
| `test_scaling.py` | PASS, 1.0–2.0 | PASS | PASS | PASS | PASS |
| `test_extreme.py` | PASS, 2465×4825, 11.9 MP | PASS, 2465×4943, 12.2 MP | PASS, 2465×4943, 12.2 MP | PASS, 2465×4943, 12.2 MP | PASS, 1657×3294, 5.5 MP |
| `test_multiarea.py` | PASS, 2230×643 | PASS, 2230×643 | PASS, 2231×622 | PASS, 2229×621 | PASS, 2229×610 |
| `test_multiwindow.py` | PASS, 2230×643 | PASS, 2230×643 | PASS, 2231×622 | PASS, 2229×621 | PASS, 2229×610 |
| `test_1000.py` | PASS, 12579×6013, 8.29 s | PASS, 12591×6026, 7.51 s | PASS, 12591×6026, 11.56 s | PASS, 12581×6021, 12.52 s | PASS, 12581×6021, 13.95 s |
| `test_1000.py` @120 dpi | PASS, 15724×7511, 118.1 MP | PASS, 15713×7514, 118.1 MP | PASS, 15713×7514, 118.1 MP | PASS, 15727×7521, 118.3 MP | PASS, 15727×7521, 118.3 MP |
| `test_limits.py` | PASS, 249×257, D_min + padding 120 | PASS | PASS | PASS | PASS, 249×258 |
| `test_readonly.py` | PASS, real ACL deny | PASS | PASS | PASS | PASS |
| `test_diskfull.py` | PASS, injected ENOSPC | PASS | PASS | PASS | PASS |
| `test_arealost.py` | PASS, lost area after snapshot | PASS | PASS | PASS | PASS |
| `test_artifact.py` | PASS, extension install | PASS | PASS | PASS | PASS |
| `test_estimate.py` | PASS, zoom-invariant | PASS | PASS | PASS | PASS |
| `test_estimate_selected.py` | PASS, selected subgraph | PASS | PASS | PASS | PASS |
| `test_preview.py` | PASS, 0 differing px | PASS, 0 differing px | PASS, 0 differing px | PASS, 0 differing px | PASS, 0 differing px |
| `test_group.py` | PASS, nested groups + maximized | PASS | PASS | PASS | PASS |
| `test_boost.py` | PASS, DPI 300 via scale boost | PASS | PASS | PASS | PASS |
| `test_naming.py` | PASS, owner name + 96 dpi | PASS | PASS | PASS | PASS |
| `test_clipboard.py` | PASS, OS clipboard checked | PASS | PASS | PASS | PASS |
| `test_path.py` | PASS, empty dir refused | PASS | PASS | PASS | PASS |

1.6.1: **no five-version matrix.** On 5.3.0 the unit suite is 25/25, the smoke tier is
8/8, and the affected cases pass: `test_path.py`, `test_naming.py`, `test_export.py`,
`test_diskfull.py`, `test_readonly.py`, `test_clipboard.py` and `test_cancel.py`. The new
unit case, `test_resolve_path`, requires `~/Pictures/x.png` to resolve under the home
directory, and `test_quick_filepath` gained the same check for the quick export path.
`test_disk_full` now also injects `EDQUOT`.

1.6.0: **35/35 source GUI runs passed on each of the five versions** (175/175 total), and
the unit suite is 24/24 on each version. `test_preview.py` is the new case: it zooms until
the overlay is visible, requires equal padding on all four sides of the live graph bounds,
counts the frame's pixels in a screenshot (4407 on 5.3.0, 4531 on 4.2.23; 0 with the toggle
off), and exports the same tree with the overlay on and off with 0 differing pixels. Three
unit cases cover the frame geometry and padding, the dash/label text, and the handler
lifecycle.

1.5.1: **34/34 source GUI runs passed on each of the five versions** (170/170 total), and
the unit suite is 21/21 on each version. The new unit case,
`test_select_outside_tiles`, checks the tile geometry used by the per-tile link selection;
`test_large.py` gained a wider band threshold because a full-strength link may cross the
padding band. `test_longlink.py` still reports 1.000, so the fade fix is unchanged.

1.5.0: **34/34 source GUI runs passed on each of the five versions** (170/170 total), and
the unit suite is 20/20. `test_selected_links.py` is the new case: it exports one selection
with and without Keep Links to Connected Nodes, requires the frame to stay within 2 px of
the selection, and requires the link to the unselected neighbour to appear in the right
padding band only when the option is on. The table above is the 1.4.0 matrix.

1.4.1: **33/33 source GUI runs passed on each of the five versions** (165/165 total).
`test_longlink.py` is the new case; it also passes at 20000 units on all five and at 192 DPI
on 5.3.0.

Re-run for 1.3.6: **29/29 source GUI runs passed on each of the five versions**, including
`test_1000.py` at 120 dpi and `test_group.py` with `NODEATLAS_TEST_MAXIMIZE=1`.
The 1.3.6 artifact runs Geometry Nodes and then skips the Compositor on 4.2.23, 4.5.9 and
5.1.2 because the add-on guards it against a native crash. The post-1.3.6 source fix
removes that guard: `test_trees.py` now exports the Compositor on all five,
`test_selected_comp.py` covers selected-only compositor export (5.1+ exports, 4.2/4.5
refuse with a clear error), `test_padding.py` checks the density-independent padding
unit, and the source matrix is **32/32 per version**.
`test_artifact.py` passed via classic install on all
five and via extension export on all five. The official installer was used on 4.2.23 and
5.3.0; on 4.5.9, 5.1.2 and 5.2.4 the local installer subprocess cannot start Python, so
the same payload was extracted into a local repository and loaded as
`bl_ext.nodeatlas_test.node_atlas`.

All GUI tests validate that the editor state is restored and that failed/cancelled
exports leave no PNG. The 1000-node test forces the memmap path and ~75.8 MP (118 MP at
120 dpi); the density test uses D=2, zero padding and `view.ui_scale = 2.0`; the scaling test runs
effective scales 1.0/1.25/1.5/2.0 in one session (size spread ≤ 15 px); the extreme
test runs at D_max with `view.ui_scale = 6` (4.0 max on 4.2); the limits test clamps D_min
and uses 120 px padding; the multi-area/multi-window tests keep the other editor/window
untouched; the max-MP test uses a 1 MP limit. The read-only test applies a real Windows
ACL deny entry, and the disk-full test injects ENOSPC at the save boundary. The estimate
test checks that the panel size is independent of zoom and matches the PNG, including the
filtered Selected Nodes subgraph; the naming test checks the owner-based `{tree}` token and
96 dpi `pHYs`; the clipboard test reads the image back from the Windows clipboard with
.NET, uses the **Copy to Clipboard** operator and checks that no file is written; the
path test verifies the empty-Directory prompt; the group test enters two nested node
groups and checks that the edit path, pin state and selection are restored, both in a
normal layout and with an already-maximized editor. The boost test requests 300 dpi
above the base limit, checks the image and verifies that `view.ui_scale` is restored
without a clamp warning.

## Packaging

- `blender --command extension validate node_atlas`: PASS.
- `blender --command extension build --source-dir node_atlas --output-dir dist`:
  produces `node_atlas-1.6.1.zip` with the manifest and the eight package modules.
- **1.6.1 artifact:** build and `extension validate` PASS; the zip contains only the
  manifest and the eight package modules, with no `__pycache__`. On 5.3.0 the official
  installer (`install-file -r user_default -e`) installed it into an isolated
  `BLENDER_USER_EXTENSIONS` profile and `test_artifact.py` exported a PNG from
  `bl_ext.user_default.node_atlas`; the classic folder copied into an isolated
  `scripts/addons` profile enabled `node_atlas` and exported too.
- `node_atlas-1.6.1.zip` SHA256:
  `0568D75FB4FC2145BD63C7BF34FBF6EEE388D53F80F25BA7C94AFCBE02B35A79`.
- **1.6.0 artifact:** build and `extension validate` PASS; the zip contains only the
  manifest and the eight package modules (`preview.py` included), with no `__pycache__`.
  The official installer (`install-file -r user_default -e`) installed it into an isolated
  `BLENDER_USER_EXTENSIONS` profile on 4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0, and
  `test_artifact.py` exported a PNG from `bl_ext.user_default.node_atlas` on each. The
  classic folder copied into an isolated `scripts/addons` profile enabled `node_atlas` and
  exported on all five.
- `node_atlas-1.6.0.zip` SHA256:
  `733ECD77A9480B09A2DBD72882DAE3A1C1A825D36A42955F333E15614A7132F6`.
- **1.5.1 artifact:** build and `extension validate` PASS; the zip contains only the
  manifest and the seven package modules, with no `__pycache__`. The official installer
  (`install-file -r user_default -e`) installed it into an isolated `BLENDER_USER_EXTENSIONS`
  profile on 4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0, and `test_artifact.py` exported a PNG
  from `bl_ext.user_default.node_atlas` on each. The classic folder copied into an isolated
  `scripts/addons` profile enabled `node_atlas` and exported on all five.
- `node_atlas-1.5.1.zip` SHA256:
  `60585F4B766FE5124835A3E099A7A369C5C47928D977DCFFA9F288D8BA2F12DA`.
- **1.5.0 artifact:** build and `extension validate` PASS; the zip contains only the
  manifest and the seven package modules, with no `__pycache__`. The official installer
  (`install-file -r user_default -e`) installed it into an isolated `BLENDER_USER_EXTENSIONS`
  profile on 4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0, and `test_artifact.py` exported a PNG
  from `bl_ext.user_default.node_atlas` on each. The classic folder copied into an isolated
  `scripts/addons` profile enabled `node_atlas` and exported on all five.
- `node_atlas-1.5.0.zip` SHA256:
  `F616F80A4523DDA5A11D0511481E3DBF2FED4B1DDBC9A1643249AB82E8B92D6D`.
- **1.4.0 artifact:** `extension validate` PASS; extension install and GUI export PASS on
  all five versions with the official installer (`install-file -r user_default -e`,
  module `bl_ext.user_default.node_atlas`); classic add-on install and export PASS on all
  five. Each run used an isolated `BLENDER_USER_CONFIG`/`BLENDER_USER_SCRIPTS`/
  `BLENDER_USER_EXTENSIONS` profile. The zip contains only the manifest and seven package
  modules, with no `__pycache__`.
- **1.4.1 artifact:** build and `extension validate` PASS; the zip contains only the
  manifest and the seven package modules, with no `__pycache__`. The official installer
  (`install-file -r user_default -e`) installed it into an isolated `BLENDER_USER_EXTENSIONS`
  profile on 4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0, and `test_artifact.py` exported a PNG
  from `bl_ext.user_default.node_atlas` on each. The classic folder copied into an isolated
  `scripts/addons` profile enabled `node_atlas` and exported on all five.
- `node_atlas-1.4.1.zip` SHA256:
  `6FD9661FD91B46C79E1C65CE6BB534789FA2727E852C8EBC85F9A8B628F25FE9`.
- `node_atlas-1.4.0.zip` SHA256:
  `CFEBF1C4BB673A4421A3F19310D60B766482C27EA3D829EE0E7C40CB0B6CDEF8`.
- 1.3.6 artifact (previous release): `extension validate` PASS; classic install/export
  PASS on all five versions; extension export PASS on all five. The official extension
  installer was used on 4.2.23 and 5.3.0. On 4.5.9, 5.1.2 and 5.2.4 the local installer
  subprocess could not start Python (`No module named 'encodings'`), so the same zip was
  extracted into a local repository and loaded as
  `bl_ext.nodeatlas_test.node_atlas`.
- Classic add-on clean-profile install: PASS on Blender 4.2.23, 4.5.9, 5.1.2, 5.2.4
  and 5.3.0 in isolated `BLENDER_USER_SCRIPTS/scripts/addons` profiles (0.6.1); the
  0.6.2, 0.7.0, 0.8.0 and 1.0.0 packages were re-validated on 5.3.0. The 1.1.0, 1.2.0,
  1.2.1, 1.3.0, 1.3.1, 1.3.2, 1.3.3, 1.3.4 and 1.3.5 packages were copied into isolated
  profiles on all five versions; `test_artifact.py` enabled `node_atlas` and exported a
  PNG on each.
- Extension clean-profile install: PASS across the same five versions with 0.6.1; the
  0.6.2, 0.7.0, 0.8.0 and 1.0.0 zips were installed into isolated repositories with
  `install-file --enable`, loading `bl_ext.nodeatlas_test.node_atlas`. The 1.1.0, 1.2.0,
  1.2.1, 1.3.0, 1.3.1, 1.3.2, 1.3.3, 1.3.4 and 1.3.5 zips installed and exported through
  `bl_ext.nodeatlas_test.node_atlas` on 4.2.23 and 5.3.0. On 4.5.9, 5.1.2 and 5.2.4 the
  local builds' `--command extension` Python runtime is incomplete (their bundled
  `python.exe` cannot find the stdlib), so the same 1.3.5 zip payload was validated
  through the classic install path on those versions instead. The 1.4.0 zip installed
  through the official installer on all five.
- Linux and macOS are untested: no Linux distribution is installed under WSL and no Mac
  hardware is available. `system.ui_scale` cannot be changed from RNA, so OS-level
  scaling percentages were approximated with the effective view scale (1.0–2.0).

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

1. **Compositor on Blender 4.2–5.1 (fixed in 1.4.0).** The native crash is in
   `node_area_refresh` after `SpaceNodeEditor.pin = True` on a compositor tree.
   Measured on 4.2.23 and 4.5.9: `pin = False` exports correctly and the minimal
   `screenshot_area` path works; 5.1.2 accepts `pin = True`. The 1.3.6 artifact blocked
   every Compositor export below 5.2; 1.4.0 leaves the compositor tree unpinned on
   4.2/4.5 and passes 32/32 on all five versions.
2. **Selected-only Compositor export needs 5.1+.** A filtered copy cannot be shown
   without pin, pinning a compositor tree crashes 4.2/4.5 when the area is rebuilt, and
   `Scene.node_tree` is read-only there. NodeAtlas raises a clear error instead of
   crashing or exporting the whole tree.
3. **macOS/Retina and Linux/X11** were not tested.
4. View restoration is nearest-pixel (`View2D.cur` is not exposed); UI/tree/selection
   restoration is exact.
5. **Long links faded in middle tiles (fixed in 1.4.1).** `node_link_dim_factor` lowers a
   link to 5 % once the nearer socket is about a tenth of the view width outside the view,
   so a connection spanning three tiles lost its middle segment (measured ratio 0.059).
   The export now selects the nodes outside each tile and mutes `wire_select` for the run;
   median/peak is 0.977 on 4.2.23 and 4.5.9 and 1.000 on 5.1.2-5.3.0, at 12000 and 20000
   units, with every changed pixel inside the link band. `test_longlink.py` requires
   median/peak >= 0.9 and trough/peak >= 0.75 (4.2/4.5 anti-alias a 1-px link by up to 16 %)
   and checks selection, theme alpha and undo restoration.
6. Per-run setting overrides and transparent background are not in 0.7.0.
7. If Blender hard-crashes mid-export, the in-memory `view.ui_scale` cannot be restored
   by the add-on. Blender saves preferences only on a normal quit; NodeAtlas never calls
   `save_userpref`.
8. **Copy to Clipboard** relies on Blender's image clipboard operator. Very large images
   may be refused by the OS or take a long time to paste; normal file exports are
   unaffected.
9. **Selected outline on edge nodes (fixed in 1.5.1).** The per-tile selection used
   `View2D.region_to_view`, which could lag one pan behind; a reroute already inside a tile
   was marked selected and captured with the white selection outline, most visible on the
   small reroute dots. The selection now derives the tile box from the anchored layout;
   `test_select_outside_tiles` checks the geometry and the long-link test still reports
   1.000 after the change.

## Not in scope for 1.0.0

Batch export of all groups, transparent background, SVG/JSON/HTML, headless capture
and AI upscaling are deferred; see [`ROADMAP.md`](ROADMAP.md).
