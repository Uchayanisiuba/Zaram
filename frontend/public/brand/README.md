# Brand assets

Drop the exported files here. Nothing needs wiring afterwards — the interface
already looks for them and falls back to the wordmark until they arrive.

**Everything must be a local file.** `frontend/scripts/check-no-remote-assets.mjs`
fails the build on anything fetched from a CDN, and a logo is exactly the sort
of thing that gets hotlinked "just for now".

## What to export

| File | Format | Size | Used by |
|---|---|---|---|
| `zaram-mark.svg` | SVG, square viewBox | vector | The top-left mark on every workspace |
| `zaram-mark-light.svg` | SVG, square viewBox | vector | Light backgrounds, if the gradient fails contrast |
| `zaram-icon-512.png` | PNG, transparent | 512×512 | Source for the desktop icon |
| `zaram-icon.ico` | ICO, multi-size | 16/32/48/64/128/256 | Windows executable and installer |

The gradient app-icon tile from the brand sheet — rounded square, mark centred —
is the right source for `zaram-icon-512.png`. The bare glyph, no tile, no
wordmark, is right for `zaram-mark.svg`.

## Two things the export must get right

**Square viewBox on the mark.** It renders at 32×32 in the chrome and the
component sets both width and height. A viewBox with the wordmark baked in
would letterbox the glyph down to nothing.

**No text in the SVG.** The wordmark beside the glyph is live text in the
product's own display face, so it inherits weight, spacing and the gradient
treatment already in the stylesheet. A second wordmark rendered as vector paths
would drift from it at the first typographic change and would not scale with the
user's text settings.

## The Windows icon

`electron-builder.yml` picks up `build/icon.ico` by convention — that is a
different directory to this one, at the repo root. Put `zaram-icon.ico` there as
`icon.ico` as well.

Without it, the packaged executable carries Electron's default icon, which is
the single most obvious "this is a hobby project" signal in a first-run
experience whose whole job is to be trusted.

Note that `--config.win.signAndEditExecutable=false` — currently needed to build
without the symlink privilege — **skips the step that applies this icon.** The
icon and the code signature arrive together or not at all.
