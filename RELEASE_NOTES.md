# NodeAtlas 1.5.1

**Released:** 21 November 2026

NodeAtlas exports any Blender node tree as one high-resolution PNG with real editor
background padding, selected-nodes support, `Esc` cancellation and full UI restoration.
It captures the Node Editor in overlapping tiles and stitches them with
[NumPy](https://numpy.org/doc/stable/); nothing is re-rendered and no external
dependencies are needed.

## What's new in 1.5.1

- **Reroute nodes near a tile edge no longer look selected.** A node that was already in
  the frame could be marked as outside the view for one tile and drawn with the white
  selection outline; the small reroute dots made it easy to see. The tile selection now
  uses the anchored tile position, so the outline appears only on nodes that are really
  outside the image. Connections that cross tiles keep full strength.

## Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees.
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
