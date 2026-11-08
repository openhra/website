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
can select a capture directory. The default output is `<scratch>/openplans-coverage-ui/`:
`desktop.png`, `phone.png`, `phone-table.png`, `phone320-verification.png`,
`phone320-contact.png`, and `browser-checks.json`. Captures are
local review artifacts, not production assets. The checker requires the current
whole page to fit at 320, 360, 390, 768, 1280 and 1440 CSS pixels, with desktop scrollbars present. A planted 1000px element
at 320px must fail that same overflow assertion. It never changes production
HTML or coverage data files. Response mutants
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

## Keyboard and phone verification

The checker tabs forward from the validation table region through all three layer
buttons, the year select, the state select and map attribution, then reverses through
the selects with Shift+Tab. Space and Enter activate layer buttons. Native select
closed-control type-ahead changes both years and selects Alaska, DC, Hawaii and
Texas; these checks use CDP keyboard input, never assigned values or synthetic
`change` events. On macOS, arrow events sent into the native popup alone did not
change its selection, so the checker uses the supported closed-control interaction.
Every change must preserve focus, update the selected map/detail, and update the
polite atomic live status. The accessibility tree must expose that live status.
Focus indicators must be visible, teal, at least 3px with a 5px offset, with the
focused control inside the viewport. Actual screen-reader speech is not recorded. The W5 run is recorded in
`work-notes/phone-layout-browser-checks.json` and `work-notes/phone-layout-04-tests.md`.

At 320px, the verification table stays inside its labelled keyboard-focusable scroll
region and long cells wrap. The contact widget grid extends into the gutters to retain its full 304px width;
it is neither scaled nor cropped, and contact text keeps its normal gutters. Both the interactive view and script-disabled saved
view must fit the page. Contact handler/scripts/ids and CSP are unchanged. No form
was submitted and no CAPTCHA challenge was solved.

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
