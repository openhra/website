# OpenHRA brand system

## Positioning

OpenHRA builds open-source, self-hosted tools for individual coverage HRAs and health benefits. It uses public data and keeps the sources. Its first project, OpenPlans, turns public health-plan files into an API for plans, premiums, subsidy estimates, drugs and providers. It states data gaps and current coverage limits.

Each project's public repository is its main page. Websites introduce the work and point to the source. See [Repository first](REPO-FIRST.md) for page hierarchy, documentation ownership and repository artwork.

## Name

Write OpenPlans with a capital O and capital P in page copy, headings, metadata, accessible labels and artwork. Keep technical identifiers exactly as supplied: `openhra/openplans`, repository URLs, package/CLI names, filenames and `OPENPLANS_*` variables. The publisher User-Agent remains `openplans/0.1 (public health-plan source discovery; +https://plans.openhra.com/)` verbatim. A repository path printed in artwork is still a technical identifier.

## Character and voice

Calm, precise and useful. Write for people evaluating an integration, operating a service or understanding a request in their server logs. Treat insurers and other data publishers as partners. Their files make this work possible.

| Rule | Do | Don't |
| --- | --- | --- |
| Lead with what exists | "US health plan data. On your server." | "The future of health benefits." |
| Make provenance concrete | "Every answer can be traced to the public file it came from." | "Data you can always trust." |
| State limits alongside capabilities | "Texas and Florida, for every insurer whose published files could be read." | "Complete nationwide coverage." |
| Describe missing data honestly | "Unknown stays unknown." | "We fill every gap." |
| Respect publishers | "It downloads only files you publish for the public." | "We break through the barriers." |
| Prefer facts to competition | "Built from public sources." | "Taking on the insurers." |
| Keep invitations practical | "Open the repository." | "Transform your business today." |
| Keep status visible | "Public preview." | "Production-ready." |

Use sentence case for headings, short paragraphs and descriptive links. Keep identifiers, flags and API paths exact; set them in monospace. Explain ICHRA before using it with a general audience. Numbers need a source and date. Never invent adoption, performance, endorsements or road-map commitments. Never publish contact addresses in source or docs; retain the existing contact verification flow.

Legal notices, attribution, licence statements and affiliation disclaimers are outside a voice pass. The inherited text remains unchanged.

## Colour

Use light colours only for now, by owner direction on 2026-11-08. The page background is true white, `#ffffff`, in both light and dark OS settings. Use teal for the identity, dark green for body text and muted green-grey for secondary text. Define the colours in `tokens.css`. Both sites import it, declare `color-scheme: light`, and use a matching HTML colour-scheme hint before CSS loads. Only favicons adapt to the browser tab colour.

Keep section bands, repository cards and illustration backgrounds white. Divide long pages with fine horizontal rules, generous whitespace, numbered labels and column dividers. Do not alternate tinted backgrounds. Hero panels have a thin teal top edge. Keep the [H] construction grid and [P] repository lock-up prominent. Use pale neutral fills only for table headings, code and the verification placeholder. No shadows or broad tinted panels.

| Semantic token | Value | Use |
| --- | --- | --- |
| `--bg` | `#ffffff` | Page ground, header and footer |
| `--surface` | `#ffffff` | Section bands and white panels (aliases bg) |
| `--surface-subtle` | `#f5f8f7` | Table headers and reserved verification area only |
| `--ink` | `#173e37` | Headings and body text |
| `--muted` | `#53665f` | Secondary text and notes |
| `--line` | `#d9e3df` | Decorative rules, panel edges and construction grid |
| `--line-strong` | `#6b8279` | Meaningful diagram edges and connectors |
| `--accent` | `#0b6258` | Links, marks, primary actions and focus |
| `--accent-ink` | `#ffffff` | Text on accent fill |
| `--accent-soft` | `#edf7f3` | Touch feedback only |
| `--support` | `#4b617e` | Optional secondary annotation |
| `--code-bg` | `#f0f5f3` | Commands and identifiers only |
| `--diagram-bg` | `#ffffff` | White repository card and illustrations (aliases surface) |

Use the fixed teal ramp for illustrations and semantic tokens for text and controls. Do not assume every ramp colour is readable as text on white.

| Token | Hex |
| --- | --- |
| `--teal-50` | `#edf7f3` |
| `--teal-100` | `#d7eee6` |
| `--teal-300` | `#9bd6c5` |
| `--teal-400` | `#70cbb5` |
| `--teal-600` | `#167367` |
| `--teal-700` | `#0b6258` |
| `--teal-800` | `#114c44` |
| `--teal-950` | `#102d29` |

### Measured contrast

Contrast uses WCAG sRGB relative luminance, rounded to two decimals. Every normal-text pair must reach 4.5:1. Meaningful non-text graphics and focus indicators must reach 3:1. The matrix covers all site text roles on permitted backgrounds, including optional support and touch-feedback colours. White applies equally to `bg`, `surface` and `diagram-bg`. This audit covers site colours. It excludes the existing third-party verification frame.

| Foreground | White | `surface-subtle` | `code-bg` | `accent-soft` | Requirement |
| --- | ---: | ---: | ---: | ---: | --- |
| `ink` | 11.79:1 | 11.04:1 | 10.70:1 | 10.78:1 | 4.5:1 |
| `muted` | 6.12:1 | 5.72:1 | 5.55:1 | 5.59:1 | 4.5:1 |
| `accent` | 7.24:1 | 6.77:1 | 6.57:1 | 6.62:1 | 4.5:1 |
| `support` | 6.34:1 | 5.94:1 | 5.76:1 | 5.80:1 | 4.5:1 |

| Additional pair | Ratio | Requirement |
| --- | ---: | --- |
| `accent-ink` / `accent`. Primary action, selection and skip link | 7.24:1 | 4.5:1 |
| `bg` / `ink`. Primary action hover | 11.79:1 | 4.5:1 |
| `line-strong` / `bg`. Meaningful diagram connectors on white | 4.12:1 | 3:1 |
| `line-strong` / `surface-subtle`. Meaningful edges on the table-header surface | 3.86:1 | 3:1 |
| `accent` / `line`. Mark across decorative construction-grid lines | 5.51:1 | 3:1 |

Use full-contrast `accent` for focus with a 5 px offset. This places the indicator against the surrounding white or pale background, outside the filled action. Do not use `line` for text or as the sole boundary of an interactive control. Its rules and grid are decorative. Headings, spacing and labels establish the structure. Do not apply opacity to text. Links in prose remain underlined. White text is reserved for solid `accent` or `ink` fills.

### Bringing dark back later

The dark theme has been removed. Do not keep it in an unused selector or restore the old values piecemeal. If the owner requests it, design and measure a complete semantic override in `tokens.css`, revise both HTML colour-scheme hints, and update standalone logo/mark exports together. Recheck every text, hover, focus, code, table and diagram pair, then capture both sites at desktop and phone widths in both OS settings. Only introduce a second README asset and theme selector if the owner also wants adaptive repository artwork. The current fixed-white exports remain white until then; version history retains the former dark artwork.

## Type

No font downloads. Headings and body use `system-ui, sans-serif`; code, labels and data use `ui-monospace, monospace`. The logo's main lettering is drawn as vector paths, independent of installed fonts. Its small endorsement uses the system font stack.

| Role | Size | Weight / line height | Notes |
| --- | --- | --- | --- |
| Desktop hero | 52–66 px | 550 / 1.04 | −.055em tracking; two clear phrases |
| Phone hero | 40–58 px | 550 / 1.04 | −.045em tracking at narrow widths |
| Section heading | 28–38 px | 550 / 1.16 | −.035em tracking |
| Subheading | 17–18 px | 650 / 1.35 | Sentence case |
| Body | 15–16 px | 400 / 1.65 | Maximum 70 characters per line |
| Intro | 16–17 px | 400 / 1.75 | Secondary colour |
| Navigation / actions | 12–14 px | 550–600 | At least 44 px target height |
| Eyebrow / table heading | 9–11 px | 500 / 1.5 | Uppercase; metadata only |
| Code / data / notes | 11–14 px | 400 / 1.7–1.8 | Numeric columns use tabular figures |

Small uppercase labels supplement the copy. They must not be the only explanation of a feature. Keep body copy readable and content in order when zoomed. Let tables wrap. If a table needs scrolling, its container must remain keyboard-focusable.

## Mark and wordmarks

Use [H] for OpenHRA and [P] for OpenPlans. Both marks keep the original open square brackets, teal colour and rounded joins. The capital letter distinguishes the organisation from its project. The OpenPlans lock-up uses [P] with the small text endorsement "by OpenHRA". Never add an [H] mark beside that endorsement.

The OpenPlans lettering uses the same "Open" paths, 2.7-unit rounded strokes, cap height and spacing rules as OpenHRA. Its capital P uses the OpenHRA R bowl without the diagonal leg. The remaining lowercase letters use the same style. Keep the [P] mark and "by OpenHRA" endorsement unchanged.

Construction uses a 32 × 32 unit grid and 4-unit strokes throughout. The bracket path remains `M12 4H4v24h8M20 4h8v24h-8`: vertical centres at x=4 and x=28, square caps and round joins. Its painted bounds are x=2…30 and y=2…30. Keep this construction identical for both marks.

The capitals share painted cap bounds y=8…24 and a 4-unit weight. [H] uses stems at x=12 and x=20 from y=10 to y=22, joined at y=16. [P] uses a stem at x=12 from y=10 to y=22 and a closed upper bowl to x=20 and y=16. The P bowl's counter remains open. Both letters occupy x=10…22, centred within the bracket opening; the P's longer lower stem balances its upper bowl. Do not replace these paths with a font glyph.

At 16 px, the 4-unit stroke becomes 2 px, the H's inner spaces stay open and the P has a 2 × 1 px counter. Use the same paths at 16, 24, 32 and 64 px. No alternate micro mark is needed. The asset proof includes both marks, both favicons and their monochrome variants at these sizes. Check them on white in both OS settings after any geometry change; favicons also need a browser-tab check.

- `mark-openhra.svg` and `mark-openplans.svg`: standalone fixed teal [H] and [P] for white.
- `logo-openhra.svg`: [H] and the original geometric OpenHRA wordmark.
- `logo-openplans.svg`: [P], the path-drawn OpenPlans wordmark and the small text endorsement.
- Each mark and lock-up has a `-mono.svg` counterpart using fixed neutral ink on white.
- Root `favicon.svg`: adaptive [P] for the plans site.
- `openhra/favicon.svg`: adaptive [H], copied to the sister site's root as its own favicon.
- Repository README headers and the social preview use [P]; the OpenHRA hero uses [H]. The OpenPlans entry on the organisation page also uses [P]. Each site's footer uses its own mark.

Use a minimum of 16 px for a standalone mark, 140 px wide for the OpenHRA lock-up and 250 px wide for the endorsed OpenPlans lock-up. Allow at least 4 units of clear space outside the mark's painted bounds in layouts, and 8 units around a lock-up. Browser favicon slots retain the supplied 32-unit viewBox; do not add padding that shrinks the 16 px drawing. Keep proportions intact.

Use the supplied assets, correct letter and white ground. Do not close the bracket gaps, fill the P counter, typeset a replacement letter or wordmark, alter the stroke weight, rotate the mark, add shadows or put it over a busy image. Do not use [H] to identify OpenPlans or [P] to identify OpenHRA. No medical-cross or certification treatments.

For a single-colour print process, use the monochrome artwork in one solid ink. Inline SVG can inherit `currentColor`; external marks and logos use the fixed white-system ink and accent. Repository artwork copies the colours from `tokens.css` and includes an explicit white background. Refresh those export colours and the PNG whenever the tokens change. The README uses one image in every OS theme.

## Layout, spacing and radius

Use a 4 px base rhythm. Shared spacing tokens are 4, 8, 12, 16, 24, 32, 48, 64 and 96 px. The page frame is at most 1152 px wide, including 32 px desktop side padding; phone padding reduces to 20 px. Sections have 72 px vertical padding on desktop and 48 px on phone. Give the hero more space.

Use a 4 px radius for controls and code labels, 8 px for technical panels and tables, and 16 px for a large explanatory illustration. Use pill shapes only if a future state needs them. Avoid nested rounded cards, decorative shadows and floating dashboard elements. Prefer a ruled grid for related capabilities, and a narrow heading column alongside principles or rules.

At 760 px, hero, API and contact layouts stack. At 480 px, feature grids become a single column. The verification container reserves 304 × 78 px, which fits a 360 px viewport with room for its side padding. Do not shrink or crop the verification widget.

## Iconography and imagery

Use simple, single-colour line symbols. Use a short arrow for navigation, a return-shaped arrow for a rule, and the frame mark for project identity. Give decorative symbols `aria-hidden="true"`. Every action keeps a visible text label. Use the accent at full contrast. Avoid icon libraries and their network requests.

Illustrations explain real relationships. The OpenPlans diagram shows public source files entering an API on the operator's own server. The umbrella illustration enlarges the mark on a construction grid. These are explanatory illustrations. Do not present them as product screenshots or invent a dashboard. No stock hospital imagery, portraits, customer logos, shields, growth charts or imagery suggesting endorsement. No animation is needed. Respect reduced-motion preferences.

## Implementation and sister-site handoff

`tokens.css` owns colour, type families, spacing and radii. `site.css` owns shared components. Each site's root `style.css` imports those two files, then applies its own layout rules. All requests stay local except the existing contact verification script and frame. The local `mcp-copy.js` handles endpoint copying on both pages and makes no network requests. There is no frontend build step, new dependency, font request or tracking.

For the sister-site handoff, copy these files into that site's existing checkout:

1. `brand/openhra/index.html` → root `index.html`.
2. `brand/openhra/style.css` → root `style.css`.
3. `brand/tokens.css`, `brand/site.css` and all `brand/*.svg` → the same paths under `brand/`.
4. `brand/openhra/favicon.svg` → root `favicon.svg` (the [H] favicon; the plans root favicon is [P]).
5. `mcp-copy.js` → root `mcp-copy.js`.

Keep the sister site's existing `contact.js`, `api/contact.js` and hosting configuration. The HTML uses root-relative asset paths for this handoff. Opening the nested HTML as a file does not reproduce the intended deployment. Preview it with the handoff files mapped to a local site root. The current page sources are `plans/index.html` and `openhra/index.html` in the website tree. Keep the handoff copies aligned with the organisation page and styles.
