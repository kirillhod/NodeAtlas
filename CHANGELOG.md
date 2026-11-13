# Changelog

## 1.3.4

- Keep the collapsible **Advanced** controls inside the Settings box instead of a
  separate child panel, fixing the detached label/background on refresh.
- Pin restored group paths so Blender keeps them across redraws; nested group export no
  longer returns to the main tree.
- Keep **Open Last Export** as a compact Settings icon.

## 1.3.3

- Capture the node tree and group path when the export is requested, so a context
  reset before the timer runs can no longer export the root tree.
- Rebuild nested groups through Blender's group-edit operator and re-apply the path after
  view restoration, which survives redraws.
- Move **Open Last Export** to a small icon in the Settings header, so it no longer
  shifts the panel height or overlaps Estimated/Advanced.

## 1.3.2

- Fix the remaining node-group exit: restore the group path again after leaving
  maximize, and do not toggle an already-maximized editor.
- Add an **Open Last Export** button after a successful save; Blender's status-line
  report itself cannot be made clickable.

## 1.3.1

- Restore the full node-group edit path after export, so exporting from inside nested
  groups no longer returns to the main tree.
- Put **Copy to Clipboard** first in the panel, header and menu; Export Current Tree and
  Export As follow.
- Clarify the Export Current Tree tooltip: it writes to the **Default Directory** from
  **Advanced** and asks for a path when that is empty.

## 1.3.0

- Add **Export As** and **Copy to Clipboard** buttons to the Node Editor header alongside
  the quick export.
- Move **Default Directory** and **Filename Pattern** to the top of a collapsible
  **Advanced** panel.
- Disable the quick-export shortcut by default; choose the key and Ctrl/Shift/Alt in
  **Advanced**.
- Show the main Node Atlas settings inside the **Export As** file dialog.
- Default exports to the user's Desktop, with XDG and OneDrive detection and a home
  fallback.
- Raise the default Output DPI to 128 and explain the Max Megapixels safety limit in the
  UI and README.
- Rebuild the README: compact centered panel screenshot, grouped settings, no author
  section or marketing copy.

## 1.2.1

- Fix the panel estimate in **Selected Nodes** mode: it now measures the filtered
  selection instead of the whole tree, and matches the selected-only export.

## 1.2.0

- Replace the **Copy to Clipboard** preference with a dedicated panel/menu button that
  exports the current tree straight to the clipboard without writing a file.
- Keep normal exports unchanged; they no longer copy implicitly.

## 1.1.0

- Write PNG `pHYs` metadata with the effective DPI and drop imbuf's fixed 72-dpi
  `pHYs`/EXIF so saved files report the requested density.
- Fix the panel size estimate: it now uses the target DPI instead of the current zoom,
  so it is zoom-invariant and matches the exported PNG.
- Resolve filename `{tree}` to the owning material/world/light/object/scene/texture, add
  `{datablock}` and `{type}` tokens, and replace whitespace with `_`.
- Add an optional **Copy to Clipboard** step after a successful export.
- An empty Default Directory now opens the file dialog instead of writing to a temporary
  folder.
- Add estimate, naming, clipboard and path GUI tests; the headless suite is 16/16.

## 1.0.0

- First stable release: current-tree and selected-nodes export for Shader, Geometry
  Nodes, Compositor and Texture as one high-resolution PNG.
- Validate the release artifact as an extension on Blender 4.2.23, 4.5.9, 5.1.2, 5.2.4
  and 5.3.0, and as a classic add-on on 5.3.0.
- Publish the validated-platform scope honestly: Windows only, one physical display,
  and Compositor export limited to Blender 5.2+ because 4.2–5.1 crash natively.
- No behavior changes since 0.8.0.

## 0.8.0

- Add a settings table, supported-version notes and a troubleshooting section to the
  README.
- Add `SPDX-License-Identifier: GPL-3.0-or-later` headers to the package and tests.
- Add a scaling GUI test: effective scales 1.0/1.25/1.5/2.0 in one session, with view
  restore after every export and a size spread guard.
- Validate the extension build and clean classic/extension installs for the release
  candidate.
- Record Windows-only coverage honestly: Linux, macOS and a second physical monitor
  are untested; no screenshots or example assets are committed.

## 0.7.0

- Validate the output directory before capture: missing parents are created, denied
  directories and full disks fail with a clear message and start no job.
- Map write failures to a readable `OutputError`; disk-full saves report "Not enough
  free disk space" instead of a traceback and still remove the temporary PNG.
- Probe writability with a private file instead of `tempfile.mkstemp`, which can loop
  forever on Windows when an ACL denies writes.
- Add unit tests for the preflight, long paths, locked targets and disk-full mapping.
- Add GUI tests for a real ACL read-only directory, injected disk-full, a lost editor
  area after the snapshot, and minimum density with 120 px padding.
- Validate a 118 MP export with 1000 nodes and the memmap path on Blender 4.2–5.3.
- Add `tests/run_blender.ps1`, an optional Windows wrapper that kills a stuck Blender
  after a wall-clock timeout instead of blocking the test loop.

## 0.6.2

- Fix DPI normalization when Resolution Scale is not 1: Blender exposes the effective
  scale in `system.ui_scale` after a UI refresh, so the previous code multiplied the
  resolution scale twice.
- Add an extreme-density GUI test at D_max with `view.ui_scale` 6/4.
- Re-validate high-density and extreme-density output on Blender 4.2–5.3.

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
- Add a 1000-node GUI test; it exercises the memmap path at ~75.8 MP.
- Update the implementation plan, README and QA report.

## 0.5.0

- First MVP: current-tree and selected-nodes export to one PNG.
- Tiled `WINDOW` capture, overlap stitching, real-background padding, top-anchored crop.
- `output_dpi` density normalization independent of monitor and zoom.
- Shader, Geometry Nodes and Compositor trees.
- Timer-driven progress, `Esc` cancel, full editor state restore and undo neutrality.
- Global preferences and Node Atlas sidebar panel.
- Extension manifest and build validation.
