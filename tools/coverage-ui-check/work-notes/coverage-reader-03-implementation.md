# Implementation — coverage reader

- `plans/index.html`: only section 06 and one deferred local coverage script reference.
  Committed Providers/2026 map, Texas detail, A's exact fallback table, year/date,
  native disabled controls, public Census attribution and source downloads.
- `plans/style.css`: appended scoped coverage styles; original bytes retained.
- `plans/coverage.js`: index/dataset validation, SHA-256/byte checks, exact BigInt
  arithmetic, coherent rendering, URL restoration, races, safe DOM text and failures.
- `plans/coverage-table.html`: standalone dated default with A's verbatim table.
- `plans/brand/us-states.svg`: documented Census geometry, all 51 paths, inset and
  small-state labels, public source/hash metadata and self-contained default styles.
- `tools/coverage-ui-check/`: static parity/protected-content checker, headed-browser
  checks, public handoff notes and recorded request/selection/negative results.

Decisions: keep the SVG inline in the page so no-JS and fetch failures retain the
map as well as the table. The separate asset remains available for reuse; both use
identical paths. State selection changes only detail/highlight; all rows come from
the same immutable selected dataset. No aggregate score. Pending requests use a
separate wanted selection and a monotonic ID as well as AbortController. Never
replace focused controls during a successful dataset switch.

2027 absent-source language is qualified as publication in this snapshot, because
A's record has `denominator_unverified`, not a claim about a newly checked external
CMS publication. The Unknown label and nulls remain unchanged. Supplemental NY/VT
records retain their known provenance even with a null statewide denominator.

The brief's local main merge imported existing site copy changes; none were authored
as part of this reader. No protected content, contact behavior, CSP, tokens, scanner
inputs, scanner outputs or shared gate edits were made by B. Local main/develop and
remotes were not moved. A's branch remains an ancestor.
