# NodeAtlas release

The version lives in three places and all must match in the tagged commit:
`node_atlas/blender_manifest.toml`, `__version__` and `bl_info["version"]` in
`node_atlas/__init__.py`. `bl_info` is kept for classic add-on compatibility.

## Steps

1. Confirm the target version and that the user explicitly asked for a release.
2. Bump all three version fields in one commit. `bl_info["version"]` is a tuple:
   `(1, 3, 6)` for `1.3.6`.
3. Update the records in the same change:
   - `CHANGELOG.md`: a new top section with user-visible changes only.
   - `RELEASE_NOTES.md`: title, date, what's new, features and known limitations, written
     for users. Verification counts and capture paths belong in `QA_REPORT.md`.
   - `AGENTS.md` §1 status line and `QA_REPORT.md` when the matrix or counts changed.
   - `README.md` only when user-facing behavior changed.
   - `IMPLEMENTATION_PLAN.md` only when a milestone or scope changed; it is a roadmap,
     not the release log.
4. Run the unit suite, then `tests/run_matrix.ps1 -Tier smoke` on the primary version.
   A release claim needs `-Tier full` on the five-version matrix recorded in
   `QA_REPORT.md`; do not infer Linux or macOS support. The procedure is
   [`live-check.md`](live-check.md).
5. Build and validate the extension:

   ```powershell
   & $env:BLENDER --command extension validate node_atlas
   & $env:BLENDER --command extension build --source-dir node_atlas --output-dir dist
   & $env:BLENDER --command extension validate dist/node_atlas-<version>.zip
   Get-FileHash dist/node_atlas-<version>.zip -Algorithm SHA256
   ```

6. Install the zip into a clean profile and run `test_artifact.py`; also copy the folder
   into an isolated classic `BLENDER_USER_SCRIPTS/scripts/addons` profile and export
   there. Use `-UserConfig` with the runner. Record the Blender versions.

   Create the isolated `config`, `scripts` and `extensions` directories before starting
   Blender and set `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS` and
   `BLENDER_USER_EXTENSIONS`. A missing config directory falls back to the real profile.
   Do not use `repo-add --clear-all`: it rewrites the active preferences and can drop the
   user's repositories.
7. Commit the version bump and records, then tag that exact commit locally:

   ```powershell
   git tag -a v1.3.6 -m "Node Atlas 1.3.6"
   git show v1.3.6:node_atlas/blender_manifest.toml
   git show v1.3.6:node_atlas/__init__.py | Select-String '__version__|"version"'
   git tag --list 'v*'
   ```

## Rules

- A commit that lacks any of the three version updates is not a release commit.
- Never move, delete, or reuse a tag; ship a new patch version instead.
- Never push, publish a release, upload to an extension platform, or create a PR.
- `dist/` is ignored; never commit the zip or a hash file.
- Release notes are for users: what's new, features, supported versions, known
  limitations. No test matrix, capture paths, hashes or publishing status — those belong
  in `QA_REPORT.md`. No Install section, no marketing.
- Be honest in the notes: GUI-only capture, Compositor on all validated versions
  (selected-only 5.1+), Linux/macOS untested, temporary DPI boost, nearest-pixel view
  restore.
