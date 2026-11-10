# Coverage reader checks

Both availability views use `plans/coverage.js` and static JSON. The reader loads
the index and six small datasets to count measured states and choose the default.
It validates the selected dataset again when controls change. No API or third-party
request supplies coverage data. Provenance links are ordinary downloads.

Run the offline gate from the website directory:

```sh
tools/gate.sh --full
```

The gate checks saved tables against the scanner generator, Census geometry,
metadata, clean URL configuration, required pages, protected contact and legal
blocks, security headers, white ground, reader and CSS budgets. A Node DOM fixture
executes the production reader against committed data. It verifies initial URL
restoration, replacement, history handling, measured-state counts, native sharing,
clipboard confirmation and unknown-state rendering without a browser or network.
Isolated mutants must fail their intended diagnostic. The five availability
controls remove initial state restoration, drop share parameters, remove copy
confirmation, render unknown as a number or remove the full page from the gate.

For real-browser checks, start the local preview and shared headed browser:

```sh
python3 tools/coverage-ui-check/preview.py --port 8779
agent-browser --headed --profile "$HOME/agent-browser" open http://127.0.0.1:8779/
node tools/coverage-ui-check/browser.mjs
```

`COVERAGE_PREVIEW_URL` selects a loopback preview. `COVERAGE_CAPTURE_DIR` selects
where to save screenshots and `browser-checks.json`. The preview honors the hosting config's existing `cleanUrls` setting, so both the
preview and production serve `availability.html` at `/availability`. A normal
Python static server does not provide that extensionless route.

The browser suite checks all 306 state/layer/year selections, current counts,
patterns, fractions and dates against JSON. It exercises initial deep links and
real browser back/forward on both pages, native-share dispatch and clipboard
fallback with visible live confirmation. Those APIs are stubbed in the test so no
external share sheet opens and the clipboard is not overwritten.

Keyboard checks use Tab, Shift+Tab, Space, Enter and native closed-select type-ahead
for both years and AK, DC, HI and TX. Focus stays on the control, focus indicators
remain visible and the accessibility tree exposes polite live status. The suite
does not record actual screen-reader speech.

Layout checks cover 320, 360, 390, 768, 1280 and 1440 CSS pixels, desktop scrollbars,
200% desktop equivalent, dark OS preference, reduced motion and forced colors.
Both pages have 1280, 390 and 320 captures. A separate 320 capture shows the full
page table. Captures are review evidence, not production artwork.

Document-start response mutants test malformed data, unsupported versions, wrong
years, corrupt hashes, absent states, HTML strings, unknown values changed to zero
and 404 responses. A delayed old request deliberately ignores cancellation and
must still lose to the newest selection. Script-disabled views keep the saved
dated Premiums 2026 fallback. Measured zero, unknown and quarantined states use
distinct fills and labels.

The landing table and detailed source links are native disclosures. The full page
shows the table, state detail, source links and methodology. Both default to
Premiums 2026 because it measures 49 states. Premiums 2027 measures 29.
Unknown stays not yet measured. Quarantined units remain in the denominator.

No contact form is submitted and no CAPTCHA challenge is solved by these checks.
