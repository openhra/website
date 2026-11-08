# Design

CLI → selected-input reader → reconciliation model → deterministic serializer → staged semantic checker → directory publication.

Create model.py for shared arithmetic/contracts; inputs.py for read-only ZIP/CSV and selected report adapters; scan.py for publication; check.py for independent release consistency; schema.json for strict structural contract; tests/ for handwritten evidence and mutations; README and selection example for operators. Existing gate and preview checker were rejected as inventory adapters in Analyze. All new files stay in tools/coverage-scan and plans/data/coverage.

Public source archive SHA-256 and member SHA-256 bind inventories to exact bytes. Each ledger records state/year, roster and source-member row digests, selected import hashes, scoped snapshot hashes and positive association flags. Six datasets always contain exactly 51 states. Unknown evidence remains null; unsupported adapters never fabricate denominators.

TODO: path/hash boundary, inventories, issuer and premium reconciliation, serving declarations, serialization/checker, static data/table, mutation tests, full gate and local main/develop synchronization complete. Static data is included in the passing-gate local handoff commit; owner evidence follow-up remains explicit.
No open questions. Separate validated runs is retained. Legacy evidence is explicitly selected, never discovered by report globbing. No network code.
