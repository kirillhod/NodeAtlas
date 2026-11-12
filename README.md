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

> **Status:** research and validation are complete
> ([Blender 5.3.0](https://developer.blender.org/docs/release_notes/5.3/)); the add-on
> is not implemented yet. The full design, measurements and pitfalls are in
> [`NodeGraph_Export_Report.md`](NodeGraph_Export_Report.md).

## Planned features

- One PNG for the whole graph, including nodes outside the visible area
- Output density independent of monitor DPI and zoom (`output_dpi`, 96 = 1:1)
- Real background padding captured from the editor, not painted
- Selected-nodes-only export
- Shader, Geometry Nodes and Compositor trees
- Clean frame: UI panels, gizmos, selection and context path hidden during export
- Full editor state restoration, including on failure
- Undo-neutral: the capture pipeline never pushes an undo step
- [Blender 4.2+](https://www.blender.org/download/) (fast raw-buffer path on 5.2+)

## Requirements

- [Blender 4.2](https://www.blender.org/download/) or newer
- A GUI session ([Blender cannot capture UI in `--background`](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html))

## Development

The repository currently contains the specification and the implementation roadmap
([`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)). Implementation notes, conventions
and verified constraints are in [`AGENTS.md`](AGENTS.md). Planned source layout:

```text
node_atlas/
├─ __init__.py
├─ operators.py
├─ capture.py
├─ bounds.py
├─ stitch.py
├─ preferences.py
└─ blender_manifest.toml
```

## Author

[kirillhod](https://github.com/kirillhod)

## License

[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html). See [`LICENSE`](LICENSE).
