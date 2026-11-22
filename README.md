<p align="center"><img src="docs/images/featured-small.png" alt="Node Atlas" width="480"></p>

Exports any Blender node tree as one high-resolution PNG — Shader, Geometry Nodes,
Compositor or Texture, the whole graph, on the real editor background or on a transparent
one.

`Blender 4.2+` · `GPL-3.0-or-later` · `Windows tested`

![A whole shader tree in one 5068 × 2506 PNG](docs/images/example-export.png)

## What it does

| Capability | Detail |
| --- | --- |
| **Whole graph** | Captures the editor in tiles and stitches them; nodes outside the view are included |
| **Density** | Output DPI sets the size (96 = 1:1, default 128); monitor DPI and zoom do not matter |
| **Padding** | Captured, not painted, in units: 1 unit = 1 px at 96 DPI, so 20 units = 27 px at 128 DPI |
| **Transparent Background** | Off by default; removes the editor background and the padding. Every tile is captured twice, so the export takes about twice as long |
| **Preview** | Optional dashed rectangle and size label for the capture area, off by default; the export hides it automatically |
| **Scope** | Current tree, or selected nodes through a temporary copy that leaves your file intact; links to directly connected nodes can stay visible |
| **Output** | PNG file or clipboard; `Esc` cancels; the sidebar opens the last export |
| **Safety** | Max Megapixels 200 stops before capture; DPI clamps are reported |
| **Undo** | No undo step is added; editor, selection and view are restored after success, error or cancel |

> [!NOTE]
> During export the editor is maximized and the graph scrolls while tiles are captured; the
> interface scale may rise for dense output. Everything is restored afterwards.

## Use

Press `N` in a Node Editor → **Node Atlas** → **Export Current Tree**, **Export As…** or
**Copy to Clipboard**. The dashed frame over the graph shows the exported rectangle with
its estimated size and padding; turn on **Show Capture Area** to see it.
Turn on **Transparent Background** to drop the editor background and the padding.

<p align="center"><img src="docs/images/panel.png" alt="Node Atlas panel" width="240"></p>

## Install

| | |
| --- | --- |
| **Extension** | **Edit → Preferences → Extensions → Install from Disk…**, then pick `node_atlas-*.zip` from [Releases](https://github.com/kirillhod/NodeAtlas/releases) |
| **Classic** | Copy `node_atlas/` into `scripts/addons/` and enable it in **Add-ons** |

From source: `blender --command extension build --source-dir node_atlas`.

## Limits

- **GUI only.** `--background` cannot capture the editor.
- **No batch export or SVG/JSON output.**
- **Linux, macOS and a second physical monitor are untested.** Windows: 4.2.23, 4.5.9,
  5.1.2, 5.2.4, 5.3.0.
- **Selected Compositor nodes need Blender 5.1+.**
- **View returns to the nearest pixel;** the clipboard may refuse very large images.
- **The capture shows the editor as it is drawn.** A node row under the pointer keeps its
  hover highlight, so park the pointer outside the graph for a clean export.
- **Transparent Background** hides the backdrop grid while it captures and dims the editor
  once per pass. The PNG keeps straight alpha: viewers show a checkerboard, and a clipboard
  paste may flatten it onto white or black.

## Settings and defaults

| Setting | Default |
| --- | --- |
| Output DPI | `128` (96 = 1:1) |
| Padding | `20` units |
| Transparent Background | Off (about twice the export time when on) |
| Max Megapixels | `200` |
| Scope | Current Tree |
| Keep Links to Connected Nodes | Off (Selected Nodes scope only) |
| Show Capture Area | Off |
| Default Directory | Desktop (home if absent); `~` is expanded |
| Filename Pattern | `{blend}_{tree}_{date}.png`, plus `{datablock}` and `{type}` |
| Hide UI, Header Buttons | On |
| Advanced, quick export shortcut | Off |

## Troubleshooting

| Message | Fix |
| --- | --- |
| Output directory … is not writable | Choose a writable folder |
| Not enough free disk space | Free space on the destination drive |
| DPI clamped from X to Y | Lower Output DPI or raise Blender's UI scale |
| Output would be … above the N MP limit | Raise Max Megapixels or lower Output DPI |
| Node Editor is too small for export | Enlarge the Node Editor |
| `no image clipboard support` or `clipboard copy returned …` | Lower Output DPI or save to a file |
| No application could open … | Install a PNG viewer, or check that `xdg-open` exists on Linux |
| Could not measure the background step | Retry the export; report it if it repeats |

## Development

The add-on is plain Python with no third-party packages, and `node_atlas/` works both as
an extension and as a classic add-on. Tests: [`tests/README.md`](tests/README.md).
Architecture and measured facts: [`NodeGraph_Export_Report.md`](NodeGraph_Export_Report.md).
Scope: [`ROADMAP.md`](ROADMAP.md). Agent workflow: [`AGENTS.md`](AGENTS.md).

Regenerate the panel and demo images with
`blender --factory-startup --python docs/make_images.py`.

---

[Changelog](CHANGELOG.md) ·
[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html) ·
[Issues](https://github.com/kirillhod/NodeAtlas/issues)
