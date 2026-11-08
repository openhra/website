# Design — coverage publication gate

Normal gate → A's CLI checker → publication checks → B's static checker.
Full gate → existing repaired site mutations → isolated coverage mutations →
A's standard-library fixture tests → B's available static parity controls.

Edit `tools/gate.sh` and `tools/gate-selftest.sh` only for integration and actual
diagnostic assertions. Create a publication checker because A does not compare
the site or the selected input manifest, and B does not validate selected ledgers
or refresh history. Create a mutation runner because the old shell controls only
exercise general site checks. Reuse A's serialization and contract functions.
Create the requested operator runbook; keep lifecycle notes in this leased tree.

The publication boundary accepts `--root`, a previous validated directory or a
local committed baseline. No network, GUI, private input cache or new dependency.
Normal checked-out repositories use HEAD as the previous publication; unborn
self-test copies omit historical comparisons and retain all artifact checks.
Migration requires reviewed code/contract changes, not a bypass CLI flag.

Interpret the year title as the coverage section heading and standalone fallback
page title; require their caption and map title to match the default dataset.
Check the reader assignments bind heading/caption to the selected dataset year.
No open questions.
