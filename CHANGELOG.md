# Changelog

## 0.6.1

- Spill the stitching accumulator and weights to memmaps when the canvas is large.
- Remove temporary PNG files when the final atomic rename fails.
- Validate the Windows matrix on Blender 4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0.
- Validate clean classic and extension installs across the tested versions.
- Add high-density, 120-node, max-MP, texture, cancel and failure GUI tests.

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
- Validate the legacy path on Blender 4.5.9 LTS and 5.1.2.
- Validate the raw path on Blender 5.2.4 LTS.
- Test cancel, failure recovery and undo neutrality on Blender 4.2, 4.5, 5.1, 5.2 and 5.3.
- Keep the deterministic repeat test at zero differing pixels on both versions.
- Validate a 120-node graph and the max-MP guard on Blender 4.2 and 5.3.
- Validate Unicode filename sanitization and a classic clean-profile install.
- Validate a clean extension install from the built zip.
- Validate high-density export (D=2, zero padding) and extension installs across 4.2–5.3.
- Add memmap spill for large stitch canvases and clean up temporary PNGs on failed saves.
- Validate 0.6.1 clean classic and extension installs on 4.2.23–5.3.0.
- Add a multi-area GUI test: a second Node Editor remains untouched by export/restore.
- Add a multi-window GUI test: export from one window leaves the other unchanged.
- Update the implementation plan, README and QA report.

## 0.5.0

- First MVP: current-tree and selected-nodes export to one PNG.
- Tiled `WINDOW` capture, overlap stitching, real-background padding, top-anchored crop.
- `output_dpi` density normalization independent of monitor and zoom.
- Shader, Geometry Nodes and Compositor trees.
- Timer-driven progress, `Esc` cancel, full editor state restore and undo neutrality.
- Global preferences and Node Atlas sidebar panel.
- Extension manifest and build validation.
