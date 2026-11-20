# NodeAtlas roadmap

Post-1.0 scope. The 1.0.0 plan is complete and kept in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) as a record; this file owns what comes
next.

**Policy:** one feature per release, no dates and no promise attached to an entry. A
feature moves from `Next` to a version number only after the shipped release has been on
the platform long enough to show real demand. Fixes ship as `1.4.x`, features as `1.5.0`.

## Now

- **Verify Blender 6.0.** The Compositor path depends on
  [`scene.compositing_node_group`](https://docs.blender.org/api/current/bpy.types.Scene.html#bpy.types.Scene.compositing_node_group),
  which is deprecated in 6.0. This is compatibility, not a feature, and it needs a 6.0
  build to test.

## Next

- **Batch export.** Write every node tree of one type, or every group in the current tree,
  as separate PNGs with collision-safe names. Deferred from 1.0.0 twice (report §6.5,
  plan §8) to keep the panel small. Cost: a loop over trees, filename collisions, one
  snapshot/restore per tree, and new tests.
- **Transparent background.** Two-background matting is validated (report §11.14:
  mean |Δα| = 0.000000, foreground min 0.9908), so the method is sound. Cost: two captures
  per tile, roughly twice the export time, plus an alpha write path through `imbuf` and
  the NumPy fallback on 4.2–5.1. Ships behind an experimental flag, as the plan proposed.

## Later

- **Linux and macOS QA.** The code has no known platform dependency; there is simply no
  test record. Needs hardware, not code.
- **Second physical monitor.** Two windows on one display are covered; physical placement
  is not scripted.

## Not planned

- SVG, JSON or HTML output, headless capture, AI upscaling: different products, and
  headless capture cannot see the editor at all.
- Batch across all four tree types in one run: it multiplies the state machine and the
  test matrix for a case that overlaps with `Next`.
