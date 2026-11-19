# Extension platform submission

Owner-only checklist. An agent may prepare the zip, listing text and images, but must not
push, create a public release, upload, or submit for review.

## Gate

- The GitHub repository is public and Issues are enabled.
- Blender ID has MFA enabled.
- A GitHub Release exists with the same `node_atlas-<version>.zip` that was validated.
- The tag, manifest version, `__version__` and `bl_info["version"]` match.
- License is GPL-3.0-or-later; bundled assets are CC0; the code is Python only. No wheels,
  network calls, ads, paid gating, or Blender branding.
- The manifest has `website`, `support`, `copyright`, `tags`, and `[permissions]`. The
  platform supports the `files` and `clipboard` permissions used here.

## Assets

- Icon: 256x256 PNG.
- Featured image: at least 1920x1080, 16:9, JPG/PNG/WebP.
- Preview: at least one JPG/PNG/WebP/MP4.
- Generate them from the current UI. Do not use the Blender logo or trademarked
  third-party artwork.

## Listing text

- Describe only the shipped version: any node tree, real background padding, selected
  nodes, output DPI, clipboard, and state restoration.
- State the limits: GUI-only capture, Compositor on all validated versions (selected-only
  needs 5.1+), Linux and macOS untested,
  temporary DPI boost, nearest-pixel view restore, no transparent background, no batch
  export.
- No planned features and no donation links. This is a project decision, stricter than
  the platform rules.
- Differentiate from Node Tree Screenshot by the tiled high-resolution output and the
  restoration guarantees.

## Submit

- Open `/submit/` on [extensions.blender.org](https://extensions.blender.org/), upload
  the zip, add the description and assets, and submit.
- One version at a time; the default upload cooldown is two hours. The approval queue is
  long and review can take weeks or months.
- Do not re-upload the same version; bump the patch version instead.

## References

- [Extension documentation](https://docs.blender.org/manual/en/dev/advanced/extensions/getting_started.html)
- [Platform Terms of Service](https://extensions.blender.org/terms-of-service/)
