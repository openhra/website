# Premium 2027 serving evidence handoff

W4F independently reviewed the finalized 2027 oracle and the read-only OpenPlans
producer. The exact reviewed artifact supplies serving lineage through a separate,
hash-pinned `p6d-pointer-v1` selection. The [source review](../README.md#reviewed-federal-2027-serving-lineage)
records the report hash, producer commit/file hashes, active-pointer query and
publication transaction. All 29 aggregate results equal their finalized state
reports, and all selected import IDs match finalized ACTIVE, passing PUF import
JSON with six reconciled files. Those import statuses only corroborate activation;
the producer's explicit serving-pointer lineage grants eligibility.

Assumption: evidence describes serving eligibility in separate validation runs,
not one live deployed database. The broad published exchange inventory includes
all published products. Only PY2027 premium eligibility changes. No 2026 evidence
supports a 2027 count. The remaining 22 premium scopes in 2027 remain Unknown;
Oregon is absent from the federal 2027 inventory and is not borrowed from 2026.

Implementation: `d8e87b52d492026a38f1faf9c2024ea7ff347924`. Cutoff and generation
remain `2026-11-08T13:00:00Z`. Actual 2027 oracle observations are retained.
Selection now has 16 evidence selections from 14 distinct finalized reports.

## Count and status diff

Exactly 29 states changed from Unknown (null N/percentage) to measured N = D,
100.0%. Their numerators total 2,115,809 rate rows; every denominator is unchanged.

| State | Before N | After N | Unchanged D |
| --- | ---: | ---: | ---: |
| AK | null | 3,424 | 3,424 |
| AL | null | 72,726 | 72,726 |
| AR | null | 19,482 | 19,482 |
| AZ | null | 31,365 | 31,365 |
| DE | null | 2,142 | 2,142 |
| FL | null | 584,001 | 584,001 |
| HI | null | 2,091 | 2,091 |
| IA | null | 23,817 | 23,817 |
| IN | null | 102,408 | 102,408 |
| KS | null | 23,664 | 23,664 |
| LA | null | 34,068 | 34,068 |
| MI | null | 233,372 | 233,372 |
| MO | null | 50,847 | 50,847 |
| MS | null | 18,513 | 18,513 |
| MT | null | 14,994 | 14,994 |
| NC | null | 78,285 | 78,285 |
| ND | null | 9,180 | 9,180 |
| NE | null | 17,340 | 17,340 |
| NH | null | 16,220 | 16,220 |
| OH | null | 193,290 | 193,290 |
| OK | null | 23,205 | 23,205 |
| SC | null | 177,174 | 177,174 |
| SD | null | 8,109 | 8,109 |
| TN | null | 35,751 | 35,751 |
| TX | null | 223,533 | 223,533 |
| UT | null | 16,848 | 16,848 |
| WI | null | 79,713 | 79,713 |
| WV | null | 12,597 | 12,597 |
| WY | null | 7,650 | 7,650 |

The other five datasets, their evidence ledgers and the default provider table
are byte-identical to the preceding release. All 2026 figures, provider/formulary
classifications, quarantines and unknown issuers retain their prior values.
Only the 2027 premium dataset, its content-addressed ledger and the index change.

## Negative controls

All 25 inherited tests (including every W4A control) remain and pass. Three added
2027 tests prove that reconciled rows without explicit serving selection retain
D and null N/percentage, a forged measured record without pointer lineage fails,
a reviewed 2026 pointer cannot establish 2027 eligibility, and an unreviewed 2027
artifact is rejected even after its selection hash is updated. A test-only pin
substitution exercises the reviewed adapter with handwritten fixtures; production
accepts only the independently reviewed per-year hashes. Existing controls retain
missing-report semantics, issuer denominators, quarantine attribution, source and
state/year binding, failed-refresh behavior, deterministic output, read-only inputs,
network prohibition, and failed-publication preservation.

## Acceptance

- [x] Existing finalized 2027 evidence and read-only producer reviewed; explicit
  serving lineage documented independently of rate reconciliation.
- [x] Exact 2027 artifact approved and explicitly selected for all 29 scopes; no
  automatic promotion of general federal reports or cross-year borrowing.
- [x] Regenerated coverage: six datasets with 51 states each; schema, arithmetic,
  lineage, privacy and budgets PASS. Release: 296,351 bytes; largest dataset:
  28,890 bytes; largest ledger: 69,522 bytes.
- [x] Scanner suite: 28 tests OK, including the required no-serving-evidence
  control and all inherited negative controls.
- [x] Two independent full-input runs produce identical release and table bytes.
  SHA-256 maps are in [premium-2027-reproducibility.json](premium-2027-reproducibility.json).
- [x] Final `git merge develop`: already up to date. Full site gate with the
  supplied publication denylist: `PASS`, including `selftest: PASS (clean copy
  and 6 negative controls)`. Scanner tests and checker pass after the merge.
- [x] Work confined to scanner tooling and static coverage data. No source/input
  writes, database/API/publisher access, paid calls, private paths, raw reports,
  legal edits, live site edits, contact/CSP changes, remotes or pushes.

## Follow-up

1. No additional operator evidence is needed for these 29 scopes. Any future or
   changed oracle artifact still needs producer review or sanitized `serving-v1`
   evidence. Unpublished 2027 SBE scopes remain Unknown until their own evidence
   exists; this task does not create that evidence.
