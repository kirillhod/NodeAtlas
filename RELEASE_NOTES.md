# NodeAtlas 1.3.3 release notes

**Release date:** 13 November 2026
**Artifact:** `node_atlas-1.3.3.zip` (Blender extension) and the same package as a
classic add-on.

NodeAtlas exports any Blender node tree as one high-resolution PNG with real editor
background padding, selected-nodes support, `Esc` cancellation and full UI restoration.
It captures the Node Editor in overlapping tiles and stitches them with
[NumPy](https://numpy.org/doc/stable/); no re-rendering and no external dependencies.

## Changes since 1.3.2

- Capture the active tree and nested group path when the export is requested; a context
  reset before the timer runs no longer exports the root tree.
- Re-enter groups through Blender's group-edit operator and re-apply the path after view
  restoration, so the path survives redraws.
- **Open Last Export** is now a small icon in the Settings header, not a full-width
  button; it no longer shifts the panel and overlaps Estimated/Advanced.

## Changes since 1.3.1

- Exporting from a nested node group now restores the path even when the Node Editor was
  already maximized, and leaves the maximized layout alone.
- A successful save shows **Open Last Export** in the sidebar; Blender's status-line
  report itself is not clickable.

## Changes since 1.3.0

- Exporting from inside nested node groups now restores the complete edit path instead
  of jumping back to the main tree.
- **Copy to Clipboard** is the first action in the panel, header and menu.
- The Export Current Tree tooltip names the **Default Directory** from **Advanced**.

## Changes since 1.2.1

- All three export actions are available in the Node Editor header.
- **Advanced** is a collapsible subpanel with folder and filename settings first.
- The quick-export shortcut is off by default; pick the key and modifiers yourself.
- The **Export As** dialog shows the main export settings instead of "No Properties".
- Quick exports go to the **Desktop** by default on Windows, macOS and Linux; clearing
  the folder asks for a path.
- Default Output DPI is **128**; Max Megapixels is documented as a safety limit.

## Changes since 1.2.0

- The panel **Estimated** size now uses the filtered selection in **Selected Nodes**
  mode; previously it showed the whole-tree size.

## Changes since 1.1.0

- **Copy to Clipboard** is now a dedicated button next to **Export Current Tree** and
  **Export As…**. It exports directly to the clipboard without writing a file; the
  previous preference toggle was removed.

## Changes since 1.0.0

- Saved PNGs now carry `pHYs` metadata with the effective DPI (96 dpi reports 96, not
  imbuf's 72), and the fixed 72-dpi EXIF block is removed.
- The panel **Estimated** size no longer depends on the current zoom and matches the
  exported PNG.
- `{tree}` in the filename pattern now uses the owning material/world/light/object/
  scene/texture name; `{datablock}` and `{type}` were added, and whitespace becomes `_`.
- Optional **Copy to Clipboard** puts the saved PNG on the system clipboard.
- An empty **Default Directory** opens the file dialog instead of writing to a
  temporary folder.

## Validated platforms

| Blender | OS | Capture path | Result |
|---|---|---|---|
| 5.3.0 | Windows 10 22H2 | `Window.screenshot` | PASS |
| 5.2.4 LTS | Windows 10 22H2 | `Window.screenshot` | PASS |
| 5.1.2 | Windows 10 22H2 | `screenshot_area` | PASS for Shader/GN/Texture |
| 4.5.9 LTS | Windows 10 22H2 | `screenshot_area` | PASS for Shader/GN/Texture |
| 4.2.23 LTS | Windows 10 22H2 | `screenshot_area` | PASS for Shader/GN/Texture |

The 1.3.3 artifact exported a PNG as an extension on Blender 4.2.23 and 5.3.0 and as a
classic add-on on all five versions. On 4.5.9, 5.1.2 and 5.2.4 the local builds'
`--command extension` Python runtime is incomplete, so the same zip payload was
validated through the classic install path. Unit tests are 16/16 on
all five versions. The host had two 2048×1152 displays at 125% OS scale; GUI tests ran
on the primary display. Effective UI scales 1.0/1.25/1.5/2.0 were covered through
Resolution Scale (`view.ui_scale`), because `system.ui_scale` follows the OS.

## Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees.
- Output density independent of monitor DPI and zoom (`output_dpi`, 96 = 1:1).
- Real background padding captured from the editor, not painted.
- Full editor state restoration after success, error or cancel.
- Undo-neutral: the capture pipeline never pushes an undo step.
- Timer-driven progress and `Esc` cancellation.
- Guarded output: read-only directories and full disks fail before capture with a clear
  message.

## Install

Extension:

```powershell
blender --command extension build --source-dir node_atlas
```

Install `node_atlas-1.0.0.zip` through *Edit → Preferences → Extensions*.

Classic add-on: copy the `node_atlas/` folder into Blender's `scripts/addons/` and enable
**Node Atlas** in *Edit → Preferences → Add-ons*.

Press `N` in any Node Editor and open the **Node Atlas** tab. The quick export shortcut is
`Ctrl+Shift+E`; settings live in the sidebar and add-on preferences.

## Known limitations

- GUI only; `--background` cannot capture the editor.
- **Linux and macOS are untested.** No Linux distribution is installed under WSL and no
  Mac hardware is available. The code path is platform-neutral, but there is no QA
  record.
- **A second physical monitor is untested.** Two Blender windows on the primary display
  are covered.
- **Compositor on Blender 4.2–5.1 is blocked.** Those builds crash natively during
  compositor capture; NodeAtlas reports a clear error. Use Blender 5.2+ for the
  Compositor.
- Very long links may fade; Blender exposes no public setting to disable link LOD.
- The view is restored to the nearest pixel (`View2D.cur` is not exposed); tree, UI and
  selection restoration is exact.
- Transparent background, batch export, SVG/JSON and headless capture are deferred.
- **Copy to Clipboard** depends on Blender's image clipboard support and OS limits;
  very large images may be rejected or slow to paste. Normal file exports are unaffected.
- No screenshots or example images are committed; the README is text-only by decision.

## Verification

- `blender --background --factory-startup --python tests/unit/test_core.py`: 16/16 on
  4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0.
- Live GUI suite: export, legacy adapter, selected nodes, all tree types, Texture,
  determinism, cancel, injected failure, 120-node, max-MP, density, scaling, Dmax,
  multi-area, multi-window, 1000 nodes at 118 MP, limits, read-only, disk-full, lost
  area, estimate invariance, owner naming + DPI metadata, clipboard and path prompting.
- Release artifact: extension install on all five versions and classic install on 5.3.0
  with a GUI export from the installed module.
- Full measurements and known issues are in [`QA_REPORT.md`](QA_REPORT.md).

The tag is local; nothing was pushed. Publishing to the
[Blender extensions platform](https://extensions.blender.org/) requires explicit
approval.
