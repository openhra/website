# Static coverage reader checks

The runtime needs no service, framework, dependency or build step. Serve `plans/`
as the site root. The reader requests only same-origin `data/coverage/index.json`
and one selected layer/year file. Provenance and evidence downloads are ordinary
links, not automatic requests. The existing contact verification remains separate.

Run the offline checks:

```sh
python3 tools/coverage-scan/check.py plans/data/coverage
python3 tools/coverage-ui-check/check.py --selftest
python3 -m unittest discover -s tools/coverage-scan/tests
tools/gate.sh --full
```

For browser checks, start a local preview and the shared headed browser, then run
the dependency-free Node CDP checker against that existing tab:

```sh
python3 -m http.server 8779 --bind 127.0.0.1 --directory plans
# In another terminal:
agent-browser --headed --profile "$HOME/agent-browser" open http://127.0.0.1:8779/
node tools/coverage-ui-check/browser.mjs
```

`COVERAGE_PREVIEW_URL` can select another loopback preview; `COVERAGE_CAPTURE_DIR`
can select a capture directory. The default output is `/tmp/openplans-coverage-ui/`:
`desktop.png`, `phone.png`, `phone-table.png`, and `browser-checks.json`. Captures are
local review artifacts, not production assets. The checker creates one temporary
baseline HTML page from A's local branch, serves it through the existing preview,
and removes it in `finally`. It never changes coverage data files. Response mutants
are document-start browser wrappers removed between cases.

The static checker verifies byte-identical A fallback fragments against the default
JSON, the exact Census geometry/state/label set, reader/CSS budgets, unsafe DOM
operations, explicit default year/date, and protected page/contact/CSP/token parity
against local `main`. It must be run after the brief's required `main` merge.

The browser checker compares every detail, table row, state fill and date for all
306 state/layer/year selections, URL restoration, snapshot aging, requested widths,
media preferences, 200% desktop equivalent (720 CSS pixels at 2x), focus and live
announcements, same-origin requests and the named response/visual negative controls.
The semantic mutants have their dataset hashes recomputed so rejection must reach
the reader's field/semantic validation. A separate hash mutant retains the expected
digest. The race ignores AbortSignal on purpose, proving request-ID gating too.

## Verification limits recorded by the checker

- At 320 CSS pixels with a 15px desktop scrollbar, the existing verification table
  and fixed 304px contact area make the page 324px wide (305px client width). The
  unchanged A baseline has exactly the same overflow. Coverage adds no overflow
  and uses 16px gutters. The checker records `pageNoOverflow: false`, and rejects
  any increase over baseline or any overflow inside coverage. Section 05 and the
  contact area are outside B's lease; the whole-page acceptance remains open.
- On this macOS Chrome, CDP keyboard events activate buttons but do not operate
  native select popups. The checker records this explicitly instead of treating
  synthetic `change` events as keyboard proof. It verifies all selection results,
  full state options, focus retention and announcements. Native keyboard-only
  year/state navigation (including DC, Alaska and Hawaii) still needs a platform
  that can drive those popups or a manual pass.
- No form was submitted and no CAPTCHA challenge was solved. Contact handler,
  scripts, identifiers and CSP are byte-identical to `main`.

## Publication assumptions

Default Providers / 2026 uses Texas as the initial detail. Unknown stays Unknown,
including known inventories without serving evidence. Quarantine-only map shapes
use hatching and the Quarantined label. A's saved fragment is retained verbatim,
including its numeric 0/16 fraction beside the explicit Quarantined status; the
interactive table leads with Quarantined.

For 2027 premiums, a record with no public provenance or denominator is labelled
“Source not published yet in this snapshot; Denominator unverified.” This is a
statement about the committed publication only. It does not infer a current CMS
publication status or borrow 2026 data. A future scanner refresh should publish
`source_not_published` when that stronger external observation is evidenced. The
reader uses that explicit reason directly when supplied.

`Date.now()` only annotates whether the fixed as-of date is older than seven days;
it never changes evidence values. All views remain labelled dated snapshots and
separate validated runs. Publication/data refresh and integrating these checks into
the shared gate belong to C/owner.
