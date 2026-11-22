# Node Atlas 1.7.1

**Released:** 22 November 2026

Node Atlas exports any Blender node tree as one high-resolution PNG: the whole graph in a
single image, with the real editor background or a transparent one.

### What's new in 1.7.1

- **No stray selection outlines.** When Blender's interface **Resolution Scale** was set to
  anything other than 100 %, nodes and frames that were fully inside the capture could be
  drawn as selected, leaving their highlight and frame tint in the PNG. The export now
  measures node positions the same way the editor draws them, so the temporary selection
  used to keep long links at full strength always stays outside the captured tiles.
- **Deterministic View is gone.** Every export now primes the view with **View All**, so
  repeated exports of the same graph are pixel-identical. The option was in the sidebar and
  in **Export As**, and nothing needs to be enabled in its place.

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

Blender **4.2 and newer**. Version 1.7.1 was checked on 4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4
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
