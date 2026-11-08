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
It selects 25 public archives, 14 finalized reports, 80 premium source scopes and
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

Premium evidence reconciles the 49 comparable 2026 source scopes and 29 federal
2027 scopes against the public archives. **The committed release measures only the
19 2026 SBE serving scopes.** The federal reports do not export an explicit serving
pointer: 30 federal 2026 and 29 federal 2027 scopes retain their source denominators,
null numerators/percentages and `serving_evidence_absent`. Passing comparisons alone
are not promoted to serving evidence. This is a deliberate unresolved evidence gap
relative to the brief's 49-measured-state target. Supplying audited `serving-v1`
records below can resolve it without changing the metric or contacting a database
from this scanner. NY/VT supplemental checks remain supporting evidence with null
denominators. Oregon uses only its federal 2026 scope; its SHOP-only SBE bundle is
not added. No 2027 record borrows 2026 sources.

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
