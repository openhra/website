# Premium serving evidence handoff

W4D reviewed existing finalized evidence and the OpenPlans producer without changing either input tree. The exact reviewed 2026 oracle artifact supplies serving lineage through a separate, hash-pinned `p6d-pointer-v1` selection. See the [source review](../README.md#reviewed-federal-2026-serving-lineage). No generic reconciliation result is promoted automatically.

Assumption: the lane targets the 30 federal PY2026 scopes. The 29 federal PY2027 scopes remain null pending separate review or audited serving exports. Population remains `separate_validated_runs`; this does not assert one live deployed snapshot.

Implementation: `7aa575dfc32d08429ad414f24e069b8bcc8d8103`. Cutoff and generation time remain `2026-11-08T13:00:00Z`; original state observation dates are retained. Public source denominators and source bytes are unchanged. The 15 evidence selections refer to 14 distinct finalized reports.

## Count and status diff

Exactly 30 states changed from Unknown (null numerator and percentage) to a measured numerator equal to D, or 100.0%. The 19 already-measured SBE states retain their figures, bringing 2026 to 49 measured scopes. NY/VT remain supplemental and unknown; Oregon uses the federal catalog only.

| State | Before N | After N | Unchanged D |
| --- | ---: | ---: | ---: |
| AK | null | 3,883 | 3,883 |
| AL | null | 67,473 | 67,473 |
| AR | null | 24,225 | 24,225 |
| AZ | null | 31,161 | 31,161 |
| DE | null | 2,703 | 2,703 |
| FL | null | 567,681 | 567,681 |
| HI | null | 2,091 | 2,091 |
| IA | null | 32,283 | 32,283 |
| IN | null | 113,526 | 113,526 |
| KS | null | 19,839 | 19,839 |
| LA | null | 29,886 | 29,886 |
| MI | null | 233,321 | 233,321 |
| MO | null | 48,246 | 48,246 |
| MS | null | 19,482 | 19,482 |
| MT | null | 31,110 | 31,110 |
| NC | null | 75,072 | 75,072 |
| ND | null | 10,353 | 10,353 |
| NE | null | 22,338 | 22,338 |
| NH | null | 18,974 | 18,974 |
| OH | null | 204,663 | 204,663 |
| OK | null | 27,846 | 27,846 |
| OR | null | 24,072 | 24,072 |
| SC | null | 191,760 | 191,760 |
| SD | null | 8,772 | 8,772 |
| TN | null | 36,975 | 36,975 |
| TX | null | 203,592 | 203,592 |
| UT | null | 17,409 | 17,409 |
| WI | null | 138,006 | 138,006 |
| WV | null | 22,440 | 22,440 |
| WY | null | 6,579 | 6,579 |

The 30 new numerators sum to 2,235,761 rate rows. The other five datasets and the default provider table are byte-identical to W4A. All provider/formulary figures, partial classifications, quarantines and unknown issuers remain unchanged.

## Checks and negative controls

The scanner unit suite retains all 21 W4A tests and adds four serving-evidence tests. A fixture with every rate row reconciled and no selected serving report retains D with null N/percentage, Unknown status and `serving_evidence_absent`. A forged measured 2/2 record with no pointer fails the semantic checker. Unreviewed federal-shaped pointer artifacts fail even when their selection hashes are updated; distinct pointer/reconciliation artifacts fail; removing the explicit pointer selection preserves Unknown. A test-only pin substitution exercises the reviewed adapter using handwritten fixtures; production accepts only the reviewed artifact hash.

The source review also checked every selected 2026 import ID against its finalized import JSON (ACTIVE, passed, six files, matching state/year). Those import statuses corroborate activation but do not replace the oracle pointer lineage. No database, API, publisher endpoint, paid service, OpenPlans command, source edit or input-tree write was used.

## Acceptance

- [x] Existing finalized reports and read-only OpenPlans source reviewed; explicit serving lineage documented and restricted to the exact reviewed artifact.
- [x] Selection and reconciliation extended; all 30 federal 2026 scopes now have numerators, and every changed scope is listed above.
- [x] Coverage regenerated and checked: six datasets, 51 states each; arithmetic, lineage, privacy and budgets PASS. Release is 291,389 bytes; largest dataset 28,890 bytes; largest ledger 69,522 bytes.
- [x] All 21 W4A tests retained; complete suite of 25 tests passes, including the required reconciled-without-serving negative control.
- [x] Two independent full-input runs produce identical bytes for all 13 release JSON files and the provider table. SHA-256 maps are in [premium-evidence-reproducibility.json](premium-evidence-reproducibility.json).
- [x] `git merge develop`: already up to date. Full site gate with the operator-supplied publication denylist: PASS, including its six negative controls. Scanner tests and checker were rerun after the merge.
- [x] Changes confined to scanner tooling and static coverage data. No remote access, push, private paths, raw reports, legal edits, live site edits or contact/CSP changes.

The full gate initially caught a pre-existing literal path prefix inside the privacy regex. Grouping the alternative path roots preserves its matching behavior and removes that denylist false positive. The publication schema and metric are unchanged; the implementation commit identifies the new input adapter.

## Follow-up

1. Review the separate federal 2027 oracle artifact, or provide audited `serving-v1` records, if its 29 null premium numerators should be assessed. This lane deliberately approves only the 30 federal 2026 scopes requested.
