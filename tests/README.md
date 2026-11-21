# Tests

NodeAtlas has headless unit tests and live-GUI tests. The GUI tests need a real
Blender window; `--background` cannot capture the UI.

The agent-facing verification loop, evidence rules and cleanup are in
[`docs/agent/live-check.md`](../docs/agent/live-check.md); this file stays the canonical
test inventory.

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
blender --factory-startup --python tests/gui/test_selected_comp.py
blender --factory-startup --python tests/gui/test_padding.py
blender --factory-startup --python tests/gui/test_trees.py
blender --factory-startup --python tests/gui/test_texture.py
blender --factory-startup --python tests/gui/test_repeat.py
blender --factory-startup --python tests/gui/test_longlink.py
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
blender --factory-startup --python tests/gui/test_ui_options.py
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

Tree coverage: Shader Node Tree is the default in most tests; `test_trees.py` covers
Geometry Nodes and the Compositor on every version. On Blender 4.2/4.5 the test leaves
the compositor tree unpinned because pinning it crashes the next area refresh.
`test_selected_comp.py` exports selected compositor nodes on 5.1+ and asserts the clear
refusal on 4.2/4.5 (a filtered copy cannot be pinned there and `Scene.node_tree` is
read-only). `test_texture.py` covers the Texture Node Editor. `test_longlink.py` exports a
link that spans five tiles and requires its middle segment to keep the same brightness as
its ends, with selection, the theme `wire_select` alpha and undo restored.
`test_ui_options.py` covers `hide_ui` and `restore_ui`; `test_export.py`, `test_large.py`
and `test_padding.py` also run `png_content.check_capture` for opaque pixels, real padding
and non-empty content.
`test_padding.py` exports at 192 DPI and requires the 20-unit padding to become 40 px. The
commands above are for debugging; they do not run the runner's PNG content check, so use
the wrapper or the matrix runner when the result is evidence.

## Matrix runner

`tests/run_matrix.ps1` runs a tier of the source tests on one or more Blender versions.
Pass each binary as `version=path`; separate entries with a semicolon:

```powershell
# Fast loop: 8 cross-cutting tests on the primary version.
powershell -File tests/run_matrix.ps1 -Tier smoke `
  -Blender '5.3.0=C:\Blender\5.3\blender.exe'

# Release matrix: 30 tests plus the 120 dpi and maximized variants on five versions.
powershell -File tests/run_matrix.ps1 -Tier full `
  -Blender '4.2.23=C:\Blender\4.2\blender.exe;4.5.9=C:\Blender\4.5\blender.exe;5.1.2=C:\Blender\5.1\blender.exe;5.2.4=C:\Blender\5.2\blender.exe;5.3.0=C:\Blender\5.3\blender.exe'
```

`-Tier smoke` runs `test_export.py`, `test_trees.py`, `test_texture.py`,
`test_selected.py`, `test_repeat.py`, `test_estimate.py`, `test_group.py` and
`test_ui_options.py`. `-Tier full` runs every source GUI test plus the two variants. The
unit suite is not included; run it with `run_blender.ps1 -Background` or directly.

`-Parallel` starts one child matrix per version. This cuts wall-clock time but lets GUI
windows overlap; treat the first parallel run as an experiment. `-IncludeArtifact` adds
`test_artifact.py` with `-UserConfig`, so it uses the current profile and requires the
add-on or extension to be installed; it cannot be combined with `-Parallel`. Before any
case runs, the runner probes every binary with `--background --python-expr` and stops
with a clear error when its embedded Python cannot start.

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

The wrapper requires the test's own `PASS` verdict in the log. A Blender process that
exits 0 without running the test, for example after an embedded-Python startup failure,
is reported as `NO PASS VERDICT` and exits 3.

After a successful run the wrapper samples every exported PNG on a grid of up to 96 by
96 points. A blank or single-colour image passes the size assertions but is not a valid
capture, so the wrapper exits 2 when an output has fewer than 8 sampled colours or less
than 0.2% non-background samples. Use `-SkipContentCheck` to disable this and
`-KeepTemp` to keep the run folder; the wrapper then prints its `TEMP=` path.

Results from the full Windows matrix are in [`QA_REPORT.md`](../QA_REPORT.md).
