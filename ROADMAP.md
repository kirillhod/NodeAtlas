# NodeAtlas roadmap

Post-1.0 scope. The 1.0.0 plan is complete and kept in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) as a record; this file owns what comes
next.

**Policy:** one unit of work at a time, no dates. A unit is a fix or a feature: fixes ship
as `1.4.x`, features as `1.5.0`. `Now` holds the unit in progress; `Next` holds the unit
after it. An entry carries a goal and a checkable exit, or it stays in `Backlog`. When a
unit ships and its release is tagged, it leaves the file and `Next` moves up. Measurements
live in the [report](NodeGraph_Export_Report.md), test evidence in
[`QA_REPORT.md`](QA_REPORT.md); this file states intent and links to them, it does not
restate them.

## Now

### Long-link visibility — fix, `1.4.1`

**Goal:** a connection that crosses tile boundaries looks the same in the PNG as it does on
screen — continuous, not faded or missing.

**Why now:** it is the only known defect in the output itself, and `README.md` documents it
as "long links may fade". It appears on exactly the large graphs the add-on exists for, it
is cheaper than anything in `Backlog`, and it needs no unreleased Blender build — unlike
the 6.0 watch item, which cannot start.

**Exit:**

- links spanning two and three tiles are continuous in the final PNG on 4.2 and 5.3 at
  96 and 128 DPI (the full matrix belongs to the release);
- overlap difference within tolerance, `holes = 0`, node positions within 2 px (report §8);
- full state restored after success, cancel and injected failure; undo sentinel passes;
- `README.md` no longer calls this a limitation, or states the residual Blender limit and
  the workaround when both sockets are offscreen.

**Cost:** an ordering or draw change in the tile loop plus the usual live check; no new
control and no panel change.

## Next

### Capture-area preview — feature, `1.5.0`

**Goal:** see exactly what will be captured, including padding, before a long export starts.

**Why now:** a paid competitor has it, and the bounds and pixel estimate are already
computed for the panel, so the change is presentation only. A mis-framed run costs minutes
and a second run.

**Exit:**

- the outline matches the exported rectangle for both scopes and for zero and non-zero
  padding: the drawn rect equals the computed bounds, and the PNG is
  `ceil(content) + 2 * padding`;
- the overlay never reaches the captured pixels: exports with the toggle on and off are
  identical, with `holes = 0` in both;
- the draw handler is removed on unregister and does not leak across areas or exports;
- state restore and undo neutrality are unchanged.

**Cost:** a draw handler, a toggle and its restore, and a geometry test; the pixel maths does
not change.

## Backlog

Ideas that have not earned a slot. An entry moves to `Next` only when it gets a goal and a
checkable exit.

| Entry | State |
|---|---|
| Transparent background | Method measured (report §11.14: mean \|Δα\| = 0.000000, foreground min 0.9908). Cost: two captures per tile and an alpha path through `imbuf` and the NumPy fallback. |
| Batch export | Deferred from 1.0.0 twice (report §6.5, plan §8). Cost: a loop over trees, collision-safe names, one snapshot per tree. |
| Hide the grid | Cosmetic: a clean background without grid lines. |
| JPG and WEBP output | A second encoder and a lossy quality choice; PNG is the only format today. |
| Split tiles or frames into separate files | A documentation workflow, not a capture improvement. |
| Open the containing folder | Micro-UX: `Open Last Export` already opens the file itself. |

## Later

- **Blender 6.0 compatibility.** The Compositor path depends on
  [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group),
  which is deprecated in 6.0. No 6.0 build exists yet, so there is nothing to test and
  nothing in `Now` depends on it. When a release or beta appears: run the per-version matrix,
  Compositor included, and let the existing version adapter absorb any change.
- **Linux and macOS QA.** The code has no known platform dependency; there is simply no
  test record. Needs hardware, not code.
- **Second physical monitor.** Two windows on one display are covered; physical placement
  is not scripted.

## Not planned

- SVG, JSON or HTML output, headless capture, AI upscaling: different products, and
  headless capture cannot see the editor at all.
- Batch across all four tree types in one run: it multiplies the state machine and the
  test matrix for a case that overlaps with `Backlog`.
