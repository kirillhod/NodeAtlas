# NodeAtlas 1.4.0 release notes

**Release date:** 19 November 2026

NodeAtlas exports any Blender node tree as one high-resolution PNG with real editor
background padding, selected-nodes support, `Esc` cancellation and full UI restoration.
It captures the Node Editor in overlapping tiles and stitches them with
[NumPy](https://numpy.org/doc/stable/); no re-rendering and no external dependencies.

## Changes since 1.3.6

- **Compositor export works on Blender 4.2–5.1.** Pinning a compositor tree crashed those
  versions on the next area refresh; the tree now stays unpinned there, and the version
  guard is gone.
- **Selected-nodes compositor export needs Blender 5.1+.** On 4.2/4.5 a filtered copy
  cannot be shown without the crashing pin, so the export stops with a clear message
  instead of a crash or the whole tree.
- **The node outline stays out of the padding.** A visual margin follows
  `ceil(2.5 × UI scale)` around the node bounds, so the outline no longer lands in the
  background band.
- **Padding is density-independent.** The value is now in units (1 unit = 1 px at
  96 DPI) and scales with Output DPI, so the margin keeps the same proportion to the
  graph at any density. At 96 DPI nothing changes; the default 20 is 27 px at the
  default 128 DPI.

## Validated platforms

| Blender | OS | Capture path | Result |
|---|---|---|---|
| 5.3.0 | Windows 10 22H2 | `Window.screenshot` | PASS, Shader/GN/Compositor/Texture |
| 5.2.4 LTS | Windows 10 22H2 | `Window.screenshot` | PASS, Shader/GN/Compositor/Texture |
| 5.1.2 | Windows 10 22H2 | `screenshot_area` | PASS, Shader/GN/Compositor/Texture |
| 4.5.9 LTS | Windows 10 22H2 | `screenshot_area` | PASS, Shader/GN/Compositor/Texture |
| 4.2.23 LTS | Windows 10 22H2 | `screenshot_area` | PASS, Shader/GN/Compositor/Texture |

The extension installs and exports on all five versions through the official installer,
and the same package works as a classic add-on on all five. The host had two 2048×1152
displays at 125% OS scale; GUI tests ran on the primary display. Effective UI scales
1.0/1.25/1.5/2.0 were covered through Resolution Scale (`view.ui_scale`), because
`system.ui_scale` follows the OS.

## Features

- Current-tree or selected-nodes export for Shader, Geometry Nodes, Compositor and
  Texture trees; selected-nodes compositor export needs Blender 5.1+.
- Output density independent of monitor DPI and zoom (`output_dpi`, 96 = 1:1).
- Real background padding captured from the editor, not painted, in density-independent
  units.
- Full editor state restoration after success, error or cancel.
- Undo-neutral: the capture pipeline never pushes an undo step.
- Timer-driven progress and `Esc` cancellation.
- Guarded output: read-only directories and full disks fail before capture with a clear
  message.

## Known limitations

- GUI only; `--background` cannot capture the editor.
- **Linux and macOS are untested.** No Linux distribution is installed under WSL and no
  Mac hardware is available. The code path is platform-neutral, but there is no QA
  record.
- **A second physical monitor is untested.** Two Blender windows on the primary display
  are covered.
- **Selected-nodes compositor export requires Blender 5.1+.** Exporting the whole
  compositor tree works on 4.2 and newer.
- Very long links may fade; Blender exposes no public setting to disable link LOD.
- The view is restored to the nearest pixel (`View2D.cur` is not exposed); tree, UI and
  selection restoration is exact.
- Transparent background, batch export, SVG/JSON and headless capture are deferred.
- **Copy to Clipboard** depends on Blender's image clipboard support and OS limits;
  very large images may be rejected or slow to paste. Normal file exports are unaffected.
- No screenshots or example images are committed; the README is text-only by decision.

## Verification

- Unit suite: 19/19 on Blender 4.2.23, 4.5.9, 5.1.2, 5.2.4 and 5.3.0.
- Live GUI suite: 32/32 runs per version on all five versions (30 tests plus the 120 dpi
  and maximized-group variants): export, legacy adapter, selected nodes, selected
  compositor, padding units, all tree types, Texture, determinism, cancel, injected
  failure, 120-node, max-MP, density, scaling, Dmax, multi-area, multi-window, 1000 nodes
  at 118 MP, limits, read-only, disk-full, lost area, estimate invariance, naming +
  DPI metadata, clipboard and path prompting.
- Release artifact: extension install and GUI export on all five versions, and classic
  add-on install and export on all five.
- Full measurements and known issues are in [`QA_REPORT.md`](QA_REPORT.md).

The tag is local; nothing was pushed. Publishing to the
[Blender extensions platform](https://extensions.blender.org/) requires explicit
approval.
