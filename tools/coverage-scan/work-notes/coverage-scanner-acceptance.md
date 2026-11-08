# Coverage scanner handoff

Input scope: 25 explicitly selected public archives and 14 finalized evidence reports. The input tree is read-only and its operator-supplied root is intentionally absent from every committed artifact. Selection covers 80 premium source scopes (49 comparable 2026, 29 comparable 2027, plus two supplemental 2026 scopes) and eight issuer scopes. Fixed cutoff and generation timestamps are 2026-11-08T13:00:00Z. Population remains separate_validated_runs; the metric includes all published exchange products, dental and SHOP where published.

Implementation identity: a1dc8b9cc8b88be27f94aec3b40a612d45baa78e. No browser, live page, contact, legal, CSP, gate, roadmap, task index, remote or OpenPlans source changes. No network/API/database access, paid calls or input-tree writes. No evidence-file writes are delegated to B/C; C can invoke the checker read-only.

## Acceptance

- [x] Standard-library unit suite: 21 tests, including hand-authored independent input fixtures and rehashed semantic mutants.
- [x] Coverage checker: PASS, six layer/year datasets with the exact 51-state set.
- [x] All eight report-derived issuer figures match DESIGN.md. Provider TX 14/32 (43.8%), FL 11/26 (42.3%), NC 6/13 (46.2%); GA 0/16 is Quarantined. Prescriptions are 11/32, 9/26, 3/13, 0/16. TX issuer 92388 remains unknown in D; partial ACTIVE sources are counted and labelled.
- [ ] Premium measured-state target of 49 for 2026: only 19 selected SBE scopes have explicit serving declarations. All 49 comparable 2026 source scopes reconcile, but 30 federal scopes retain D with null N/percent and serving_evidence_absent. The same applies to all 29 comparable federal 2027 scopes. The scanner accepts sanitized serving-v1 pointers to close this evidence gap. NY/VT supplemental rows remain unknown; OR SHOP is excluded; no 2027 borrowing.
- [x] Publication budgets/privacy: 13 JSON files, 286,257 bytes; index 8,065 bytes; largest dataset 28,768 bytes; largest ledger 64,512 bytes. Tooling table fragment is 4,729 bytes. Public sources are bound by archive/member SHA-256 and physical-row/all-cell digests; ledgers contain no raw records or private metadata.
- [x] Two independent full-input runs: all 13 release files and the table fragment are byte-identical. Both SHA-256 maps and the implementation pin are recorded in reproducibility.json.
- [x] Full site gate: PASS, including six site negative controls. Main was merged once (already up to date), and develop was merged into the lane (already up to date). Static data is included in this local handoff commit after the passing gate. Local commits use the required identity and trailers; nothing is pushed.

## Negative controls

All mutations are isolated fixture copies. Reject 14/32 changed to 50%; missing DC; duplicate TX/state/issuer; changed year; zero denominator; fractional count; withheld denied issuer (including simultaneous report/manifest removal); QUARANTINED counted ACTIVE; absent or wrong-state/year positive association; failed refresh replacing the prior pointer; GA adapter failure blamed on publisher access; OR SHOP double count; NY/VT supplemental promotion; changed source hash; private absolute path or escaped symlink; truncated report; unsupported schema/keyword; unsupported not_imported source-validity claims. Each fails with a named predicate. An intentionally absent report succeeds as Unknown with null N/percent. A valid prior ACTIVE pointer survives a later failed refresh with a warning. Failed staging preserves the prior release.

## Remaining owner evidence

1. Supply or select audited federal serving-catalog pointers, bound to the selected import IDs and public rate archive hashes, for 30 scopes in 2026 and 29 in 2027. Do not promote passing oracle results alone. This is the only unmet data acceptance target; no numbers are guessed.
