# AGENTS.md

Operating instructions for coding agents working on **NodeAtlas**.

## 1. Project

NodeAtlas is a [Blender](https://www.blender.org/) add-on that exports any node tree
([Shader](https://docs.blender.org/manual/en/latest/editors/shader_editor.html),
[Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html),
[Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html),
[Texture](https://docs.blender.org/manual/en/latest/editors/texture_node/index.html))
as one high-resolution PNG. It captures the
[Node Editor](https://docs.blender.org/manual/en/latest/interface/controls/nodes/node_editors.html)'s
`WINDOW` region in overlapping tiles, stitches with
[NumPy](https://numpy.org/doc/stable/), and saves through
[`imbuf`](https://docs.blender.org/api/current/imbuf.html). No re-rendering.

**Status:** 0.6.0. M0–M5 are implemented (Shader/Geometry Nodes/Compositor/Texture),
the legacy 4.2–5.1 path is validated for Shader/GN/Texture on Blender 4.2.23, 4.5.9
and 5.1.2, and cancel/error/undo are tested on 4.2–5.3. Compositor on 4.2–5.1 is
guarded due to a native crash. Linux/macOS and M7–M9 hardening/packaging remain.

**Agreed identifiers** (do not rename without approval):

| Item | Value |
|---|---|
| Display name | Node Atlas |
| Manifest id | `node_atlas` |
| Operators | `node_atlas.export_png`, `node_atlas.export_as` |
| Panel / tab | `NODE_PT_node_atlas` / **Node Atlas** |
| Preferences | `NodeAtlasPreferences` |

## 2. Source of truth

[`NodeGraph_Export_Report.md`](NodeGraph_Export_Report.md) is authoritative and contains
**measured facts**, not suggestions. Read §4.3–4.6 before geometry/capture/stitching,
§5 before design decisions, §6 for the validated algorithm, §11 for test expectations.
Do not simplify a formula, constant or ordering without reproducing the measurement.
If implementation diverges, say why and update the report.

## 3. Layout

```text
node_atlas/              # extension/add-on root
├─ __init__.py           # registration, menus, panel
├─ operators.py          # timer job, progress, cancel, file dialog
├─ capture.py            # snapshot/restore, tree switch, tiles, adapters
├─ bounds.py             # view metrics, bounds, layout, selected-only copy
├─ stitch.py             # canvas, feathering, top crop, PNG save
├─ preferences.py        # global defaults
├─ log.py                # namespaced logger
└─ blender_manifest.toml
tests/                   # unit + live-GUI scripts, fixtures
reference/prototypes/    # archived validated research scripts
```

Keep the manifest at the package root. The package must work both as a classic add-on
and as an extension. Do not commit generated artifacts.

## 4. Environment

- **Blender 4.2+ target**, primary development on **5.3.0 / Windows**; Blender 4.2.23,
  4.5.9, 5.1.2, 5.2.4 and 5.3.0 are validated for the Shader/GN/Texture paths. The
  Compositor on 4.2–5.1 is guarded because of a native crash; Linux/macOS QA is
  pending. Test 4.2 LTS, 4.5 LTS, 5.1, 5.2, 5.3 on Windows/macOS/Linux.
- **[Python 3.11](https://www.python.org/)** is bundled with 4.2+; NumPy is available
  inside Blender. No third-party dependencies (no [Pillow](https://python-pillow.org/),
  no wheels).
- **GUI only.** `--background` cannot capture UI; pixel tests need a real window.
- **No build step.** Symlink/junction the package into `scripts/addons/` or install it
  as an extension; reload with *F3 → Reload Scripts*.
- LF line endings, UTF-8, no generated files committed.

## 5. Non-negotiable rules

Verified on Blender 5.3.0. Violating them yields plausible-looking but wrong images.

1. **Positions and sizes scale differently.**
   [`view_to_region(node.location)`](https://docs.blender.org/api/current/bpy.types.View2D.html#bpy.types.View2D.view_to_region)
   is wrong when effective UI scale ≠ 1. Always use:

   ```python
   upp = (v2d.region_to_view(100, 0)[0] - v2d.region_to_view(0, 0)[0]) / 100.0
   k   = 1.0 / upp                      # px per node unit — sizes
   S   = prefs.system.ui_scale * prefs.view.ui_scale
   s   = S * k                          # px per node unit — positions
   ox, oy = v2d.view_to_region(0.0, 0.0, clip=False)
   left = ox + s * node.location_absolute.x
   top  = oy + s * node.location_absolute.y
   right, bottom = left + node.dimensions.x * k, top - node.dimensions.y * k
   ```

   Use `location_absolute` and `dimensions` (not `height`); bounds are zero before the
   first draw.

2. **Never assume zoom.** `view2d.reset()` is non-deterministic. Prime with
   [`node.view_all()`](https://docs.blender.org/api/current/bpy.ops.node.html#bpy.ops.node.view_all),
   set scale with
   [`zoom_border`](https://docs.blender.org/api/current/bpy.ops.view2d.html#bpy.ops.view2d.zoom_border)
   (linear), then **measure** `upp`. `zoom_in/out` with an explicit factor jump to the
   clamp. Density `D = output_dpi / 96`, target `upp = S / D`, limit `upp >= 0.43311`
   (`D_max = S / 0.43311`). No PNG DPI metadata.

3. **Pan sign is inverted.** `pan(+dx, ...)` moves content left, `pan(..., -dy)` moves it
   down; steps are exact integer pixels. Anchor tile 0 with 1–2 nudge passes. Set
   `smooth_view = 0` during export, otherwise animation causes drifting tiles.

4. **Buffers are bottom-up and the final crop is top-anchored** (no `+1`):

   ```python
   c0 = UH - fh - PAD_eff              # UH = canvas height
   final = canvas[c0:c0 + fh, PAD_eff:PAD_eff + fw]
   assert (wsum[c0:c0 + fh, PAD_eff:PAD_eff + fw] > 0).all()
   ```

   [`Window.screenshot`](https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.screenshot)
   returns `(h, w, 4)` bottom-up; use
   `np.frombuffer(buf, np.uint8).reshape(h, w, 4)` and verify the returned shape. A
   naive crop silently removes the graph top; `+1` adds an uncovered black row.

5. **Crop `PAD` from every tile edge.** Edges contain scrollbar/frame/shadow pixels.
   `PAD_eff = max(16, ceil(8 * view.ui_scale))`,
   `OVERLAP_eff = max(120, 2 * PAD_eff + 32)`. Overlap mismatch means a geometry bug —
   investigate, do not feather over it.

6. **Padding is captured, never painted.** `M = padding + PAD_eff`; the band is real
   theme background, the outer `PAD_eff` is cropped. Final size is
   `ceil(content) + 2 * padding`. Add `VIS ≈ ceil(2.5 * view.ui_scale)` for the
   active-node glow, which lies outside `Node.dimensions`.

7. **Switch tree and maximize.** Switch with `pin = False` → `tree_type` →
   `show_backdrop` → `pin = True` → `node_tree`, then verify `edit_tree`. Call
   [`screen_full_area(use_hide_panels=True)`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screen_full_area),
   hide header/toolbar/sidebar/context path/gizmo, clear selection and active, then
   **re-acquire** `area`/`region`/`space`. Restore order: tree/UI/selection →
   `ui_scale`/`smooth_view` → leave maximize and re-acquire → zoom/center → `area.type`.
   If leaving maximize no-ops, retry with a fresh `win.screen.areas[0]`. Call
   `redraw_timer(DRAW_WIN_SWAP, 1)` before every shot.

8. **Compositor:** use
   [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group)
   (5.3; deprecated in 6.0), `show_backdrop = False`, output
   [`NodeGroupOutput`](https://docs.blender.org/api/current/bpy.types.NodeGroupOutput.html).
   Detect and crop the asset-shelf regions **after** switching tree type
   (≈102 px on Compositor; `show_region_asset_shelf` is read-only).

9. **Selected-only = temporary filtered copy.**
   [`nt.copy()`](https://docs.blender.org/api/current/bpy.types.ID.html#bpy.types.ID.copy)
   the tree, keep `node.select` plus descendants of selected frames, unparent kept nodes
   from unselected frames preserving `location_absolute`, remove the rest,
   display/capture, restore the original, then
   [`bpy.data.batch_remove([tmp])`](https://docs.blender.org/api/current/bpy.types.BlendData.html#bpy.types.BlendData.batch_remove).
   Hidden selected nodes are skipped; empty selection warns. Crop-only and `node.hide`
   are rejected (they leave nodes or placeholders).

10. **Undo must stay untouched.** Use RNA/data APIs only. **Never** call
    [`undo_push`](https://docs.blender.org/api/current/bpy.ops.ed.html#bpy.ops.ed.undo_push),
    `node.delete`, `node.duplicate`, `node.select_all` or any undoable operator from the
    pipeline.

11. **Snapshot/restore and preferences.** Snapshot before mutation; restore in reverse
    order in `finally`: tree/pin, regions, gizmo, context path, selection/active,
    `view.ui_scale`, theme, `smooth_view`, view (nearest pixel). Never save preferences
    and never call
    [`read_homefile`](https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.read_homefile).
    Handle missing windows/areas; abort but still restore.

12. **Saving:** [`imbuf.new`](https://docs.blender.org/api/current/imbuf.html) +
    [`ImBuf.with_buffer`](https://docs.blender.org/api/current/imbuf.types.html) +
    `np.frombuffer(buf, ...)[:] = arr`, then `imbuf.write(..., filepath=...)`.
    `buf[:] = arr` fails. Write `*.tmp.png` then `os.replace`. 4.2–5.1 fallback:
    the NumPy PNG writer in `stitch._write_png_numpy` (no color-management
    round-trip); `bpy.data.images` is not used for saving.

13. **Version adapters:** 5.2+ uses `Window.screenshot`; 4.2–5.1 uses
    [`screenshot_area`](https://docs.blender.org/api/current/bpy.ops.screen.html#bpy.ops.screen.screenshot_area)
    with forced PNG/Image settings and a header crop. Detect capabilities (`hasattr`),
    do not scatter version checks.

14. **Memory:** RGBA uint8 ≈4 B/px; float accumulator ≈16 B/px. Enforce `max_mp`, use
    [`np.memmap`](https://numpy.org/doc/stable/reference/generated/numpy.memmap.html)
    or split output for huge graphs, warn near `D_max`.

## 6. Coding conventions

- English for code, comments, docs, commits.
- Idempotent `register()`/`unregister()`; remove menus/keymaps on unregister.
- All ids use the `node_atlas.` prefix.
- Long work runs in a cancellable timer state machine, never a blocking `execute()`.
- Centralize state mutation in one snapshot/restore helper; keep geometry/stitching as
  pure functions testable without a window.
- Keep the add-on importable headless; no import-time side effects.
- Reference the report section in comments for non-obvious math.

## 7. Definition of done

A change is done only after a live GUI run. Verify: size `ceil(content) + 2*padding`;
`holes = 0`; real padding with no frame/scrollbar; overlap diff < 0.1; node positions
within 2 px; repeatable `view_all` exports; full state restored after success, cancel and
injected exception; undo sentinel passes. Compare geometry invariants, not pixels, across
machines. Record Blender version, OS, `system.ui_scale`, region size, `D`, `padding`,
grid. Full matrix: report §8 and plan §6.

## 8. Documentation

- Update the report with the measurement when a fact changes; keep this file and
  `README.md` in sync (README is user-facing).
- External references must be clickable Markdown links to canonical sources on first
  mention in a document/major section — not every repetition, and never bare URLs.
  Internal references use relative links. The rule applies to prose, not code.
- Canonical starts: [Blender API](https://docs.blender.org/api/current/),
  [Blender manual](https://docs.blender.org/manual/en/latest/),
  [Blender release notes](https://developer.blender.org/docs/release_notes/),
  [extension docs](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html).
- Project is [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html); write original code
  and comply with competitor licenses.

## 9. Git

- **Local commits are allowed and encouraged** after a coherent verified change.
- **Do not push** or add/change remotes; do not publish branches, tags, releases or PRs.
- **Commit messages:** English, plain imperative, **no conventional prefixes** such as
  `feat:`, `docs:`, `fix:` or `chore:`. Start with a verb that states the change, e.g.
  `Add ...`, `Remove ...`, `Implement ...`, `Fix ...`, `Update ...`, `Refactor ...`.
  Keep the subject short; use the body for the *why* and report/milestone references.
- **Version tags:** every milestone/release commit that bumps the version (`0.1.0` …
  `1.0.0`) must carry an annotated tag `vMAJOR.MINOR.PATCH` on that exact commit:

  ```bash
  git tag -a v1.0.0 -m "NodeAtlas 1.0.0"
  ```

  The tag, the manifest version and `__version__` must match. Pre-releases use
  `vX.Y.Z-rc.N`. Tag only the version-bump commit; ordinary feature/fix/docs commits do
  not get a tag. Never move, delete or reuse a tag — ship a new patch version instead.
  Tags stay local; the no-push rule applies to them too.
- Do not rewrite history unless explicitly asked.
- Check `git status` before committing; no captures, `dist/`, `*.blend1`,
  `__pycache__/`.
