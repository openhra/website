# Availability checks

The full scanner refresh passed at cutoff `2026-11-08T16:33:27Z`. All six datasets
reported zero count or status changes. The provider and prescription records from
an earlier issuer-only rerun matched the preceding publication exactly. The public
schema checker and coverage publication gate passed.

The offline selection fixture executes coverage.js with committed JSON. It checks
initial state restoration, layer/year selection, URL replacement, history events,
native sharing, clipboard copy confirmation, measured-state summaries and unknown
states. The UI self-test rejects each requested mutant for its intended diagnostic:

- Initial URL state ignored.
- Share URL loses the selection.
- Clipboard copy has no visible confirmation.
- Unknown state becomes a measured number.
- Availability page disappears from the gate's required page list.

The full site gate also runs 51 publication mutation controls, 28 scanner tests,
saved-table parity, geometry, privacy and content checks. Mutants use temporary
copies or intercepted browser responses. Production sources are never damaged.

The browser suite passed all 306 state/layer/year comparisons, native keyboard
controls and focus, live-status accessibility semantics, back/forward on both
pages, share selection, fallback and malformed-response controls, stale-response
races, script-disabled fallback and same-origin coverage requests. It checks 320,
360, 390, 768, 1280 and 1440 CSS pixels, desktop zoom equivalent, dark OS preference,
reduced motion and forced colors. All widths fit without horizontal page overflow.

Screenshots for both pages at 1280, 390 and 320 are in this directory, with an
additional full-table capture at 320. Native share and clipboard APIs were stubbed
during browser tests. No operating-system share sheet opened and the real clipboard
was not changed. Actual screen-reader speech was not recorded.

An early real-browser run reached Chrome's history-update throttle because the
exhaustive test dispatched hundreds of synthetic state changes at once. The test
now paces each 51-state batch. This does not change production behavior.

Final post-merge gate output is recorded in the lane report.
