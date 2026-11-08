# Tests — coverage publication gate

Full gate: PASS. The saved mutation-control log records the named diagnostics.

- 51 coverage mutations: all 14 required defect families, strict count types,
  ledger/source integrity, all budgets, year references, scanner/input identity,
  unchanged-evidence date rewrites, backward publication time and same-hash bytes.
- A positive refresh control advances the validated cutoff, repins the ledger
  hashes and retains the original observations/assertions; it passes.
- A's 21 fixture tests: PASS, including real-input adapter predicates, immutable
  inputs, no sockets, fixed-run reproducibility and failed publication preservation.
- B's five deterministic static controls: PASS.
- Six repaired existing site controls: PASS, with clean and restored copies.
- Original data/site/scanner artifacts remain byte-identical; whitespace check
  passes. No private evidence or network was used.

Tests exposed the old HTML self-test's unknown-argument shortcut and buffered-tag
parser gap; both are fixed. Duplicate issuer and scanner-version mutants hit A's
earlier intended schema predicates, and their asserted diagnostics reflect that.
Review also found that unchanged observations must ignore a ledger path/hash
change caused solely by a later cutoff; the positive control protects that case.

Limits: hashes bind assertions, not the truth of unavailable private reports. No
browser suite, native popup keyboard check or production deployment is claimed.
