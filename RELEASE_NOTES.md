# Node Atlas 1.6.1

**Released:** 22 November 2026

Node Atlas exports any Blender node tree as one high-resolution PNG: the whole graph in a
single image, with the real editor background and padding.

### What's new in 1.6.1

- **Home folders now work.** A folder written as `~/Pictures` was kept relative on Linux
  and macOS, so the PNG landed in a folder literally named `~`. Both the quick export and
  **Export As** now expand it to your home directory.
- **The editor is always restored.** The **Restore UI** option is gone: every export puts
  the sidebar, toolbar, header, gizmo and node selection back, including exports that hide
  the interface while capturing. No mode is left that can keep panels hidden.
- **A full quota reads as a full disk.** Linux and macOS report an exhausted quota as a
  generic write error; it now says the disk is full, like Windows does.
- **Cmd on macOS.** The quick-export shortcut now uses Cmd, the key macOS users expect,
  and the preference is labelled **Cmd**.
- **Clearer errors.** **Open Last Export** says when the system has no application for the
  PNG instead of doing nothing, and a hand-edited Linux `user-dirs.dirs` with `${HOME}` or
  escaped spaces now yields the right default folder.

### Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees.
- Optional links to the nodes directly connected to the selection.
- Capture-area preview that shows the exported rectangle and its estimated size.
- Output density independent of monitor DPI and current zoom: 96 DPI is 1:1 with node
  pixels.
- Real background padding captured from the editor, not painted.
- Full editor state restored after success, error or cancel.
- Undo-neutral: an export never adds an undo step.
- Timer-driven progress and `Esc` cancellation.
- Read-only folders and full disks are reported before capture starts, not after.

### Supported versions

Blender **4.2 and newer**. Version 1.6.0 was checked on 4.2.23 LTS, 4.5.9 LTS, 5.1.2, 5.2.4
LTS and 5.3.0; the 1.6.1 changes were checked on 5.3.0 only. Shader, Geometry Nodes,
Compositor and Texture trees are covered.

### Known limitations

- GUI only: `--background` cannot capture the editor.
- **Linux and macOS are untested.** The code does not depend on the platform, but there is
  no test record for either. The `~`, quota, `Cmd` and folder fixes above are reasoned from
  the APIs, not from a run on those systems.
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

### Verification

The 1.6.1 zip was installed on Blender 5.3.0 through the official extension installer and
also as a classic add-on, and exported a real PNG in both cases.

### Install

1. Download `node_atlas-1.6.1.zip` below.
2. In Blender open **Edit → Preferences → Extensions**.
3. Use **Install from Disk…**, choose the zip and enable **Node Atlas**.

Requires Blender 4.2 or newer. The same zip also works as a classic add-on.
