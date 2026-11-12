# Archived research prototypes

These scripts are the validated prototypes referenced by
[`NodeGraph_Export_Report.md`](../../NodeGraph_Export_Report.md). They are **reference
material**, not part of the add-on or its test suite.

- Written and measured against Blender 5.3.0 on Windows.
- Output paths are sanitized: scripts write under a `nodeatlas_ref` directory in the
  system temporary directory, never to a user-specific or repository path.
- Fixture generators live in [`tests/fixtures/`](../../tests/fixtures/).
- Generated `.blend` files and capture outputs are not committed.
- Some scripts expect specific fixture files (`scene_uniq.blend`, `scene_graphs.blend`,
  etc.) and must be run from a GUI Blender session.

Do not import these modules from the add-on. Reimplement the validated behavior in
`node_atlas/` following [`AGENTS.md`](../../AGENTS.md).
