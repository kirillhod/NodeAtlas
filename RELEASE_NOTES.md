# NodeAtlas 1.4.0

**Released:** 19 November 2026

NodeAtlas exports any Blender node tree as one high-resolution PNG with real editor
background padding, selected-nodes support, `Esc` cancellation and full UI restoration.
It captures the Node Editor in overlapping tiles and stitches them with
[NumPy](https://numpy.org/doc/stable/); nothing is re-rendered and no external
dependencies are needed.

## What's new in 1.4.0

- **Compositor export no longer crashes on Blender 4.2–5.1.** All four tree types work on
  every supported version.
- **Selected nodes from a Compositor tree need Blender 5.1 or newer.** On 4.2 and 4.5 the
  export stops with a clear message instead of crashing or exporting the whole tree.
- **The node outline no longer lands in the padding**, so the background band stays clean
  at every UI scale.
- **Padding is set in units** — 1 unit is 1 px at 96 DPI — so the margin keeps the same
  proportion to the graph at any Output DPI. At 96 DPI the result is unchanged; the
  default 20 units is 27 px at the default 128 DPI.

## Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees.
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
- Very long links may fade; Blender offers no public setting to disable link level of
  detail.
- The view returns to the nearest pixel; the tree, the interface and the selection are
  restored exactly.
- No transparent background, batch export, SVG or JSON output, or headless capture.
- **Copy to Clipboard** depends on Blender's image clipboard support and OS limits; very
  large images may be rejected or slow to paste. Normal file exports are unaffected.
