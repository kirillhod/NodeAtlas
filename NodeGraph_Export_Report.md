# NodeAtlas — Exporting Any Blender Node Graph to a Single PNG

**Date:** 12 November 2026 (updated after practical tests)  
**Status:** research complete; the capture pipeline has been validated on a live [Blender 5.3.0](https://developer.blender.org/docs/release_notes/5.3/). **NodeAtlas (working name) has not been written yet** — by agreement, features were designed and verified first: a global padding that preserves the real graph background, monitor-DPI/zoom independence (`output_dpi`), UI placement/state restoration, [Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html)/[Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html) support, and transparent-background prototypes. The add-on code will follow after sign-off.  
**Scope:** 4 existing solutions, the [public Python API](https://docs.blender.org/api/current/) of Blender 4.2–5.3, architecture options, and pitfalls.

**What was done**

- Read the sources of [Node Tree Screenshot](https://codeberg.org/lukas_tonne/node_tree_screenshot) and [PrintNodes](https://github.com/b-init/PrintNodes); reviewed [NodeExporter](https://extensions.blender.org/add-ons/node-exporter/) and [blender-node-export](https://github.com/draberf/blender-node-export);
- verified signatures and version availability against the official API docs ([`Window.screenshot`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot), [`imbuf`](https://docs.blender.org/api/current/imbuf.html), [`screen.screenshot_area`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area), [`Node.dimensions`](https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.dimensions), [`view2d.pan`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.pan));
- built a comparison table of solutions and approaches;
- **validated every critical step on a live [Blender 5.3.0](https://developer.blender.org/docs/release_notes/5.3/)**: region coordinates, row orientation, alpha, `Node.dimensions` accuracy, `imbuf` copying, `view2d.pan` sign/linearity, seams, state restoration; a tiled-export prototype produced a 24-node graph as a single seam-free PNG;
- found and explained the root cause of drifting tiles — the UI scale (see §4.3 and §11.2);
- **validated global padding on the real captured background** (no fill) and **DPI normalization via zoom**, including the maximum achievable density and the `view.ui_scale` bypass (§11.7–§11.11);
- found a critical crop trap that silently removes the top rows of the graph, and a deterministic priming method that makes repeated exports bit-identical (§11.8, §11.10).

**Not verified:** Blender 4.2–5.1 (the [`screenshot_area`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area) fallback), macOS/Retina, Linux/X11, graphs with 1000+ nodes, peak memory, and cross-machine pixel determinism. See §7.

---

## 1. Summary

1. **The task is solvable, but only through UI screenshots.** Blender has no public API that renders a node editor into an offscreen buffer. The practical approach is a tiled capture of the [Node Editor](https://docs.blender.org/manual/en/latest/interface/controls/nodes/node_editors.html)'s `WINDOW` region, stitched into one image.
2. **A direct competitor already exists** — the official [Node Tree Screenshot](https://extensions.blender.org/add-ons/node-tree-screenshot/) extension (Lukas Tönne). It does exactly this but has limitations: Blender 5.1+, bundled [Pillow](https://python-pillow.org/) (17.9 MB), panels leak into the frame, inaccurate node bounds, gaps on long links, no progress/cancel.
3. **Main finding:** Blender **5.2+** exposes [`Window.screenshot(region=..., use_alpha=...)`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot), which returns raw RGBA pixels. This removes temporary PNGs, render-setting mutations, and the mandatory Pillow dependency: capture only the node canvas and stitch with [NumPy](https://numpy.org/doc/stable/) + [`imbuf`](https://docs.blender.org/api/current/imbuf.html).
4. **Recommended path:** tiled raster capture with exact `WINDOW`-region cropping, automatic area maximization/UI hiding, state restoration in `finally`, overlapping tiles with feathering, and a fallback to [`bpy.ops.screen.screenshot_area`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area) for Blender 4.2–5.1. Vector/HTML export is a separate branch, not the MVP: it does not reproduce Blender pixels.
5. **Main pitfall (Blender 5.3, `ui_scale = 1.25`):** [`view2d.view_to_region(node.location)`](https://docs.blender.org/api/current/bpy.types.View2D.html#bpy.types.View2D.view_to_region) **does not** match where the node is actually drawn. Node positions are scaled by the effective UI scale, while [`Node.dimensions`](https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.dimensions) is not scaled by the system part. The error grows with distance from the graph origin. The correct formula is in §4.3; it was verified on 24 nodes to within 1–2 px. Without it, tiled export cannot be assembled.
6. **DPI independence is achieved with zoom, not with system settings.** `system.ui_scale`/`dpi` are read-only, but [`preferences.view.ui_scale`](https://docs.blender.org/api/current/bpy.types.PreferencesView.html#bpy.types.PreferencesView.ui_scale) (Resolution Scale) is **writable** (0.5–6.0). Effective scale `S = system.ui_scale * view.ui_scale`; output density `D` (pixels per node unit) is set by `upp = S/D`. Verified: `D = 0.5…17`, output size independent of the starting view. `D_max = S/0.43311`: 2.886 at `S=1.25`, 5.77 at `view=2`, **17.3 at `view=6`**. Monitor resolution does not cap `D` — only tile count, time, and the practical memory limit.
7. **Global padding is captured, not painted.** The content is anchored at `padding + PAD` from the tile edge, so the `padding` band contains the real graph background (theme color, grid dots), and the outer `PAD` pixels are cropped away. Verified 0/20/40/120 px with `holes = 0`; outer rows/columns match the background (no frame or scrollbar). The active-node outline extends beyond `Node.dimensions`; selection is cleared during export.
8. **Repeatability:** `view2d.reset()` is not deterministic (it preserves the current center). Priming with [`bpy.ops.node.view_all()`](https://docs.blender.org/api/current/bpy.ops.node.html#bpy.ops.node.view_all) before the exact zoom makes repeated full exports **bit-identical** (0 differing pixels), including across processes and with the maximized area.
9. **Ctrl+Space matters.** [`bpy.ops.screen.screen_full_area(use_hide_panels=True)`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screen_full_area) grows the `WINDOW` region from 2100×1170 to 2560×1361: the big scene's grid drops from 3×4 to 2×3 tiles and capture time from 0.46 s to 0.21 s. `D_max` is unchanged. Area/region/space references must be re-acquired after the call.
10. **[Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html) and [Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html) work with the same pipeline (verified).** The editor switches with `space.tree_type = 'GeometryNodeTree' | 'CompositorNodeTree'`, then `space.node_tree = <tree>` and `space.pin = True`. GN: 8 nodes → 2571×1115 PNG (`holes = 0`, padding 40), `D=2` → 5059×2149 (content ≈2×). Compositor: 5 nodes → 2170×936 (`holes = 0`), with `space.show_backdrop = False`. Two separate processes produced **0 differing pixels** for both. In Blender 5.3 the compositor tree is [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group) (deprecated for 6.0); a compositor group uses [`NodeGroupOutput`](https://docs.blender.org/api/current/bpy.types.NodeGroupOutput.html), not `CompositorNodeComposite`.
11. **The UI lives where the user works, and state restoration is verified.** An N-panel (“Node Atlas” tab) plus a header icon, `Ctrl+Shift+E`, and View/Context/File-Export menus; global defaults in `AddonPreferences`. The full area layout, tree/pin, UI flags, selection/active, `ui_scale`, and `smooth_view` are restored exactly, including after an induced exception; the view returns to the nearest pixel (`upp` error 0.000334, center ≈1 px). See §6.5 and §11.13.
12. **Transparent background is not native, but two-background matting works (verified).** `use_alpha=True` is opaque. Capturing the same graph over black and white (sRGB blending; inter-channel α std `0.00032`) gives clean RGBA: background α ≈`5×10⁻⁶`, foreground min `0.9908`, and black/white vs magenta/green alpha agree exactly. Single-key chroma-key is cheaper but approximate: the best key for the test graph (green, no color conflict) still leaves a green fringe (edge ΔRGB G `+21.4`, composite error mean 14.3/255; decontamination 8.9), while magenta/cyan/white/gray keys fail on graph colors. See §11.14.
13. **Selected-nodes-only export works by capturing a temporary filtered copy (verified).** [`nt.copy()`](https://docs.blender.org/api/current/bpy.types.ID.html#bpy.types.ID.copy) + keeping selected nodes (plus descendants of selected frames), unparenting from unselected frames while preserving `location_absolute`, removing the rest, then displaying the temp tree gives a clean image with no unselected nodes inside the crop. Original tree, links, selection, and frames are unchanged (state test PASS); temp tree is removed afterwards. Crop-only leaves unselected nodes in the bbox; hiding in place leaves collapsed/placeholder blocks and shrinks frames. Shader, Geometry Nodes, and Compositor verified. See §11.15.
14. **The capture pipeline does not pollute Undo (verified).** With a user-added node as a sentinel, one Undo removes that node and Redo restores it after: maximize/hide/pan/screenshot, the selected-only temp copy and removal, an induced failure after temp-tree assignment, `view.ui_scale` changes, theme background changes, and selection changes. The operations used are data/UI APIs (no undoable operators, no [`undo_push`](https://docs.blender.org/api/current/bpy.ops.ed.html#bpy.ops.ed.undo_push)). See §11.16.

---

## 2. Existing solutions

### 2.1. Node Tree Screenshot (Lukas Tönne)

- Official extension, [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html), version 1.1.1, 17.9 MB, requires **Blender 5.1+**, roughly 7k downloads at the time of review ([extension page](https://extensions.blender.org/add-ons/node-tree-screenshot/), [source](https://codeberg.org/lukas_tonne/node_tree_screenshot)).
- How it works:
  - computes bounds from `node.location_absolute` + `node.width`/`node.height` + `preferences.system.ui_scale`, with a 30 px margin;
  - calls [`bpy.ops.view2d.reset()`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.reset), then pans across tiles;
  - captures each tile with `bpy.ops.screen.screenshot_area` into a temporary TIFF;
  - stitches with PIL or NumPy and saves in the render format.
- Strengths: proven approach, works in any `NODE_EDITOR`, two stitching methods, carefully restores format/title/context path.
- Weaknesses:
  - panels/toolbar remain in the frame — the author asks users to hide them manually;
  - `node.height` is inaccurate (acknowledged in a code comment), so previews may be cut and extra margins appear;
  - tiles have no overlap, so seams are possible;
  - long links fade in the middle (Blender LOD);
  - no progress/cancel;
  - hard Python-version coupling because of bundled Pillow wheels.
- Takeaway: the closest reference; our add-on should keep its strengths and remove these limitations.

### 2.2. PrintNodes (b-init / Yeetus)

- Old add-on (2.80+), GPL-3.0, tile capture via a modal timer, PIL bundled per OS ([GitHub](https://github.com/b-init/PrintNodes)).
- Useful ideas:
  - automatically hides the grid, scrollbars, and selection highlight through the theme;
  - supports selected-nodes-only;
  - crops empty margins by comparing against the background color;
  - restores theme and region settings.
- Weaknesses:
  - requires manual fullscreen;
  - scrollbars must not enter the frame;
  - known crash when a NodeFrame is selected in selected-only mode;
  - Blender 3.0+ is not officially supported (needs a custom build);
  - the modal timer makes the process slow and fragile.
- Takeaway: useful ideas (auto-crop, selected-only, theme restoration), but do not copy the architecture.

### 2.3. NodeExporter (KrazyGFX)

- GPL-3.0, Blender 4.2+, exports Geometry Nodes and Shader Materials to JSON + a standalone HTML/Canvas viewer ([extension page](https://extensions.blender.org/add-ons/node-exporter/)).
- Supports 2× PNG from the browser, transparent background, interactivity, collapsed nodes, hidden sockets.
- Weaknesses: it is **not** a pixel copy of Blender — different colors, curves/ramps not drawn, no Normal ball; not all tree types.
- Takeaway: a good source of ideas for a data-extraction layer, not for an exact PNG.

### 2.4. blender-node-export (draberf)

- GPL-3.0, exports a Node Graph to **SVG**: Blender theme, selected-only, visible-area limit, imitation widget quality, gradients, size/page, saved configuration ([GitHub](https://github.com/draberf/blender-node-export)).
- Strengths: vector sharpness, portable format, careful layout.
- Weaknesses: SVG, not PNG; widgets (ColorRamp, Curves, etc.) are only imitated; no preview thumbnails.
- Takeaway: the best reference if a vector branch is ever added.

### 2.5. Built-in tools

- `Window > Save Screenshot` and `Save Screenshot (Area)` — visible area only, no stitching.
- Render/OpenGL — cannot render the node editor.
- The comparison table below summarizes the options.

### Comparison table

| Solution | Output | Blender | Capture | Stitching | Limitations |
|---|---|---|---|---|---|
| Node Tree Screenshot | PNG/TIFF | 5.1+ | `screenshot_area` tiles | PIL/NumPy | panels in frame, `node.height`, no overlap, LOD |
| PrintNodes | PNG | 2.80–3.x | `screenshot_area` + modal timer | PIL | manual fullscreen, fragile, crash on frames |
| NodeExporter | PNG/JSON/HTML | 4.2+ | data extraction, browser render | — | not pixel-accurate |
| blender-node-export | SVG | 4.2+ | data extraction | — | vector imitation, not PNG |
| Built-in screenshot | PNG | all | visible area | — | no full graph |
| **This proposal** | **PNG** | **4.2+, fast path 5.2+** | **`Window.screenshot` tiles** | **NumPy + `imbuf`** | GUI-only session |

---

## 3. Implementation approaches

### 3.1. Tiled raster capture (recommended)

Capture the `WINDOW` region of the Node Editor in overlapping tiles, panning between captures, then stitch with NumPy. Exact, preserves every Blender visual (text, widgets, previews, link LOD), works on all supported versions with a version-specific capture adapter.

### 3.2. Raw framebuffer (Blender 5.2+)

[`Window.screenshot`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot) returns the window buffer as a `memoryview`; no temporary files. This is the fast path used by the prototype.

### 3.3. Vector / HTML rendering

Reconstruct nodes/links from `NodeTree.nodes`/`links` and draw in SVG/Canvas. Resolution-independent, but cannot reproduce Blender text metrics, widget rendering, previews, and LOD exactly. A separate branch, not the MVP.

### 3.4. Offscreen GPU

No public API renders the node editor offscreen. Compositor/`gpu` offscreen APIs do not cover editor drawing. Not viable.

---

## 4. Blender API and tools

### 4.1. Context and editor

- `bpy.context.space_data` → [`SpaceNodeEditor`](https://docs.blender.org/api/current/bpy.types.SpaceNodeEditor.html): `edit_tree`, `node_tree`, `path`, `pin`, `overlay`.
- `space.tree_type` is writable and has four editor modes: `GeometryNodeTree` ([Geometry Node Editor](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html)), `CompositorNodeTree` ([Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html)), `ShaderNodeTree` ([Shader Editor](https://docs.blender.org/manual/en/latest/editors/shader_editor.html)), `TextureNodeTree` ([Texture Node Editor](https://docs.blender.org/manual/en/latest/editors/texture_node/index.html)). `space.node_tree` is writable, `space.edit_tree` is read-only and follows the tree being edited; `space.pin = True` keeps the chosen tree when the active object/material changes.
- **Compositor in Blender 5.3:** the scene tree is [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group) (writable pointer, deprecated in 6.0 along with [`scene.use_nodes`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.use_nodes)); it is a `CompositorNodeTree`. The final output is a [`NodeGroupOutput`](https://docs.blender.org/api/current/bpy.types.NodeGroupOutput.html) node — `CompositorNodeComposite` no longer exists. Set [`space.show_backdrop`](https://docs.blender.org/api/current/bpy.types.SpaceNodeEditor.html#bpy.types.SpaceNodeEditor.show_backdrop) = `False` before capture, otherwise the backdrop image covers the canvas.
- **Geometry Nodes:** any `GeometryNodeTree` (a node group used by a `NODES` modifier) can be assigned to `space.node_tree` directly. For a valid modifier the group needs an output socket in its interface; for pure capture the tree only has to be drawable.
- `context.area`, `context.region`; check `space.type == 'NODE_EDITOR'` and `space.edit_tree is not None`.
- [`bpy.context.temp_override(area=..., region=..., space_data=...)`](https://docs.blender.org/api/current/bpy.types.Context.html#bpy.types.Context.temp_override) — call View2D/node operators in the right region.
- [`bpy.ops.screen.screen_full_area(use_hide_panels=True)`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screen_full_area) — maximize the area (Ctrl+Space equivalent).
- **Important:** after maximizing/restoring, old `area`/`region`/`space` references may be invalid; re-acquire them.

### 4.2. Graph geometry

- [`NodeTree.nodes`](https://docs.blender.org/api/current/bpy.types.NodeTree.html#bpy.types.NodeTree.nodes), `NodeTree.links`.
- [`Node.location_absolute`](https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.location_absolute) — position including parent Frame nodes.
- [`Node.dimensions`](https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.dimensions) — exact size after drawing (including previews); read-only. Better than `Node.height`, which does not reflect the real height for most nodes.
- `Node.width`, `Node.height` — fallback while `dimensions` is zero.
- `Node.hide` — collapsed state; `Node.parent` — Frame; `Node.select` — for selected-only.
- `Node.inputs/outputs`, `NodeSocket` — if hidden sockets must be accounted for.

### 4.3. View control

- `NodeTree.view_center` — current center, read-only.
- [`View2D.region_to_view(x, y)`](https://docs.blender.org/api/current/bpy.types.View2D.html#bpy.types.View2D.region_to_view) / [`view_to_region(x, y)`](https://docs.blender.org/api/current/bpy.types.View2D.html#bpy.types.View2D.view_to_region) — convert pixels to node coordinates and back. Use them to **measure** the actual scale (`units_per_px`) instead of assuming it.
- **Verified on Blender 5.3:** `view_to_region(location)` is **not** where the node is drawn when `ui_scale ≠ 1`. The working formula (verified on 24 nodes, error ≤ 2 px):

  ```python
  upp = (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0
  k   = 1.0 / upp        # px per node unit — for SIZES
  S   = bpy.context.preferences.system.ui_scale * bpy.context.preferences.view.ui_scale
  s   = S * k            # px per node unit — for POSITIONS
  ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)   # screen position of graph origin

  left   = ox + s * node.location_absolute.x
  right  = left + node.dimensions.x * k
  top    = oy + s * node.location_absolute.y
  bottom = top - node.dimensions.y * k
  ```

  The graph origin `(0, 0)` is the only point where both mappings coincide, so tests “near zero” do not catch the problem. At effective UI scale 1 (`system.ui_scale * view.ui_scale = 1`) the factor is 1 and the discrepancy disappears. `system.ui_scale` is read-only but readable; `preferences.view.ui_scale` is writable.
- `region.width`, `region.height`, `region.x`, `region.y` — pixels; region origin is the **bottom-left** corner.
- [`bpy.ops.view2d.pan(deltax, deltay)`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.pan) — pans in pixels. **The sign is inverted relative to intuition:** with `deltax = +100`, on-screen content moves by −100 px (verified via `view_to_region(0,0)` before/after). Linearity is exact across the range: requests of 100/500/1000/2000/3000 px produced −100/−498/−998/−1999/−2998 px (rounding ≤ 2 px, no clamp), also at `upp = 0.63` and `1.60`. Therefore, to move content left by `step_x`, call `pan(+step_x, ...)`; to move content up (next row below), call `pan(..., -step_y)`.
- [`bpy.ops.view2d.reset()`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.reset) — resets the zoom; usually 1:1 (`units_per_px ≈ 1.0005`), but not guaranteed (one test gave 1.0946 because of the aspect). Always measure. **Not deterministic for repeated exports** (it keeps the current center; see §11.10).
- **Zoom facts (5.3.0), verified:**
  - `zoom_in()`/`zoom_out()` with no arguments step by ≈ 0.925/1.0816 per call;
  - passing `zoomfacx/zoomfacy` does **not** set the factor: `zoom_in(1.1)` and `zoom_in(2.0)` both jump to the maximum magnification `upp = 0.43311` (≈ 2.31×), and likewise for `zoom_out`;
  - [`bpy.ops.view2d.zoom_border(xmin, xmax, ymin, ymax, wait_for_input=False)`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.zoom_border) is linear and exact: `r = 0.9/0.7/0.5/0.45/0.44` → `upp = 0.90120/0.70093/0.50067/0.45103/0.44076`; it clamps to `0.43311` at `r ≤ 0.43`;
  - zoom limits: `upp ∈ [0.43311, 20.00953]` (verified with 12 `zoom_in` and 40 `zoom_out` calls).
- **Deterministic priming:** [`bpy.ops.node.view_all()`](https://docs.blender.org/api/current/bpy.ops.node.html#bpy.ops.node.view_all) before the exact zoom. Unlike `reset`, it derives the base view from node bounds and region size, independent of the previous center. Verified: repeated exports are bit-identical (§11.10).
- `bpy.context.preferences.view.smooth_view = 0` — **required** during export; otherwise `pan`/`zoom` animate and a capture may catch an intermediate frame (`view_to_region` already reports the final one).
- [`bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)`](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.redraw_timer) — forced redraw before capture; works from a timer/operator with `temp_override(window, area, region)`.

**Output-density normalization (the “Output Image DPI” replacement).** Density is `D` pixels per node unit. It is independent of the monitor and current zoom when the editor scale is set explicitly:

```python
S    = system_ui_scale * view_ui_scale   # effective UI scale
D    = output_dpi / 96.0                 # 96 = canonical "100%"; default D = 1.0
upp  = S / D                             # target units-per-pixel
# set upp via zoom_border, then MEASURE the actual upp
k    = 1.0 / upp_measured                # px per unit — sizes
s    = S * k                             # px per unit — positions
```

- `system_ui_scale` is `preferences.system.ui_scale` (OS DPI, read-only); `view_ui_scale` is `preferences.view.ui_scale` (Resolution Scale, **writable**, 0.5–6.0). On another monitor `upp` changes, but **not** `D` or the output size.
- `D = 1.0` is “canonical 100%”: 1 px per node unit, as at 1:1 with `ui_scale = 1`.
- Limits: `D_max = S / 0.43311` (2.886 at `S = 1.25`; 5.77 at `view = 2`; 17.3 at `view = 6`), `D_min = S / 20`. Clamp outside the range and warn the user.
- `Node.dimensions` is in node units and independent of zoom, but **depends on `view.ui_scale`** (doubles at 2.0). Consequently, at a fixed `D` the pixel size of content stays almost constant, while at `D_max` it grows with `view.ui_scale` — that is the density bypass (§11.9).
- At `D = 0.5/0.75/1.0/2.0`, `view.ui_scale = 1`: content 1094.2 / 1641.6 / 2189.6 / 4380.8 px — ratios 1 : 1.5003 : 2.0011 : 4.0037.
- **Area maximization** (Ctrl+Space) grows the `WINDOW` region to the whole window (2560×1361 instead of 2100×1170): fewer tiles, faster capture; `D_max` is unchanged. Re-acquire references after the call.

### 4.4. Image capture

- **Blender 5.2+:** [`Window.screenshot(region=None, use_alpha=False)`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot) → `memoryview` `(h, w, 4)` uint8, rows **bottom-up**. Verified on 5.3.0:
  - `region=((x1, y1), (x2, y2))` uses window coordinates with a **bottom-left** origin; the result is **bit-identical** to a slice of the full screenshot `full[y1:y2, x1:x2]` (verified by FFT search and comparison: maxdiff = 0);
  - out-of-window regions are silently clipped (a smaller buffer is returned — always check the shape);
  - `use_alpha=True` yields alpha = 255 everywhere (the window is opaque); transparent backgrounds cannot be obtained this way;
  - repeated captures after `redraw_timer` are identical (A == B == C);
  - the region capture **excludes** the header and sidebar but **includes edge decorations**: on the right a scrollbar band (≈5 px, columns 2092–2096) + a 2 px frame; on the bottom a 4 px band (rows 3–6) + frame row 0; on the left/top only a ≈1 px frame. The earlier “left shadow 12–16 px” turned out to be node content at the tile edge, not a region decoration. Edge pixels corrupt tile overlap (see §4.6): they caused seams and “scrollbars” at tile joints.
  - therefore each tile is cropped by `PAD` on all sides with a matching placement offset; after cropping, overlap matches **bit-for-bit** (mean abs diff = 0.0000). `PAD` must scale with `view.ui_scale` (scrollbar ≈17 px at view=6).
- **Blender 4.2–5.1:** [`bpy.ops.screen.screenshot_area(filepath=...)`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area) — a temporary PNG/TIFF; it depends on `scene.render.image_settings`, so force PNG/Image and restore. In 5.3 it captures the **whole area including the header** (2100×1202 vs 2100×1170 for the `WINDOW` region) → crop the header height.
- `bpy.ops.screen.screenshot(filepath=...)` — the whole window, if needed.

### 4.5. Clean frame

- `space.show_region_header`, `show_region_toolbar`, `show_region_ui`, `show_region_asset_shelf` — hide regions.
- `space.overlay.show_context_path` — remove the group breadcrumb.
- `space.show_gizmo`, `space.show_gizmo_active_node`, `space.show_backdrop` (compositor; must be `False`, otherwise the render backdrop covers the nodes) — hide extras.
- Clear `node.select` and `node_tree.nodes.active` during capture: the active-node contour/glow is drawn outside `Node.dimensions` (≈3 px at 1×, ≈16 px at view=6) and would eat into the padding.
- Theme: `context.preferences.themes[0].node_editor` (`space.back`, `grid_levels`, `wire_select`, `node_selected`, `node_active`), `user_interface.wcol_scroll.item` — remove grid, scrollbars, selection highlighting.
- Make all theme/region changes inside `try/finally`; never save user preferences.

### 4.6. Stitching and saving

- NumPy: `np.frombuffer` (zero-copy from `memoryview`), `np.empty`, `np.memmap` for very large images.
- `imbuf.load`, `imbuf.new`, `imbuf.write`, [`imbuf.types.ImBuf.with_buffer(write=True)`](https://docs.blender.org/api/current/imbuf.types.html) (Blender 5.2+). Working pattern (verified on 5.3.0):

  ```python
  img = imbuf.new((w, h), planes=32, buffer_type="BYTE")
  with img.with_buffer(write=True) as buf:
      np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:] = arr   # arr: (h, w, 4) uint8, bottom-up
  imbuf.write(img, filepath=path)
  img.free()
  ```

  `buf[:] = arr` does **not** work (`NotImplementedError: ... ndim = 1`); use `np.frombuffer(buf, ...)[:] = arr`. `img.filepath`/`file_type` are not required — `imbuf.write(..., filepath=...)` is enough. `imbuf.write` can fail if the target file is locked (`OpenImageIO write failed`); write to `.tmp.png` and `os.replace`.
- Fallback: [`bpy.data.images.new`](https://docs.blender.org/api/current/bpy.types.BlendData.html#bpy.types.BlendData.images) + [`pixels.foreach_set`](https://docs.blender.org/api/current/bpy.types.Image.html#bpy.types.Image.pixels) (slower, float memory), or [Pillow](https://python-pillow.org/) (not a required dependency). The add-on uses a small NumPy PNG writer for the 4.2–5.1 save path to avoid color-management round-trips.
- **Stitching:** tiles are placed by exact pan offsets (`view2d.pan` moves content exactly the requested integer pixels, with an inverted sign). Overlap 120 px + linear feathering. **Crop `PAD` on every tile edge** — otherwise scrollbar/frame pixels enter the overlap and create bright joint lines. Verified on a 24-node graph:
  - without cropping: mean abs diff in overlap 0.6–0.9, visible joint lines;
  - with cropping: mean abs diff = **0.0000** (one pair 0.014, sub-pixel text rendering); on the final image, the difference between adjacent columns/rows at a seam is no different from neighboring ones (0.88 vs 0.80/0.14, 1.79 vs 1.92/1.61) — there is no seam at all, not “almost none”.
- **Final crop must be anchored to the TOP of the canvas.** `imbuf`/`np.frombuffer` rows are **bottom-up** (row 0 = bottom row of the PNG). Content is pinned to the top of the canvas, so:

  ```python
  c0 = UH - fh - PAD              # UH = canvas height, fh = final height
  final = canvas[c0:c0 + fh, PAD:PAD + fw]
  assert (wsum[c0:c0 + fh, PAD:PAD + fw] > 0).all()
  ```

  The naive `canvas[PAD:PAD + fh]` takes the bottom rows and **silently cuts off the top of the image**. Verified on a 3-row graph: it removed the entire top row (top margin 1005 px instead of 40). The `+1` variant includes one **uncovered** canvas row; while padding was filled, it was masked, but with the real background it appears as a black line. Always assert full coverage.
- **Global padding uses the real background, never a fill.** Content is anchored at `M = padding + PAD` from the top/left edge of tile 0; the capture area is `cw + 2M` × `chh + 2M`; final size `ceil(content) + 2*padding`. The `padding` band is physically captured (theme color, grid dots), and the outer `PAD` pixels (frame/shadow/scrollbar) are cropped away. Do not paint the band; if a clean margin is required, add a visual margin for the node outline (`VIS ≈ ceil(2.5 * view.ui_scale)`) or increase `padding`.
- **PAD/OVERLAP scale with UI scale:** `PAD_eff = max(16, ceil(8 * view.ui_scale))`, `OVERLAP_eff = max(120, 2*PAD_eff + 32)`. At view=6 the measured scrollbar is ≈17 px, frame ≈8 px, shadow ≈15 px; `PAD = 16` is insufficient. A too-large `PAD` with a fixed overlap makes `OVERLAP − 2*PAD` negative and breaks the ramp.
- PNG format: `ib.file_type = 'PNG'`; optionally `ib.compress`, `ib.planes`.

### 4.7. Extension packaging

- [`blender_manifest.toml`](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html) (schema 1.0.0): `id = "node_atlas"`, `name = "Node Atlas"`, `tagline = "Export any node tree as one high-resolution PNG"`, `version`, `maintainer`, `type = "add-on"`, `blender_version_min = "4.2.0"`, `license = ["SPDX:GPL-3.0-or-later"]`, optional `platforms`, `wheels`, `[permissions]`.
- `__init__.py` with `register()` / `unregister()`.
- Menus: `bpy.types.NODE_MT_view.append(...)` and/or `NODE_MT_context_menu.append(...)`; plus an N-panel.
- Operator `poll()`: active editor is `NODE_EDITOR` with an `edit_tree`.
- Version detection: `bpy.app.version` / `hasattr(window, "screenshot")`.

---

## 5. Key constraints and pitfalls

Only items verified on a live Blender 5.3.0 or hard platform constraints are listed.

1. **GUI only.** `--background` cannot capture UI (`Window.screenshot` is unavailable/returns no frame); the add-on must run in a normal window. The window must not be minimized: an invisible window's framebuffer is not updated.
2. **⚠️ UI scale is the main trap (verified).** At `ui_scale = 1.25`, node positions on screen are multiplied by the effective UI scale, while `Node.dimensions` is not multiplied by the system part. Therefore `view_to_region(node.location)` points to the wrong place and the error grows with distance from `(0,0)`. On a 24-node test graph the error reached hundreds of pixels — tiles could not be stitched. Fix: the formula in §4.3 (`s = S*k` for positions, `k` for sizes). At `ui_scale = 1` the symptom disappears, so the bug is easy to miss.
3. **⚠️ Region edges contain a scrollbar and frame — crop them.** At `WINDOW` edges: right ≈5 px scrollbar + 2 px frame, bottom ≈4 px + 1 px, left/top ≈1 px frame. These pixels are not graph content but enter every tile. If not cropped, they land in the overlap: overlap no longer matches (mean abs diff 0.6–0.9 instead of 0) and bright bands/“scrollbars” appear at joints. Crop `PAD` on all sides and offset tile placement by `PAD`; crop the final image from the top of the canvas (§19). After this, overlap matches bit-for-bit (0.0000); feathering only guards sub-pixel text.
4. **Seams are not “slightly different”.** After fixing geometry and cropping, overlap is identical: mean abs diff 0.0000, max 0.014. If the metric is above ~0.1, look for a positioning error or edge decoration — not for feathering. Feathering masks the symptom and **hides** the real bug (exactly what happened initially: seams “disappeared” while the image was wrong).
5. **The test scene must be visually heterogeneous.** Six *identical* chains look like “a repeated tile”, so a correct stitch cannot be distinguished from a broken one. Use chains with different nodes/sizes/colors.
6. **`smooth_view` is required.** With `smooth_view != 0`, `pan`/`zoom` animate: `view_to_region` already returns final values while the framebuffer still shows an intermediate frame → drifting tiles. Set `0` during export and restore.
7. **Never assume the scale.** `view2d.reset()` gave `upp = 0.99952` in one test and `1.0946` in another (aspect-dependent). Always measure `upp` via `region_to_view` after reset/zoom.
8. **Panning sign and precision.** `pan(dx, dy)` moves content by **(−dx, −dy)** — the opposite of intuition. Linearity is exact without clamping: requests up to 3000 px had ≤ 2 px error (rounding). Integer pixels mean sub-pixel phase is not compensated; anchor the first tile iteratively (1–2 “measure → nudge” passes), then use fixed integer steps.
9. **`Node.dimensions` = 0 before the first draw.** Call `redraw_timer` before collecting bounds; otherwise bounds are empty or clipped (especially preview and collapsed nodes). `Node.height` is not a substitute.
10. **Use `Node.location_absolute`, not `location`.** Inside Frame nodes, `location` is local; bounds require `location_absolute`.
11. **The old `screenshot_area` depends on output settings.** If Output Properties is set to video/FFmpeg, the operator may fail; force PNG/Image and restore. In 5.3 it captures the area **including the header** (2100×1202 vs 2100×1170) → crop.
12. **Transparent background (verified).** `use_alpha=True` yields alpha = 255 everywhere; the window is opaque. Two-background matting (black/white or any two flat backgrounds) reconstructs clean alpha in sRGB; single-key chroma-key is approximate and leaves a visible fringe even with a safe key. See §11.14; transparent mode is not the MVP default.
13. **Huge images.** 100 MP RGBA ≈ 400 MB in uint8; `bpy.data.images` with float pixels is 4× larger. The float32 accumulator costs ≈16 B/px (3 channels + weights). Use a limit, `np.memmap`, or split into several PNGs. A 3×5 grid on 24 nodes produced 5346×4513 px (96 MB uint8, ~250 MB peak during stitching).
14. **UI state.** Restore: view (scale + center), regions, gizmo, context path, `smooth_view`, cursor, selection/active node, `preferences.view.ui_scale`, maximization. All in `finally`. [`bpy.ops.wm.read_homefile`](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.read_homefile) inside a timer caused `EXCEPTION_ACCESS_VIOLATION` — do not do it.
15. **Version differences.** `Window.screenshot` is 5.2+; `ImBuf.with_buffer` is 5.2+; `imbuf` is 4.2+; theme/region properties change between versions. Add a compatibility layer and feature detection.
16. **“Any” graph.** The export covers the currently open tree. Exporting all groups in a .blend requires a batch mode (switch the tree in the editor). `SpaceNodeEditor.edit_tree`/`id`/`path` are read-only; `node_tree`, `pin`, `tree_type` are writable (verified).
17. **Long links fade.** Blender has `node_link_dim_factor`; there is no public setting. Visual breaks on long links remain; the add-on cannot fix them.
18. **License.** Official extensions require a GPL-compatible license; competitors are [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html). If code is borrowed, comply with GPL; preferably write original code.
19. **⚠️ Buffer orientation and crop (verified).** `imbuf`, the `np.frombuffer` screenshot, and the final array are **bottom-up** (row 0 = bottom PNG row; verified with colored bands). Content is at the top of the canvas, so crop `canvas[UH - fh - PAD : ...]` (no `+1`). A naive `canvas[PAD : PAD + fh]` cuts off the top of the graph: on a 3-row test the whole row disappeared, margins became 1005/672 instead of 40/40. The error is invisible without margin/coverage checks and does not break seams. The `+1` variant adds one uncovered row; only a filled padding masks it, so with the real background assert `wsum > 0`.
20. **Zoom cannot be set with `zoomfacx/zoomfacy`.** Any explicit factor on `zoom_in`/`zoom_out` jumps to the `upp = 0.43311` clamp; the no-argument step is ≈0.925/1.0816. Exact scale requires `zoom_border` (linear, error ≤ 0.2 %), clamped to `upp ∈ [0.43311, 20.01]`. Density limit: `D_max = S/0.43311`, where `S = system.ui_scale * view.ui_scale`: 2.886 at `S=1.25`, 5.77 at view=2, 17.3 at view=6 (D=17 verified).
21. **Padding is final-image pixels and the real background.** The same `padding` looks different relative to content at `D=0.5` and `D=2.0`; if proportional margins are wanted, specify them in node units and multiply by `D`. `padding` is part of the capture area (`M = padding + PAD_eff`); **do not fill** the band — it must contain the real graph background. Account for the node's outer contour/glow: it is not included in `Node.dimensions` and occupies ≈16 px at `view.ui_scale = 6`.
22. **Repeatability: `view2d.reset()` is not suitable; `node.view_all()` is.** Reset preserves the current center, so the rasterization phase drifts: two reset runs had mean abs diff 0.67 and 1.8 % pixels > 2. With `node.view_all()` before zoom, three full runs (including after other exports) and two cross-process runs had **0 differing pixels**. This is the recommended deterministic mode; differences across machines/GPU/fonts remain possible.
23. **Maximize the area (Ctrl+Space) for speed.** `screen_full_area(use_hide_panels=True)` grows the `WINDOW` region from 2100×1170 to 2560×1361: big-scene grid 3×4 → 2×3, capture 0.46 → 0.21 s. `D_max` is unchanged. After maximizing, old `area`/`region`/`space` are invalid — re-acquire; restore by calling the operator again.
24. **`PAD` and `OVERLAP` depend on UI scale.** Edge decorations scale: at `view.ui_scale = 6`, scrollbar ≈17 px, frame ≈8 px, shadow ≈15 px; `PAD = 16` is insufficient. Use `PAD_eff = max(16, ceil(8*view.ui_scale))`, `OVERLAP_eff = max(120, 2*PAD_eff+32)`; otherwise `OVERLAP − 2*PAD` goes negative and the grid/ramp breaks.
25. **Selection and the active node change the image.** The orange active-node contour is drawn outside `Node.dimensions` and eats padding at large UI scale (≈16 px at view=6). Clear `select` and `nodes.active` during export and restore afterwards.
26. **`view.ui_scale` is a user preference.** It is writable (0.5–6.0) but live and may persist after a crash. Set/restore in `try/finally`, do not save preferences, and warn the user if the session dies. `system.ui_scale`/`dpi` are read-only — change them only via the OS/restart.
27. **Compositor needs its own setup (verified).** `space.tree_type = 'CompositorNodeTree'`, `space.node_tree = scene.compositing_node_group`, `space.pin = True`, and **`space.show_backdrop = False`**. In 5.3 the tree is a node group (`scene.compositing_node_group`; `scene.use_nodes` and the pointer are deprecated for 6.0); the output is `NodeGroupOutput`, and `CompositorNodeComposite` is gone. Add a compatibility adapter for 5.x/6.x.
28. **Geometry Nodes needs a valid interface only for the modifier.** Assign `space.tree_type = 'GeometryNodeTree'`, `space.node_tree = <group>`, `pin = True`. For drawing/capture any group works; to avoid a modifier warning (“Node group must have an output socket”) add an output socket to `node_group.interface`.
29. **Tree switching order matters.** Set `pin = False` → `tree_type` → `show_backdrop` → `pin = True` → `node_tree`; then redraw and verify `space.edit_tree` is the expected tree. Switching `tree_type` resets the edited tree, so assigning `node_tree` before it may be lost.
30. **Restore the view after leaving maximization (verified).** The `WINDOW` region changes size (2560×1361 → 2100×1170); restoring zoom/center on the maximized region and then shrinking the layout shifts the center. Correct order: restore tree/UI/selection → `ui_scale`/`smooth_view` → leave maximize and re-acquire area/region/space → restore `upp` and center → restore area type if changed.
31. **View restoration is nearest-pixel, not bit-exact.** `View2D.cur` is not exposed and `NodeTree.view_center` is read-only; `pan` is integer. The saved view returns with `upp` error ≤ 0.03 % and center error ≈1 px; the editor screenshot differs only by sub-pixel AA (mean 0.53). All layout/UI/tree/selection settings are exact; on an induced exception the `finally` path restores them exactly. Do not promise pixel-identical view restoration.
32. **Selected-only export: crop-only is not enough (verified).** An unselected node that lies inside the selected nodes' bounding box remains in the image. Hiding unselected nodes (`node.hide = True`) is also not clean: hidden nodes are still drawn as collapsed/placeholder blocks, and hiding children shrinks the enclosing frame (observed frame height 422.5 → 360.5 px). Use a temporary filtered copy (§11.15).
33. **Selected-only semantics (agreed).** `selected` = `node.select` (active is not added implicitly). If a **frame** is selected, include its descendants; if a selected node has an unselected parent frame, unparent it **preserving `location_absolute`** and remove the frame; hidden selected nodes are excluded. Links to removed nodes disappear; links between kept nodes are preserved. If nothing is selected, show a warning instead of silently exporting the whole tree.
34. **Temporary copy details.** [`nt.copy()`](https://docs.blender.org/api/current/bpy.types.ID.html#bpy.types.ID.copy) creates an orphan tree for Shader/Material trees (not in `bpy.data.node_groups`) and a real group for GN/Compositor; both display fine in the editor and are removed with [`bpy.data.batch_remove([tmp])`](https://docs.blender.org/api/current/bpy.types.BlendData.html#bpy.types.BlendData.batch_remove) after restoring the original tree. Do not touch `tmp` after removal (ReferenceError). The original tree, links, selection, and frames are unchanged (state test PASS for Shader, GN, Compositor). Frame locations may be normalized in the copy, but the visual layout is preserved.
35. **Compositor asset shelf overlaps the WINDOW bottom (verified).** `show_region_asset_shelf` is read-only in Python and cannot be toggled via `screen.region_toggle`/`wm.context_set_boolean`; for the Compositor the `ASSET_SHELF` + `ASSET_SHELF_HEADER` regions occupy ≈102 px at the bottom and are included in a WINDOW screenshot. Detect their height **after switching to the actual tree type** (it was 2 px for GN, 102 px for Compositor) and crop that many rows from every tile; otherwise the asset-shelf footer leaks into the output. Recompute per run/tree type.
36. **Selected-only + compositor:** combine the filtered copy with the asset-shelf crop; the temp compositor group is not assigned to the scene, so hide `show_backdrop` and do not rely on scene compositing. The capture pipeline works on the displayed tree only.
37. **Undo cleanliness is verified — do not break it.** The pipeline uses only data/UI APIs: `nt.copy`, `nodes.remove` on the temp tree, `bpy.data.batch_remove`, `space.node_tree`/`tree_type`/`pin`, region flags, selection flags, `view.ui_scale`, theme colors, `view2d.*`/`node.view_all`, `screen_full_area`, screenshots. None of these pushed an undo step in 5.3: after a user-added node + `undo_push`, one Undo removed that node and Redo restored it, through all pipeline variants. **Never** use undoable operators ([`node.delete`](https://docs.blender.org/api/current/bpy.ops.node.html#bpy.ops.node.delete), `node.duplicate`, `node.select_all`, etc.) and never call [`undo_push`](https://docs.blender.org/api/current/bpy.ops.ed.html#bpy.ops.ed.undo_push) in the add-on — do selection/copy/removal through RNA as in the prototype. This must be re-checked on 4.2–5.1.
38. **Leaving maximize can no-op on a stale area after an exception.** If regions were hidden and an exception occurs while maximized, the first `screen_full_area` may return `FINISHED` but leave the area maximized; retry with a **fresh** `win.screen.areas[0]` and its `WINDOW` region. Verified: retry restored the exact 4-area layout; undo/redo still clean.

---

## 6. Proposed add-on architecture

### 6.1. Modules

```
node_atlas/
├─ __init__.py          # registration, menu, panel
├─ operators.py         # ExportPNG: file selector, progress, cancel
├─ capture.py           # maximize, hide UI, tiles, version adapters
├─ bounds.py            # graph bounds, selected-only, frames, groups
├─ stitch.py            # NumPy buffer, overlap, imbuf/Pillow fallback
├─ preferences.py       # global defaults (output_dpi, padding, limits)
└─ blender_manifest.toml
```

**Name and IDs (agreed):** display name **NodeAtlas**, tagline “Export any node tree as one high-resolution PNG”, manifest `id = "node_atlas"`. Operator: `node_atlas.export_png` (quick) and `node_atlas.export_as` (file dialog). Panel class `NODE_PT_node_atlas`, sidebar tab **“Node Atlas”**. Preferences class `NodeAtlasPreferences`. The `bl_idname` prefix keeps all registrations in one namespace and avoids collisions with Node Tree Screenshot / NodeExporter / PrintNodes.

### 6.2. MVP algorithm

The algorithm is not a sketch: it describes the **validated** prototype ([`tiling5_test.py`](reference/prototypes/tiling5_test.py) — base capture, [`tiling6_test.py`](reference/prototypes/tiling6_test.py) — padding/DPI, [`tiling7_test.py`](reference/prototypes/tiling7_test.py) / [`tiling9_test.py`](reference/prototypes/tiling9_test.py) — determinism/fullscreen, Blender 5.3.0). All steps run from a timer callback ([`bpy.app.timers.register`](https://docs.blender.org/api/current/bpy.app.timers.html)) because an operator's `execute()` cannot wait for a redraw; the frame is updated only between timer calls.

1. **Preparation (once).** Check the context; save state: view, region visibility, `show_gizmo`, `overlay.show_context_path`, `smooth_view`, cursor, node selection/active, `preferences.view.ui_scale`, and the editor's tree/pin. Set `smooth_view = 0`. Select the tree: `space.pin = False` → `space.tree_type` (`ShaderNodeTree`/`GeometryNodeTree`/`CompositorNodeTree`/`TextureNodeTree`) → `space.show_backdrop = False` (compositor) → `space.pin = True` → `space.node_tree = <tree>`; for the compositor in 5.3 the tree is `scene.compositing_node_group`. **Maximize the area** (`bpy.ops.screen.screen_full_area(use_hide_panels=True)`, Ctrl+Space) and **re-acquire** `area`/`region`/`space` — old references may be invalid. Hide header/toolbar/sidebar/asset shelf/context path, disable gizmo, **clear node selection and active** (the active-node contour is outside `Node.dimensions` and eats padding).

   **Selected-only mode (if requested):** keep the original tree, duplicate it (`tmp = tree.copy()`), build the keep set from `node.select` (add descendants of selected frames), unparent kept nodes whose parent is not kept while preserving `location_absolute`, remove all other nodes, assign `space.node_tree = tmp`, redraw, then capture. At the end restore the original tree and `bpy.data.batch_remove([tmp])`. Hidden selected nodes are skipped; if nothing is selected, warn. Crop-only and `node.hide` are **not** acceptable substitutes (§11.15).
2. **Normalize the view for the chosen density.** Deterministic base: **`bpy.ops.node.view_all()`**, not `view2d.reset()` (reset keeps the current center and the rasterization phase drifts; see §11.10). Then set `upp = S / D`, where `S = system.ui_scale * view.ui_scale` and `D = output_dpi / 96` (§4.3): loop “measure `upp` → `zoom_border` around the center / `zoom_in|zoom_out` step” until the error is < 0.2 %. Then **measure** the actual scale:

   ```python
   upp = (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0
   k = 1.0 / upp
   s = S * k
   ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
   ```
3. **Bounds and padding.** For every node with `dimensions > 0`: `left = ox + s*loc.x`, `right = left + w*k`, `top = oy + s*loc.y`, `bottom = top - h*k`; union. Add a visual margin `VIS ≈ ceil(2.5 * view.ui_scale)` — the outer contour/glow is not in `Node.dimensions` (≈16 px at `view.ui_scale = 6`). Content `cw × chh`; `PAD_eff = max(16, ceil(8 * view.ui_scale))`, `OVERLAP_eff = max(120, 2*PAD_eff + 32)`; margin `M = padding + PAD_eff`; capture area `W = cw + 2M`, `H = chh + 2M`.
4. **Tile grid.** `step_x = region.width - OVERLAP_eff`, `step_y = region.height - OVERLAP_eff`; `nx = ceil((W-OVERLAP_eff)/step_x)`, `ny = ceil((H-OVERLAP_eff)/step_y)`. Tile 0: iteratively place the content's top-left at `(M, th-M)` with `pan(round(cur - target))`, 1–2 iterations (remember the inverted sign). Each next tile: exact pan `((i-cur_i)*step_x, (cur_j-j)*step_y)`, no coordinate math.
5. **Capture.** Before each shot: `redraw_timer(DRAW_WIN_SWAP, 1)`, then `win.screenshot(region=((region.x, region.y), (region.x+w_, region.y+h_)))`; verify the buffer shape is `(h_, w_, 4)`. Immediately crop `PAD_eff` from every side (frame/scrollbar/shadow; at `view.ui_scale = 6` the scrollbar is ≈17 px, so 16 is too small) — the remaining tile is `cw × ch`.
6. **Stitch.** Canvas `((ny-1)*step_y + th, (nx-1)*step_x + tw)`; cropped tile `(i,j)` goes to `x = i*step_x + PAD_eff`, `y = UH - th - j*step_y + PAD_eff`. Weights: linear ramp over `OVERLAP_eff - 2*PAD_eff` only on sides with a neighbor; result `acc / max(wsum, eps)`.
7. **Crop, padding, save.** The array is bottom-up and content is pinned to the canvas top:

   ```python
   fw = ceil(cw) + 2*padding
   fh = ceil(chh) + 2*padding
   c0 = UH - fh - PAD_eff          # no +1: otherwise one uncovered row enters
   final = canvas[c0:c0+fh, PAD_eff:PAD_eff+fw]
   assert (wsum[c0:c0+fh, PAD_eff:PAD_eff+fw] > 0).all()
   ```

   **Do not fill anything:** the `padding` band is the real graph background (theme color, grid dots) captured from the screen. Save via `imbuf.new/with_buffer/imbuf.write` (§4.6); the 4.2–5.1 fallback uses a NumPy PNG writer.
8. **Restore.** In `finally`: restore the original tree/selection/active; restore region visibility/gizmo/context path while still maximized; leave maximization (`screen_full_area`; if it returns but the area is still maximized, retry with a fresh `win.screen.areas[0]`); re-acquire `area`/`region`/`space`; restore `preferences.view.ui_scale`/`smooth_view`; restore the view (`zoom_border` to saved `upp`, pan to the saved center); restore `area.type` if it was changed. Remove temp trees with `bpy.data.batch_remove`. **Never** use undoable operators (`node.delete`/`duplicate`/`select_all`) or `undo_push`; the whole pipeline is verified undo-neutral (§11.16).

**Validated result (6 distinct chains, 24 nodes, reference run):** `k = 0.99952`, `s = 1.24941`, bounds 5378×4545 px, grid 3×5, step 1980×1050, `PAD = 16`. Overlap after cropping: **mean abs diff 0.0000** (one pair 0.0142) — pixel-identical. Output PNG **5346×4513**; all checked nodes matched the model within 2 px; margins ≈20 px; seam-line gradients match neighboring rows/columns. Time: 15 tiles in 0.50 s (33 ms/tile), stitching 1.51 s.

**Validated result (padding + DPI, `scene_both.blend`):** content 1094.2 / 1641.6 / 2188.7 / 4380.8 px at `D = 0.5/0.75/1.0/2.0` (ratios correct); `D = 4.0` at `view.ui_scale = 2` gives 8760×2394 px; padding 20/40/120 px is physically captured (real background, `holes = 0`) and the size grows by exactly `2*padding`; maximizing the area (Ctrl+Space) reduces the big-scene grid from 3×4 to 2×3 and capture time from 0.46 s to 0.21 s. `D = 17` at `view.ui_scale = 6` is assembled without holes (2761×4737 with padding 20).

### 6.3. Options

- **Density:** `output_dpi` (default 96 = `D 1.0`; agreed), internally `D = output_dpi/96`, `upp = S/D`; clamp to `D_max = S/0.43311` (§11.9). `S = system.ui_scale * view.ui_scale`.
- **Global padding:** exact **final-image pixels** (agreed; default 20); part of the capture area as `padding + PAD_eff`; the band keeps the real background, no fill.
- **PAD/OVERLAP:** scale with UI scale: `PAD_eff = max(16, ceil(8*view.ui_scale))`, `OVERLAP_eff = max(120, 2*PAD_eff+32)`.
- **Megapixel limit:** hard memory cap; warn when approaching `D_max`.
- **Background:** theme (default) / solid color / **experimental transparent** — two-background matting (recommended quality, 2 captures) or chroma-key (1 capture, approximate, key-conflict check required); **never fill the padding** if the real background is required. See §11.14.
- **Area:** maximize (Ctrl+Space) during export and restore afterwards.
- **State:** hide UI automatically; restore regions/gizmo/context path/selection/active/`view.ui_scale`; retry leaving maximize with a fresh area if needed.
- **Undo safety:** all data changes via RNA (`nt.copy`, `nodes.remove`, `batch_remove`, selection/region flags); no undoable operators, no `undo_push`; verified undo-neutral (§11.16).
- **Scope:** current tree / selected nodes only / all groups (v2). Selected-only = `node.select`; selected frames include descendants; selected nodes inside unselected frames are unparented with their absolute position preserved; hidden selected nodes are skipped; empty selection warns. Implemented via a temporary filtered tree copy (verified on Shader, GN, Compositor), never by cropping or `node.hide`. Tree types: Shader (Material/World/Light), Geometry Nodes and Compositor are supported by the same code path (GN/Compositor verified in §11.12); Texture Nodes and nested groups are expected but still untested.
- **Defaults:** global in `AddonPreferences` (`output_dpi`, `padding`, limit), overridable in the export panel for one run.
- **Output:** PNG; multiple files when the limit is exceeded.

### 6.4. Compatibility

| Blender version | Capture | Stitch/save |
|---|---|---|
| 4.2–5.1 | `bpy.ops.screen.screenshot_area` → temporary PNG | NumPy + Python PNG writer |
| 5.2–5.3 | `Window.screenshot(region=...)` → memoryview | NumPy + `imbuf.new` + `with_buffer` + `imbuf.write` |

Target `blender_version_min` — **4.2.0**; on 5.2+ the fast path is enabled automatically.

### 6.5. User interface placement

The add-on should be reachable from the place where the user already works, without opening a separate window or leaving the node editor.

**1. N-sidebar panel (primary UI).** A panel in the Node Editor sidebar:

```python
class NODE_PT_node_atlas(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Node Atlas"
    bl_label = "Node Atlas"
```

- Works in **all four** editor modes (Shader, Geometry Nodes, Compositor, Texture) because they share `NODE_EDITOR`.
- Contents, top to bottom:
  - a large primary button **Export Current Tree** — one click, uses the last/global settings and a generated file name;
  - **Export As…** — file browser (`ExportHelper`);
  - compact settings: **Output DPI** (96 = `D 1.0`), **Padding (px)**, **Max MP**, **Scope** (current tree / selected nodes), **Background** (theme / solid color);
  - an estimated output size line, and a warning when `output_dpi` exceeds `D_max = S/0.43311`;
  - an expandable **Advanced** section: `PAD`/`OVERLAP` scaling, deterministic mode (`view_all`), hide/restore UI, save current view, default directory, filename pattern.
- The panel `poll()` returns true only when `context.space_data` is a `SpaceNodeEditor` with an `edit_tree`, so it never appears in unrelated editors.
- The user opens it with `N` (standard sidebar shortcut); the tab name “Node Atlas” is visible next to Item/Tool.

**2. Header icon (quick access).** Append a small operator button to `NODE_HT_header` with an image icon (`IMAGE_DATA` or `RENDER_STILL`) and a tooltip “Export Node Graph as PNG (Ctrl+Shift+E)”. This is the fastest path for users who do not want the sidebar open; it can be disabled in preferences if the header feels crowded.

**3. Menus.** Append the same operator to:

- `NODE_MT_view` — “Export Node Graph as PNG” (quick) and “Export Node Graph as PNG…” (file dialog);
- `NODE_MT_context_menu` — right-click in the editor;
- `TOPBAR_MT_file_export` — `File > Export > Node Graph as PNG…` for discoverability.

**4. Keyboard shortcut.** Register `Ctrl+Shift+E` in the `Node Editor` keymap for the quick export, with a preference to enable/disable it and to choose another shortcut later. The keymap entry is added on `register()` and removed on `unregister()` so it does not leak.

**5. Global defaults (AddonPreferences).** `Edit > Preferences > Add-ons > Node Atlas` stores `output_dpi` (96), `padding` (20), `max_mp`, a default output directory (empty asks for a path on every quick export), filename pattern (`{blend}_{tree}_{date}.png`; `{tree}` resolves to the owning material/world/object/scene/texture, `{datablock}` to the tree name, `{type}` to the tree type), `hide_ui`, `restore_ui`, `deterministic`, `copy_to_clipboard`, `background`, and whether to show the header button. The panel shows these values and can override them for one run; a “Use defaults” button resets the overrides.

**6. Progress, cancel, result.** The operator runs as a timer-driven modal job: the status bar shows “Capturing tile i/n”, `Esc` sets a cancel flag, and the `finally` block restores the UI. On success, report the output path, pixel size, and elapsed time; optionally open the PNG in the Image Editor. On error, show a popup with the exception and confirm that the UI was restored.

**7. “Any tree”.** The quick action exports the tree currently displayed in the editor (`space.edit_tree`/`space.node_tree`). This covers Material/World/Light shader trees, Geometry Nodes, Compositor, and Texture trees as soon as the user opens them. A dropdown “Export all trees of this type…” and a batch mode over all groups are v2 features; they should not complicate the primary panel.

The panel is the natural home for settings; the header icon and `Ctrl+Shift+E` are for speed; the menus are for discoverability. No separate floating window is needed.

---

## 7. What remains to verify

Verified on 5.3.0 (see §11): screenshot orientation/coordinates, alpha, `Node.dimensions`, panning, seams, `imbuf`, `ui_scale`, DPI normalization, real-background padding, determinism, maximization, state restoration. Open questions:

1. `screenshot_area` (4.2–5.1 fallback) in a real 4.x/5.1 build — header crop, output-settings dependency.
2. `Node.dimensions` accuracy for graphs with preview nodes after a depsgraph update (no previews were used in tests).
3. OS scaling 150/200% and Retina (physical vs logical pixels), Linux/X11 and macOS/Metal; confirm that `D` stays constant at another `ui_scale` (`system.ui_scale` is read-only in 5.3, so it was not changed).
4. LOD fading of long links (documented as a limitation).
5. Maximum PNG size and peak memory on 1000+ node graphs; practical limit at `D_max` for different `view.ui_scale`.
6. Pixel-exact restoration of view/selection/`view.ui_scale`/maximization after export.
7. All tree types: **Geometry Nodes and Compositor are verified** (§11.12); Texture Nodes, World/Light shader trees, nested Node Groups and group batch remain to be tested.
8. Determinism: `node.view_all()` gave 0 differences on one machine; check other GPUs/fonts/versions.
9. Behavior at the density limits (0.06 and 17.3): readability, memory, time; whether auto-clamping with a warning is enough.
10. Padding when the image is very small (padding > content), at `padding = 0`, and at high `view.ui_scale` (node contour ≈16 px).
11. Supersampling (capture at 2×D and downscale) as a way to stabilize AA and improve text quality — not tested.
12. Multiple windows and the user closing/moving the editor area mid-export; the snapshot/restore logic is per window and needs a guard.
13. The actual `Esc`/cancel path of the timer state machine, and scene/camera changes during a long capture.
14. Transparent mode implementation: two-background matting vs chroma-key, theme save/restore, double capture time, automatic key-conflict detection, RGBA PNG output, and alpha quality on graphs with many semi-transparent shadows/previews.
15. Selected-only on very large trees: copy cost, memory, cleanup, and whether `nt.copy()` can be avoided; hidden/active nodes policy.
16. Compositor asset-shelf height on other themes/UI scales and Blender versions; auto-detection/crop of any bottom overlay region.
17. Undo neutrality on 4.2–5.1 and on very large graphs; verify that no future operator (delete/duplicate/select-all) is introduced into the pipeline.

---

## 8. Work plan

| Stage | Content | Estimate |
|---|---|---|
| 0. Experiments | Blender 5.3 + 5.2 + 4.2, API and artifacts | 0.5–1 day |
| MVP | Current tree, maximize/hide UI, bounds, tiles, stitch, PNG, restore | 1–2 days |
| v0.2 | 4.2–5.1 fallback, overlap, progress/cancel, memory limits, options | 3–5 days |
| v1.0 | All tree types, group batch, manifest, docs, QA matrix | 1–2 weeks |
| v2 | SVG/JSON export, headless batch, CI tests | optional |

### Test matrix

- **Tree types:** Shader (Material/World/Light), Geometry Nodes, Compositor, Texture, nested Node Groups.
- **Content:** 1 / 10 / 100 / 1000 nodes; Frames; collapsed; reroute; multi-input; preview nodes; ColorRamp/Curves; long links; hidden sockets; empty tree.
- **Environments:** Blender 4.2 LTS, 4.5 LTS, 5.1, 5.2, 5.3; Windows/macOS/Linux; 100/125/150/200% scaling; OpenGL/Vulkan/Metal; one and two monitors.
- **Checks:** PNG size, no UI, no seams (overlap diff), text readability, correct bounds, `holes = 0`, padding = requested on all sides, node positions vs model, state restoration, no saved preferences, temp-file cleanup, peak memory and time.
- **Automation:** `blender --factory-startup --python test.py` with a fixture .blend; on Linux, GUI under Xvfb; pixel checks via `imbuf`/NumPy. Full UI capture in CI needs a virtual display — a separate task.

---

## 9. Conclusion

The add-on is worth building, and practice confirms it. There is no public API for offscreen node rendering, but tiled `WINDOW`-region capture gives pixel-accurate results: the prototype assembled a 24-node graph into a single 5346×4513 PNG without seams. Key findings: (1) node positions are scaled by the effective UI scale while sizes are not scaled by the system part; (2) `view2d.pan` moves content exactly but with the opposite sign; (3) tile edges contain a scrollbar/frame and `PAD` must scale with `view.ui_scale`; (4) **output density is normalized by zoom**: `D = S/upp`, and the limit is raised through writable `preferences.view.ui_scale` (2.886 → 17.3); monitor resolution does not cap it; (5) **padding is captured from the screen**: the band keeps the real background, `holes = 0`; (6) **the final crop must be anchored to the canvas top** (no `+1`), otherwise rows are silently lost or a black line appears; (7) **`node.view_all()` + `zoom_border` gives bit-identical exports**, while `view2d.reset()` does not; (8) **Ctrl+Space** reduces tile count and roughly halves capture time; (9) **Geometry Nodes and Compositor pass the same pipeline** (`tree_type`/`node_tree`/`pin`; compositor needs `show_backdrop = False` and `scene.compositing_node_group`), including padding, DPI scaling, and cross-process bit-identical output; (10) **the UI is an N-panel + header/menus/shortcut**, and the full editor state (layout, tree, UI flags, selection, `ui_scale`) is restored exactly, even after an induced failure — the view returns to the nearest pixel; (11) **transparent background** is not native, but two-background matting reconstructs clean alpha (sRGB, background α ≈5×10⁻⁶, cross-pair agreement 0), while single-key chroma-key leaves a measurable fringe (best green key: composite error 14.3/255, decontamination 8.9); (12) **selected-nodes-only export** is done with a temporary filtered tree copy (not crop-only, not `node.hide`), preserving frame/absolute-position semantics and leaving the original tree untouched; verified on Shader, GN, and Compositor; (13) **the whole pipeline is undo-neutral** — data/UI APIs only; one Undo removes a user-added sentinel node and Redo restores it after every variant, including the temp-tree copy and an induced failure. Remaining work: the 4.2–5.1 fallback, group batch, Texture/World/Light trees, the cancel/multi-window paths, transparent-mode implementation, and re-checking undo neutrality on 4.x.

---

## 10. Sources

### Projects

- [Node Tree Screenshot — extension page](https://extensions.blender.org/add-ons/node-tree-screenshot/)
- [Node Tree Screenshot — source](https://codeberg.org/lukas_tonne/node_tree_screenshot)
- [PrintNodes — GitHub](https://github.com/b-init/PrintNodes)
- [NodeExporter — extension page](https://extensions.blender.org/add-ons/node-exporter/)
- [blender-node-export (SVG) — GitHub](https://github.com/draberf/blender-node-export)

### Blender API and manual

- [`Window.screenshot`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot)
- [`bpy.ops.screen`](https://docs.blender.org/api/current/bpy.ops.screen.html) — `screenshot_area`, `screen_full_area`, `screenshot`
- [`bpy.ops.view2d`](https://docs.blender.org/api/current/bpy.ops.view2d.html) — `pan`, `zoom_in`, `zoom_out`, `zoom_border`, `reset`
- [`bpy.ops.node.view_all`](https://docs.blender.org/api/current/bpy.ops.node.html#bpy.ops.node.view_all)
- [`bpy.ops.wm.redraw_timer`](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.redraw_timer)
- [`View2D`](https://docs.blender.org/api/current/bpy.types.View2D.html) — `region_to_view`, `view_to_region`
- [`Node`](https://docs.blender.org/api/current/bpy.types.Node.html) — `dimensions`, `location_absolute`, `select`
- [`NodeTree`](https://docs.blender.org/api/current/bpy.types.NodeTree.html)
- [`SpaceNodeEditor`](https://docs.blender.org/api/current/bpy.types.SpaceNodeEditor.html)
- [`PreferencesSystem`](https://docs.blender.org/api/current/bpy.types.PreferencesSystem.html) — `ui_scale`, `dpi`
- [`PreferencesView`](https://docs.blender.org/api/current/bpy.types.PreferencesView.html#bpy.types.PreferencesView.ui_scale) — writable `ui_scale`
- [`Context.temp_override`](https://docs.blender.org/api/current/bpy.types.Context.html#bpy.types.Context.temp_override)
- [`imbuf`](https://docs.blender.org/api/current/imbuf.html) and [`imbuf.types`](https://docs.blender.org/api/current/imbuf.types.html)
- [Extension manifest / getting started](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html)
- [Preferences — Interface (Resolution Scale)](https://docs.blender.org/manual/en/latest/editors/preferences/interface.html)
- Blender source: [node link drawing / `node_link_dim_factor`](https://projects.blender.org/blender/blender/src/branch/main/source/blender/editors/space_node/drawnode.cc)

### Archived research artifacts

The validated prototypes are archived in [`reference/prototypes/`](reference/prototypes/);
the fixture generators are in [`tests/fixtures/`](tests/fixtures/). Generated `.blend`
fixtures and capture outputs are intentionally not committed; the scripts write to a
temporary directory.

- Base tiled capture: [`tiling5_test.py`](reference/prototypes/tiling5_test.py)
- Padding + DPI: [`tiling6_test.py`](reference/prototypes/tiling6_test.py)
- Determinism + `view.ui_scale` + real background: [`tiling7_test.py`](reference/prototypes/tiling7_test.py)
- Max density: [`tiling8_test.py`](reference/prototypes/tiling8_test.py)
- Fullscreen (Ctrl+Space): [`tiling9_test.py`](reference/prototypes/tiling9_test.py)
- Zoom semantics: [`zoom_probe2.py`](reference/prototypes/zoom_probe2.py), [`zoom_limits.py`](reference/prototypes/zoom_limits.py)
- Pan sign/linearity: [`pan_probe.py`](reference/prototypes/pan_probe.py)
- `view.ui_scale` effect: [`ui_scale_test.py`](reference/prototypes/ui_scale_test.py)
- Maximization: [`maximize_probe.py`](reference/prototypes/maximize_probe.py)
- Determinism: [`repro_inproc.py`](reference/prototypes/repro_inproc.py), [`repro_shot.py`](reference/prototypes/repro_shot.py)
- Padding/background checks: [`pad_bg_check.py`](reference/prototypes/pad_bg_check.py), [`pad_scale_probe.py`](reference/prototypes/pad_scale_probe.py)
- Geometry Nodes + Compositor: [`tiling11_test.py`](reference/prototypes/tiling11_test.py)
- Clean GN/Compositor export with asset-shelf crop: [`tiling12_test.py`](reference/prototypes/tiling12_test.py)
- UI state restore: [`restore_test.py`](reference/prototypes/restore_test.py)
- Transparent background: [`matte_capture.py`](reference/prototypes/matte_capture.py), [`analyze_matte2.py`](reference/prototypes/analyze_matte2.py)
- Selected-only: [`selected_copy_test.py`](reference/prototypes/selected_copy_test.py), [`selected_state_test.py`](reference/prototypes/selected_state_test.py), [`selected_gn_comp_test.py`](reference/prototypes/selected_gn_comp_test.py)
- Undo safety: [`undo_case.py`](reference/prototypes/undo_case.py), [`undo_extra.py`](reference/prototypes/undo_extra.py)
- Fixtures: [`tests/fixtures/`](tests/fixtures/) (generated locally, not committed)

---

## 11. Practical validation (Blender 5.3.0)

Everything below was produced by running real scripts in a GUI session of Blender 5.3.0 (Windows, `system.ui_scale = 1.25`, `dpi = 90`, window 2560×1361, `WINDOW` region 2100×1170 unless maximized). Prototypes are archived in [`reference/prototypes/`](reference/prototypes/); generated fixtures and capture outputs are not committed.

### 11.1. What was tested and how

| Question | Method | Result |
|---|---|---|
| Screenshot orientation/coordinates | slice a full screenshot, FFT shift search | bit-identical, `full[y1:y2, x1:x2]`, rows bottom-up |
| Capture determinism | 3 consecutive shots | maxdiff = 0 |
| Alpha | `use_alpha=True` | 255 everywhere, no transparency |
| `Node.dimensions` | compare with actual drawing | exact, but 0 before the first draw |
| `view2d.pan` accuracy | shifts of 200/400/1050/1980 px + correlation | 0 px error; sign inverted |
| Position vs size scaling | nodes at increasing distance from (0,0) | positions × effective UI scale, sizes × `k` |
| Seams | mean abs diff of tile overlap | 0.0000 after edge cropping |
| `imbuf.write` | save (h,w,4) uint8 | works via `with_buffer` + `np.frombuffer` |
| Node positions in the final PNG | detect colored header near the predicted point | dx 0…2, dy −2…−1 px |
| DPI normalization | `D = 0.5/0.75/1.0/2.0` from different start views | content 1094.2/1641.6/2189.6/4380.8 px, ratios ≤ 0.1 % |
| Real-background padding | capture with `FILL_PADDING = False`, bbox + bands | padding physically captured, `holes = 0`, outer edges = background |
| Repeatability | 2 reset runs vs 3 `view_all` runs | reset: mean 0.67 (1.8 % > 2); `view_all`: 0 differing pixels |
| Zoom API | `zoom_in/out` with/without factors; `zoom_border` 0.9…0.3 | exact only `zoom_border`; limits `upp 0.43311…20.0` |
| Max density | `view.ui_scale = 2`, `D = 4`; `view = 6`, `D = 17` | 8801×2434 and 2761×4737, `holes = 0` |
| Ctrl+Space | `screen_full_area(use_hide_panels=True)` | region 2100×1170 → 2560×1361; fewer tiles, same `D_max` |
| Buffer orientation/crop | colored bands through `imbuf`; naive crop test | row 0 = bottom; naive crop lost the top row (1005/672 vs 40/40) |
| Tree type switching | set `tree_type`/`node_tree`/`pin` for GN, Compositor, Material | `edit_tree` matches; dims 8/8, 5/5, 4/4 |
| Geometry Nodes export | D=1 and D=2, padding 40 | 2571×1115 and 5059×2149, `holes = 0`, content ≈2× |
| Compositor export | D=1, padding 40, `show_backdrop=False` | 2170×936, `holes = 0` |
| Cross-process GN/COMP determinism | two separate Blender processes | 0 differing pixels (all three outputs) |
| Selected-only | copy/filter tree, capture, restore | clean images, original tree/links/selection exact (PASS) |
| Compositor asset shelf | detect region heights, crop tiles | 102 px excluded, footer absent, `holes = 0` |
| Undo neutrality | sentinel node + `undo_push`, run pipeline, one Undo/Redo | sentinel removed/restored; all variants PASS |

### 11.2. Root cause of drifting tiles

Symptom: with `ui_scale = 1.25` the tile grid assembled, but far from the graph origin nodes were misplaced (error grew linearly with distance) and the image could not be stitched.

Cause: **node positions are drawn with the effective UI scale, while `Node.dimensions` is not multiplied by the system part.** `view_to_region(location)` only accounts for the viewport scale, so it returns the wrong point. `(0,0)` is the only point where both mappings coincide, which is why “near zero” tests passed.

Working formula (verified on 24 nodes, error ≤ 2 px):

```python
upp = (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0
k = 1.0 / upp
S = system.ui_scale * view.ui_scale
s = S * k
ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
left = ox + s * node.location_absolute.x
top  = oy + s * node.location_absolute.y
right, bottom = left + node.dimensions.x * k, top - node.dimensions.y * k
```

### 11.3. Second cause — scrollbar and region-edge frame

Even with correct geometry, bright bands remained at tile joints. Edge measurement of a single tile (mean brightness by column/row, background = 25):

- right edge: 5 px scrollbar band (brightness ≈31.5) at 2092–2096, then a 2 px frame (60.8);
- bottom edge: 4 px band (34.4) at rows 3–6, frame (61.8) at row 0;
- left edge: only a ≈1 px frame; the “soft shadow” of 12–16 px seen in the first measurement was node content at the tile edge, not a region decoration;
- top edge: only a ≈1 px frame and content.

These pixels enter the overlap and differ between neighboring tiles. Hence the “seams” and “scrollbars at joints” visible in intermediate artifacts (`out_tiles2/final.png`, `out_tiles3/final.png`; not committed).

**Solution:** crop `PAD` from every tile edge, offset placement by `PAD`, anchor the final crop to the **top** of the canvas, and leave the padding band unfilled. `PAD` scales with `view.ui_scale`; at 6 it must be ≥ ≈24 px (measured 17 px scrollbar + 8 px frame + 15 px shadow), and the tested value was 48.

### 11.4. What the “repeated graph” in old screenshots meant

The `scene_big.blend` test scene contained **6 identical chains** (Noise → ColorRamp → Principled → Output) in 3 rows × 2 columns. The output therefore **legitimately** looks like the same graph repeated six times; it is not a stitching error. Such a scene cannot distinguish a correct stitch from a broken one.

For validation, `scene_uniq.blend` was built: the same 24 nodes but distinct chains (Noise/Voronoi/Wave/Magic/Brick/Gradient, different BSDFs/Emission/Diffuse, labels `C1…C6`). It shows each chain exactly once and seams passing through nodes without a line.

### 11.5. Reference run

Scene `scene_uniq.blend`, 24 nodes, `MARGIN=40`, `OVERLAP=120`, `PAD=16`:

```
k 0.99952  s 1.24941  bounds 5378x4545  grid 3x5  step 1980x1050
overlap x: 1980,0 -> diff 0.0000 / 0.0142
overlap y: 0,-1050 -> diff 0.0000 (all 4 pairs)
capture 15 tiles: 0.50 s (33 ms/tile)
stitch: 1.51 s
result: 5346x4513 PNG, no holes
node positions: dx 0..2, dy -2..-1 px
seam-line gradient: 0.88 / 1.18 / 0.63 / 1.79 — same as neighboring rows/columns
margins: ~20 px on all sides
```

This run used the correct top-anchored crop ([`tiling5_test.py`](reference/prototypes/tiling5_test.py)). When the script was rewritten from scratch, the crop bug was reproduced — see §11.8; checking margins/coverage on all sides is mandatory.

### 11.6. Practical limitations

- GUI session only; capture is impossible in `--background`.
- `bpy.ops.wm.read_homefile` inside a timer → `EXCEPTION_ACCESS_VIOLATION`.
- `bpy.context.active_object` does not exist in 5.3 — use `view_layer.objects.active`.
- `buf[:] = arr` for `ImBuf` does not work (`ndim = 1`); use `np.frombuffer(buf, ...)[:] = arr`.
- `preferences.system.ui_scale` and `.dpi` are read-only in 5.3 but readable; assignment raises `AttributeError`.
- `preferences.view.ui_scale` is writable (0.5–6.0) and affects node/UI sizes live.
- `SpaceNodeEditor`: `edit_tree`, `id`, `path` are read-only; `node_tree`, `pin`, `tree_type`, `shader_type`, `show_region_ui/toolbar`, `show_gizmo`, `overlay.show_context_path` are writable.
- Long links still fade (`node_link_dim_factor`); the add-on cannot fix it.

### 11.7. Global padding and DPI normalization

Scene `scene_both.blend` (M_Small: 4 nodes; M_Uniq: 24 nodes), `FILL_PADDING = False` (real background captured). `system.ui_scale = 1.25`, `dpi = 90` (read-only). Target `upp = S/D`, `S = system.ui_scale * view.ui_scale`; base `node.view_all()`, then exact `zoom_border`.

| Run | D | view.ui_scale | content, px | final, px | holes | grid | capture/stitch |
|---|---|---|---|---|---|---|---|
| small d050 | 0.50 | 1.0 | 1094.2 × 301.2 | 1135 × 342 | 0 | 1×1 | 0.04 / 0.06 s |
| small d075 | 0.75 | 1.0 | 1641.6 × 451.8 | 1682 × 492 | 0 | 1×1 | 0.03 / 0.06 s |
| small d100 r1 | 1.00 | 1.0 | 2188.7 × 602.4 | 2229 × 643 | 0 | 2×1 | 0.07 / 0.13 s |
| small d100 v2 | 1.00 | 2.0 | 2189.1 × 598.1 | 2230 × 639 | 0 | 2×1 | 0.07 / 0.13 s |
| small d400 v2 | 4.00 | 2.0 | 8760.3 × 2393.7 | 8801 × 2434 | 0 | 5×3 | 0.49 / 0.77 s |
| big p40 v1 | 1.00 | 1.0 | 4239.1 × 3572.8 | 4320 × 3653 | 0 | 3×4 | 0.46 / 0.62 s |
| big p40 maximized | 1.00 | 1.0 | 4241.2 × 3574.6 | 4322 × 3655 | 0 | 2×3 | 0.21 / 0.45 s |
| one node max | 17.00 | 6.0 | 2720.2 × 4696.9 | 2761 × 4737 | 0 | 2×5 | 0.33 / 0.47 s |

At `D = 17` with `padding = 20` the geometry is correct and `holes = 0`, but the node's outer glow (≈16 px at `view = 6`) occupies most of the 20 px band; use a larger padding or `VIS` if a clean background margin is required at extreme density.

Conclusions:

1. **Density scales accurately.** Content ratios 1 : 1.5003 : 2.0011 : 4.0037 for `D` 0.5 : 0.75 : 1 : 2 (ideal 1 : 1.5 : 2 : 4), error ≤ 0.1 %. At `D=4`, `view=2`, content is 8760.3 px — exactly 4× `D=1`.
2. **Size does not depend on the starting view.** Three `D=1.0` runs from different states (after other exports, with maximization) produced identical 2229×643 and **0 differing pixels** (§11.10).
3. **Padding is captured from the screen.** `holes = 0` in every run: every final pixel is real captured data. The outer `PAD` pixels are cropped, so no frame/scrollbar enters. In the `padding` band the real background remains: for big p40, top band `std 0.63 / mean 25.04` vs empty interior `std 0.78 / mean 25.05`; outer rows/columns 25.0–25.65 (a frame would be ≈60, a scrollbar ≈31).
4. **Size grows by exactly `2·padding`** (4240→4320→4480 and 3573→3653→3813); at `padding = 0` margins are zero and content reaches the edge. Padding 20/40/120 px is verified by geometry and node detection; the background-based bbox metric is no longer valid because the band contains real grid dots.
5. **Node positions.** At `padding = 40/120`, all 24 nodes are found: dx 0…1, dy −2…0 px; at `view=2`, dx 0…2, dy −2…0; at `D=4`, within 2 px. The active-node contour was cleared (it otherwise eats ≈3 px at 1× and ≈16 px at 6×).
6. **`view.ui_scale` changes text metrics by a fraction of a percent.** At fixed `D=1`, content is 2188.7×602.4 (view=1) vs 2189.1×598.1 (view=2): width +0.02 %, height −0.7 %. This is text layout rounding, not a scale error.

### 11.8. Buffer orientation, top crop, and a “hidden” row

When the prototype was rewritten, the final crop was `canvas[PAD:PAD + fh]`. The result looked plausible, had no seams, and the middle-node position check passed (dy ≈ 0), but:

- a 3-row scene became 2 rows — **the top row vanished**;
- margins became 1005 px top and 672 px bottom instead of 40/40;
- the PNG size stayed “correct” (4320×3653) because `fh` was computed from the model, not from the actual image.

Cause: `imbuf`/`np.frombuffer` rows are **bottom-up**. Verified separately: writing a red band into buffer row 0 and a blue band into the last row puts the red band at the **bottom** of the saved PNG. Content is pinned to the canvas top, so the crop must start at high indices:

```python
c0 = UH - fh - PAD          # no +1
final = canvas[c0:c0 + fh, PAD:PAD + fw]
assert (wsum[c0:c0 + fh, PAD:PAD + fw] > 0).all()
```

The `+1` variant includes one **uncovered** canvas row (the outer `PAD` rows are not captured). While padding was filled, the black row was masked; with the real background it became visible, and `holes` first equaled the image width. Correct is no `+1`.

After the fix: all rows are present, `holes = 0`, and the position check finds all 24 nodes. Practical conclusion: **checking seams is not enough** — validate coverage, content size, and node positions independently.

### 11.9. Maximum DPI, screen resolution, and bypassing the limit

`preferences.view.ui_scale` (Resolution Scale) is **writable** (0.5–6.0); `system.ui_scale` and `dpi` are read-only. Effective scale `S = system.ui_scale * view.ui_scale`; the zoom limit in `upp` is independent of `S` and equals 0.43311. Therefore:

| `view.ui_scale` | `S` (system 1.25) | `D_max = S/0.43311` | big scene at `D_max`, px | MP | float32 accumulator |
|---|---|---|---|---|---|
| 1.0 | 1.25 | 2.886 | 12 234 × 10 311 | 126 | ≈ 2.0 GB |
| 2.0 | 2.50 | 5.77 | 24 459 × 20 615 | 504 | ≈ 8.1 GB |
| 6.0 | 7.50 | 17.32 | 73 421 × 61 881 | 4 543 | ≈ 72.7 GB |

Verified: `D=4` at `view=2` (4-node graph → 8801×2434, 5×3 tiles) and `D=17` at `view=6` (one node → 2761×4737, `holes=0`, positions within 2 px). **Monitor resolution (2560×1361) does not affect `D_max`** — only tile count, time, and the practical memory limit. At `view=6` the 2560×1361 region covers ~341 node units horizontally, so many tiles are needed, and `PAD`/`OVERLAP` must be scaled (§5.24).

For this 2560×1361 screen: a maximized tile is 2560×1361, so the big scene at `D_max` with `view=1` (12 234×10 311 px) needs about 5×9 = 45 tiles — a couple of seconds of capture, but ~2 GB for the accumulator. With `view=2` the output is 24 459×20 615 px (≈8 GB accumulator) and with `view=6` ≈73 421×61 881 px (≈73 GB) — those are memory-bound, not screen-bound. A larger monitor reduces the tile count and time, but does not increase `D`.

How to go beyond: (a) raise `view.ui_scale` to 6 (the main path); (b) raise OS scaling → `system.ui_scale` (restart required, affects the whole UI); (c) external vector/HTML rendering (different fidelity) or AI upscaling (not real detail). Within Blender, more detail than the editor draws at `upp = 0.43311` cannot be obtained.

### 11.10. Reproducibility, Ctrl+Space, PAD, and selection

- `view2d.reset()` is **not** deterministic: it preserves the current center, so the rasterization phase drifts. Two reset runs: raw frames mean 6.2 (27 % pixels > 2), tiled output mean 0.67 (1.8 % > 2).
- `bpy.ops.node.view_all()` before zoom **is deterministic**: three full `D=1` runs (including after other exports) — **0 differing pixels**; two cross-process runs — 0; with area maximization — 0. View_all derives the base from node bounds and region size, not from the previous center.
- **Options for repeatability:** (A) recommended — prime with `view_all` + `zoom_border`; bit-identical on the same machine, no restart needed. (B) If `reset` is used, accept AA-only differences and validate geometry (size, margins, positions) instead of pixels. (C) Supersample (capture at 2×D, downscale) to stabilize AA/text at fractional phases — not tested, costs 4× pixels/time. (D) Cross-machine reproducibility is not guaranteed; compare geometry invariants in tests.
- Recommended mode: `view_all` → `zoom_border` to `S/D` → measure `upp` → anchor by pan. For tests, compare geometry (size, margins, positions), not only pixels; cross-machine determinism (GPU/fonts) is not guaranteed.
- **Ctrl+Space:** `screen_full_area(use_hide_panels=True)` grows the `WINDOW` region from 2100×1170 to 2560×1361. Big scene: grid 3×4 → 2×3, capture 0.46 → 0.21 s, stitch 0.62 → 0.45 s; `D_max` unchanged. References become invalid — re-acquire; restore by calling the operator again.
- **PAD/OVERLAP:** at `view=6` the measured scrollbar is ≈17 px, frame ≈8 px, shadow ≈15 px, so `PAD=16` is too small. Use `PAD_eff = max(16, ceil(8*view.ui_scale))`, `OVERLAP_eff = max(120, 2*PAD_eff+32)`. Otherwise `OVERLAP − 2*PAD` goes negative and the grid/feathering breaks.
- **Selection:** the active node draws a contour outside `Node.dimensions` (≈3 px at 1×, ≈16 px at 6×). Clear `select`/`nodes.active` during export and restore afterwards; otherwise the contour eats padding and makes the image depend on the current selection.

### 11.11. Summary of the two requested features

- **Global padding** — the `padding` pixels are physically part of the capture (`M = padding + PAD_eff`); final size `ceil(content) + 2·padding`; the band contains the **real graph background** (theme color, grid dots), no fill. Verified 0/20/40/120 px, `holes = 0`; outer rows/columns match the background. The active-node contour is outside `Node.dimensions` (≈3 px at 1×, ≈16 px at 6×) — clear selection or add `VIS ≈ ceil(2.5*view.ui_scale)`.
- **DPI independence** — explicit zoom: `D` is user-defined, `upp = S/D`, `S = system.ui_scale * view.ui_scale`. Verified `D = 0.5…17` with ≤ 0.1 % error; writable `view.ui_scale` raises `D_max = S/0.43311` from 2.886 to 5.77 (view=2) and 17.3 (view=6). **Agreed:** the setting is named `output_dpi` (96 = `D 1.0`), `padding` is in final pixels. The PNG carries a `pHYs` chunk with the effective (clamped) DPI; imbuf's fixed 72-dpi `pHYs`/EXIF metadata is replaced on save.
- **Storage:** global defaults in `AddonPreferences` (`output_dpi`, `padding`, MP limit), overridable in the export panel for one run.
- **Repeatability:** `node.view_all()` + `zoom_border` is bit-identical (0 differences) across three runs and two processes; `view2d.reset()` is not. Details in §11.10.

### 11.12. Geometry Nodes and Compositor (verified)

Scene `scene_graphs.blend` (generated by [`make_scene_graphs.py`](tests/fixtures/make_scene_graphs.py)) contains three trees: `M_Small` (Shader), `GN_Test` (8 nodes), `COMP_Test` (5 nodes). The generic runner is [`tiling11_test.py`](reference/prototypes/tiling11_test.py); outputs are not committed.

| Run | Tree | D | content, px | final, px | holes | grid | capture/stitch | bottom UI |
|---|---|---|---|---|---|---|---|---|
| gn_d100_p40 | Geometry Nodes | 1.00 | 2490.5 × 1034.6 | 2571 × 1115 | 0 | 2×1 | 0.07 / 0.12 s | 2 px |
| comp_d100_p40 | Compositor | 1.00 | 2089.3 × 855.7 | 2170 × 936 | 0 | 2×1 | 0.08 / 0.12 s | 102 px |
| comp_d200_p40 | Compositor | 2.00 | 4179.6 × 1711.9 | 4260 × 1792 | 0 | 3×2 | 0.22 / 0.32 s | 102 px |
| gn_d200_p40 (earlier) | Geometry Nodes | 2.00 | 4978.6 × 2068.2 | 5059 × 2149 | 0 | 3×2 | 0.20 / 0.32 s | — |

- **Switching works.** `space.tree_type` accepts `GeometryNodeTree` and `CompositorNodeTree`; after `pin = True` and `node_tree = <tree>`, `space.edit_tree` is the expected tree. All nodes get non-zero `Node.dimensions` (8/8 GN, 5/5 Compositor). The same session switched GN → Compositor → GN and re-captured correctly.
- **Geometry and padding are identical to Shader.** Content-edge bbox at threshold 50: GN l/b/r/t = 39/41/38/37, Compositor = 40/40/28/37 (compositor right edge affected by the wire/glow threshold), GN D=2 = 40/40/35/37 (target 40). `holes = 0`; the size formula `content + 2·padding` holds. `D=2` doubles content (GN 2490.5→4978.6 = 2.0004×; Compositor 2089.3→4179.6 = 2.0005×).
- **Compositor asset shelf (important).** The Compositor editor shows an `ASSET_SHELF` + `ASSET_SHELF_HEADER` at the bottom of the `WINDOW` region (73 + 29 = **102 px** in the test; Geometry Nodes had 2 px). The property `show_region_asset_shelf` is read-only in Python and cannot be toggled by `screen.region_toggle` or `wm.context_set_boolean`; if left alone, the asset-shelf footer (catalog tabs + Search) leaks into the bottom of the capture. The pipeline must **detect the region heights after switching to the actual tree type** and crop them from every tile. With that crop the footer is gone; the final Compositor image is clean (output `final_comp_d100_p40.png`, not committed). Recompute the height per run because it depends on the tree type.
- **Compositor specifics:** use `scene.compositing_node_group` (writable in 5.3; deprecated in 6.0 along with `scene.use_nodes`), `space.show_backdrop = False`, and note that `CompositorNodeComposite` no longer exists — the output is `NodeGroupOutput`. The compositor group must have an interface output socket to be valid.
- **Geometry Nodes specifics:** assign any `GeometryNodeTree`; for a modifier to be valid, add an output socket to `node_group.interface` (otherwise Blender warns “Node group must have an output socket”; drawing still works).
- **Determinism:** two separate Blender processes produced **0 differing pixels** for the three earlier outputs (`out_graphs/proc1_*`, not committed), confirming that `view_all` priming and the rest of the pipeline are editor-agnostic.
- **Remaining:** Texture Nodes, World/Light shader trees, nested groups as separate exports, and batch over all groups still need a test; “all graphs” in the sense of “the tree currently displayed in the Node Editor” is now verified across Shader, Geometry Nodes, and Compositor.

### 11.13. UI state restoration and safety (verified)

Script: [`restore_test.py`](reference/prototypes/restore_test.py); scene `scene_both.blend`; standard four-area layout (Dope Sheet, Node Editor 2100×1202, Outliner, Properties). Three modes: `success` (full simulated export), `fail` (same, but an exception is raised after all mutations) and `areatype` (the 3D View is temporarily converted to a Node Editor, maximized, mutated, then restored).

The snapshot included: window size, every area's type/position/size, the node `WINDOW` region, `tree_type`, `node_tree`, `edit_tree`, `pin`, selection and active node, header/UI/toolbar visibility, gizmo, context path, backdrop, `preferences.view.ui_scale`, `smooth_view`, view scale (`upp`) and view center.

| Check | success | induced exception | 3D→Node→3D |
|---|---|---|---|
| Area layout (4 areas, type/x/y/w/h) | exact | exact | exact |
| Window size 2560×1361 | exact | exact | exact |
| `WINDOW` region (2,126,2100,1170) | exact | exact | exact |
| `tree_type` / `tree` / `edit_tree` / `pin` | exact | exact | exact |
| Selection and active node | exact | exact | exact |
| Header/UI/toolbar/gizmo/context/backdrop | exact | exact | exact |
| `ui_scale` / `smooth_view` | exact | exact | exact |
| Area type restored (VIEW_3D) | — | — | exact |
| View scale `upp` | diff 0.000334 | diff 0.000334 | — |
| View center | ≈1 px | ≈1 px | — |
| Pixel diff of the editor | mean 0.53 (sub-pixel) | mean 0.53 | — |

**Result:** all layout/UI/tree/selection preferences are restored exactly, including the transient maximization and the temporary area type. On an induced exception the `finally` path restored exactly the same state, so an export error does not leave the user with a maximized/hidden editor.

**Important ordering discovered by the test:** the view must be restored **after leaving maximization**. If the zoom/center is restored on the maximized 2560×1361 region and then the layout is restored to 2100×1170, the center shifts. The correct sequence is: restore tree/UI/selection → restore `ui_scale`/`smooth_view` → leave maximize and re-acquire `area`/`region`/`space` → restore zoom (`zoom_border` to the saved `upp`) and pan the saved center back to the region center → restore the area type if it was changed.

**View exactness limit:** `View2D.cur` is not exposed in the Python API and `NodeTree.view_center` is read-only; `pan` accepts integer pixels. Therefore the view is restored to the nearest pixel: `upp` error ≤ 0.03 %, center error ≈1 px, and the editor screenshot differs only by sub-pixel AA (mean 0.53). Everything else is bit-exact. If pixel-identical view restoration is required, the only robust option would be a separate temporary window/editor; that is not the MVP.

**Implementation rules for the add-on:**

1. Take the snapshot before any mutation; restore in `finally`, in reverse order.
2. Never save user preferences; restore `view.ui_scale` even if it was changed for high-D export.
3. Do not call `read_homefile`; do not change `area.type` unless unavoidable (the operator is invoked from a Node Editor).
4. Re-fetch `area`/`region`/`space` after `screen_full_area`; old references are invalid.
5. Guard against a closed area/window: check references before each timer step; if the area disappears, abort and skip the parts that can no longer be restored.
6. Run the capture as a timer state machine; on `Esc`/cancel jump directly to the restore stage.
7. Report success/failure and the output path; on failure, state explicitly that the UI was restored.
8. If the session crashes mid-export, `view.ui_scale` may persist; keep it at the user value by default and change it only when the requested `D` exceeds `D_max` (with a warning).

Not yet tested: multiple windows, the user closing the editor area mid-export, the actual `Esc`/cancel path, and OS display-scaling changes during capture.

### 11.14. Transparent background: chroma-key vs two-background matting

Scene `scene_matte.blend` (generated by [`make_scene_matte.py`](tests/fixtures/make_scene_matte.py)) (Noise → ColorRamp → Principled → Output; the ramp intentionally contains magenta and cyan to expose key conflicts). Capture script: [`matte_capture.py`](reference/prototypes/matte_capture.py); analysis: [`analyze_matte2.py`](reference/prototypes/analyze_matte2.py); outputs are not committed.

Method: set `preferences.themes[0].node_editor.space.back` to six flat colors (black, white, magenta, green, cyan, gray), set `grid_levels = 0`, hide the UI/selection, call `node.view_all()` before every capture, and screenshot the same 2100×1202 region. Cropping 16 px (`PAD`) gives 2068×1170. The view was identical for every background: `upp = 1.145813`, center `(1088.0729, −125.9269)` exactly.

**Two-background matting.** For two backgrounds `B0`, `B1`, `I = αF + (1−α)B` is solved per pixel. The screenshots are blended in **sRGB**, not linear: inter-channel alpha std is `0.00032` in sRGB vs `0.01536` in linear (48× worse). With black/white:

- `α = 1 − (I_white − I_black)/254` per channel; the black/white and magenta/green pairs agree on edges with **mean |Δα| = 0.000000** (p99 = 0), so the model is consistent;
- background: α mean `5×10⁻⁶`, max `0.0079`; foreground: mean `0.999986`, min `0.9908`;
- edge pixels (0.05 < α < 0.95): 0.63 % (15 343 px); edge α percentiles `0.051 / 0.059 / 0.075 / 0.11 / 0.295 / 0.781 / 0.949` (the ~0.3 cluster is the node shadow, i.e. real semi-transparency).

**Chroma-key.** A distance keyer with thresholds fitted on the reference alpha (an upper bound for a single-key chroma-key) gives:

| Key | α MAE | α p95 | α >0.10 | α >0.25 | fg holes | comp. mean | comp. p95 | comp. max | mean ΔRGB (simple) |
|---|---|---|---|---|---|---|---|---|---|
| **green** | 0.067 | 0.126 | 10.6 % | 0 % | 2.7 % | 14.3 | 34.5 | 47 | +0.1 / **+21.4** / +4.0 |
| magenta | 0.059 | 0.119 | 8.5 % | 0 % | 8.8 % | 16.7 | 37.6 | 45 | **+17.2** / +2.5 / **+23.7** |
| cyan | 0.068 | 0.150 | 14.5 % | 0 % | 14.7 % | 19.1 | 50.7 | 61 | −1.4 / +21.7 / +22.9 |
| white | 0.060 | 0.202 | 8.9 % | 3.0 % | 9.2 % | 21.9 | 48.3 | 71 | +19.0 / +22.3 / +24.0 |
| gray | 0.056 | 0.153 | 13.1 % | 0.3 % | 24.8 % | 12.3 | 21.1 | 43 | +8.2 / +11.0 / +12.5 |

`comp.` is the mean absolute RGB error (0–255) on edge pixels when the keyed result is composited over a checkerboard, compared to the two-background reference. `fg holes` is the fraction of opaque foreground pixels whose keyed alpha drops below 0.9.

- **Green is the only safe key in this graph:** the minimum distance from the key to any foreground color is `0.334` (no conflict). Magenta, cyan, white, and gray all occur in the graph (the ramp/UI), hence the large `fg holes`.
- Even with the best key, **simple keying leaves a visible green fringe**: mean ΔRGB `[+0.1, +21.4, +4.0]` (G channel), composite error 14.3/255, p95 34.5, max 47. Decontamination (`F = (I − (1−α)K)/α`) reduces it to mean 8.9, p95 16.7, max 33, but does not remove it (alpha errors remain).
- Visual 1:1 crops: `z_ref.png` (reference), `z_simple_green.png` (green fringe), `z_decon_green.png` (reduced); not committed.

**Conclusions**

1. **True transparency is not native.** `Window.screenshot(use_alpha=True)` is opaque; the alpha must be reconstructed.
2. **Two-background matting is high quality and cheap in code, expensive in capture:** it needs two captures with different flat backgrounds and assumes the graph/UI is static between them (`view_all` makes the view deterministic). The alpha is exact up to 8-bit quantization; the padding becomes α=0 automatically. It is the recommended transparent mode.
3. **Chroma-key is a one-capture approximation:** with a carefully chosen key (green here) and decontamination, the result is usable but still shows a fringe on text/wire edges; with a key that appears in the graph it fails visibly. A single fixed key is not safe for arbitrary graphs; the add-on would need a key-conflict check or a two-key/matting mode.
4. Both modes require temporarily changing the theme background and `grid_levels = 0`, then restoring them exactly (same `try/finally` rules as §11.13) and not saving preferences.
5. Recommendation: **opaque background in the MVP**; transparent mode as an experimental option: two-background matting first, chroma-key second (clearly labelled “approximate”).

### 11.15. Exporting only selected nodes (verified)

Scene `scene_selected.blend` (generated by [`make_scene_selected.py`](tests/fixtures/make_scene_selected.py)) — a shader tree with N1 → R1 → B1 → O1, an unselected U1 placed **inside** the N1+R1 bounding box, frame F1 with two children, and frame F2 with a selected C3 and unselected C4. Test scripts: [`selected_copy_test.py`](reference/prototypes/selected_copy_test.py), [`selected_state_test.py`](reference/prototypes/selected_state_test.py), [`selected_gn_comp_test.py`](reference/prototypes/selected_gn_comp_test.py); outputs are not committed.

Three approaches were evaluated:

1. **Crop only** (bounds from selected nodes, no hiding): unselected U1 lies inside the bbox and would appear in the image — rejected.
2. **Hide in place** (`node.hide = True` for unselected): not a clean hide. Hidden nodes are still drawn as collapsed/placeholder blocks (green rectangles in the test), and hiding children shrinks the parent frame (F1 height 422.5 → 360.5 px) — rejected.
3. **Temporary filtered copy** (chosen): duplicate the tree, keep selected nodes (+ descendants of selected frames), unparent kept nodes from unselected frames while preserving `location_absolute`, remove everything else, display the copy, capture, restore the original, and remove the copy. Verified clean:

| Case | Kept | Links kept | Result |
|---|---|---|---|
| N1 + R1 | N1, R1 | N1→R1 | only these two nodes; U1/B1/O1/frames absent (`copy_N1_R1.png`) |
| frame F1 selected | F1 + both children | — | frame and contents only (`copy_F1_frame.png`) |
| C3 selected inside F2 | C3 only | — | C3 at its absolute position, F2/C4 removed (`copy_C3_child.png`) |

- **Geometry Nodes and Compositor:** the same copy/filter works; e.g. GN `Position → Set Position` and Compositor `Render Layers → Glare` were exported alone with their links preserved (`sel_GN_pos_setpos.png`, `sel_COMP_layers_glare.png`; not committed). The compositor run also confirmed the asset-shelf crop: 102 px of shelf/header is excluded, so the footer does not appear.
- **State safety:** after each case the original tree had the same node count (11), links (3), per-node `location_absolute`/dimensions/parent/select/hide, and editor tree; `RESULT PASS` for N1+R1, F1, C3. The temp tree is removed (`bpy.data.batch_remove` success; for Shader trees it is an orphan, for GN/Compositor it is in `bpy.data.node_groups`; do not access it after removal).
- **Semantics (agreed):** selected = `node.select` (active is not added implicitly); selected frames include all descendants; selected nodes inside unselected frames are unparented with absolute coordinates preserved; hidden selected nodes are skipped; empty selection warns instead of falling back to the whole tree. Links to removed nodes disappear; links between kept nodes remain.
- **Performance/limits:** copying a whole tree is O(N) in nodes/links and temporary memory; for very large graphs this needs measuring. The operation uses Python data APIs (no operators) and is verified undo-neutral in §11.16.
- **UI:** scope selector “Current tree / Selected nodes”; when “Selected nodes” is active, show the count and disable the export button if the selection is empty. Optional filename suffix `_selected`.

### 11.16. Undo safety (verified)

Scripts: [`undo_case.py`](reference/prototypes/undo_case.py), [`undo_extra.py`](reference/prototypes/undo_extra.py); outputs are not committed.

Method: add a `ShaderNodeMath` through the Node Editor operator (this creates a normal undo step), call `bpy.ops.ed.undo_push("USER")` as a test marker, run one pipeline variant, then call `bpy.ops.ed.undo()` once and `bpy.ops.ed.redo()`. If the pipeline pushed any undo step, the first Undo would revert a capture action and the sentinel node would remain. In every case the sentinel was **removed by Undo and restored by Redo**, i.e. the pipeline left the undo stack untouched.

| Variant | Undo | Redo | Result |
|---|---|---|---|
| control (no pipeline) | sentinel removed | restored | PASS |
| maximize + hide UI + `view_all`/pan + screenshot + restore | removed | restored | PASS |
| selected-only temp tree: `nt.copy` → filter → assign → capture → restore → `batch_remove` | removed | restored | PASS |
| induced exception after temp-tree assignment (`finally` restore) | removed | restored | PASS |
| `view.ui_scale` 1.0 → 1.5 → 1.0 | removed | restored | PASS |
| theme background black/white → restore | removed | restored | PASS |
| selection cleared and restored via RNA | removed | restored | PASS |

Why it is clean: the pipeline uses **data/UI APIs**, not undoable operators — `nt.copy()`, `tmp.nodes.remove()`, `bpy.data.batch_remove()`, `space.node_tree`/`tree_type`/`pin`, region visibility, `node.select`, `preferences.view.ui_scale`, theme colors, `view2d.*`, `node.view_all`, `screen_full_area`, `Window.screenshot`. `bpy.ops.wm.redraw_timer` and view operators do not push undo steps. The add-on must **never** call `bpy.ops.ed.undo_push` or operators such as `node.delete`, `node.duplicate`, `node.select_all`; the prototype uses RNA for all data changes.

Caveat: this is verified on Blender 5.3.0; the same test must be part of QA on 4.2–5.1 because some operators/versions may differ. Undo memory/old temp-tree data should also be checked on very large graphs.

**Layout restoration after an exception.** If the region flags were hidden and an exception is raised while the area is maximized, the first `screen_full_area` can return `FINISHED` but leave the editor maximized. The fix is to retry with a fresh `win.screen.areas[0]` and its `WINDOW` region; this restored the exact four-area layout, and the Undo/Redo test still passed. The recommended restore order is: original tree/selection → region visibility/gizmo/context → leave maximize (retry with fresh area if needed) → re-fetch area/region/space → `ui_scale`/`smooth_view` → view zoom/center → area type if changed.
