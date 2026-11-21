# NodeAtlas 1.6.0

**Released:** 21 November 2026

NodeAtlas exports any Blender node tree as one high-resolution PNG with real editor
background padding, selected-nodes support, `Esc` cancellation and full UI restoration.
It captures the Node Editor in overlapping tiles and stitches them with
[NumPy](https://numpy.org/doc/stable/); nothing is re-rendered and no external
dependencies are needed.

## What's new in 1.6.0

- **See the capture before it starts.** The Node Editor draws a dashed rectangle around
  the area that will be exported and labels it with the estimated size, megapixels,
  density and padding. For Selected Nodes it also shows the node count. The rectangle
  follows the graph when nodes move and stays correct when you zoom.
- **The label matches the file.** Both the outline and its numbers use the same estimate
  as the sidebar, so the PNG is the size the frame promised.
- **Never in the image.** The preview disappears for the whole export, so no outline or
  text can land in a tile. **Show Capture Area** in the sidebar turns it off if you prefer
  a clean editor.

## Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees.
- Capture-area preview with the estimated size, density and padding before the export.
- Optional links to the nodes directly connected to the selection.
- Output density independent of monitor DPI and current zoom: 96 DPI is 1:1 with node
  pixels.
- Real background padding captured from the editor, not painted.
- Full editor state restored after success, error or cancel.
- Undo-neutral: an export never adds an undo step.
- Timer-driven progress and `Esc` cancellation.
- Read-only folders and full disks are reported before capture starts, not after.

## Supported versions

Blender **4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4 LTS and 5.3.0** on Windows, with Shader,
Geometry Nodes, Compositor and Texture trees. Each version was tested with the extension
installed through the official installer and with the classic add-on.

## Known limitations

- GUI only: `--background` cannot capture the editor.
- **Linux and macOS are untested.** The code does not depend on the platform, but there is
  no test record for either.
- **A second physical monitor is untested.** Two Blender windows on the primary display
  work.
- **Selected nodes from a Compositor tree need Blender 5.1+.** Exporting the whole
  compositor tree works on 4.2 and newer.
- A connected node that lies inside the selected area is drawn with its links; the toggle
  keeps the links to the nearest node only, not the whole connected graph.
- The view returns to the nearest pixel; the tree, the interface and the selection are
  restored exactly.
- No transparent background, batch export, SVG or JSON output, or headless capture.
- **Copy to Clipboard** depends on Blender's image clipboard support and OS limits; very
  large images may be rejected or slow to paste. Normal file exports are unaffected.
