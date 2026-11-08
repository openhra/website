# State coverage map implementation plan

Status: design only, November 8, 2026. The owner corrected the architecture to an **offline site-repo scanner, committed static JSON files, and a small local reader**. There is no OpenPlans API dependency and no new OpenPlans command. This plan supersedes that part of the original brief.

Execute A → B → C in dependency order. Each brief below is self-contained; each has a lease, acceptance checks and negative controls. The orchestrator may assign one lane at a time. Avoid concurrent edits to shared files or output data. The latest lane protocol is v1: queue off, merge main once, run the repository’s full gate, commit locally on PASS. Do not push or modify remotes/protected branches. The protected-branch promotion policy is not changed by this plan.

The current site’s definition of done is `tools/gate.sh --full`; it has no `--fast` flag. Use that supported full command. Do not claim JSON or map validation merely because today’s HTML-only gate passes.

## Intended result

A dated coverage section whose numbers can be reproduced from public inventory files plus the operator’s selected import records. It keeps unknown/quarantined data explicit, preserves section 05 Verification and the contact/legal blocks, uses brand tokens, and loads only static same-origin coverage assets. See [DESIGN.md](DESIGN.md) for exact metrics and [mockup.html](mockup.html) for the design preview.

## Architecture and reuse

```text
public files + finalized import records (read-only)
    → offline scanner in tools/coverage-scan/
    → staged JSON + safe evidence ledgers + saved table
    → schema/semantic checker and full site gate
    → local reviewed commit / orchestrator publication
    → plain site reader → map, state detail, accessible table
```

Reuse brand tokens/artwork, section 06, the full-gate pattern, existing independently validated report evidence, and Census geometry. The site has no existing inventory scanner or data reader; contact.js must retain its separate job. Keep implementation flat: scanner parsing → normalization/reconciliation → serialization; reader validation → shared selection model → DOM rendering. No services or persistence layers are needed.

## Ordered lane briefs

## Slice A — scanner and static evidence files

**Task:** Implement the offline scanner in this site repository. Read `AGENTS.md`, the brand rules, `docs/coverage-map/DESIGN.md`, and this whole brief. Follow the latest owner protocol: queue off, merge main once before final validation, full site gate, local commit only on PASS. Never push or touch remotes. Do not modify OpenPlans source or call its API. The scanner is not an OpenPlans command.

**Depends on:** approved metric/contract v1 in DESIGN.md; access to operator-selected finalized public-source and import-report inputs. Use `OPENPLANS_DATA_DIR` supplied at execution, never hardcode or commit its value. Input tree is read-only. No running database, credentials, paid calls or publisher crawls are required.

**Lease:** `tools/coverage-scan/**`, `plans/data/coverage/**`. Do not edit live HTML/CSS/scripts, gate files, legal/contact content, roadmap, task indexes or other lanes. Coordinate the `plans/data/coverage/**` lease with C before handoff; C is read-only on it unless A delegates an explicit fixture correction.

**Build:**

1. Standard-library Python entry point `tools/coverage-scan/scan.py`; separate parsing/reconciliation from serialization. Define strict schema in `schema.json`, fixtures/tests in `tests/`, operational README and a safe selection-manifest example. Existing gate and contact code cannot supply inventory reconciliation; do not vendor OpenPlans code.
2. Require an explicit input-selection manifest (paths relative to the supplied data root), fixed as-of/generated-at timestamps and output directory. Resolve inputs within that root; reject escapes, symlinks outside it, secret URLs and unexpected formats. Never recursively ingest every report. Select final recovered/active evidence, not synthetic mutants, interrupted logs or historical attempts.
3. Reconstruct issuer rosters from public plan files, not only readable registries or manifest counts. Reconcile rate rows to source members and serving-catalog evidence. Respect OR federal versus SHOP scope, NY/VT filed-rate priority and year membership. Consume sanitized manifests/reports; no API/database access or new OpenPlans command. Missing evidence produces explicit unknown; malformed or contradictory evidence fails the run.
4. Apply DESIGN.md units/formula/buckets. Same state/year positive associations and ACTIVE pointers are required. A prior valid active pointer survives a failed refresh; no duplicate issuer counting. Separate publisher-access, source-validation and importer-limit reasons. Partial ACTIVE presence remains labelled. Reference edge counts and NPPES membership never become coverage.
5. Emit index, six layer/year datasets for 2026/2027, content-addressed safe evidence ledgers, and a default Providers/2026 HTML table fragment in the tooling output directory for B. All 51 states exist in every dataset. Retain nulls and provenance dates. No personal data/raw logs/local paths/connection strings. Public report hashes alone do not establish a public denominator; ledger inputs must bind it to the public file bytes.
6. Add a dependency-free semantic checker `check.py` that B/C can invoke. Enforce schema/type/allowlist, exact 51-state set, exact integer rounding, buckets, lineage, hashes, timestamps and file budgets. Treat malformed/unsupported schema as failure. Produce a concise count diff from the preceding snapshot.
7. Write to staging; validate before atomic replacement. Fixed input bundle + version + timestamps produce byte-identical output twice. Do not introduce a site build step. Document rerun on new finalized reports and how self-hosters supply their own records.

**Acceptance:**

- [ ] `python3 -m unittest discover -s tools/coverage-scan/tests` passes; include fixtures independent of implementation output.
- [ ] `python3 tools/coverage-scan/check.py plans/data/coverage` prints PASS.
- [ ] Golden report-derived provider figures are TX 14/32 (43.8%), FL 11/26 (42.3%), NC 6/13 (46.2%); GA 0/16 is quarantined, not zero-colored missing coverage. Formulary figures are 11/32, 9/26, 3/13, 0/16. A newer selected coherent dataset can differ only with reviewed source evidence.
- [ ] Premium 2026 evidence resolves 49 comparable catalog-row scopes; NY/VT remain unknown unless an audited filed-rate adapter is added under a separately agreed lease. OR is not double-counted. 2027 never borrows 2026 sources.
- [ ] Output stays within DESIGN.md budgets and contains no private paths, raw records, email addresses or secret values.
- [ ] Two fixed-input runs have identical SHA-256s; no reads/writes outside the declared roots; no network/API access during scanning.
- [ ] Full `tools/gate.sh --full` prints PASS; changed files stay within lease. Commit locally with the owner’s required trailers, and report input scope, limitations and command output.

**Negative controls:** isolated fixture copies only. Change 14/32’s percentage to 50%; delete DC; duplicate TX; change a year; supply a 0 denominator; use a fractional count; remove a denied issuer from the roster; count QUARANTINED rows as ACTIVE; remove positive association or change its state/year; replace an active pointer with a later failed refresh; assign GA adapter failure to publisher denial; merge OR’s SBE SHOP rows into federal D; promote NY/VT supplemental rows; change source hash; inject a private absolute path; truncate a report. Each must fail at the relevant predicate with a specific reason. An intentionally absent report must succeed as Unknown, not as 0%.

**Handoff:** schema, scanner/checker, generated static files, safe ledgers, default-table fragment, tests and README. No browser production code. Record unresolved evidence in the output and report, not in guessed numbers.

## Slice B — static reader and geographic map

**Task:** Add the map to section 06 Availability using only committed same-origin static JSON. Read `AGENTS.md`, brand rules, `docs/coverage-map/DESIGN.md`, the scanner contract and this brief. The design preview is a visual reference; do not ship its combined mockup data as production data. No OpenPlans API calls or new command. Queue off; merge main once, full gate, local commit on PASS; no push/remotes.

**Depends on:** A’s passing schema, generated files, checker and default-table fragment. Do not proceed with guessed data or a divergent field layout. If A exposes unknown evidence, render Unknown as designed.

**Lease:** `plans/index.html` section 06 only plus one local deferred coverage script reference; `plans/style.css` narrowly scoped coverage styles; `plans/coverage.js`; `plans/coverage-table.html`; `plans/brand/us-states.svg`; `tools/coverage-ui-check/**`. Shared file edits require coordination before starting. Do not edit section 05 Verification, contact flow/IDs/scripts, publisher blocks, notices, legal text, CSP, tokens, live API or data files owned by A. No framework, dependency, tracker, external script/font or hosting build step.

**Build:**

1. Reuse existing brand tokens/mark/lock-up and `docs/coverage-map/map.svg` geographic derivation. Preserve all 50 states plus DC and public Census attribution. Use white ground, teal ramp, line-strong boundaries, separate unknown dots and quarantine hatching. Keep AK/HI inset labels and small-state callouts.
2. Plain `coverage.js` loads `data/coverage/index.json` and one selected layer/year dataset. Validate version, required state set, bounds, exact arithmetic and fetched hashes before replacing any visible values. No API, runtime map service or third-party request. Use text nodes, not unsafe HTML interpolation.
3. Native labelled layer buttons (`aria-pressed`), year select, state select. Default Providers/2026 for initial publication; derive advertised years from index. Do not add an “All” score. Show unit/scope, as-of, state observation date, count fraction, partial/quarantine/unknown breakdown and provenance. Separate validated runs must be labelled until single-snapshot evidence exists.
4. Persistent detail panel plus real accessible table, updated atomically from the same state records. SVG is one named image; state picker is the keyboard/phone equivalent. Do not make tiny SVG paths mandatory interactive targets. Keep focus on the triggering control and one polite selection announcement. Quarantined-only 0/D renders “Quarantined,” not a zero fill. Unknown is never coerced to zero.
5. Commit the default table in page markup and `coverage-table.html` from A’s fragment; B’s checker enforces equality against JSON. Retain it when JS/fetch fails. Enable controls only after valid data loads. Provide an explicit default-state/date label and download links. Snapshot age >7 days uses dated-snapshot wording, not a fresh claim.
6. Handle race conditions and invalid/missing JSON: abort old requests or gate by current request ID; preserve last known table and announce failure. No blank map or partial mixed-year render. Existing contact behavior/CSP remain unchanged.
7. Desktop: map and side detail; phone: controls, map, detail, table, 16px gutters. Three wrapping table columns. No page-level horizontal scroll at 320px or 200% zoom. Use native 44px controls for small states and DC.

**Acceptance:**

- [ ] Scanner checker passes; every switch/state detail/table cell agrees with the same static data record and as-of date.
- [ ] Browser request log proves only same-origin static coverage assets are requested by the component; existing contact verification is unchanged.
- [ ] Keyboard-only selection of layer, year, DC/AK/HI and all other states; readable full state names; correct pressed state; focus and live announcement remain useful.
- [ ] At 320/360/390/768/1440 CSS pixels, 200% zoom, OS dark, reduced motion and forced colors: white ground, no page overflow, visible controls, status text/patterns readable without color. Capture desktop and phone and inspect them.
- [ ] JavaScript disabled, 404/invalid JSON and unknown schema retain the dated fallback table. A slow old fetch cannot overwrite a newer selection. Zero/quarantine/unknown are distinct.
- [ ] Census source attribution is visible; one geometry entry per allowed state, all small-state labels legible; no new remote assets.
- [ ] Full `tools/gate.sh --full` prints PASS; UI checker passes. No protected content or CSP diff. Commit locally with required trailers.

**Negative controls:** temporary files only. Supply an impossible percent, omit a state, corrupt dataset hash, inject HTML into a reason string, respond with wrong year/schema, delay the first request until after the second, force 404, disable scripts, and substitute unknown with numeric zero. Expect fail-closed rendering or explicit test rejection, never an attractive false map. Remove a table row or alter one default-table value and require the parity test to fail. Drop white-ground styling and require the visual/computed-style check to fail. Restore before final checks.

**Handoff:** implemented local reader/map and fallback, repeatable UI checks, reviewed captures, browser requests and keyboard findings. Leave publication and data refresh orchestration to C/owner.

## Slice C — site gate and publication checks

**Task:** Make committed static coverage data a checked publication artifact. Read `AGENTS.md`, `docs/coverage-map/DESIGN.md`, A/B handoffs and this brief. No API, new OpenPlans command, production import or network requirement. Queue off; merge main once, full gate, local commit only on PASS; no push/remotes. Owner/orchestrator owns any subsequent publishing.

**Depends on:** A’s scanner/schema/checker and B’s reader/fallback. Run after both; do not weaken an invariant to accept their output. Fix contradictions with the owning lane. This is site integration, not a second implementation of the metric.

**Lease:** `tools/gate.sh`, `tools/gate-selftest.sh`, `tools/coverage-gate/**`, `docs/coverage-map/PUBLISH.md`. Read-only on `plans/data/coverage/**`, `plans/coverage*`, `plans/brand/us-states.svg`, site HTML/CSS and scanner. A data correction requires an explicit lease handoff; no opportunistic redesign/legal/contact edits. Do not change orchestrator files or move task files.

**Build:**

1. Invoke A’s dependency-free checker from the normal gate so malformed committed data cannot pass. Full mode additionally runs isolated mutation controls and B’s available deterministic parity checks. Preserve existing gate behavior and PASS/FAIL reporting; do not make network or GUI startup a gate dependency.
2. Verify index paths/bytes/hashes; every year × layer × 51-state combination exactly once; numerator/denominator/rounding and bucket identities; null rules; proven-empty versus unknown distinctions; state/year/provenance consistency; safe URL/path fields; size budgets. Verify map state IDs and default HTML table parity with the committed default dataset.
3. Bind data to its selected evidence ledger and scanner version. Recompute safe roster classifications and row totals. Flag impossible refresh changes (lost states, changed scope/version without migration, altered dates, same hash with different bytes). Do not require private raw report availability on public CI; real-input recomputation happens at generation, public artifacts remain independently checkable with their ledgers.
4. Add self-tests that actually execute the data checker on temporary mutated copies and assert the expected diagnostic, not merely any nonzero exit. The existing full self-test passes unknown CLI arguments for some controls; do not copy that weakness. Prove the clean temporary copy passes first and the restored copy passes last.
5. Write an operator runbook: choose final reports and public source snapshots; set data-root/timestamps locally; scan to staging; run check and review the per-state diff; replace files atomically; refresh the fallback from the same data; full gate; local reviewed commit. Owner/orchestrator publishes the commit through the repository’s protected-branch policy. Keep previous valid committed data when scanning fails; fix forward, never pretend it refreshed.
6. Describe absent/stale evidence honestly. No unrequested cron job. A different deployment/self-hoster regenerates from its own selected records; the page never introspects a live instance. Retain old snapshot dates until a validated publication succeeds.

**Acceptance:**

- [ ] Normal `tools/gate.sh` rejects invalid coverage JSON/geometry/table; full `tools/gate.sh --full` prints PASS with clean-copy and named negative-control results.
- [ ] Exact arithmetic and complete 51-state set checked for every advertised layer/year; schema/hash/size/lineage rules enforced offline.
- [ ] Full test suite proves each planted defect below was rejected for its intended reason; clean originals remain byte-identical.
- [ ] `plans/coverage-table.html`, saved section table and default JSON agree; no drift hidden behind a successful interactive fetch.
- [ ] Existing HTML/contact/white-background checks still pass. No private paths, addresses, secret values, raw import files or new dependency/network step in public artifacts.
- [ ] Runbook clearly assigns scanner and publication to the orchestrator; no API/new OpenPlans command. Local commit with required trailers only after PASS.

**Negative controls:** (1) TX 14/32 stored as 50.0%; (2) DC omitted; (3) duplicate state or layer/year; (4) N>D, negative, float, bool or null-to-zero count; (5) D=0 with percent; (6) active bucket includes quarantine; (7) ledger issuer removed, duplicated or wrong year; (8) dataset/source hash altered; (9) future or mixed as-of timestamps; (10) unauthorized URL, parent traversal or private path; (11) file over size budget; (12) SVG missing DC; (13) stale fallback table value; (14) supplemental NY/VT or OR SHOP rows treated as serving premium denominator. Each must fail the intended validator predicate, and the unmodified fixture must pass.

**Handoff:** gate integration, mutation-control log and publication runbook. Report any unverified private evidence separately from public artifact checks. No deployment/push in this slice unless the owner explicitly expands its scope.

## Delivery and unresolved decisions

The owner may review the scope questions in DESIGN.md before commissioning slices. Default implementation uses the exact broad exchange-inventory scope, not an unproven individual-medical market share. NY/VT comparable premiums remain unknown until a separately scoped filed-rate adapter is justified. Different validated databases remain labelled as such; a map cannot imply one deployment merely by joining their reports.

A failure keeps the prior dated static snapshot. Fix forward on a task branch and rerun the relevant checks. Never revert other lanes or weaken classification rules to produce higher percentages. No new scheduled refresh, paid generation or external service is part of these slices.

Draft brief copies are written to the orchestrator’s gitignored drafts directory as `W4-A-coverage-scanner.md`, `W4-B-coverage-reader.md`, and `W4-C-coverage-gate.md`. This plan is their public source of truth; keep copies identical at handoff.
