# Node Atlas

**[Blender](https://www.blender.org/) add-on that turns any node graph into one clean,
high-resolution PNG.**

No re-rendering, no stitching by hand, no tiny screenshots. Node Atlas captures the whole
[Node Editor](https://docs.blender.org/manual/en/latest/interface/controls/nodes/node_editors.html)
— including the parts outside your current view — and saves a single readable image for
documentation, tutorials, reviews or your portfolio.

![Example export](docs/images/example-export.png)

## What it does

- **The whole graph in one image.** Nodes outside the visible area are captured and
  stitched automatically.
- **Crisp at any size.** Choose an output DPI; the result does not depend on your monitor
  or current zoom.
- **Only what you need.** Export the current tree or just the selected nodes.
- **Works across Blender.** Shader, Geometry Nodes, Compositor and Texture trees.
- **Clean presentation.** UI panels, gizmos and selection are hidden; the background is
  the real editor background, not a painted rectangle.
- **Your file stays untouched.** The editor, tree, selection and view are restored after
  success, error or cancel. No undo steps are added.
- **Copy to Clipboard.** Export straight to the clipboard without saving a file.

## Install

### Blender 4.2 or newer (extension)

1. Download the latest `node_atlas-*.zip` from the repository's **Releases** page.
2. In Blender open **Edit → Preferences → Extensions**.
3. Use **Install from Disk…**, choose the zip and enable **Node Atlas**.

If you work from source, build the zip with
`blender --command extension build --source-dir node_atlas` and install that.

### Classic add-on

Copy the `node_atlas` folder into your Blender `scripts/addons/` directory and enable
**Node Atlas** in **Edit → Preferences → Add-ons**.

## Use

![Node Atlas panel](docs/images/panel.png)

1. Open any Shader, Geometry Nodes, Compositor or Texture Node Editor.
2. Press `N` and open the **Node Atlas** tab.
3. Choose:
   - **Export Current Tree** — save the whole graph using your default folder/name.
   - **Export As…** — pick a file name and location.
   - **Copy to Clipboard** — put the image on the clipboard without writing a file.
4. Press `Esc` to cancel a running export.

If **Default Directory** is empty, **Export Current Tree** opens the file dialog instead
of writing to a temporary folder. `Ctrl+Shift+E` is the quick export shortcut.

## Settings

Settings live in the sidebar and in **Edit → Preferences → Add-ons → Node Atlas**.

| Setting | Default | What it does |
|---|---|---|
| Output DPI | 96 | Output density; 96 = 1:1 node pixels |
| Padding (px) | 20 | Background margin around the graph |
| Max Megapixels | 200 | Stop before capturing an image larger than this |
| Scope | Current Tree | Export everything or only selected nodes |
| Default Directory | empty | Folder for quick exports; empty asks for a path |
| Filename Pattern | `{blend}_{tree}_{date}.png` | How exported files are named |
| Hide UI During Export | on | Hide header, toolbar, sidebar and gizmos |
| Restore UI | on | Restore the editor after success, error or cancel |
| Deterministic View | on | Make repeated exports of the same graph match |
| Header Button | on | Show the quick export button in the Node Editor header |
| Ctrl+Shift+E | on | Enable the quick export shortcut |

The filename pattern supports `{blend}`, `{tree}` (the material, object, scene or texture
that owns the tree), `{datablock}` (the raw tree name), `{type}` and `{date}`. Unknown
fields fall back to the default pattern; spaces become `_`.

## Supported versions

Validated on Windows with Blender **4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4 LTS and 5.3.0**.
The Compositor requires Blender 5.2 or newer. Linux and macOS are untested.

## Good to know

- This is a GUI add-on; it cannot capture the interface with `--background`.
- Keep the Blender window visible and unobstructed while exporting.
- Compositor export on Blender 4.2–5.1 is blocked by a Blender crash and shows a clear
  error instead.
- The view is restored to the nearest pixel; very long links may fade.
- Transparent backgrounds and batch export are planned for later versions.

## Troubleshooting

- **"Output directory … is not writable"** — choose a writable folder.
- **"Not enough free disk space"** — free space on the destination drive.
- **"DPI clamped from X to Y"** — the requested DPI is too high for the current UI
  scale. Lower Output DPI or increase Blender's UI scale.
- **"Output would be … above the N MP limit"** — raise Max Megapixels or lower Output
  DPI.
- **"Node Editor is too small for export"** — enlarge the Node Editor area.
- **Clipboard copy failed** — the OS may reject very large images; try a lower Output DPI.

## Development

Tests and the full test matrix are described in [`tests/README.md`](tests/README.md) and
[`QA_REPORT.md`](QA_REPORT.md). The measured specification and design notes are in
[`NodeGraph_Export_Report.md`](NodeGraph_Export_Report.md), with the roadmap in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) and changes in
[`CHANGELOG.md`](CHANGELOG.md).

The README images can be regenerated with a normal GUI Blender session:

```powershell
blender --factory-startup --python docs/make_images.py
```

## Author

[kirillhod](https://github.com/kirillhod)

## License

[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html). See [`LICENSE`](LICENSE).
