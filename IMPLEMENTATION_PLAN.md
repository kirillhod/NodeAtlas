# NodeAtlas — Implementation Plan to 1.0.0

**Status:** in progress; 0.5.0 MVP implemented (see below).
**Based on:** [`NodeGraph_Export_Report.md`](NodeGraph_Export_Report.md) (validated on Blender 5.3.0)
and [`AGENTS.md`](AGENTS.md) (non-negotiable rules).  
**Target:** `node_atlas` 1.0.0 — a stable, documented extension for
[Blender 4.2+](https://www.blender.org/download/) that exports the current node tree,
or the selected nodes, as one PNG.

**Progress (1.0.0):** All milestones are complete. NodeAtlas exports the current tree or
selected nodes for Shader, Geometry Nodes, Compositor and Texture on Blender 4.2–5.3
(Windows), using the raw screenshot path on 5.2+ and the legacy adapter on 4.2–5.1.
Hardening covers 1000 nodes at 118 MP, extreme Dmax/Dmin, padding 0/120, effective
scales 1.0–2.0, two Node Editor areas, two windows, real read-only output, injected
disk-full, locked targets and long paths. Packaging, docs, SPDX headers and the QA
report are committed, and both install methods were validated from clean profiles.
Linux, macOS and a second physical monitor remain untested and are stated as such in
the release notes; screenshots are intentionally omitted.

| Milestone | Version | Status |
|---|---|---|
| M0 Foundation | 0.1.0 | Done (combined into 0.5.0) |
| M1 Geometry/bounds | 0.2.0 | Done |
| M2 Capture 5.2+ | 0.3.0 | Done |
| M3 Stitch/save | 0.4.0 | Done |
| M4 Operator/UI MVP | 0.5.0 | Done; per-run overrides and popups deferred |
| M5 Tree types | 0.6.0 | Done for Shader/GN/Compositor/Texture; 6.0 adapter open |
| M6 Legacy adapter | 0.6.0 | Done for Shader/GN/Texture on 4.2.23/4.5.9/5.1.2; Compositor 4.2–5.1 is guarded |
| M7 Hardening | 0.7.0 | Done: limits, fault injection and output-path guards pass on Windows 4.2–5.3 |
| M8 Packaging/QA | 0.8.0 | Done for Windows; Linux/macOS and a second monitor are documented as untested |
| M9 Release | 1.0.0 | Done: artifact regression passed, local annotated tag `v1.0.0` |

**Post-release (1.1.0):** DPI `pHYs` metadata, a zoom-invariant size estimate,
owner-based filename tokens, optional clipboard copy and the empty-Directory prompt are
implemented and tested on Blender 4.2–5.3. See [`CHANGELOG.md`](CHANGELOG.md) and
[`RELEASE_NOTES.md`](RELEASE_NOTES.md).

This plan is a dependency-ordered roadmap, not a promise of dates. Estimates are focused
development days and exclude waiting for Blender builds, OS/hardware access and review.

---

## 1. Definition of 1.0.0

1.0.0 is released when a user can install NodeAtlas from a clean Blender profile and,
without editing preferences or restarting:

- export the visible
  [Node Editor](https://docs.blender.org/manual/en/latest/interface/controls/nodes/node_editors.html)
  tree to one seamless PNG with correct bounds, padding
  and density on Blender 4.2–5.3;
- export only selected nodes;
- do the same for
  [Shader](https://docs.blender.org/manual/en/latest/editors/shader_editor.html),
  [Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html)
  and [Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html)
  trees (Texture trees verified
  or explicitly documented as supported-with-caveats);
- choose `output_dpi`, `padding`, `max_mp`, scope and background (theme or solid);
- see progress, cancel with `Esc`, and get a clear result or error;
- always get the original UI, tree, selection, view and `view.ui_scale` restored,
  including after an exception;
- never get a polluted Undo stack;
- install the same artifact as a Blender extension and as a classic add-on.

Out of 1.0.0 unless the open decisions in §8 change:

- batch export of all trees/groups in a `.blend`;
- transparent background (two-background matting / chroma-key);
- SVG/JSON/HTML export;
- headless/`--background` capture;
- AI upscaling or vector reconstruction.

---

## 2. Scope map

| Capability | 1.0.0 | Notes |
|---|---|---|
| Current tree → PNG | Yes | Primary path |
| Selected nodes only | Yes | Temporary filtered copy, report §11.15 |
| [Shader](https://docs.blender.org/manual/en/latest/editors/shader_editor.html) trees (Material/World/Light) | Yes | Verified |
| [Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html) | Yes | Verified |
| [Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html) | Yes | [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group), asset-shelf crop |
| [Texture Nodes](https://docs.blender.org/manual/en/latest/editors/texture_node/index.html) | Yes, if verified | Fallback: document caveat |
| [Blender 5.2–5.3](https://developer.blender.org/docs/release_notes/5.2/) | Yes | [`Window.screenshot`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot) fast path |
| [Blender 4.2–5.1](https://developer.blender.org/docs/release_notes/4.2/) | Yes | [`screenshot_area`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area) adapter |
| `output_dpi` / density normalization | Yes | 96 = 1:1 |
| `padding` in output pixels | Yes | Real background, no fill |
| `max_mp` guard | Yes | Hard error before capture; memmap above threshold |
| Background: theme | Yes | Default |
| Background: solid color | Yes | Theme override with exact restore |
| Background: transparent | No (1.1) | Experimental in report §11.14 |
| Batch all groups | No (1.1) | Report §6.5 defers it; see §8 |
| Progress + cancel | Yes | Timer state machine |
| UI state restore | Yes | Snapshot/restore, report §11.13 |
| Undo-neutral | Yes | Verified, report §11.16 |
| Extension manifest + zip | Yes | [`blender_manifest.toml`](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html) |
| Docs + QA matrix | Yes | README, CHANGELOG, QA report |
| Linux/macOS | Best effort | Must be stated in release notes |

---

## 3. Quality gates

Every milestone must satisfy the global rules:

- Follow [`AGENTS.md`](AGENTS.md) §5 absolutely (scale split, pan sign, bottom-up crop,
  PAD crop, `view_all` priming, restore order, undo neutrality, no saved preferences).
- No third-party dependencies; [NumPy](https://numpy.org/doc/stable/) is provided by
  Blender.
- No undoable operator and no `undo_push` in the pipeline.
- The add-on imports cleanly in `--background` (registration must not require a GUI).
- Tests compare **geometry invariants** first; pixel equality only on the same machine.
- Every milestone ends with a version-bump commit tagged `vX.Y.Z` (AGENTS §9), with the
  manifest version and `__version__` in sync.
- A feature is not done until it has run in a live GUI Blender; record Blender version,
  OS, `system.ui_scale`, window/region size, `D`, `padding` and tile grid.

---

## 4. Target architecture

Keep pure logic separate from [`bpy`](https://docs.blender.org/api/current/) so it can
be tested headlessly.

```text
node_atlas/
├─ __init__.py          # register/unregister, version, menu/keymap wiring
├─ operators.py         # timer state machine: ExportPNG, ExportAs
├─ capture.py           # snapshot/restore, tree switch, maximize, tiles, adapters
├─ bounds.py            # view metrics, node rects, layout, selected-only copy
├─ stitch.py            # canvas, feathering, top crop, coverage, PNG save
├─ preferences.py       # global defaults
├─ log.py               # namespaced logger, no bare prints
└─ blender_manifest.toml
```

Suggested contracts (names may change; behavior may not):

```python
# bounds.py
@dataclass(frozen=True)
class ViewMetrics:   # report §4.3
    upp: float; k: float; s: float; ox: float; oy: float

@dataclass(frozen=True)
class Layout:        # everything capture/stitch need
    pad: int; overlap: int; margin: int
    content_w: float; content_h: float
    grid_x: int; grid_y: int
    step_x: int; step_y: int
    canvas_w: int; canvas_h: int
    final_w: int; final_h: int

def measure_view(v2d, ui_scale: float) -> ViewMetrics: ...
def node_rect(node, vm: ViewMetrics) -> tuple[float, float, float, float]: ...
def compute_layout(content, region_w, region_h, padding, view_ui_scale) -> Layout: ...
def build_selected_copy(tree) -> tuple[NodeTree, int]: ...   # raises EmptySelection

# capture.py
class EditorSnapshot:
    def take(context) -> "EditorSnapshot": ...
    def restore(self) -> None: ...          # never raises; logs failures

class CaptureSession:
    def select_tree(space, tree) -> None: ...
    def enter(context) -> None: ...         # maximize, hide UI, clear selection
    def normalize_view(target_upp) -> ViewMetrics: ...
    def capture_tile(index, layout) -> np.ndarray: ...
    def leave() -> None: ...

# stitch.py
def stitch(tiles, layout) -> tuple[np.ndarray, np.ndarray]: ...  # canvas, weights
def crop_final(canvas, weights, layout) -> np.ndarray: ...
def save_png(rgba, path) -> None: ...                            # atomic

# operators.py
# States: PREPARE → NORMALIZE → CAPTURE → STITCH → SAVE → RESTORE → DONE/ERROR
```

The operator's [`execute()`](https://docs.blender.org/api/current/bpy.types.Operator.html#bpy.types.Operator.execute)
starts the timer; all redraw-dependent work happens between timer callbacks.
Cancellation sets a flag that jumps to `RESTORE`.

---

## 5. Milestones

### M0 — Foundation and archived evidence (`0.1.0`)

**Goal:** an installable empty add-on with a reproducible test environment.

Tasks:

- [ ] Create `node_atlas/` package skeleton, `register()`/`unregister()`, a panel that
      only appears in `NODE_EDITOR`, and empty `NodeAtlasPreferences`.
- [ ] Add [`blender_manifest.toml`](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html)
      (`id = "node_atlas"`, GPL-3.0-or-later, min 4.2.0).
- [ ] Single version source (`__init__.py` + manifest kept in sync, checked by a test).
- [ ] `log.py` with a namespaced logger and debug switch; no bare `print` in shipping code.
- [ ] Archive the validated prototypes from the research session into
      `reference/prototypes/` and the fixture generators into `tests/fixtures/`
      (tiling5/6/7/9/11/12, restore_test, selected_*, undo_*, pan/zoom probes,
      make_scene_*). Record origin, date and Blender version.
- [ ] Test harness skeleton: `tests/unit` (headless) and `tests/gui` (live window);
      JSON result schema with environment fields and PASS/FAIL per check.
- [ ] Dev install script (`scripts/dev_install.ps1` junction + shell equivalent) and a
      reload instructions section.

**Exit:** clean install and reload with no console errors; panel/prefs visible; add-on
imports in `blender --background`; fixtures and prototypes committed under the repo.

**Estimate:** 1–2 days.

---

### M1 — Geometry, bounds and selected-only (`0.2.0`)

**Goal:** all off-screen math is implemented and tested before touching capture.

Tasks:

- [ ] Implement `measure_view`, `node_rect`, union of
      [`Node.dimensions`](https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.dimensions) +
      [`location_absolute`](https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.location_absolute);
      fallback to `width/height` while dimensions are zero.
- [ ] Implement layout: `VIS`, `PAD_eff`, `OVERLAP_eff`, `M`, grid, canvas and final
      size; clamp/warn for `D` outside `[S/20, S/0.43311]`.
- [ ] Implement output-size estimation for the panel and `max_mp` prediction.
- [ ] Implement selected-only temp copy with agreed semantics (frames include
      descendants, unparent with absolute position, hidden selected skipped, empty
      selection raises); add cleanup that is safe after exceptions.
- [ ] Unit-test the scale formula against synthetic UI scales (1.0, 1.25, 2.0, 6.0) and
      the monotonic density ratios from report §11.7.
- [ ] Test selected-only on all three cases from §11.15 (N1+R1, frame F1, C3 inside F2)
      and assert original tree/link/selection state is unchanged.

**Exit:** 24-node fixture bounds match the report model within 2 px; selected cases pass;
layout values reproduce the reference grids; no mutation of user data.

**Estimate:** 2–3 days.

---

### M2 — Capture engine, Blender 5.2+ fast path (`0.3.0`)

**Goal:** capture correctly positioned tiles and restore the editor, without saving yet.

Tasks:

- [ ] `EditorSnapshot.take/restore` covering window/area/region geometry, `tree_type`,
      `node_tree`, `edit_tree`, `pin`, selection/active, region flags, gizmo, context
      path, backdrop, `view.ui_scale`, `smooth_view`, `upp`, view center, area type.
- [ ] Tree selection order: `pin = False` → `tree_type` → `show_backdrop` → `pin = True`
      → `node_tree`; verify `edit_tree`.
- [ ] Enter:
      [`screen_full_area(use_hide_panels=True)`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screen_full_area),
      re-fetch area/region/space, hide header/toolbar/sidebar/context path, disable
      gizmo, clear selection and active.
- [ ] Normalize:
      [`node.view_all()`](https://docs.blender.org/api/current/bpy.ops.node.html#bpy.ops.node.view_all)
      → [`zoom_border`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.zoom_border)
      loop to target `upp` (<0.2 % error) → measure; `smooth_view = 0`.
- [ ] Tile grid and anchoring: inverted
      [`pan`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.pan)
      sign, 1–2 nudge passes for tile 0, fixed integer steps afterwards.
- [ ] Capture:
      [`redraw_timer(DRAW_WIN_SWAP, 1)`](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.redraw_timer),
      [`Window.screenshot`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot),
      shape check, crop `PAD_eff` from every side; detect and crop bottom overlay
      regions (asset shelf).
- [ ] Restore in the documented order, including retry of `screen_full_area` with a
      fresh area; report restoration failures without masking the original exception.
- [ ] Feature-gate the adapter; older Blender gets a clear "not yet supported" error
      until M6.

**Exit:** on `scene_uniq`, tile anchors within 2 px, every tile shape correct, overlap
between adjacent cropped tiles mean abs diff < 0.1, no frame/scrollbar pixels, state
restored after both success and a dry-run failure.

**Estimate:** 3–5 days.

---

### M3 — Stitching and PNG output (`0.4.0`)

**Goal:** a complete PNG file from captured tiles, with hard correctness checks.

Tasks:

- [ ] Canvas accumulation with weights and linear feathering over
      `OVERLAP_eff − 2·PAD_eff`.
- [ ] Exact tile placement; assert no uncovered pixels in the final crop.
- [ ] Top-anchored crop with no `+1`; expose `holes`, margins and overlap metrics to tests.
- [ ] Save through [`imbuf.new`](https://docs.blender.org/api/current/imbuf.html) +
      `with_buffer` + `imbuf.write`; atomic `.tmp.png` + `os.replace`; 4.2–5.1
      fallback via the NumPy PNG writer (`stitch._write_png_numpy`).
- [ ] Memory prediction and `max_mp` enforcement before capture;
      [`np.memmap`](https://numpy.org/doc/stable/reference/generated/numpy.memmap.html)
      canvas above a threshold; clean temporary files in `finally`.
- [ ] Regression test: `scene_uniq` at `D=1`, `padding=40`; `scene_both` small/big;
      `D=0.5/1/2`; `padding=0/20/40/120`.
- [ ] Add a test-only node-position detector (colored headers / predicted rects) and
      assert ≤2 px error on the 24-node fixture.

**Exit:** expected sizes (`ceil(content) + 2·padding`), `holes = 0`, overlap ≈0,
margins exact, positions ≤2 px, PNG opens in Blender and external viewers.

**Estimate:** 2–3 days.

---

### M4 — Operator, UI and end-to-end MVP (`0.5.0`)

**Goal:** a user can install the add-on and export with one click on Blender 5.2+.

Tasks:

- [ ] Timer state machine with progress text, cancel flag (`Esc`), and a restore stage
      that always runs.
- [ ] `node_atlas.export_png` (quick, generated filename) and `node_atlas.export_as`
      ([`ExportHelper`](https://docs.blender.org/api/current/bpy_extras.io_utils.html#bpy_extras.io_utils.ExportHelper)).
- [ ] Filename pattern `{blend}_{tree}_{date}.png`, sanitization, default directory
      (`//` or configured), collision handling.
- [ ] Panel: Export Current Tree, Export As…, `output_dpi`, `padding`, `max_mp`, scope,
      background (theme), estimated size, `D_max` warning, Advanced section.
- [ ] Global defaults in `NodeAtlasPreferences` + per-run overrides + "Use defaults".
- [ ] Header button, View menu, context menu, File > Export, `Ctrl+Shift+E`; all removed
      on unregister.
- [ ] Error popup includes exception, stage and an explicit "UI restored" statement;
      success reports path, pixels and elapsed time.
- [ ] State/undo regression: cancel mid-capture, induced failure at every stage, undo
      sentinel after a full export.

**Exit:** one-click export on 5.3; cancel/error leave a pristine editor; undo sentinel
passes; no preferences saved; panel values survive restart.

**Estimate:** 3–4 days.

---

### M5 — All tree types and Compositor (`0.6.0`)

**Goal:** the same pipeline for Shader, Geometry Nodes, Compositor and Texture.

Tasks:

- [ ] Map editor mode → tree type; support Material/World/Light shader trees, any
      `GeometryNodeTree`, compositor group, texture tree.
- [ ] Compositor 5.3:
      [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group),
      `show_backdrop = False`,
      [`NodeGroupOutput`](https://docs.blender.org/api/current/bpy.types.NodeGroupOutput.html);
      add a small version adapter for 6.0 deprecations.
- [ ] Detect asset-shelf/header region heights **after** switching the tree type and
      crop them from every tile; recompute per run.
- [ ] GN interface warning (missing output socket) without blocking capture.
- [ ] Selected-only across all tree types; compositor + asset-shelf combination.
- [ ] Build a Texture Nodes fixture if one is missing; verify or document caveat.
- [ ] Tests: `scene_graphs` (GN/Compositor), `selected_gn_comp_test`, cross-run
      determinism, two tree switches in one session.

**Exit:** clean PNGs for Shader, GN, Compositor, Texture; no footer/backdrop/context
path; selected-only works; repeated runs produce identical geometry and, on one machine,
identical pixels.

**Estimate:** 2–3 days.

---

### M6 — Blender 4.2–5.1 adapter (`0.6.0`)

**Goal:** meet the 4.2+ support promise.

Tasks:

- [x] [`screenshot_area`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area)
      adapter: temporary PNG/TIFF, force PNG/Image settings, restore
      `scene.render.image_settings`, crop the header; determine actual region size per
      version instead of assuming.
- [x] Loading/saving fallback: [`bpy.data.images`](https://docs.blender.org/api/current/bpy.types.BlendData.html#bpy.types.BlendData.images)
      with `Non-Color` + `pixels.foreach_get` for reading a legacy screenshot;
      NumPy PNG writer for saving.
- [x] Capability detection module (`hasattr`, `bpy.app.version`) used only at the adapter
      boundary.
- [x] Re-run geometry, selected-only, state-restore and undo suites on 4.2 LTS, 4.5 LTS
      and 5.1.
- [x] Document version-specific limitations and anything not reproducible.

**Exit:** at least 4.2/4.5 and 5.1 pass the geometry/state/undo suites on Windows; if a
build is unavailable, 1.0.0 either waits or the release notes downgrade that version to
"untested" — no silent claims.

**Estimate:** 3–4 days, plus access to builds.

---

### M7 — Hardening and limits (`0.7.0`)

**Goal:** no known crash, silent corruption or state loss in realistic edge cases.

Tasks:

- [x] Fault injection at every state: missing region/window, area closed mid-export,
      stale references, failed screenshot, locked output file, disk full (simulated).
      A lost area after the snapshot, an injected capture failure, a locked target and
      an injected ENOSPC save are covered by GUI/unit tests; missing contexts are
      guarded by `poll` and by re-acquiring `area`/`region` every stage.
- [x] Large graphs: 100 and 1000 nodes; 100+ MP; memmap path; performance report.
      1000 nodes produce 75.8 MP at 96 dpi and 118.1 MP at 120 dpi (10.9–19.3 s).
- [x] Extreme density: `D_min`, `D_max` at `view.ui_scale` 1/2/6; padding 0 and 120;
      `view.ui_scale` restore after forced high-D export.
- [x] Multiple windows and multiple Node Editor areas: pick one deterministically and
      guard against the others changing.
- [x] Unicode/odd tree and file names; long paths; read-only directories.
- [x] Full state/undo suite across variants: fullscreen, hidden UI, temp tree, induced
      exception, theme override, `ui_scale` change, selection change.
- [x] Verify no preference save anywhere; document the crash-recovery caveat for
      `view.ui_scale` (Blender saves preferences only on a normal quit; a hard crash
      can leave the export-time scale unsaved or persisted from an earlier save).

**Exit:** all fault/limits tests pass or have a documented, user-visible guard; no
unrestored-state failures; undo-neutral on every tested version.

**Estimate:** 3–4 days.

---

### M8 — Packaging, docs and QA matrix (`0.8.0`)

**Goal:** a release candidate that can be installed by someone who has never seen the repo.

Tasks:

- [x] Validate and build the extension
      ([`extension validate/build`](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html));
      install from the zip on a clean profile; also test classic add-on installation.
- [x] README: install (both methods), usage, settings, supported versions, limitations
      (GUI-only, link LOD, view restore to nearest pixel), troubleshooting, license.
- [x] Add 2–3 small screenshots and one example output; keep them compressed and
      committed intentionally. Skipped by decision on 12 November 2026: the README is
      text-only and no binary assets are committed.
- [ ] CHANGELOG, version bump, SPDX/license headers, remove debug code.
      Changelog, SPDX headers and debug cleanup are done; the 0.8.0 bump happens at
      release.
- [x] QA matrix runs: 4.2 LTS / 4.5 LTS / 5.1 / 5.2 / 5.3; Windows full; Linux/macOS
      where available; scaling 100/125/150/200 %; one and two monitors.
      Windows 4.2–5.3 and effective scales 1.0–2.0 pass on the available single monitor;
      Linux/macOS are documented as untested and a second monitor is unavailable.
- [ ] Optional CI: headless unit tests + manifest validation + `ruff`/`compileall`;
      GUI capture remains a manual/virtual-display job. Not added: the repository has no
      remote and the current release is validated locally.
- [x] Commit a QA report with environment, measurements, known issues.

**Exit:** release candidate installs from the artifact, README instructions work
verbatim, QA report committed, no open blocker.

**Estimate:** 3–5 days.

---

### M9 — 1.0.0 release

**Goal:** tag and publish.

Tasks:

- [ ] Feature freeze; only fixes.
- [ ] Final regression on the release artifact, not the dev install.
- [ ] Confirm manifest/version/license/metadata; rebuild from a clean tree.
- [ ] Create annotated tag `v1.0.0` on the version-bump commit; verify the tag matches
      `blender_manifest.toml` and `__version__`.
- [ ] Write release notes with validated platforms and limitations.
- [ ] Publish to the [Blender extensions platform](https://extensions.blender.org/)
      (or attach both artifacts) only with explicit user approval.

**Exit:** the definition in §1 is satisfied and the tagged commit reproduces the tested
artifact.

**Estimate:** 1–2 days.

---

## 6. Test strategy

### 6.1 Tiers

1. **Headless unit (no capture):** view math, layout, bounds, selected-tree semantics,
   stitcher on synthetic arrays, version/feature detection. Run with
   `blender --background --factory-startup --python tests/unit/test_core.py`
   ([`--background` docs](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)).
2. **Headless fixture (no capture):** load fixtures, collect node bounds, verify
   expected layout/size for known scenes. This catches most geometry regressions
   without a GUI.
3. **Live GUI integration:** real capture, stitch, save, restore. Driven by a timer
   runner; writes `result.json` and exits Blender. This is the gate for every capture
   or state change.
4. **Manual platform matrix:** OS scaling, monitors, Linux/macOS, extension install.

### 6.2 Core assertions

- final size `= ceil(content) + 2·padding` (within rounding);
- coverage `wsum > 0` everywhere; `holes = 0`;
- padding band is real background; no frame/scrollbar/asset-shelf pixels;
- overlap diff after cropping: mean < 0.1 (expect ≈0);
- node positions vs model ≤2 px;
- `upp` error after normalization < 0.2 %;
- density ratios at `D = 0.5/0.75/1/2` match theory;
- repeated exports with `view_all` priming: 0 differing pixels on the same machine;
- state snapshot equality after success, cancel and induced exception;
- view restored within ~1 px and 0.03 % `upp`;
- undo sentinel removed by Undo, restored by Redo;
- no `*.blend1`, temp images or preference writes left behind.

### 6.3 Fixtures and baselines

- Import the existing `scene_*.blend` fixtures; if any is missing, recreate it from the
  archived `make_scene_*.py` and record the recipe.
- Store expected **metrics** (size, grid, margins, positions, hashes) as JSON, not large
  golden PNGs. Keep one small reference image per tree type for visual review.
- Baselines are machine-specific for pixels; geometry baselines are portable.

### 6.4 CI

Capture cannot run in a normal headless CI. Add CI for `compileall`, unit tests, manifest
validation and a headless fixture suite. Optional Linux GUI job under Xvfb is a stretch
goal, not a release blocker.

---

## 7. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Temp prototypes/fixtures disappear | Lose evidence and test scenes | Archive them in M0, commit fixtures |
| 4.2–5.1 API differs from 5.3 | Legacy support slips | Adapter boundary + early M6; no silent claims |
| Blender 6.0 compositor changes | Future breakage | Version adapter for tree pointer/output node |
| UI restore fails on exceptions | User loses layout/work | Central snapshot/restore, fault injection in M7 |
| Memory blow-up at high `D` | Crash/OOM | Pre-capture `max_mp`, memmap, clear limits |
| Asset-shelf height varies | Footer leaks into PNG | Runtime region detection + per-run crop |
| GPU/font differences | Pixel tests flaky across machines | Assert geometry; pixels only locally |
| Scope creep (batch/transparent/SVG) | 1.0.0 delayed | Explicitly out of scope; revisit in 1.1 |
| Multi-window/area closing | Undefined behavior | Deterministic area selection + guards |
| Long links fade | Visual limitation | Document; do not attempt to fix |
| [GPL](https://www.gnu.org/licenses/gpl-3.0.html)/competitor code | License violation | Original code; report references only |

---

## 8. Open decisions (defaults proposed)

1. **Batch all groups in 1.0.0?** Report §6.5 defers it to v2, while §8 lists "group
   batch" under v1.0. **Proposed default:** defer to 1.1; 1.0.0 ships single-tree and
   selected-only export. This keeps the primary panel and QA matrix small.
2. **Transparent background in 1.0.0?** §11.14 recommends opaque for the MVP.
   **Proposed default:** theme + solid color in 1.0.0; two-background matting and
   chroma-key behind an experimental flag in 1.1.
3. **Texture Nodes release gate?** **Proposed default:** include if verification passes;
   otherwise ship with a documented caveat rather than blocking 1.0.0.
4. **Platform gate.** **Proposed default:** Windows 4.2–5.3 fully validated; Linux/macOS
   validated where hardware is available and stated honestly in the release notes.
5. **Distribution.** **Proposed default:** publish to the Blender extensions platform
   and attach a classic add-on zip to the release.

Decisions 1–2 are the only ones that materially change the milestone list.

---

## 9. Estimates and dependency graph

```text
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M7 ──► M8 ──► M9
                              │                 ▲
                              └──► M6 ──────────┘
```

| Milestone | Version | Focus | Dev days |
|---|---|---|---|
| M0 | 0.1.0 | Foundation, fixtures, harness | 1–2 |
| M1 | 0.2.0 | Geometry, bounds, selected-only | 2–3 |
| M2 | 0.3.0 | Capture engine (5.2+) | 3–5 |
| M3 | 0.4.0 | Stitch and save | 2–3 |
| M4 | 0.5.0 | Operator/UI, end-to-end MVP | 3–4 |
| M5 | 0.6.0 | Tree types + Compositor | 2–3 |
| M6 | 0.6.0 | Legacy 4.2–5.1 | 3–4 |
| M7 | 0.7.0 | Hardening, limits, fault injection | 3–4 |
| M8 | 0.8.0 | Packaging, docs, QA matrix | 3–5 |
| M9 | 1.0.0 | Release | 1–2 |
| **Total** | | | **23–35** |

M6 can run in parallel with M5 once M4 is stable. M8's platform passes need external
builds and hardware and are the most likely source of calendar variance.

---

## 10. Release checklist (1.0.0)

- [x] Manifest validates; version matches `__version__`; license/metadata correct.
- [x] Clean-profile install from the built artifact (extension and classic add-on).
- [x] Full GUI regression on the artifact, not the dev tree.
      `test_artifact.py` exported and restored the editor from the installed extension
      on all five versions; the full GUI suite ran on the tagged source tree.
- [x] Geometry/state/undo suites green on every claimed version.
- [x] README install/usage instructions verified from scratch.
- [x] CHANGELOG and known limitations published.
- [x] No debug prints, no temp files, no saved preferences.
- [x] Annotated tag `v1.0.0` points at the version-bump commit; tag, manifest and
      `__version__` agree.
- [x] Tag `v1.0.0` is local (not pushed); the built artifact and
      [`RELEASE_NOTES.md`](RELEASE_NOTES.md) are ready, publishing awaits explicit
      approval.
