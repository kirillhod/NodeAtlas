# Node Atlas 1.7.2

**Released:** 24 November 2026

Node Atlas exports any Blender node tree as one high-resolution PNG: the whole graph in a
single image, with the real editor background or a transparent one.

### What's new in 1.7.2

- **A lost Node Editor no longer leaks editor settings.** If the editor area disappears
  during an export — its type changes, another file opens, the window closes — the export
  now still returns Blender's **Resolution Scale** and the view animation. Before, a normal
  quit could save the temporary values, leaving the whole interface larger and the animated
  view switched off.
- **Restore Editor Settings.** If Blender is closed while an export is running, the Node
  Atlas sidebar offers one button on the next start. It puts back the node background, the
  grid, the selected-link tint, **Resolution Scale** and the view animation from before the
  export. Nodes, links and the tree are left alone, and the button appears only when
  something still differs.

1.7.2 is a patch for 1.7.1: the exported PNG and the existing controls are unchanged.

### Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes and Texture trees, and
  the whole Compositor tree.
- Optional links to the nodes directly connected to the selection.
- Capture-area preview that shows the exported rectangle and its estimated size.
- Transparent background: the editor background and the padding are removed, while shadows,
  links and semi-transparent frames keep their real alpha.
- Output density independent of monitor DPI and current zoom: 96 DPI is 1:1 with node
  pixels.
- Real background padding captured from the editor, not painted, optionally transparent.
- Full editor state restored after success, error or cancel.
- Undo-neutral: an export never adds an undo step.
- Timer-driven progress and `Esc` cancellation.
- Read-only folders and full disks are reported before capture starts, not after.

### Supported versions

Blender **4.2 and newer**. Version 1.7.2 was checked on 4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4
LTS and 5.3.0, with Shader, Geometry Nodes, Compositor and Texture trees.

### Known limitations

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
- **Transparent Background** writes straight alpha into the PNG. Viewers show it on a
  checkerboard, and a clipboard paste may flatten it onto white or black.
- **The capture shows the editor as it is drawn**, so a node row under the pointer keeps
  its hover highlight; park the pointer outside the graph for a clean export.
- **Copy to Clipboard** depends on Blender's image clipboard support and OS limits; very
  large images may be rejected or slow to paste. Normal file exports are unaffected.
- No batch export, SVG or JSON output, or headless capture.
- **Restore Editor Settings** restores appearance preferences only; it does not bring back
  nodes, links, the view or a file that was closed during the export.
