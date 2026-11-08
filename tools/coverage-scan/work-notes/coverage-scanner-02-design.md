# Design

CLI → selected-input reader → reconciliation model → deterministic serializer → staged semantic checker → directory publication.

Create model.py for shared arithmetic/contracts; inputs.py for read-only ZIP/CSV and selected report adapters; scan.py for publication; check.py for independent release consistency; schema.json for strict structural contract; tests/ for handwritten evidence and mutations; README and selection example for operators. Existing gate and preview checker were rejected as inventory adapters in Analyze. All new files stay in tools/coverage-scan and plans/data/coverage.

Public source archive SHA-256 and member SHA-256 bind inventories to exact bytes. Each ledger records state/year, roster and source-member row digests, selected import hashes, scoped snapshot hashes and positive association flags. Six datasets always contain exactly 51 states. Unknown evidence remains null; unsupported adapters never fabricate denominators.

TODO: validate path/hash boundary; parse inventories; reconcile issuer reports and pointer audits; reconcile premium reports and serving declarations; serialize/check; generate static data/table; mutation tests; full gate; merge local main/develop; commit.
No open questions. Separate validated runs is retained. Legacy evidence is explicitly selected, never discovered by report globbing. No network code.
