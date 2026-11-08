# Design preview review

Reviewed November 8, 2026. These are design artifacts; the scanner, production reader and production data gate remain the future slices in PLAN.md. Live site files are unchanged.

## Evidence findings

- The independently downloaded federal 2026 Plan Attributes archive matches SHA-256 `954e697885efcb709aed0be1de14075afe11704bf3447372960d08c879950af2` from the import evidence. Its roster has **32 TX issuers**, 26 FL issuers and 13 NC issuers. The TX import reports contain 31: issuer `92388` is a SHOP-only dental issuer present in the public catalog and absent from the reports. It is explicitly unknown in the preview. Final TX figures are **14/32 = 43.8% providers; 11/32 = 34.4% prescriptions**, not the narrower report-only fractions.
- The independently downloaded GA SBE bundle matches SHA-256 `4e33017f3c9a05d38a6f765df26982f258eaa999bd39dc6b8221e191f9011933`; `GAPlans05052026.csv` has 16 distinct issuer IDs, exactly matching the quarantined roster.
- FL and NC ACTIVE issuer sets match their final database-audit active-pointer lists for both kinds. TX final provider statuses match its independent audit. Federal base-ID and premium-oracle checks pass for both years.
- NY/VT supplemental source counts are not used as serving coverage. OR’s SHOP-only SBE bundle is not added to its federal denominator. No assumption of a single deployed API is made.

## Visual judgment and iteration

The first render exposed a coordinate-order error that compressed the contiguous map. Corrected the latitude/longitude projection and re-rendered. The final Census geography is recognizable, with all 51 scopes, separate AK/HI insets, labelled small-state callouts, and a clear Texas selection. A browser geometry-ratio sanity check now catches the initial failure shape.

The initial 320px check exposed 5px of page overflow. Reduced the narrow-phone header mark and switch padding; all tested widths now fit their available document width. Added a readable small-state abbreviation line below the phone map; the 44px native state picker and full-name table remain the usable selection/detail path for small states.

The white ground, restrained teal and clear denominator sentence fit the existing brand. The desktop detail column keeps the fraction, partial/quarantine counts and unknown issuer visible beside the map. The phone order is map → detail → table, with 16px gutters. The table is deliberately long and wraps; it does not create horizontal scroll. Numeric absence is always explained rather than portrayed as lack of insurance coverage.

Final captures:

- [Desktop, 1440 × 1300](desktop.png)
- [Phone, 390 × 1650](phone.png)
- [Phone table, 390 × 1100](phone-table.png)

## Checks actually run

`python3 docs/coverage-map/check_mockup.py --self-test` prints:

```text
mockup: PASS (6 datasets, 51 states each, exact percentages, issuer ledgers, SVG and fallback)
```

Seven isolated negative controls were rejected for the intended reason: wrong percentage, missing DC from a dataset, unknown coerced to zero, quarantine classified as active, DC missing from SVG, fallback table row missing, and fallback table value changed. Clean originals pass afterward; mutants exist only in memory.

The browser review checks all 306 state/layer/year detail and table combinations. Widths 320, 360, 390, 768 and 1440 have no page overflow, 51 state paths and 51 table rows. OS dark preference retains a white computed background; reduced-motion preference is applied. Native layer-button activation by Space is exercised. The state selector retains focus during the key probe, but the headless native popup does not change its value; **do not claim a complete keyboard-select or assistive-technology audit** from that probe. The production slice requires that manual check. With scripts disabled, all 51 saved rows remain and the controls stay disabled. See [browser-checks.json](browser-checks.json).

Normal JavaScript syntax checks pass for the preview and review helper. Public artifact scanning found no email addresses or private absolute paths. No raw import reports, credentials or source archives are included.

`tools/gate.sh --full` prints `PASS`, including its existing `selftest: PASS (clean copy and 6 negative controls)`. That gate’s current scope does not cover these docs; the preview checks above supply the additional evidence. Its existing self-test passes invalid CLI arguments for several mutations, so those failures alone do not demonstrate the intended content predicate; slice C explicitly requires diagnostic-specific controls. The denylist check is skipped when no operator denylist file is supplied.

Not exercised in this design lane: a screen reader, forced-colors visual audit, browser-native 200% zoom, production network error handling/CSP integration, or the not-yet-built scanner. These are explicit acceptance checks in the implementation briefs, not claims of current implementation.

## Reproduce the local preview

No dependencies or hosting build step are added. From the repository root:

```sh
python3 -m http.server 8764 --bind 127.0.0.1
```

Open `http://127.0.0.1:8764/docs/coverage-map/mockup.html` in a local browser. The preview fetches only its committed JSON; it never calls a service API. Opening the HTML directly as a file leaves the saved table intact, but local fetch policy may prevent the switches from enabling.

For automated review/captures, use Node with built-in `fetch` and `WebSocket`, and a separately launched local **headless** browser exposing the debugging protocol on port 9374. Use a dedicated temporary browser profile. Then run:

```sh
node docs/coverage-map/review_browser.mjs
python3 docs/coverage-map/check_mockup.py --self-test
tools/gate.sh --full
```

`COVERAGE_CDP_URL` and `COVERAGE_PREVIEW_URL` can override the local review endpoints. The helper rewrites the three PNGs and browser-checks.json only. It is a docs preview utility, not part of site runtime or a deployment build.

## Task acceptance

- [x] Precise per-state/year metrics, independent public denominators, partial/unknown/quarantine treatment, source precedence and limits.
- [x] Corrected no-API architecture: site-repo scanner, committed static JSON, small reader; schema/field meanings, size budgets, provenance and rerun/validation plan.
- [x] White/teal map design for 50 states + DC, public-domain Census source/attribution, mobile layout, table fallback and specified keyboard/screen-reader behavior.
- [x] Dated mockup using real derived numbers, desktop/phone captures, visual inspection and corrections.
- [x] Ordered A scanner / B reader / C gate briefs with leases, checks and negative controls; separate identical draft copies in the orchestrator’s ignored drafts directory.
- [x] DESIGN.md records decisions and owner follow-ups; no live site/legal/contact changes. Main merged once (already up to date); full gate passes before local commit.
