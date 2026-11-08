# State coverage map design

Design date: November 8, 2026. This proposal includes a preview derived from reports. It is not a production feature. The owner corrected the architecture to use an offline scanner → committed static JSON → small site reader. Neither the scanner nor the page calls the OpenPlans API. No new OpenPlans command is required.

## What the percentage can honestly mean

Use the heading "What data is available?" and describe this as public-source coverage. The evidence does not measure the fraction of the entire individual insurance market, people enrolled, doctors accepting a plan, medicines covered, or successful API queries. A nationwide market-share claim needs a different denominator that is complete and uses a consistent scope.

The first version measures the published exchange inventory. It includes medical and dental products, and SHOP rows where a catalog publishes them. Off-exchange-only products, Medicare, Medicaid and employer plans outside that inventory are outside scope. Do not call this "individual-medical market share." Keep the denominator sentence immediately below the switches, in state details, and in the table caption/methods. Never average the three layers or offer an "All" percentage.

The mockup combines separate validated import runs. It does not describe one currently deployed database. Keep that label until a scanner input bundle proves a single consistent serving snapshot. In Georgia, a later premium catalog import does not prove that the earlier quarantined drug/provider imports have been repaired.

### Metrics, keyed by state and plan year

| Layer | Unit and denominator D | Numerator N | Display and limits |
| --- | --- | --- | --- |
| Premiums | Published rate rows in the selected serving catalog, with evidence for that state/year. Count source row identity, not quotes or people. Include the source's published product mix. | Rows imported in full and checked independently against every source field, in a catalog proven eligible for serving. | `N / D` and "rate rows imported and checked." Null rate cells stay null. This says nothing about support for every household, tobacco price, rating method or subsidy rule. |
| Providers | Distinct issuer IDs in the complete published exchange plan catalog for that state/year, whether a registry URL exists or not. | Issuers with at least one currently ACTIVE provider source set and a positive plan-linked association in the same state/year. | `N / D` and "issuers with active network data." One issuer is one vote. Partial active sources count as presence. Display their count separately. This is not the percentage of networks or providers covered. |
| Prescriptions | The same published issuer inventory as Providers, including dental issuers in this initial broad scope. | Issuers with at least one currently ACTIVE formulary source set and a positive plan-linked drug association in the same state/year. | `N / D` and "issuers with active formulary data." A dental issuer with no drug file remains unresolved unless authoritative product evidence proves the file is inapplicable. Do not remove it from D without that evidence. This is not a drug-coverage probability. |

The reports and public files let us reproduce imported source-rate rows and issuer-level source availability. They do not provide enrollment weights. To measure plan-level network/formulary completeness, we would need a complete expected plan-to-source mapping. A nonzero edge count is insufficient. Label the different units prominently. A future individual-medical-only mode must filter public plan attributes before selecting both numerator and denominator. It must publish a new metric version and cannot reuse today's 32/26/13/16 issuer totals.

Compute integer tenths of a percent, using nonnegative integers:

```text
percent_tenths = floor((2000 * N + D) / (2 * D))  # nearest 0.1%, half up
visible percent = percent_tenths / 10
```

Store integers. Never store a preformatted percent string. Require `0 <= N <= D`, `D > 0`, and exact recomputation. `D = 0` with proven empty inventory means **Not applicable**, with percent null. An unverified/missing denominator is **Unknown**, with N, D and percent null. If D is known but an import report is absent, preserve D. Set N/percent null and show D unassessed units. A missing report is not a measured zero.

### Unknown, partial and quarantine are different

For issuer metrics, divide the roster into `active_complete`, `active_partial`, `quarantined`, `unknown`, and `not_imported`. These counts sum to D when D is known. `active_complete + active_partial = N`. "Complete" means the importer's advertised-child validation completed, not that every plan/network/drug in the market is represented. An issuer with some active data and a newer failed refresh belongs in an active bucket. Keep the failed attempt as a separate warning. Never count the issuer twice or displace its valid active pointer.

Keep quarantined and unknown units in the fixed inventory denominator. Excluding them would inflate the percentage. Do not count them in N or in `not_imported`. Show the remaining buckets alongside the percentage. Never label `100 − percent` as "uncovered," "missing coverage," or "not insured." `not_imported` requires explicit positive evidence of an assessed, valid source that this snapshot has not imported. No current preview row claims that status.

OpenPlans quarantines ingestion attempts. These reports do not support the phrase "quarantined by the publisher". Display "Quarantined" with a reason and actor:

- `publisher_access`: a denial/access restriction supported by evidence. Describe it as "Publisher restricted access." A timeout alone is not a denial.
- `source_validation`: the supplied source could not pass a named validation rule.
- `importer_limit`: missing adapter, budget, worker failure, or other importer limitation.
- `undetermined`: no supported attribution. Preserve the observation without blame.

A quarantined-only state uses hatching and the word **Quarantined**, even when the stored active-presence fraction is 0/D. Unknown uses dots and **Unknown**, never a zero-colored fill. Mixed active/quarantine states keep their percentage fill. List quarantines in state details and the table. Individual missing doctor/drug lookups remain unknown. This map does not change lookup semantics.

### Premium source precedence and exceptions

Federal PY2026 has 30 state scopes; SBE PY2026 has 22. Oregon appears in both. Use its federal individual catalog, since its SBE bundle is SHOP-only. Do not add both denominators. NY/VT SBE bundles are supplemental and must not replace their filed-rate serving paths. Their mockup percentages remain unknown. Keep supplemental checked-row counts only as supporting evidence. Vermont's 26/26 filed-design identity matches and 104/104 tier comparisons prove a specific check, not a complete market denominator. New York's 174 Manhattan plans is a local query count, not a statewide denominator.

For other 19 SBE scopes, the import report establishes serving catalogs and exact rate reconciliation. PY2027 evidence covers 29 federal scopes. The reviewed evidence reports no 2027 SBE publication. Show unknown pending publication. Do not carry 2026 counts forward. The scanner must follow actual per-year source membership, never a permanent federal/SBE state list.

## Evidence used for the preview

The numbers below were computed from operator reports on November 8. They are not invented examples. [mockup-data.json](mockup-data.json) stores the derived aggregates, safe issuer classifications and input-report SHA-256s. Raw reports are private and are not copied into this repository. Their basenames are evidence identifiers, not public download links.

| State, PY2026 | Provider presence | Active with limits | Provider quarantine | Formulary presence | Active with limits | Formulary quarantine |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Texas | 14/32 = 43.8% | 4 | 17 | 11/32 = 34.4% | 1 | 20 |
| Florida | 11/26 = 42.3% | 1 | 15 | 9/26 = 34.6% | 0 | 17 |
| North Carolina | 6/13 = 46.2% | 1 | 7 | 3/13 = 23.1% | 0 | 10 |
| Georgia | 0/16, displayed Quarantined | 0 | 16 | 0/16, displayed Quarantined | 0 | 16 |

Texas also has one unknown issuer in each layer. Public-catalog issuer `92388` is a SHOP-only dental issuer absent from the 31-issuer import reports. Independently downloading the source archive and counting all issuer IDs changes the report-only 14/31 and 11/31 fractions to the declared broad-scope 14/32 and 11/32. It must not disappear from the denominator. The raw archive hash matches the import evidence.

All other 47 provider/formulary state scopes are unknown in this evidence set; all 51 are unknown for 2027. Neither a national NPPES directory nor identity enrichment counts as network participation. Use CMS reference edge counts only for comparison. Their loader omitted files and uses different deduplication. Zero reference drug edges do not establish absence of drugs. They are not numerator or denominator inputs.

Premium rows have a comparable 2026 catalog-row fraction supported by evidence in 49/51 state scopes, each 100%. NY/VT stay unknown. For 2027, 29/51 have such a fraction, each 100%. These counts describe evidence availability across state scopes. Do not publish 49/51 as a national market-coverage percentage. For example, TX 2026 is 203,592/203,592 rows, FL 567,681/567,681, NC 75,072/75,072, GA 117,147/117,147. The federal total of 2,235,761 rate rows is not the 11,090,560 cross-year comparison count on the live Verification section.

### Reproduction recipe

1. Hash the selected reports before reading them. Keep the hashes in the evidence manifest. Do not glob every report or select the latest filename lexically. Explicitly exclude synthetic mutants, before-recovery, interrupted and intermediate runs.
2. Federal premiums: select `p6d-all-states-2026.json` and `p6d-all-states-2027.json`; require each result's `passed`, exact base IDs, `premiums.passed`, matching raw/stored rows and zero mismatches. SBE: `p1g-sbe-2026.json`, state PASS and zero mismatches, count `rates_checked / counts.rate`; apply source precedence above. Cross-check the serving-scope declarations in `p1g-sbe.md`.
3. TX: select `p6c-providers-realdata.json` and `p6c-formulary-realdata.json`. FL: the corresponding final `p6h` reports. NC: final recovered `p6j` reports. Require unique issuer IDs, matching state/year, ACTIVE and `edges > 0` for N; count complete/partial separately. Cross-check FL against `p6h-database.json`, NC against `p6j-final-audit.json`, TX against `p6c-audit.json` and its reconciled final report. A current active pointer outranks a later failed attempt.
4. Reconstruct D independently from the public catalog issuer roster: TX 32, FL 26, NC 13; compare to the final manifest roster, including denied and missing URLs. TX reports contain only 31 issuers: add issuer 92388 as unknown, not quarantined or absent coverage. GA's SBE catalog contains 16 issuers. `p6i-database.json` has 16 manifests per kind, all quarantined and zero active pointers. Cross-check its SBE inventory. Never derive D from only the issuers with readable files.
5. The committed preview is an aggregate extract, not the future scanner. A fresh production snapshot must re-read public inventory files and safe import evidence, export the audit ledger below, and pass all slice A/C controls. Report hashes alone cannot let another operator reproduce a number. They need the public inventory bytes, their own import records and the scanner.

Public roots: [CMS Exchange PUFs](https://www.cms.gov/marketplace/resources/data/public-use-files), [CMS SBE PUFs](https://www.cms.gov/marketplace/resources/data/state-based-public-use-files), [2026 MR URL registry](https://download.cms.gov/marketplace-puf/2026/machine-readable-url-puf.zip), and [Georgia 2026 catalog](https://www.cms.gov/files/zip/georgiasbepuf2026.zip). The registry hash observed in these reports is `0e4defdf96866d41e9ddb76221ac726bb80dff95750754302271338548ec3dad`; GA's bundle is `4e33017f3c9a05d38a6f765df26982f258eaa999bd39dc6b8221e191f9011933`. A registry is discovery evidence, not proof of the whole catalog denominator.

## Static data contract (proposed v1)

```text
plans/data/coverage/index.json
plans/data/coverage/premiums-2026.json
plans/data/coverage/providers-2026.json
plans/data/coverage/prescriptions-2026.json
plans/data/coverage/premiums-2027.json
plans/data/coverage/providers-2027.json
plans/data/coverage/prescriptions-2027.json
plans/data/coverage/evidence/<content-sha256>.json
```

Use one file per layer/year for small, atomic reads. Do not make per-state network requests. The browser may load the evidence ledger. It must be committed and checked. File budgets, uncompressed: index ≤16 KiB, each layer/year ≤64 KiB, each evidence ledger ≤256 KiB, complete release ≤2 MiB. Shared map SVG ≤200 KiB; reader ≤16 KiB; CSS additions ≤8 KiB. These are proposed budgets enforced by slice C; the design preview has a different combined evidence layout.

Index object (all fields required unless marked optional):

| Field | Type / meaning |
| --- | --- |
| `schema_version` | Integer `1`; unknown versions fail closed. |
| `metric_version` | Literal `exchange-source-availability-v1`; ties denominator rules to this document. |
| `as_of` | ISO UTC timestamp of evidence cutoff, fixed as input for repeatable builds. |
| `generated_at` | ISO UTC timestamp supplied by the orchestrator; no wall-clock reads during serialization. |
| `scope` | Literal `published_exchange_inventory_all_products`. |
| `population` | Literal `separate_validated_runs` or `single_serving_snapshot`; latter requires evidence of one snapshot. |
| `state_codes` | Sorted exact allowlist of 50 USPS state codes plus DC; no territories/duplicates. |
| `datasets` | Array of `{layer, year, path, sha256, bytes}`; layer enum premiums/providers/prescriptions; same-origin relative JSON path only. Every advertised year must have all three layers. |
| `provenance` | Shared source dictionary: public HTTPS URL, title, source vintage, retrieved timestamp, SHA-256, optional archive-member name. No credentials/query secrets, local paths, database names or hosts. |
| `scanner` | `{version, source_commit, inputs_digest}`; implementation identity and digest of the allowlisted inputs, not machine identity. |

Every layer/year object has `schema_version`, `metric_version`, `as_of`, `layer`, `year`, `unit` (`rate_rows` or `issuers`), `scope`, and `states` keyed by the exact 51-code allowlist. Each state record:

| Field | Type / invariant |
| --- | --- |
| `numerator`, `denominator` | Nonnegative safe integers or null with the semantics above. |
| `percent_tenths` | Integer 0..1000 or null; exact half-up formula, never inferred from display. |
| `status` | `measured`, `unknown`, `quarantined`, `not_applicable`. Quarantined-only retains 0/D but renders a label/pattern. |
| `counts` | Issuer metric partition above; integers when inventory known, otherwise null. Premiums use `verified`, `quarantined`, `unknown`, `not_imported` rate-row counts; if those cannot be reconciled, withhold N/percent. |
| `reason_codes` | Array of stable, allowlisted codes, e.g. `report_absent`, `denominator_unverified`, `supplemental_catalog`, `source_not_published`, `catalog_adapter_gap`. Reader maps these to human copy. |
| `warnings` | Array of `{code, actor, count}`; actor enum described above; refresh warnings do not change the roster partition. |
| `observed_at` | Actual state evidence observation time, no later than `as_of`. Never replace older observations with generation time. |
| `provenance_ids` | Nonempty source-dictionary references when D is known; unknown states can cite the publication inventory checked. |
| `evidence` | `{path, sha256, input_ids}` linking safe ledger and selected input-report hashes. |
| `serving_basis` | `active_catalog`, `filed_rates`, `active_source_sets`, or `unverified`; identifies exactly what the evidence proves. |

This example uses real counts and an abridged field layout. It is not a publishable fixture:

```json
{"state":"TX","year":2026,"layer":"providers","unit":"issuers",
 "numerator":14,"denominator":32,"percent_tenths":438,"status":"measured",
 "counts":{"active_complete":10,"active_partial":4,"quarantined":17,
           "unknown":1,"not_imported":0},
 "serving_basis":"active_source_sets"}
```

Evidence ledgers contain selected public source URLs/hashes/member/row keys, roster issuer IDs, classification, observation timestamp, safe snapshot identity/hash, validation status, and the existence of a correctly scoped positive association. Do not export provider names, addresses, NPIs, drug records, raw logs, private paths, freeform error strings or connection details. Premium ledgers bind the source archive/member hashes, independent reconciliation digest/counts, selected serving catalog and scope rules. Fail if records are withheld without explanation. Do not shrink the denominator.

### Scanner and publication

Propose a standard-library Python scanner under `tools/coverage-scan/`. Run it explicitly from the site checkout with `OPENPLANS_DATA_DIR` and an allowlisted input-selection manifest. The manifest contains paths relative to the supplied data root, never an absolute private path. It reads cached public files and finalized import reports/manifests without changing them. It does not connect to an API/database, perform imports, scrape publisher endpoints, or change the evidence tree. If required serving-pointer evidence is missing, it emits unknown with a reason. A passing test alone does not prove that data is served.

Proposed invocation, to be implemented in slice A:

```sh
python3 tools/coverage-scan/scan.py --selection coverage-selection.json \
  --as-of "$COVERAGE_AS_OF" --generated-at "$COVERAGE_GENERATED_AT" \
  --output plans/data/coverage
python3 tools/coverage-scan/check.py plans/data/coverage
```

The operator supplies the selection file locally. Do not commit it as machine config. Maintain a public example with symbolic relative report names and no private paths. The scanner reads the data-root environment variable itself. Fixed inputs, scanner version and timestamps must produce identical bytes. Write sorted keys/arrays, LF, UTF-8 and no NaN. Generate in a staging directory and validate all files before atomically replacing the release. Keep the last committed data when generation fails.

When finalized reports land, the orchestrator selects the coherent run set, rescans, reviews count/scope/quarantine changes, runs the full site gate, and commits JSON plus a concise evidence diff on its task branch. The latest owner lane protocol is v1: queue off, merge main once, full gate, local commit on PASS. This lane does not modify branches other than its own, publish, or push. Promotion policy remains the orchestrator's responsibility; no task changes the protected-branch rules. Refresh work is explicit, not an unrequested scheduled job.

If validation fails, keep the last valid snapshot visible with its real date and fix forward. Future publication must not label stale data current. Mark a snapshot older than 7 days "Snapshot from [date]". This display threshold does not promise weekly source data refreshes. If some records have older observations, show their own dates in state details.

### Validation and failure handling

Use schema plus semantic checks offline. Reject unknown fields, noninteger counts, NaN, duplicates, invalid states/year/layers, missing states, zero-denominator fractions, stale-year borrowing, inconsistent hashes/bytes/as-of, wrong percent, roster/count disagreement, unsafe URLs/paths, conflicting source scopes, unexpected input formats and excessive file sizes. Require an ACTIVE pointer and an association in the same state/year. Checking only `status: complete` is insufficient. Reject report-only denominators when a public inventory cannot corroborate them. Reconcile known buckets exactly; never compute unknown as a catch-all subtraction without a classification record.

The reader loads the index, then the selected layer/year file from the same origin. It checks version/state set/count bounds/formula before updating the map, detail and table as one operation. Abort superseded fetches or use a generation token so late results cannot overwrite a newer selection. On parse/network/hash/version failure, keep the saved static table and announce "Coverage snapshot unavailable". Never paint zeros. Do not interpolate JSON through `innerHTML`. Pin file SHA-256s in index; slice C verifies them before publication and the reader verifies fetched content before replacing the saved view.

## Presentation and accessibility

Place the component in section 06 Availability only, after its introductory sentence and before limitations. Keep section 05 Verification verbatim: comparison accuracy is different from coverage. Preserve publisher, Contact, contact IDs/scripts, legal notices and CSP. This lane changes no live pages.

White page ground in every OS theme; import the existing tokens. Ink/muted/accent retain measured brand contrast. Use teal-100, teal-300, teal-600, teal-800 for >0–<25, 25–<50, 50–<75 and 75–100%; outlined white for a known zero. Unknown is a dotted white fill, quarantined-only diagonal hatching. Use line-strong for meaningful boundaries. Show exact numbers and status text so the map is readable without color. Do not put small white text over mid-tone ramp fills.

On desktop, put layer buttons and the year select above a geographic map. Place the state picker and persistent detail column on the right, with the table below. On phones, use 16px gutters, wrap controls, scale the map and put detail then table in normal flow. The page must never scroll horizontally. The table uses three wrapping columns and needs no sticky overlay or tooltip. Give small states labelled callouts. On phones, these callouts locate states. The full-width native state select provides a 44px control for every state, including DC, AK and HI.

Use native buttons with `aria-pressed` in a labelled group, a labelled native year select and native state select. Tab reaches controls in reading order; native arrows/typeahead work in selects, Space/Enter activate buttons. Focus stays on the triggering control when data changes. One polite live region announces selected layer/year/state after an atomic update. No live announcement on hover. The SVG is a single named image with a description pointing to the table. Do not make its paths 51 competing tab stops. A future version may allow pointer clicks on states only if the native picker still provides equivalent access. The preview intentionally uses the picker for all state selection.

Use a real `table` with a layer/year/date/unit caption, column headers, full state names as row headers, numeric counts and explicit statuses. Do not rely on generated CSS labels. The saved default Providers/2026 table contains all 51 rows in HTML and works without JavaScript. For production, scanner also emits a deterministic default-table fragment; slice B checks it into `plans/coverage-table.html` for a visible fallback link and copies the identical table into the section. Run this tooling offline for publication. It adds no hosting build step. If JS or fetch fails, keep the saved default/date intact. Enable disabled controls only after valid data loads. Provide same-origin links to other year/layer JSONs as data downloads, labelled as such.

Check at 320, 360, 390, 768 and 1440 CSS pixels, 200% zoom/reflow, keyboard-only, OS dark preference (still white), reduced motion and forced colors. Keep focus outlines, high-contrast text, full state names in the table, and visible underlined provenance links. No animation, external fonts, scripts, trackers, map tiles or runtime mapping library.

### Geography source and derivation

Use [U.S. Census Bureau 2024 cartographic state boundaries](https://www.census.gov/geographies/mapping-files/2024/geo/carto-boundary-file.html), [1:20m KML ZIP](https://www2.census.gov/geo/tiger/GENZ2024/kml/cb_2024_us_state_20m.zip). This federal geographic dataset is public-domain material. ZIP SHA-256 retrieved November 8, 2026: `37337db59415f010c594fba96a48aa6e950e633dc0e555cc7b1ce8edd794c673`.

The preview parses KML polygons, keeps 50 states plus DC (USPS codes), projects the contiguous states using Albers equal area (29.5°/45.5° standard parallels, central meridian −96°, latitude of origin 37.5°), rounds display coordinates to 0.1 SVG units, and repositions/scales Alaska and Hawaii into labelled insets. Small states get abbreviation callouts; they remain present as actual geographic paths. No unrelated metadata is copied. `map.svg` is the source geometry artifact; the preview embeds it with initial fills. Attribute the Bureau visibly below the map/methods and record the source hash in the production asset metadata. Do not use a third-party map asset with an unclear license.

## Reuse and file plan

- Reuse `plans/brand/tokens.css`, `plans/brand/mark-openplans.svg`, `plans/brand/logo-openplans.svg`, and section 06's context. No new palette or logo.
- Reuse `tools/gate.sh` and its full-mode self-test pattern; add data-contract checks in slice C. Its existing HTML checks do not validate JSON denominators or this docs preview.
- Existing `contact.js` is solely the contact flow; reject it as a home for coverage code. Create `plans/coverage.js` because data switching has a separate lifecycle and must never interfere with contact verification.
- Existing `plans/style.css` owns site layout; extend it narrowly for the map. No separate production CSS framework is needed.
- Existing OpenPlans tables `puf_active_catalog`, `state_rate_active`, `formulary_active_set`, `provider_active_set`, `qhp_coverage_manifest` and ACTIVE snapshot state explain the evidence needed. Existing independent premium oracles and final issuer reports are reuse inputs, not code to vendor or commands to add. The scanner normalizes data offline. The reader renders it. No storage or service layer is added to the site.
- New `tools/coverage-scan/` is justified because the existing site gate only checks pages/brand/contact and has no public-inventory reconciliation. New data files are justified because the current Availability prose carries no machine-readable evidence. New schema/fixtures are needed because HTML checks cannot prove the arithmetic or check that every state is present.

## Open questions for the owner

1. Keep this explicit **published exchange source-inventory** scope, or commission a later individual-medical-only metric? That later metric needs fresh filtered denominators and a new version; these numbers cannot be relabelled.
2. Which single serving snapshot should eventually replace the preview's separate validated runs? Until supplied, keep that limitation visible and do not call the figures live API coverage.
3. Add an audited filed-rate denominator adapter for NY/VT next? The first scanner must preserve unknown until it can establish statewide scope and the served row inventory.
4. The proposed stale-display threshold is 7 days. Confirm a refresh cadence when the scanner exists; this design creates no automatic schedule.
