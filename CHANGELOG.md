# Changelog

## 0.6.0

- Add a legacy `screenshot_area` capture path for Blender 4.2–5.1.
- Add a NumPy PNG writer for the legacy save path (no color-management round-trip).
- Add frame-aware absolute node positions for Blender versions without
  `Node.location_absolute`.
- Add Texture Node Editor export coverage.
- Add GUI tests for Texture, cancel, injected capture failure and the legacy path.
- Guard Compositor export on Blender 4.2–5.1: those builds crash natively during
  capture, so NodeAtlas now reports a clear error instead.
- Validate the legacy Shader/Geometry Nodes/Texture path on Blender 4.2.23 LTS.
- Test cancel, failure recovery and undo neutrality on Blender 4.2 and 5.3.
- Keep the deterministic repeat test at zero differing pixels on both versions.
- Validate a 120-node graph and the max-MP guard on Blender 4.2 and 5.3.
- Validate Unicode filename sanitization and a classic clean-profile install.
- Update the implementation plan, README and QA report.

## 0.5.0

- First MVP: current-tree and selected-nodes export to one PNG.
- Tiled `WINDOW` capture, overlap stitching, real-background padding, top-anchored crop.
- `output_dpi` density normalization independent of monitor and zoom.
- Shader, Geometry Nodes and Compositor trees.
- Timer-driven progress, `Esc` cancel, full editor state restore and undo neutrality.
- Global preferences and Node Atlas sidebar panel.
- Extension manifest and build validation.
