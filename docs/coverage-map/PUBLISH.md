# Publishing a coverage snapshot

The orchestrator selects evidence, runs the offline scanner, reviews changes and
prepares a local commit. The owner/orchestrator publishes that reviewed commit
through the repository's protected-branch policy. The page reads committed static
files; it never introspects an OpenPlans instance. There is no API, new OpenPlans
command, import, scheduled refresh or hosting build step in this workflow.

## Select and stage

1. Choose explicitly finalized import reports, audited ACTIVE serving pointers and
   the exact cached public source archives for each plan year. Exclude interrupted,
   intermediate, synthetic and before-recovery runs. Follow the versioned adapters
   in [the scanner guide](../../tools/coverage-scan/README.md) and the metric in
   [DESIGN.md](DESIGN.md). Passing reconciliation alone is not serving evidence.
2. Set `OPENPLANS_DATA_DIR` locally to the evidence-cache root. Keep its value and
   any private input-selection file outside this repository. Paths in selections
   are relative to that root. Do not print environment values or copy raw reports,
   logs, connection details, addresses or secrets into public artifacts.
3. Prepare the allowlisted selection, public URLs/hashes, source vintages and real
   retrieval/observation times. Supply fixed UTC `COVERAGE_AS_OF` and
   `COVERAGE_GENERATED_AT` values locally; generation must follow the cutoff and
   neither may be in the future. Keep old observation dates for unchanged evidence.
   `source_commit` identifies the scanner implementation/base; `version` comes
   from the scanner. A version or metric/scope change requires a separately reviewed
   migration of the scanner/schema, reader and publication checks.
4. Preserve the previous valid release for comparison, then scan into staging.
   Choose a staging directory outside the read-only input tree. For example:

   ```sh
   stage=$(mktemp -d)
   cp -R plans/data/coverage "$stage/previous"
   python3 tools/coverage-scan/scan.py \
     --selection "$COVERAGE_SELECTION" \
     --as-of "$COVERAGE_AS_OF" --generated-at "$COVERAGE_GENERATED_AT" \
     --output "$stage/coverage" --table-output "$stage/providers-table.html"
   python3 tools/coverage-scan/check.py "$stage/coverage" \
     --previous "$stage/previous"
   ```

   The selection variable names a local file. Its values are not machine config
   to commit. The standard-library scanner reads cached files only and fails closed
   on a contradictory report, missing required serving evidence format, bad hash,
   unsupported source or failed reconciliation. Missing evidence that is explicitly
   allowed by the contract remains Unknown.

## Review and replace

Review the printed per-state count/status diff and the ledgers, not just PASS.
Compare inventory membership, denominators, ACTIVE/partial/quarantined/unknown
partitions, warning actors, source/report hashes, scope, dates and scanner identity.
Keep all 51 states in each of the six layer/year datasets. Reject unexplained lost
evidence, date rewrites or changed assertions from unchanged scoped inputs.

NY/VT supplemental checks do not establish serving premium denominators. Oregon
uses its federal individual catalog, not the SBE SHOP bundle. Do not borrow one
year's evidence for another or turn a missing report into measured zero. The
current release has 19 measured SBE premium states in 2026; federal premium
numerators remain null without serving-pointer evidence. Separate validated runs
are not a single deployed snapshot.

Keep `tools/coverage-scan/selection.example.json` synchronized with the selected
release: it is also the public identity manifest checked by the gate. It may
contain only safe relative identifiers, public source metadata and selected report
hashes, never private root paths or raw evidence. The gate recomputes the input
digest and binds every scope and ledger input to this selection. The public
checker can validate safe ledger assertions, partitions and row totals, but hashes
alone cannot establish the truth of private report assertions or independently
recount unavailable raw source bytes. Real-input recomputation belongs to the
scanner at generation, using the operator's own selected records.

After review, run the same scan with the same inputs and timestamps and
`--output plans/data/coverage`. The scanner validates a staged release and swaps
the whole directory atomically on supported macOS/Linux systems. It keeps the last
valid release if scanning, validation or directory exchange fails. Do not copy
individual JSON files over the published directory. The table fragment is replaced
separately; an interrupted table refresh must fail the site gate and must not be
committed or published.

Copy the generated Providers/2026 table fragment verbatim into both
`plans/index.html`'s `coverage-table` container and `plans/coverage-table.html`.
Refresh the standalone page title, coverage heading, map name, caption, saved detail
and visible snapshot dates from that same default dataset. Keep the scanner's
tooling fragment synchronized. This requires the reader/fallback lease; C does
not modify these files. B's static checker currently pins November 8, 2026 in its
default-date assertions; the owner must update those expectations under the UI
checker lease when publishing a differently dated snapshot. A stale fallback must
never pass because interactive fetching happens to work.

## Gate and commit

```sh
python3 tools/coverage-gate/check.py --previous "$stage/previous"
tools/gate.sh --full
```

The normal gate invokes the scanner checker and publication checks offline,
including selected inputs, exact arithmetic, roster/row reconciliation, safe
paths/URLs, budgets, year labels, default JSON/table parity and Census state IDs.
It compares refreshes against local `HEAD`; use the explicit previous directory
above for review of another baseline. Full mode adds isolated named mutation
controls, scanner unit tests and B's deterministic UI parity controls. Clean and
restored fixtures must pass, each mutant must fail its named diagnostic, and the
original artifacts must remain byte-identical. No browser, private report cache or
network is required. B's separate browser suite covers interactive/visual checks;
it is not silently claimed by this offline gate.

Only after full PASS, review and make a local commit on the task branch with the
required identity/trailers. Do not push or deploy from this slice. The orchestrator
handles subsequent merging and protected-branch publication. Follow develop-flow;
never commit directly to main, force-push or rewind a published branch.

If any step fails, retain the previous committed snapshot with its actual dates,
fix forward and repeat validation. Do not change the cutoff to imply a successful
refresh. The reader labels snapshots older than seven days with their snapshot
date and retains per-state observation dates. That display rule creates no refresh
cadence. A self-hoster regenerates from its own explicitly selected evidence;
another deployment's data is never inferred from the current page.
