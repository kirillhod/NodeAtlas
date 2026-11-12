# NodeAtlas

Export any [Blender](https://www.blender.org/) node tree —
[Shader](https://docs.blender.org/manual/en/latest/editors/shader_editor.html),
[Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html),
[Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html),
[Texture](https://docs.blender.org/manual/en/latest/editors/texture_node/index.html) —
as a single high-resolution PNG.

NodeAtlas captures the
[Node Editor](https://docs.blender.org/manual/en/latest/interface/controls/nodes/node_editors.html)
in overlapping tiles, stitches them into one seamless image, and saves it without
external dependencies. Output density is controlled independently of the monitor and
current zoom.

> **Status: 1.2.0.** Current-tree and selected-nodes export work for Shader,
> Geometry Nodes, Compositor and Texture. Blender 5.2+ uses the raw screenshot path;
> Blender 4.2–5.1 uses the legacy path for Shader/GN/Texture (validated on 4.2.23,
> 4.5.9 and 5.1.2; Compositor is guarded because of a native 4.2–5.1 crash). The
> Windows 4.2–5.3 matrix, 118 MP exports, output-path guards and clean installs pass.
> Linux, macOS and a second monitor are untested. See [`RELEASE_NOTES.md`](RELEASE_NOTES.md).
> See [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

## Features

- One PNG for the whole graph, including nodes outside the visible area
- Output density independent of monitor DPI and zoom (`output_dpi`, 96 = 1:1)
- Real background padding captured from the editor, not painted
- Selected-nodes-only export using a temporary filtered tree copy
- Shader, Geometry Nodes, Compositor and Texture trees
- Clean frame: UI panels, gizmos, selection and context path hidden during export
- Full editor state restoration, including after an error or cancel
- Undo-neutral: the capture pipeline never pushes an undo step
- **Copy to Clipboard** button that exports without writing a file
- PNG density metadata (`pHYs`) matches the effective DPI
- Timer-driven progress and `Esc` cancellation

## Requirements

- [Blender 4.2](https://www.blender.org/download/) or newer; 5.2+ uses the faster
  raw-buffer capture, 4.2–5.1 uses the `screenshot_area` adapter
- A GUI session ([Blender cannot capture UI in `--background`](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html))

Validated on Windows with Blender 4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4 LTS and 5.3.0.
Linux and macOS are untested. The Compositor requires Blender 5.2+.

## Install

Classic add-on (development):

1. Copy or junction the `node_atlas/` folder into Blender's `scripts/addons/`.
2. Enable **Node Atlas** in *Edit → Preferences → Add-ons*.

Extension build:

```powershell
blender --command extension build --source-dir node_atlas
```

Install the resulting zip through *Edit → Preferences → Extensions*.

## Usage

1. Open any Node Editor (Material, Geometry Nodes, Compositor, Texture).
2. Press `N` and open the **Node Atlas** sidebar tab.
3. Use **Export Current Tree**, **Export As…**, **Copy to Clipboard**, or
   `Ctrl+Shift+E`.
4. Press `Esc` to cancel a running export; the editor is restored afterwards.

Settings live in the sidebar and in *Edit → Preferences → Add-ons → Node Atlas*. If
Default Directory is empty, **Export Current Tree** opens the file dialog instead of
writing to a temporary folder; **Export As…** always asks for a path; **Copy to
Clipboard** exports directly to the system clipboard without saving a file. The default
pattern is `{blend}_{tree}_{date}.png`.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| Output DPI | 96 | Output density; 96 = 1:1 node pixels. Clamped to the achievable range |
| Padding (px) | 20 | Real editor background around the graph, in final-image pixels |
| Max Megapixels | 200 | Abort before capture when the output would exceed this size |
| Scope | Current Tree | Export the displayed tree or only selected nodes |
| Background | Theme | Editor theme background (solid color is planned) |
| Default Directory | empty | Quick-export folder; empty opens the file dialog |
| Filename Pattern | `{blend}_{tree}_{date}.png` | Fields: `{blend}`, `{tree}`, `{datablock}`, `{type}`, `{date}` |
| Hide UI During Export | on | Hide header, toolbar, sidebar, gizmos and context path |
| Restore UI | on | Restore the editor state after success, error or cancel |
| Deterministic View | on | Prime with View All so repeated exports match |
| Header Button | on | Show the quick export button in the Node Editor header |
| Ctrl+Shift+E | on | Enable the quick export shortcut |

`{tree}` uses the owning datablock name (material, world, light, object, scene or
texture) and falls back to the tree name; `{datablock}` is always the raw tree name and
`{type}` is `Shader`, `Geometry_Nodes`, `Compositor` or `Texture`. Whitespace in token
values becomes `_`, and unknown tokens fall back to `{blend}_{tree}_{date}.png`.

Output pixel size depends on `output_dpi` and the graph, not on monitor resolution or
window size: a smaller editor only needs more tiles. Changing the effective UI scale can
move the result by a few pixels because Blender lays out nodes in whole pixels; the
`test_scaling.py` GUI test keeps that variation within 15 px from 1.0 to 2.0 effective
scale.

## Troubleshooting

- **"NodeAtlas requires a GUI Blender session"** — start Blender normally; UI capture
  is unavailable under `--background`.
- **"Compositor export on Blender 4.2–5.1 is not supported yet"** — those builds crash
  natively during compositor capture. Use Blender 5.2 or newer.
- **"Output directory … is not writable"** — choose a writable folder; the check runs
  before any capture starts.
- **"Not enough free disk space"** — free space on the destination volume; the temporary
  PNG is removed.
- **"DPI clamped from X to Y"** — `D_max = effective_ui_scale / 0.43311`; lower Output
  DPI or increase the UI scale. The PNG `pHYs` metadata reports the effective DPI.
- **"Output would be … above the N MP limit"** — raise Max Megapixels if RAM allows, or
  lower Output DPI.
- **"Node Editor is too small for export"** — enlarge the editor area.
- **Clipboard copy failed** — the clipboard export reports an error; normal file
  exports are unaffected. The OS may reject very large images; try a lower Output DPI
  or smaller padding.
- **Blank or overlapped tiles** — keep the Blender window visible and unobstructed
  during export; a minimized or occluded window can break screenshots.

## Known limitations

- GUI only; `--background` cannot capture the editor.
- Blender 4.2–5.1 uses the legacy `screenshot_area` adapter (validated on 4.2.23,
  4.5.9 and 5.1.2 for Shader/GN/Texture); 5.2+ uses the raw screenshot path.
- Compositor export on Blender 4.2–5.1 is blocked by a native Blender crash and shows
  a clear error; use 5.2+ for the Compositor.
- Very long links may fade; Blender has no public setting to disable link LOD.
- The view is restored to the nearest pixel (`View2D.cur` is not exposed).
- Linux and macOS were not tested; the code path is platform-neutral, but only Windows
  has a QA record.
- Transparent background and batch export are planned after 1.0.

## Development

The validated research prototypes are in [`reference/prototypes/`](reference/prototypes/);
fixture generators are in [`tests/fixtures/`](tests/fixtures/). Design notes, measured
constraints and conventions are in [`AGENTS.md`](AGENTS.md). Release history and tested
environments are in [`CHANGELOG.md`](CHANGELOG.md) and [`QA_REPORT.md`](QA_REPORT.md).

Run the headless core tests:

```powershell
blender --background --factory-startup --python tests/unit/test_core.py
```

Generate fixtures and run the live GUI tests:

```powershell
blender --background --factory-startup --python tests/fixtures/make_scene_uniq.py
blender --background --factory-startup --python tests/fixtures/make_scene_small.py
blender --background --factory-startup --python tests/fixtures/make_scene_both.py
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
blender --factory-startup --python tests/gui/test_naming.py
blender --factory-startup --python tests/gui/test_clipboard.py
blender --factory-startup --python tests/gui/test_path.py
blender --python tests/gui/test_artifact.py
```

`test_artifact.py` exports with an installed add-on or extension; run it against a
clean profile without `--factory-startup` so the desired install is loaded.

`tests/run_blender.ps1` wraps a GUI test with a wall-clock timeout, kills a stuck
Blender, and prints the tail of its log. It runs Blender with an isolated `TEMP` and
removes that folder afterwards, so session directories and test PNGs do not accumulate.
It is a Windows convenience; the test scripts also run directly:

```powershell
powershell -File tests/run_blender.ps1 -Blender <blender.exe> `
  -Script tests/gui/test_export.py -TimeoutSec 120
```

Set `NODEATLAS_TEST_DPI=120` for the 118 MP variant of `test_1000.py`. Direct
`blender --python` runs can leave a `blender_*` session folder in `%TEMP%`; the wrapper
removes its isolated copy automatically.

Source layout:

```text
node_atlas/
├─ __init__.py          # registration, menus, panel, keymap
├─ operators.py         # export operators and timer job
├─ capture.py           # snapshot/restore, view control, tiled capture
├─ bounds.py            # view metrics, bounds, layout, selected-only copy
├─ stitch.py            # canvas, feathering, top crop, PNG save
├─ preferences.py       # global defaults
├─ log.py               # namespaced logger
└─ blender_manifest.toml
```

## Author

[kirillhod](https://github.com/kirillhod)

## License

[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html). See [`LICENSE`](LICENSE).
