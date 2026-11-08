# Offline public-source coverage scanner

This is site publication tooling, separate from OpenPlans. Python 3.9 or later and
the standard library are sufficient. It reads operator-selected cached public ZIP
files and finalized import evidence, without an API, database, credentials, imports,
publisher requests or a site build step. Input files are read-only.

The metric is **published exchange inventory, all products**, including dental and
published SHOP rows. Providers and Prescriptions measure issuer presence, not
network completeness, enrollment, medical-only market share, provider membership
or whether a medicine is covered. Premiums measure source rate rows independently
checked by the selected import oracle in an evidenced serving catalog. Never
combine the three percentages. The normative metric is
[DESIGN.md](../../docs/coverage-map/DESIGN.md).

## Run and review

Set `OPENPLANS_DATA_DIR` in your shell to the root of your own evidence cache. Its
value must never go into a file or a commit. Paths in a selection are relative to
that root. The checked-in `selection.example.json` is the exact, safe allowlist used
for this release, with public archive hashes and finalized report hashes; it is an
example of the operator interface, not a discovery rule or machine configuration.
It selects 25 public archives, 16 evidence selections from 14 finalized reports, 80 premium source scopes and
8 provider/formulary scopes. Historical attempts, synthetic mutants and logs are
excluded. It does not authorize ingesting other files in those directories.

```sh
python3 tools/coverage-scan/scan.py \
  --selection tools/coverage-scan/selection.example.json \
  --as-of 2026-11-08T13:00:00Z \
  --generated-at 2026-11-08T13:00:00Z \
  --output plans/data/coverage
python3 tools/coverage-scan/check.py plans/data/coverage
python3 -m unittest discover -s tools/coverage-scan/tests
tools/gate.sh --full
```

The default table is `tools/coverage-scan/default-providers-2026.html`. Override its
path with `--table-output` to use another tooling output directory. Slice B can copy
this fragment verbatim into the saved page and its standalone fallback page. The
fragment includes all 51 full state names, the date, denominator scope, counts,
partial and quarantine labels. Slice C should treat `plans/data/coverage/` as
read-only and invoke `check.py`; no fixture corrections are delegated.

On a refresh, explicitly select new **finalized** reports and public files, review
each source hash and serving scope, and supply fixed cutoff and generation times.
Set `source_commit` to the full commit containing the scanner implementation used.
Keep `population` as `separate_validated_runs`: these reports do not establish one
coherent deployed snapshot. The scanner prints per-layer/year changed-state counts
against the preceding release. The checker also accepts `--previous DIR` for a
count/status diff. Review quarantine attribution, counts, inventory and observation
dates before running the full site gate and committing both data and evidence.
No unattended refresh schedule is installed.

## What the committed evidence establishes

The report-derived issuer figures are reproduced from public plan members, not
registry availability or report totals:

| State, 2026 | Providers | Prescriptions | Qualification |
| --- | --- | --- | --- |
| TX | 14/32, 43.8% | 11/32, 34.4% | One public SHOP-only dental issuer, 92388, remains unknown |
| FL | 11/26, 42.3% | 9/26, 34.6% | Partial ACTIVE presence is retained |
| NC | 6/13, 46.2% | 3/13, 23.1% | Final recovered reports are selected |
| GA | 0/16, Quarantined | 0/16, Quarantined | Catalog adapter limitation, not publisher denial |

All remaining issuer scopes are unknown. The issuer denominator is reconstructed
from each selected public plan file, including denied issuers and issuers without a
registry entry. `unassessed_issuers` explicitly declares public roster members absent
from both source report and audit; it never removes them from the denominator.
Reference edge counts, NPPES identities and enrichment never contribute to coverage.
The current adapters emit zero `not_imported` units. The checker rejects that issuer
classification until a reviewed adapter can attest an assessed, valid unimported
source; unknown and quarantined units cannot be relabelled to imply that evidence.

Premium evidence reconciles the 49 comparable 2026 source scopes and 29 federal
2027 scopes against the public archives. **The committed release measures 49 2026
serving scopes:** 19 SBE declarations plus 30 federal pointer-derived oracle results.
The source reviews below establish the federal serving lineage independently of
the passing comparisons. The separate 2027 review establishes serving eligibility
for its 29 federal scopes. Each year uses its own exact reviewed artifact and public
source bytes; the remaining 22 premium scopes in 2027 stay Unknown.
NY/VT supplemental checks remain supporting evidence with null denominators.
Oregon uses only its federal 2026 scope; its SHOP-only SBE bundle is not added.
No 2027 record borrows 2026 sources.

### Reviewed federal 2026 serving lineage

The finalized `p6d-all-states-2026.json` is selected twice, with the same SHA-256:
`federal_oracle_2026` supplies independent reconciliation and
`federal_pointer_2026` supplies serving lineage through `p6d-pointer-v1`. Its
reviewed artifact hash is
`d2e81f75f0205d82528e046a486f702a23cefd9df71dc6aceff7e3d6c5a5c795`.
This explicit second selection is required; ordinary `federal-v1` reports never
become serving evidence automatically.

Read-only review of the OpenPlans producer established these paths:

1. `scripts/oracle/all-states.mjs` selects `import_id` from `puf_active_catalog`
   for the requested state/year. It checks the selected import's file hashes
   against the acquired inputs before reusing that pointer. The result's
   `import_id` is assigned from this selected pointer.
2. If no matching pointer exists, that script awaits `importPufs` with publication
   enabled (no `publish: false`), requires a passing import, and uses the returned
   import ID. `src/ingest/puf/import.ts` commits the snapshot activation and
   `puf_active_catalog` upsert in one transaction before returning or writing its
   report. This was unconditional in the original federal producer; the later
   SBE change guards it with `options.publish !== false`, which this caller meets.
3. The script then compares the selected catalog's identities and rate rows and
   writes the state result. Thus the selected report identifies a serving catalog
   in each validation run. A generic import report's `status: ACTIVE` is
   insufficient: historical ACTIVE snapshots survive pointer replacement, and
   supplemental imports can be ACTIVE without publication.

The oracle was introduced at OpenPlans commit
`c5fee4f6d58f5fe12bda5321c0a73c4f49b40417`; the SBE publication guard was reviewed
at `38caf7b3ca43bf0a30435eb97e6af997fed56c51`. Reviewed file SHA-256s at source
commit `9129518013046d50df283f5c0564fc8c37d9da51`:

| Producer file | SHA-256 |
| --- | --- |
| `scripts/oracle/all-states.mjs` | `68be82ce8f20b29fb93562bf8a6e6dd9ba5b4c62ee558d7dbb3fed87c0be34d5` |
| `src/ingest/puf/import.ts` | `0188df4007611173e80a9a67dfcc00fb2eec2a33271c93318e8d773b99434729` |

Every 2026 oracle import ID also has a matching finalized PUF import JSON with
`passed: true`, `status: ACTIVE`, six file reconciliations and matching state/year.
Those corroborate activation but are not selected as a substitute for pointer
lineage. Batch summaries, reconciliation-only results, logs, interrupted runs and
synthetic mutants are not serving evidence.

The adapter accepts only the exact reviewed per-year artifact hashes, requires the
same artifact for reconciliation, checks state membership, catalog identity and
observation cutoff, and retains the original oracle observation dates. It does not
read OpenPlans source at scan time. Changed or future artifacts fail closed until
their producer lineage is reviewed or an audited `serving-v1` export is supplied.
The committed ledger records the pointer input hash and a digest of the selected
catalog ID alongside reconciliation and public source bytes. No import IDs or raw
logs are exported. These are **separate validated runs**, not evidence of one
currently deployed database or a live service.

The scopes changed from Unknown to a checked numerator in 2026 are:
AK, AL, AR, AZ, DE, FL, HI, IA, IN, KS, LA, MI, MO, MS, MT, NC, ND, NE, NH, OH,
OK, OR, SC, SD, TN, TX, UT, WI, WV, WY. Each numerator equals its unchanged source
row denominator, for 100.0%. Issuer figures and all 2027 values are unchanged.

### Reviewed federal 2027 serving lineage

The finalized `p6d-all-states-2027.json` is independently reviewed and selected as
both `federal_oracle_2027` and `federal_pointer_2027`. Its SHA-256 is
`2442b9f54ffd357d5f86cc05f39a10a4de571eac5f761bcc6f2890a1f48fc69e`.
The producer files at source commit `9129518013046d50df283f5c0564fc8c37d9da51`
have the hashes listed above. The oracle is byte-identical to its introduction at
`c5fee4f6d58f5fe12bda5321c0a73c4f49b40417`. Its requested-year query and
publication-enabled import path apply to 2027 independently of the 2026 results.
The import transaction sets `puf_active_catalog` before returning; a reconciliation
pass or historical ACTIVE status alone does not establish that lineage.

All 29 aggregate state results equal their finalized `p6d-2027-STATE.json`
counterparts. Each catalog ID matches a separate finalized PUF import JSON with
the same state/year, `passed: true`, `status: ACTIVE` and six reconciled files.
These corroborate activation; the reviewed oracle's pointer selection establishes
serving eligibility. No logs, batch summaries, synthetic mutants or 2026 evidence
are used to grant a 2027 numerator. Original oracle observations range from
`2026-11-08T12:02:30.488Z` to `2026-11-08T12:08:02.604Z` and are retained.

The 2027 scopes changed from Unknown to a checked numerator are:
AK, AL, AR, AZ, DE, FL, HI, IA, IN, KS, LA, MI, MO, MS, MT, NC, ND, NE, NH, OH,
OK, SC, SD, TN, TX, UT, WI, WV, WY. Their numerators total 2,115,809 rate rows;
each equals its unchanged public source denominator, for 100.0%. Oregon is absent
from the 2027 federal inventory and stays Unknown. This release changes no 2026
dataset or issuer dataset. See the per-state counts and checks in the
[2027 handoff](work-notes/premium-2027-acceptance.md).

The second `p6d-pointer-v1` selection is mandatory, bound to the same per-year
reconciliation artifact. Changed or unreviewed artifacts fail closed. A 2027
scope with reconciled rows and no serving selection retains D and null N/percent;
even an approved 2026 pointer cannot establish its serving evidence. The population
remains `separate_validated_runs`, with no claim of one currently deployed snapshot.

The legacy TX recovered audit corroborates the source report's ACTIVE snapshot IDs
against its final manifest pointers, and also repeats provider source validation.
FL/NC additionally export explicit active-set tables. A manifest's partial status
alone is never ACTIVE evidence. An exported valid ACTIVE pointer survives a later
failed manifest refresh, with a warning. No live-service availability is claimed.

Observation dates are retained per issuer from manifest updates and per state from
the audit's `recorded_at` or last manifest update. Federal oracle observation dates
are its generated timestamps. Undated SBE reports use the fixed operator evidence
review timestamp in the selection; this is separate from generation time. Public
source retrieval dates remain independent in provenance. Snapshot age must remain
visible in the reader, per DESIGN.md.

## Selection and self-hosted records

Top-level fields are required: `schema_version: 1`, `source_commit`, `population`,
`sources`, `reports`, `premium_scopes`, `issuer_scopes`. Unknown fields are rejected.
IDs are short lowercase identifiers. Every selected source/report must actually be
used; adding unused inputs fails. There is no recursive file/report ingestion.

Each source declares `path`, `sha256`, public `url`, `title`, `vintage`,
`retrieved_at`, and `members: [{name, kind}]`; kind is `plans` or `rates`. Only ZIP
members explicitly named in the selection are parsed. CSV headers can use the CMS
compact or spaced forms. The parser requires business year, state, issuer and plan
identity columns, correct year membership and complete rows. Physical row numbers
and every original cell, including null/empty rate cells, enter a deterministic
state row digest. The ledger retains archive and member hashes, row counts, row
digests and the complete public issuer roster. It exports no raw cells.

A report declares `path`, `sha256`, `format`, and `finalized: true`. The selected
formats are closed, versioned adapters, not guessed shapes:

- `federal-v1`: independent oracle `year`, aggregate `passed`, and state `results`.
  State results require `state`, `year`, `import_id`, `passed`, exact `base_ids` and
  `variant_ids`, and `premiums` with passing raw/stored counts and zero mismatches.
- `p6d-pointer-v1`: an exact reviewed 2026 or 2027 federal oracle artifact above, selected
  separately as a premium scope's `serving_report`. Its hash must equal the scope's
  `federal-v1` reconciliation report hash. Only this reviewed producer's pointer
  lineage grants serving eligibility; the adapter rejects arbitrary passing
  federal-shaped reports and unreviewed years or changed artifacts.
- `sbe-v1`: `year`, `status: PASS`, state `states` with `state`, `year`, `import_id`,
  public bundle `sha256`, `status: PASS`, zero `mismatches`, `issuers`, `base_plans`,
  `counts.rate` and `rates_checked`. Both row counts must match public file bytes.
- `sbe-declaration-v1`: the reviewed finalized serving-scope declaration used in
  this release. Its adapter is specifically limited to the 19 2026 serving SBE
  states, checks each table row's state, public URL and catalog counts, excludes
  NY/VT supplemental bundles and Oregon SHOP, and cannot establish
  federal serving pointers. New declaration formats need a reviewed adapter.
- `issuer-v1`: `state`, `year`, `kind` (`providers` or `formulary`), `running: false`,
  and unique `issuers` entries containing `issuer`, `state`, `year`, `snapshot_id`,
  `status` (`ACTIVE` or `QUARANTINED`), `completeness`, `edges`, `expected_children`,
  `complete_children`, and a sanitized machine `reason`. ACTIVE requires positive
  plan-linked associations in the same state/year and a matching audited pointer.
- `audit-v1`: `manifest` entries containing `issuer_id`, `state`, `plan_year`, `kind`
  (`provider` or `drug`), `status`, `snapshot_id`, sanitized machine `reason`, and
  `updated_at`; `active` entries containing `kind`, `issuer_id`, `snapshot_id`.
  `validation_state` is required when a GA quarantine-only scope uses this audit
  without a separate source report. Unknown fields in legacy raw reports are never
  copied. Self-hosters should provide only these sanitized fields, optional
  `recorded_at`, and zero-valued attribution checks, without raw records or logs.
- `serving-v1`: explicit sanitized ACTIVE catalog pointers, shaped as below. This
  format is the preferred way to supply self-hosted serving evidence. Every selected
  state/year must have exactly one matching pointer and source hash. NY/VT require a
  separately reviewed filed-rate adapter and cannot be promoted by this format.

```json
{
  "schema_version": 1,
  "catalogs": [{
    "state": "TX",
    "year": 2026,
    "import_id": "puf-2026-TX-example-identity",
    "status": "ACTIVE",
    "source_sha256": "replace-with-the-64-character-public-rate-archive-hash",
    "observed_at": "2026-11-08T12:00:00Z"
  }]
}
```

`import_id` must exactly match the selected oracle's real identity; the example is
symbolic. Point a premium scope's `serving_report` at that selected report's ID.
Premium scopes declare state/year, rate `source`, `plan_source`, both member names,
`report` (or null), `serving_report` (or null), and `observed_at`. Issuer scopes
instead declare state/year, `source`, `plan_member`, `layer`, `report`, `audit`,
`observed_at`, and `unassessed_issuers`. With neither audit nor report, a known issuer
inventory is retained entirely as unassessed unknown units. A missing report is not
zero. Malformed, contradictory, truncated, unsupported or hash-mismatched evidence
fails the scan and preserves the previous publication.

## Publication and validation boundary

`inputs.py` handles private input parsing and reconciliation. `model.py` holds
contract values and integer arithmetic. `scan.py` serializes canonical sorted UTF-8
JSON with LF and no floating-point percentages, stages the whole release, invokes
`check.py`, then atomically exchanges complete directories. macOS `renamex_np` and
Linux `renameat2` are called through standard-library `ctypes`; unsupported systems
fail closed on replacement. No partial generation replaces the last valid data.
The tooling table is written by a separate atomic file replacement after validation.

`schema.json` defines closed publication objects. `check.py` implements its small
explicit JSON Schema vocabulary without dependencies, and enforces the semantic
rules: exact 51-state sets, six unique datasets, allowlisted values, strict integer
types (including rejection of booleans/fractions), half-up rounding, partition sums,
quarantine semantics, ACTIVE and scoped positive-association lineage, timestamps,
content hashes, provenance and privacy. Unknown schemas and keywords fail closed.
It enforces uncompressed budgets: index 16 KiB, dataset 64 KiB, ledger 256 KiB,
whole release 2 MiB. Unknown states and nulls remain in every dataset.

The scanner binds each denominator to public archive/member bytes and row identity
digests; a private report hash alone never creates a denominator. The checker can
verify committed ledger consistency and hashes without private inputs. Reproducing
source counts requires the exact public bytes plus the operator's own sanitized
import/pointer reports. Hashes establish identity and integrity, not the truth of an
operator's assertions. New input contracts must be reviewed, not silently accepted.

Tests construct isolated input roots from hand-authored fixtures, mutate copies and
check both scanner predicates and rehashed release semantics. They cover the brief's
negative controls, missing-report unknown behavior, retained ACTIVE refresh pointers,
byte-identical repeated runs, read-only inputs, no network socket usage, and failed
staging preserving the preceding release. No new runtime dependency or site gate
modification is introduced by this lane.
The serving controls also retain a known denominator with null numerator/percentage
when every row reconciles but no pointer evidence is selected, reject a forged
measured record without that lineage, reject unreviewed P6d artifacts even with
updated selection hashes, and bind pointer evidence to the reconciliation artifact.
