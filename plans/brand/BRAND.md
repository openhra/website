# OpenHRA brand system

## Positioning

OpenHRA builds open-source, self-hosted building blocks for individual coverage HRAs and health benefits, using public data with its sources kept. Its first project, OpenPlans, turns public health-plan files into an API for plans, premiums, subsidy estimates, drugs and providers, while making missing data and current coverage limits explicit.

The public repository is each project’s primary home. Websites introduce the work and send people to the source; see [Repository first](REPO-FIRST.md) for page hierarchy, documentation ownership and repository artwork.

## Name

Write **OpenPlans** (capital O, capital P) wherever the project name is read: page copy, headings, metadata, accessible labels and artwork. Keep technical identifiers exactly as supplied: `openhra/openplans`, repository URLs, package/CLI names, filenames and `OPENPLANS_*` variables. The publisher User-Agent remains `openplans/0.1 (public health-plan source discovery; +https://plans.openhra.com/)` verbatim. A repository path printed in artwork is still a technical identifier.

## Character and voice

Calm, precise and useful. Write for people evaluating an integration, operating a service or understanding a request in their server logs. Treat insurers and other data publishers as partners whose work makes this possible.

| Rule | Do | Don’t |
| --- | --- | --- |
| Lead with what exists | “US health plan data. On your server.” | “The future of health benefits.” |
| Make provenance concrete | “Every answer can be traced to the public file it came from.” | “Data you can always trust.” |
| State limits alongside capabilities | “Texas and Florida, for every insurer whose published files could be read.” | “Complete nationwide coverage.” |
| Describe missing data honestly | “Unknown stays unknown.” | “We fill every gap.” |
| Respect publishers | “It downloads only files you publish for the public.” | “We break through the barriers.” |
| Prefer facts to competition | “Built from public sources.” | “Taking on the insurers.” |
| Keep invitations practical | “Open the repository.” | “Transform your business today.” |
| Keep status visible | “In development.” | “Production-ready.” |

Use sentence case for headings, short paragraphs and descriptive links. Keep identifiers, flags and API paths exact; set them in monospace. Explain ICHRA before using it with a general audience. Numbers need a source and date. Never invent adoption, performance, endorsements or road-map commitments. Never publish contact addresses in source or docs; retain the existing contact verification flow.

Legal notices, attribution, licence statements and affiliation disclaimers are outside a voice pass. The inherited text remains unchanged.

## Colour

**Light only for now**, by owner direction on 2026-11-08. The page ground is true white (`#ffffff`) in both light and dark OS settings. Teal carries the identity; dark green ink and muted green-grey keep text calm and readable. `tokens.css` is the single source of truth. Both sites import it, declare `color-scheme: light`, and use a matching HTML colour-scheme hint before CSS loads. Only favicons adapt to the browser tab colour.

All section bands, repository cards and illustration grounds stay white. Fine horizontal rules, generous whitespace, numbered labels and internal column dividers give the long pages rhythm without alternating tinted backgrounds. Hero panels have a thin teal top edge; the [H] construction grid and [P] repository lock-up remain the visual anchors. Pale neutral fills are confined to small technical surfaces: table headings, code and the verification placeholder. No shadows or broad tinted panels.

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

The fixed teal ramp remains available for illustration work; use semantic tokens for text and controls. A ramp swatch is not permission to use it as text on white.

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

WCAG sRGB relative luminance, rounded to two decimals. Every normal-text pair must reach 4.5:1; meaningful non-text graphics and focus indicators must reach 3:1. The matrix includes all site text roles across the permitted surfaces, including optional support and touch-feedback colours. White applies equally to `bg`, `surface` and `diagram-bg`. The sites own these colours; the existing third-party verification frame is outside this palette audit.

| Foreground | White | `surface-subtle` | `code-bg` | `accent-soft` | Requirement |
| --- | ---: | ---: | ---: | ---: | --- |
| `ink` | 11.79:1 | 11.04:1 | 10.70:1 | 10.78:1 | 4.5:1 |
| `muted` | 6.12:1 | 5.72:1 | 5.55:1 | 5.59:1 | 4.5:1 |
| `accent` | 7.24:1 | 6.77:1 | 6.57:1 | 6.62:1 | 4.5:1 |
| `support` | 6.34:1 | 5.94:1 | 5.76:1 | 5.80:1 | 4.5:1 |

| Additional pair | Ratio | Requirement |
| --- | ---: | --- |
| `accent-ink` / `accent` — Primary action, selection and skip link | 7.24:1 | 4.5:1 |
| `bg` / `ink` — Primary action hover | 11.79:1 | 4.5:1 |
| `line-strong` / `bg` — Meaningful diagram connectors on white | 4.12:1 | 3:1 |
| `line-strong` / `surface-subtle` — Meaningful edges on the table-header surface | 3.86:1 | 3:1 |
| `accent` / `line` — Mark across decorative construction-grid lines | 5.51:1 | 3:1 |

Focus uses full-contrast `accent` with a 5 px offset, so it sits against the surrounding white or pale surface rather than the filled action. Do not use `line` for text or as the sole boundary of an interactive control: its rules and grid are decorative, with headings, spacing and labels carrying the structure. Do not apply opacity to text. Links in prose remain underlined. White text is reserved for solid `accent` or `ink` fills.

### Bringing dark back later

Dark is retired, not hidden behind an unused selector. Do not restore the old values piecemeal. If the owner requests it, design and measure a complete semantic override in `tokens.css`, revise both HTML colour-scheme hints, and update standalone logo/mark exports together. Recheck every text, hover, focus, code, table and diagram pair, then capture both sites at desktop and phone widths in both OS settings. Only introduce a second README asset and theme selector if the owner also wants adaptive repository artwork. The current fixed-white exports remain white until then; version history retains the former dark artwork.

## Type

No font downloads. Headings and body use `system-ui, sans-serif`; code, labels and data use `ui-monospace, monospace`. The logo’s main lettering is drawn as vector paths, independent of installed fonts. Its small endorsement uses the system stack.

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

Small uppercase labels are supplementary, never the only explanation of a feature. Preserve readable body copy and content order when zoomed. Tables wrap naturally; their containers remain keyboard-focusable if scrolling becomes necessary.

## Mark and wordmarks

The family uses two letter marks: **[H] for OpenHRA** and **[P] for OpenPlans**. Both keep the original open square brackets, teal identity and rounded joins. The inner capital distinguishes the organisation from its project without adding a second symbol. The OpenPlans lock-up uses [P] and the small text endorsement “by OpenHRA”; never add an [H] mark beside that endorsement.

The OpenPlans lettering shares OpenHRA’s exact “Open” paths, 2.7-unit rounded strokes, cap height and spacing logic. Its capital P uses the OpenHRA R bowl without the diagonal leg. The remaining lowercase letters retain that family; the [P] mark and “by OpenHRA” endorsement are unchanged.

Construction uses a 32 × 32 unit grid and 4-unit strokes throughout. The bracket path remains `M12 4H4v24h8M20 4h8v24h-8`: vertical centres at x=4 and x=28, square caps and round joins. Its painted bounds are x=2…30 and y=2…30. Keep this construction identical for both marks.

The capitals share painted cap bounds y=8…24 and a 4-unit weight. [H] uses stems at x=12 and x=20 from y=10 to y=22, joined at y=16. [P] uses a stem at x=12 from y=10 to y=22 and a closed upper bowl to x=20 and y=16. The P bowl’s counter remains open. Both letters occupy x=10…22, centred within the bracket opening; the P’s longer lower stem balances its upper bowl. Do not replace these paths with a font glyph.

At 16 px, the 4-unit stroke becomes 2 px, the H’s inner spaces stay open and the P has a 2 × 1 px counter. The same paths serve 16, 24, 32 and 64 px: no alternate micro mark is needed. The asset proof includes both marks, both favicons and their monochrome variants at these sizes. Check them on white in both OS settings after any geometry change; favicons also need a browser-tab check.

- `mark-openhra.svg` and `mark-openplans.svg`: standalone fixed teal [H] and [P] for white.
- `logo-openhra.svg`: [H] and the original geometric OpenHRA wordmark.
- `logo-openplans.svg`: [P], the path-drawn OpenPlans wordmark and the small text endorsement.
- Each mark and lock-up has a `-mono.svg` counterpart using fixed neutral ink on white.
- Root `favicon.svg`: adaptive [P] for the plans site.
- `openhra/favicon.svg`: adaptive [H], copied to the sister site’s root as its own favicon.
- Repository README headers and the social preview use [P]; the OpenHRA hero uses [H]. The OpenPlans entry on the organisation page also uses [P]. Each site’s footer uses its own mark.

Minimum sizes: standalone mark 16 px; OpenHRA lock-up 140 px wide; endorsed OpenPlans lock-up 250 px wide. Allow at least 4 units of clear space outside the mark’s painted bounds in layouts, and 8 units around a lock-up. Browser favicon slots retain the supplied 32-unit viewBox; do not add padding that shrinks the 16 px drawing. Keep proportions intact.

Use the supplied assets, correct letter and white ground. Do not close the bracket gaps, fill the P counter, typeset a replacement letter or wordmark, alter the stroke weight, rotate the mark, add shadows or put it over a busy image. Do not use [H] to identify OpenPlans or [P] to identify OpenHRA. No medical-cross or certification treatments.

For a single-colour print process, use the monochrome artwork in one solid ink. Inline SVG can inherit `currentColor`; external marks and logos use the fixed white-system ink and accent. Repository artwork is a self-contained snapshot of `tokens.css`, with an explicit white background; refresh those export colours and the PNG whenever the tokens change. The README uses one image in every OS theme.

## Layout, spacing and radius

Use a 4 px base rhythm. Shared spacing tokens are 4, 8, 12, 16, 24, 32, 48, 64 and 96 px. The page frame is at most 1152 px wide, including 32 px desktop side padding; phone padding reduces to 20 px. Sections have 72 px vertical padding on desktop and 48 px on phone. Hero spacing is intentionally more generous.

Use a 4 px radius for controls and code labels, 8 px for technical panels and tables, and 16 px for a large explanatory illustration. Reserve pills for a future state that actually needs one. Avoid nested rounded cards, decorative shadows and floating dashboard furniture. Prefer a ruled grid for related capabilities, and a narrow heading column alongside principles or rules.

At 760 px, hero, API and contact layouts stack. At 480 px, feature grids become a single column. The verification container reserves 304 × 78 px, which fits a 360 px viewport with room for its side padding. Do not shrink or crop the verification widget.

## Iconography and imagery

Use simple, single-colour line symbols: a short arrow for navigation, a return-shaped arrow for a rule, and the frame mark for project identity. Decorative symbols have `aria-hidden="true"`; every action keeps a visible text label. Use the accent at full contrast. Avoid icon libraries and their network requests.

Illustrations explain real relationships. The OpenPlans diagram shows public source files entering an API on the operator’s own server. The umbrella illustration enlarges the mark on a construction grid. Neither is a product screenshot or an invented dashboard. No stock hospital imagery, portraits, customer logos, shields, growth charts or imagery suggesting endorsement. No animation is needed. Reduced-motion preferences are explicitly respected.

## Implementation and sister-site handoff

`tokens.css` owns colour, type families, spacing and radii. `site.css` owns shared components. Each site's root `style.css` imports those two files, then applies its own layout rules. All requests stay local except the already-existing contact verification script and frame. There is no build step, new dependency, font request, tracking or additional application script.

For the sister-site handoff, copy these files into that site's existing checkout:

1. `brand/openhra/index.html` → root `index.html`.
2. `brand/openhra/style.css` → root `style.css`.
3. `brand/tokens.css`, `brand/site.css` and all `brand/*.svg` → the same paths under `brand/`.
4. `brand/openhra/favicon.svg` → root `favicon.svg` (the [H] favicon; the plans root favicon is [P]).

Keep the sister site's existing `contact.js`, `api/contact.js` and hosting configuration. The HTML intentionally uses root-relative asset paths for this handoff; opening the nested HTML as a file does not reproduce the intended deployment. Preview it with the handoff files mapped to a local site root. No files in the sister checkout were edited during this redesign.
