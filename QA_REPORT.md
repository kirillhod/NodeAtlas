# NodeAtlas QA report

**Version:** 0.6.0  
**Date:** 12 November 2026  
**Platforms:** Windows, GUI sessions only

## Environment

| Blender | OS | Role |
|---|---|---|
| 5.3.0 | Windows | Primary development, raw `Window.screenshot` path |
| 4.2.23 LTS | Windows | Legacy `screenshot_area` path, add-on loading |

The fixtures are generated locally by `tests/fixtures/make_scene_*.py` with Blender
4.2.23 so the resulting `.blend` files open in both 4.2 and 5.3. Generated fixtures are
ignored by Git.

## Headless tests

Command:

```powershell
blender --background --factory-startup --python tests/unit/test_core.py
```

| Check | 5.3.0 | 4.2.23 |
|---|---|---|
| View metrics | PASS | PASS |
| Rect/layout math | PASS | PASS |
| Density limits | PASS | PASS |
| Single-tile stitching | PASS | PASS |
| NumPy PNG writer round-trip | PASS | PASS |
| Registration/preferences | PASS | PASS |
| Manifest/`__version__` consistency | PASS | PASS |
| Filename sanitization / Unicode | PASS | PASS |

Result: **8/8 PASS on both versions.**

## GUI tests

Commands are listed in [`README.md`](README.md). Each test starts a visible Blender
window, exports a fixture, validates the PNG and editor restoration, then exits.

| Test | 5.3.0 | 4.2.23 | Notes |
|---|---|---|---|
| `test_export.py` | PASS, 2232×1631 | PASS, 2232×1639 | Shader + sentinel, undo/redo, state restore |
| `test_legacy.py` | PASS, 2232×1631 | PASS | 5.3 forced through the legacy path |
| `test_selected.py` | PASS, 781×413 | PASS, 780×419 | Original tree unchanged |
| `test_trees.py` | PASS, GN 2533×1084, Compositor 2130×896 | PASS, GN 2533×1084; Compositor skipped | 4.2 Compositor is guarded |
| `test_texture.py` | PASS | PASS | Texture Node Editor |
| `test_repeat.py` | PASS, 0 differing pixels | PASS, 0 differing pixels | Deterministic `view_all` priming |
| `test_cancel.py` | PASS, cancelled during capture | PASS, cancelled during capture | UI restored, no PNG |
| `test_fail.py` | PASS | PASS | Injected capture failure, UI restored, no PNG |
| `test_large.py` | PASS, 6017×3131, 18.8 MP, 1.87 s | PASS, 6016×3133, 3.25 s | 120-node graph, state restored |
| `test_maxmp.py` | PASS | PASS | 1 MP guard, no PNG, UI restored |

## Packaging

- `blender --command extension validate node_atlas`: PASS.
- `blender --command extension build --source-dir node_atlas --output-dir dist`:
  produces `node_atlas-0.6.0.zip` with the manifest and package modules.
- Classic add-on clean-profile install: copied `node_atlas/` into an isolated
  `BLENDER_USER_SCRIPTS/scripts/addons`, enabled in a clean profile, version 0.6.0 and
  preferences registered.
- Extension install from the zip on a clean profile and Linux/macOS QA are still pending.

## Known issues

1. **Compositor on Blender 4.2–5.1.** Native Blender crashes with
   `EXCEPTION_ACCESS_VIOLATION` during capture. NodeAtlas detects the version/tree type
   and raises a clear error instead of risking a crash. Use Blender 5.2+ for the
   Compositor.
2. **Blender 4.5 and 5.1** were not available for this QA pass. The 4.2 legacy path is
   shared, but those builds are still marked untested.
3. **macOS/Retina and Linux/X11** were not tested.
4. View restoration is nearest-pixel (`View2D.cur` is not exposed); UI/tree/selection
   restore is exact.
5. Long links may fade; Blender exposes no public setting to disable link LOD.
6. Per-run setting overrides and transparent background are not in 0.6.0.

## Not in scope for 1.0.0

Batch export of all groups, transparent background, SVG/JSON/HTML, headless capture
and AI upscaling are deferred; see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).
