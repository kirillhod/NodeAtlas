# NodeAtlas live GUI check

NodeAtlas captures the Node Editor's `WINDOW` region, so `--background` cannot verify the
pipeline. Unit tests are headless; every capture, stitch, and restore claim needs a real
window. This is the verification procedure behind `AGENTS.md` §7.

## 1. Blender binary

Use the version under test and set it once per shell. Never commit a local path:

```powershell
$env:BLENDER = 'blender'      # or the full path to blender.exe
& $env:BLENDER --version
```

Windows is the validated platform; 4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4 LTS and 5.3.0 are
the matrix. Linux and macOS are untested; a new platform starts with §2. The Compositor is
guarded on 4.2-5.1.

## 2. First run on a new platform

A new OS becomes supported only after this section passes and the run is recorded in
[`QA_REPORT.md`](../../QA_REPORT.md). The package has exactly two platform branches, both
in `preferences.py`: the XDG desktop file on Linux and the OneDrive desktop on Windows.
Everything else is Blender or Python API, so a failure here is about pixels, scale or
window management, not about file paths. The open questions behind the list are report §7
items 3 and 16.

The wrappers in `tests/` are Windows convenience scripts; the tests do not depend on them.
On Linux or macOS run Blender directly, as every GUI test documents in its docstring. On
macOS the binary is inside the app bundle:

```bash
blender --factory-startup --python tests/gui/test_export.py
```

Work in this order and stop at the first failure:

1. **Install and export once.** The zip installs as an extension and the folder as a classic
   add-on; the panel appears and one Shader export finishes with a PNG.
2. **Screenshot size.** `capture.py` rejects a frame whose length is not
   `width * height * 4` for the `WINDOW` region (`Screenshot has N bytes, expected M`); the
   4.2-5.1 path compares `image.size` instead (`screenshot_area width ... != WINDOW width`).
   A Retina backing buffer at 2x the logical region would trip the first check. Do not relax
   it: print both sizes and treat the mismatch as the finding.
3. **Effective UI scale.** `job.py` (`ExportJob._measure`) reads `system.ui_scale` after a
   redraw and assumes
   it already includes `view.ui_scale`. `system.ui_scale` cannot be changed from RNA, so set
   the OS scaling, restart Blender, then export the same fixture at two scales and check
   that the node corners stay within 2 px and `D` stays constant. On macOS the Retina factor
   may live outside `system.ui_scale`, which would move every position by that factor; this
   is the check that catches it.
4. **Edge decorations.** `bounds.py` crops `max(16, ceil(8 * view.ui_scale))` per side and
   keeps an overlap of `max(120, 2 * pad + 32)`, both capped by the region's short side and
   sized for the scrollbar and frame measured in report §5 items 3 and 24. A theme with
   thicker edges puts them into the overlap: the seam difference rises above 0.1 and a band
   appears at the outer padding. Re-measure before changing the constants; the numbers
   belong in the report.
5. **Window management.** A capture needs a visible, unoccluded window, and maximizing
   through `screen_full_area`, leaving it, and retrying with a fresh area are all
   window-manager behaviour. Confirm that the layout, view and selection are restored after
   success, cancel and an injected exception, and that the window is not left maximized.
   Delete the Node Editor area during an export: `view.ui_scale` and `view.smooth_view` must
   still return to their saved values, because Blender writes them on a normal quit.
6. **Clipboard.** Copy is its own action (`copy_only`, plus the separate Copy operator) and
   goes through `bpy.ops.image.clipboard_copy`, which needs a clipboard owner and can fail
   on Wayland or a minimal session. A failure must surface as a reported error with the UI
   restored, and a normal file export on the same machine must stay unaffected.
7. **Transparent Background.** It changes the user's theme, so check what the user sees:
   the backdrop switches from black to mid-grey once per pass, never to white, and the grid
   is hidden for the capture. After success, cancel and an induced failure, `space.back` and
   `grid_levels` must be exactly what they were, and nothing may be written to the
   preferences. Compare the alpha: the padding is 0, nodes are 255, shadows and frames are
   partial, and compositing the PNG over the theme colour reproduces an opaque export. A
   warm theme with a coloured background is the useful second case.
8. **Interrupted export.** Quit Blender while an export is running, then start it again: the
   sidebar offers **Restore Editor Settings**, and it returns the theme background, grid,
   link tint, **Resolution Scale** and view animation. `test_recovery.py` covers the
   lost-area and marker paths without killing the process; do the manual quit once per
   platform.

Record the platform as its own row in [`QA_REPORT.md`](../../QA_REPORT.md): Blender version,
OS and its scaling, `WINDOW` region size, `D`, `padding_px`, grid, tile size, and the
invariants in §6. A new platform does not inherit the Windows results. Then continue with
the normal procedure from §3.

## 3. Fast loop

One GUI test with a wall-clock limit and an isolated `TEMP`:

```powershell
powershell -File tests/run_blender.ps1 -Blender $env:BLENDER `
  -Script tests/gui/test_export.py -TimeoutSec 120
```

The unit suite is headless:

```powershell
powershell -File tests/run_blender.ps1 -Blender $env:BLENDER `
  -Script tests/unit/test_core.py -Background
```

The smoke tier runs the eight cross-cutting GUI tests on one version:

```powershell
powershell -File tests/run_matrix.ps1 -Tier smoke -Blender "5.3.0=$env:BLENDER"
```

The wrapper prints `DONE (0)` or `TIMEOUT ...` and the last log lines. It removes its
isolated temp folder. A direct `blender --python` run can leave a `blender_*` folder in
`%TEMP%`; clean it up yourself. After a successful run the wrapper samples exported PNGs
and exits 2 for a blank or single-colour image; see
[`tests/README.md`](../../tests/README.md#matrix-runner) for the thresholds.

Fixtures are generated, not committed. Generate them with Blender 4.2 first so later
versions can open them; see [`tests/fixtures/README.md`](../../tests/fixtures/README.md).

## 4. Which test

Use the task map in [`context-map.md`](context-map.md). Run the focused GUI test while
iterating, then the unit suite plus every affected GUI test before claiming a change is
done. `tests/run_affected.ps1` selects the affected set from the diff, and
`run_matrix.ps1 -Only`/`-Group` run that set explicitly; the full five-version matrix is a
release check, not an iteration loop. The canonical test inventory is
[`tests/README.md`](../../tests/README.md); do not copy the list into a new file.

`-UserConfig` is only for installed-artifact tests (`test_artifact.py`), which must run
without `--factory-startup` so the add-on or extension is enabled from a clean profile.

## 5. Reading a result

The wrapper writes the full log to `%TEMP%\nodeatlas_logs`. Filter it:

```powershell
Get-Content $log | Select-String -Pattern 'NodeAtlas|PASS|FAIL|Error|Traceback|Saved'
```

A test passes only when it prints its own verdict and exits 0. A clean Blender quit is
not a pass; the wrapper enforces this and exits 3 with `NO PASS VERDICT` when Blender
exits 0 without a test result. Paste the command, the Blender version, and the verdict;
do not paste the whole log.

## 6. Geometry and artifact checks

The tests assert the report invariants. When you need the numbers yourself, print them
instead of opening the image:

```powershell
Add-Type -AssemblyName System.Drawing
$image = [System.Drawing.Image]::FromFile("$env:TEMP\export.png")
"$($image.Width)x$($image.Height) @ $($image.HorizontalResolution) dpi"
$image.Dispose()
```

For a capture or stitch change also confirm:

- size `ceil(content) + 2 * padding_px`, where
  `padding_px = round(padding_units * used_dpi / 96)`;
- `holes = 0`;
- the outer padding is real background with no frame or scrollbar strip;
- overlap mean absolute difference below 0.1;
- node corners within 2 px of the model;
- editor, tree, group path, selection and view restored after success, cancel, and an
  injected exception;
- the undo sentinel is unchanged.

`test_export.py` and `test_large.py` check the padding and opaque pixels from the
final PNG through `tests/gui/png_content.py`; `test_ui_options.py` covers the `hide_ui`
branch, and both visible and hidden exports must restore the full editor state. For the
capture-area preview, `test_preview.py` requires the drawn rectangle to equal the computed
bounds and compares two exports with the overlay on and off: they must match pixel for
pixel.

Only view an image when a visual decision (padding, feather, theme, text) depends on it;
an image costs thousands of tokens.

## 7. Before claiming done

- Unit suite passes.
- The smoke matrix passes on the primary Blender version.
- Every affected GUI test passes on the primary Blender version.
- Repeatability (`test_repeat.py`) and state restoration (`test_group.py`,
  `test_artifact.py`) pass when capture or restore changed.
- For a release, run `tests/run_matrix.ps1 -Tier full -RequireClean` on the five-version
  matrix, keep the `-SummaryJson` file and record the result in
  [`QA_REPORT.md`](../../QA_REPORT.md). A `TREE CHANGED` line means the run is not evidence.
- `git status` is clean of fixtures, captures, `dist/`, `*.blend1` and `__pycache__/`.
- The final message names the tests run and their verdicts; the full matrix is only
  claimed when it was actually run and recorded in [`QA_REPORT.md`](../../QA_REPORT.md).
