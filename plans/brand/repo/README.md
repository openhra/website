# OpenPlans repository artwork

These assets reuse the OpenPlans [P] mark, path-drawn OpenPlans wordmark and shared OpenHRA tokens. They are self-contained: no remote fonts, scripts or linked images. The ground is true white in every OS theme.

## README header

Copy `readme-header-light.svg` into `brand/repo/` in the source repository, then place this at the top of its README:

```html
<img src="brand/repo/readme-header-light.svg" alt="OpenPlans by OpenHRA — US health plan data. On your server." width="960" height="280">
```

The existing filename is retained for handoff compatibility. The dark header is retired; use this one white image without a theme-selecting picture element. Keep the aspect ratio, and keep a normal text project heading and description below the artwork so the README remains useful when images do not load. Development status and coverage limits belong in that text, not in a badge or an image that can become stale.

## Social preview

Upload `social-preview.png` as the repository’s social preview when preparing the public repository. It is exactly 1280 × 640 pixels, with a fixed white background and 64 px outer margins. `social-preview.svg` is its editable source. Nothing has been uploaded by this lane.

The PNG is rendered directly from the SVG in a browser at its intrinsic dimensions. If the SVG changes, regenerate the PNG at 1280 × 640 with device scale 1 and compare the result with the source. Do not resize a proof-page screenshot. No site build step is required.

## Proof and palette

Serve this site root locally and open `/brand/repo/` to compare the white header, SVG social source and delivered PNG, alongside marks and lock-ups. Check at 1280 and 390 px under both light and dark OS settings. The proof uses only local assets and the shared styles; favicons alone retain tab-colour adaptation.

`../tokens.css` is the single source of truth. Self-contained SVG exports copy `bg`, `ink`, `accent`, `muted` and `line` from it; do not invent a separate repository palette. Refresh these snapshots and the PNG when the tokens change. The full values and contrast ratios are in [BRAND.md](../BRAND.md#colour).

SVG layouts are authored directly. The embedded logo paths are copied from `../logo-openplans.svg`; do not redraw or typeset the wordmark. No badges, hosting-service logos or adoption claims are included.
