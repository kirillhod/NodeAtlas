# Node Atlas 1.7.0

**Released:** 22 November 2026

Node Atlas exports any Blender node tree as one high-resolution PNG: the whole graph in a
single image, with the real editor background and padding.

### What's new in 1.7.0

- **Transparent background.** Turn on **Transparent Background** and the editor background
  is removed from the export, including the padding, so the PNG drops straight onto any
  colour in a slide, document or mock-up. Node shadows, anti-aliased text and links keep
  their real alpha instead of being cut out with a colour key.
- **Nothing else changes in the image.** The matting is solved from two captures of the
  same tile; composited back over the editor background, the result matches a normal export
  to a mean of 0.05 and a maximum of 2.8 of 255. Node shadows and semi-transparent frames
  keep their real alpha. The option is in the sidebar and in **Export As**.
- **No white flash.** The editor darkens for one capture pass and lightens for the second,
  instead of switching colour for every tile; the theme and the backdrop grid come back
  when the export ends.
- **The capture-area preview is off by default.** Enable **Show Capture Area** in the
  sidebar if you want the dashed rectangle and its size label.
- **What it costs.** Every tile is captured twice, once over black and once over mid-grey,
  so a transparent export takes about twice as long as an opaque one. Memory use is
  unchanged.

### Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees.
- Optional links to the nodes directly connected to the selection.
- Capture-area preview that shows the exported rectangle and its estimated size.
- Output density independent of monitor DPI and current zoom: 96 DPI is 1:1 with node
  pixels.
- Real background padding captured from the editor, not painted, optionally transparent.
- Full editor state restored after success, error or cancel.
- Undo-neutral: an export never adds an undo step.
- Timer-driven progress and `Esc` cancellation.
- Read-only folders and full disks are reported before capture starts, not after.

### Supported versions

Blender **4.2 and newer**. Version 1.7.0 was checked on 4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4
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
- **Copy to Clipboard** depends on Blender's image clipboard support and OS limits; very
  large images may be rejected or slow to paste. Normal file exports are unaffected.
- No batch export, SVG or JSON output, or headless capture.

### Verification

The 1.7.0 zip was installed on every supported Blender version through the official
extension installer and also as a classic add-on, and exported a real PNG in each case.
The transparent export is covered by its own live test, which requires transparent padding,
opaque nodes, partial alpha on shadows and an exactly restored theme.

### Install

1. Download `node_atlas-1.7.0.zip` below.
2. In Blender open **Edit → Preferences → Extensions**.
3. Use **Install from Disk…**, choose the zip and enable **Node Atlas**.

Requires Blender 4.2 or newer. The same zip also works as a classic add-on.
