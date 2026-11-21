# NodeAtlas context map

`AGENTS.md` is loaded automatically; do not re-read it. This map turns a task into the
smallest set of files, measured report sections, and one focused test command. Load only
what the task needs; the research report alone is about 27k tokens.

## Do not read these end to end

| File | Approx. tokens | Read instead |
| --- | ---: | --- |
| `NodeGraph_Export_Report.md` | 27k | one section with `python tools/doc.py NodeGraph_Export_Report.md 4.6`; chapter 4 is 4k, chapter 11 is 9k |
| `IMPLEMENTATION_PLAN.md` | 8k | archived 1.0.0 record; one milestone with `python tools/doc.py IMPLEMENTATION_PLAN.md M7` |
| `ROADMAP.md` | 0.5k | read whole for scope; `Now` is the active unit, `Next` the one after |
| `QA_REPORT.md` | 3k | grep the version or test name; open the Packaging section for artifacts |
| `CHANGELOG.md` | 2k | grep the version; older entries are history, not behavior |
| `RELEASE_NOTES.md` | 2k | the first release block only |
| `README.md` | 1.4k | grep the setting or error text; it is user-facing copy |
| `node_atlas/capture.py` | 6k | grep the function, then read 80-150 lines around it |
| `node_atlas/operators.py` | 7k | grep the state or operator, then read the matching block |
| `tests/unit/test_core.py` | 4k | grep `def test_` for the named case; run the whole file anyway |
| `tests/gui/*.py` | 1-2k each | open only the scenario under test |
| `reference/prototypes/` | large | frozen evidence; grep a symbol, never sweep |
| `tests/fixtures/*.blend` | binary | never open; regenerate with the scripts in `tests/fixtures/README.md` |
| `dist/*.zip` | binary | never read; validate and install it |

`python tools/doc.py --list <file>` prints the headings and line numbers. A numeric query
matches the exact heading number (`4` is the chapter, `4.3` is one section); a text query
matches a heading prefix (`M7`). Use `--max-lines N` when a section is still too large.

## Task map

| Task | Start here | Measured facts | Focused check |
| --- | --- | --- | --- |
| Node rectangles, bounds, layout | `node_atlas/bounds.py` (`node_rect`, `compute_layout`) | report §4.2, §6.2, §11.5 | `tests/unit/test_core.py` |
| View scale, `upp`, DPI clamp | `bounds.py` (`measure_view`, `target_upp`, `planned_scale`) | report §4.3, §11.7, §11.9 | `test_core.py`, `tests/gui/test_density.py`, `test_boost.py` |
| Selected-only copy | `bounds.py` (`selected_node_names`, `build_selected_copy`) | report §11.15 | `test_selected.py`, `test_estimate_selected.py` |
| Tile capture, pan, anchor | `capture.py` (`capture_tile`, `pan`, `anchor_first_tile`) | report §4.4-§4.5, §11.1-§11.4, §11.8 | `test_export.py`, `test_repeat.py`, `test_scaling.py` |
| Maximize, leave, lost area | `capture.py` (`maximize`, `leave_maximize`, `find_area_by_bbox`) | report §11.10, §11.13 | `test_multiarea.py`, `test_multiwindow.py`, `test_arealost.py` |
| Version adapter: 5.2+ raw vs 4.2-5.1 area | `capture.py` (`can_capture_raw`, `_capture_tile_legacy`) | report §4.4, §11.1 | `test_legacy.py`, `test_artifact.py` |
| Shader/GN/Compositor/Texture switch | `capture.py` (`assign_tree`, `get_node_context`) | report §11.12; the 4.2-5.1 Compositor guard is in `operators.py` | `test_trees.py`, `test_texture.py` |
| Nested group path and `pin` | `capture.py` (`apply_tree_path`, `_restore_tree_path`) | report §11.13 | `test_group.py` |
| Stitching, feather, top crop, holes | `stitch.py` (`stitch_tiles`) | report §4.6, §11.8 | `test_core.py` |
| Long links crossing tiles | `capture.py` (`select_outside_view`, `mute_link_highlight`), `operators.py` (`_capture_one`) | report §5 item 17 | `test_longlink.py` |
| PNG save, `pHYs`, EXIF, fallback | `stitch.py` (`save_png`, `_insert_png_phys`, `_write_png_numpy`) | report §4.6, §11.7, §11.9 | `test_core.py`, `test_naming.py`, `test_artifact.py` |
| Memory cap, memmap, huge graphs | `stitch.py` (`_allocate_canvas`), `operators.py` estimate | report §11.9 | `test_large.py`, `test_maxmp.py`, `test_limits.py` |
| Output path, read-only, disk full | `stitch.py` (`check_output_path`) | - | `test_readonly.py`, `test_diskfull.py`, `test_path.py` |
| Timer job, progress, cancel | `operators.py` (`ExportJob`, `_job_tick`, `start_job`) | report §6.2, §11.13 | `test_cancel.py`, `test_fail.py` |
| Clipboard and Open Last Export | `operators.py` (`_copy_result`, `NODE_ATLAS_OT_open_last_export`) | - | `test_clipboard.py` |
| Filename pattern and tokens | `operators.py` (`render_filename`, `_filename_fields`) | - | `test_naming.py`, `test_path.py` |
| Preferences, panel, estimate, menus, keymap | `preferences.py`, `node_atlas/__init__.py` (`_estimate`) | report §6.5 | `test_core.py`, `test_estimate.py`, `test_artifact.py`, manual GUI |
| Undo neutrality | every pipeline module | report §11.16 | unit + `test_export.py`, `test_fail.py` |
| Extension manifest and packaging | `node_atlas/blender_manifest.toml` | report §4.7; `QA_REPORT.md` Packaging | `blender --command extension validate` |
| New OS or display scaling | `preferences.py` (desktop branches), `capture.py` (`capture_tile`) | report §7 items 3 and 16 | [`live-check.md`](live-check.md) §2 |
| README images | `docs/make_images.py` | - | GUI run; print dimensions, do not view |
| Release, version, tag | [`release.md`](release.md) | - | full matrix recorded in `QA_REPORT.md` |
| Extension platform submission | - | - | owner-only; no agent file, the agent prepares files and stops |
| Transparent background (not shipped) | `reference/prototypes/matte_*` | report §11.14 | prototype only; do not wire into the pipeline |

## Reading recipe

1. Locate the section with `--list`, then print it:
   `python tools/doc.py NodeGraph_Export_Report.md 4.6`.
2. For code, grep the symbol first (`rg`, `Select-String`); read a slice under about 200
   lines and expand only the call sites that matter.
3. Use the `explore` subagent for "where does this happen" / "how do these modules fit"
   questions; keep the main context for edits and test output.
4. Run the unit suite first, then the smoke matrix or one focused GUI test. The full
   matrix belongs to a release, not to every edit. The test inventory is
   `tests/README.md`; the procedure is [`live-check.md`](live-check.md).
5. Do not open an exported PNG to judge geometry. Print width, height, DPI, holes, overlap
   difference and node positions with a short script. View an image only when a visual
   decision (padding, feather, theme, text) depends on it.
6. Keep tool output short: `Select-String`, `--tail`, one test, a grep. Paste the command
   and the verdict, not the whole Blender log.

## Budget signals

- Full report: 27k tokens. Chapter 4 (`§4`): 4k. Chapter 6 (`§6`): 3.5k. Chapter 11
  (`§11`): 9k. One validation subsection (`§11.8`): 0.4k.
- `capture.py` + `operators.py` together are 13k; read one function block, not both files.
- `test_core.py` is 4k but running it is cheap; run the file instead of reading it.
- The five-version GUI matrix is dozens of Blender launches; one targeted test is minutes,
  the matrix is an afternoon. Say which one you ran.
