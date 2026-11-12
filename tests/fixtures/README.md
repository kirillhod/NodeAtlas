# Test fixtures

The `.blend` fixtures are **generated locally and not committed**: they can embed
machine-specific state. Generate them with the scripts in this directory, using the
Blender version under test:

```powershell
blender --background --factory-startup --python tests/fixtures/make_scene_uniq.py
blender --background --factory-startup --python tests/fixtures/make_scene_small.py
blender --background --factory-startup --python tests/fixtures/make_scene_both.py
blender --background --factory-startup --python tests/fixtures/make_scene_graphs.py
blender --background --factory-startup --python tests/fixtures/make_scene_selected.py
blender --background --factory-startup --python tests/fixtures/make_scene_matte.py
blender --background --factory-startup --python tests/fixtures/make_scene_one.py
```

Order matters for `make_scene_both.py`: it loads `scene_uniq.blend` and
`scene_small.blend` from this directory. Scripts write next to themselves. The generated
files are ignored by Git.

Scene summary:

| Fixture | Purpose |
|---|---|
| `scene_uniq.blend` | 24 distinct nodes, six chains; reference tiling scene |
| `scene_small.blend` | Small shader graph for density tests |
| `scene_both.blend` | `M_Small` + `M_Uniq` in one file |
| `scene_graphs.blend` | Shader, Geometry Nodes, Compositor trees |
| `scene_selected.blend` | Frames and selected-only semantics |
| `scene_matte.blend` | Transparent-background matting tests |
| `scene_one.blend` | Single-node density test |

The archived validated runners are in [`reference/prototypes/`](../../reference/prototypes/).
