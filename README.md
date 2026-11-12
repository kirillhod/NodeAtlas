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

> **Status: 0.6.1.** Current-tree and selected-nodes export work for Shader,
> Geometry Nodes, Compositor and Texture. Blender 5.2+ uses the raw screenshot path;
> Blender 4.2–5.1 uses the legacy path for Shader/GN/Texture (validated on 4.2.23,
> 4.5.9 and 5.1.2; Compositor is guarded because of a native 4.2–5.1 crash). The
> Windows 4.2–5.3 matrix and clean installs pass. M7–M9 hardening and packaging remain.
> See [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

## Features

- One PNG for the whole graph, including nodes outside the visible area
- Output density independent of monitor DPI and zoom (`output_dpi`, 96 = 1:1)
- Real background padding captured from the editor, not painted
- Selected-nodes-only export using a temporary filtered tree copy
- Shader, Geometry Nodes and Compositor trees
- Clean frame: UI panels, gizmos, selection and context path hidden during export
- Full editor state restoration, including after an error or cancel
- Undo-neutral: the capture pipeline never pushes an undo step
- Timer-driven progress and `Esc` cancellation

## Requirements

- [Blender 4.2](https://www.blender.org/download/) or newer; 5.2+ uses the faster
  raw-buffer capture, 4.2–5.1 uses the `screenshot_area` adapter
- A GUI session ([Blender cannot capture UI in `--background`](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html))

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
3. Use **Export Current Tree**, **Export As…**, or `Ctrl+Shift+E`.
4. Press `Esc` to cancel a running export; the editor is restored afterwards.

Settings live in the sidebar and in *Edit → Preferences → Add-ons → Node Atlas*. The
quick action uses the `.blend` folder and the `{blend}_{tree}_{date}.png` pattern by
default.

## Known limitations

- GUI only; `--background` cannot capture the editor.
- Blender 4.2–5.1 uses the legacy `screenshot_area` adapter (validated on 4.2.23 for
  Shader/GN/Texture); 5.2+ uses the raw screenshot path.
- Compositor export on Blender 4.2–5.1 is blocked by a native Blender crash and shows
  a clear error; use 5.2+ for the Compositor. Blender 4.5/5.1 QA is still pending.
- Very long links may fade; Blender has no public setting to disable link LOD.
- The view is restored to the nearest pixel (`View2D.cur` is not exposed).
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
```

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
