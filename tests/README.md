# Tests

NodeAtlas has headless unit tests and live-GUI tests. The GUI tests need a real
Blender window; `--background` cannot capture the UI.

## Headless unit tests

```powershell
blender --background --factory-startup --python tests/unit/test_core.py
```

Covers view metrics, layout/bounds, density clamping, stitching and memmap spill, PNG
writing and `pHYs` metadata, save errors, output-path checks, selected-node filtering,
filename tokens and registration.

## Fixtures and GUI tests

Generate the `.blend` fixtures with Blender 4.2 first; they open in later versions:

```powershell
blender --background --factory-startup --python tests/fixtures/make_scene_uniq.py
blender --background --factory-startup --python tests/fixtures/make_scene_small.py
blender --background --factory-startup --python tests/fixtures/make_scene_both.py
```

Then run the GUI tests:

```powershell
blender --factory-startup --python tests/gui/test_export.py
blender --factory-startup --python tests/gui/test_legacy.py
blender --factory-startup --python tests/gui/test_selected.py
blender --factory-startup --python tests/gui/test_trees.py
blender --factory-startup --python tests/gui/test_texture.py
blender --factory-startup --python tests/gui/test_repeat.py
blender --factory-startup --python tests/gui/test_cancel.py
blender --factory-startup --python tests/gui/test_fail.py
blender --factory-startup --python tests/gui/test_large.py
blender --factory-startup --python tests/gui/test_maxmp.py
blender --factory-startup --python tests/gui/test_density.py
blender --factory-startup --python tests/gui/test_scaling.py
blender --factory-startup --python tests/gui/test_extreme.py
blender --factory-startup --python tests/gui/test_multiarea.py
blender --factory-startup --python tests/gui/test_multiwindow.py
blender --factory-startup --python tests/gui/test_1000.py
blender --factory-startup --python tests/gui/test_limits.py
blender --factory-startup --python tests/gui/test_readonly.py
blender --factory-startup --python tests/gui/test_diskfull.py
blender --factory-startup --python tests/gui/test_arealost.py
blender --factory-startup --python tests/gui/test_estimate.py
blender --factory-startup --python tests/gui/test_estimate_selected.py
blender --factory-startup --python tests/gui/test_group.py
blender --factory-startup --python tests/gui/test_boost.py
blender --factory-startup --python tests/gui/test_naming.py
blender --factory-startup --python tests/gui/test_clipboard.py
blender --factory-startup --python tests/gui/test_path.py
blender --python tests/gui/test_artifact.py
```

`test_artifact.py` exports with an installed add-on or extension; run it against a
clean profile without `--factory-startup`. Set `NODEATLAS_TEST_DPI=120` for the 118 MP
variant of `test_1000.py`, and `NODEATLAS_TEST_MAXIMIZE=1` for the already-maximized
group-editing variant of `test_group.py`.

## Hang-safe runner

`tests/run_blender.ps1` runs one GUI test with a wall-clock limit, kills a stuck
Blender, and uses an isolated `TEMP` folder that is removed afterwards:

```powershell
powershell -File tests/run_blender.ps1 -Blender <blender.exe> `
  -Script tests/gui/test_export.py -TimeoutSec 120
```

Use `-UserConfig` for installed-artifact tests and `-Background` for unit tests. Direct
`blender --python` runs can leave a `blender_*` session folder in `%TEMP%`; the wrapper
removes its isolated copy automatically.

Results from the full Windows matrix are in [`QA_REPORT.md`](../QA_REPORT.md).
