# Tests — coverage reader

- Scanner checker: PASS, 6 datasets, exact 51-state sets, arithmetic, lineage,
  privacy and budgets. Scanner unittest suite: 21 passed.
- UI static checker: PASS, exact default table fragment/JSON, Census geometry and
  labels, explicit default year/date, script/CSS budgets and protected-file parity.
  Five temporary negatives reject row deletion, altered fraction, absent/mismatched
  plan year and removed white-ground styling.
- Browser: PASS on 306 record/detail/table/map selections, share-link restoration,
  dated stale snapshots, requested viewport widths, 200% desktop equivalent,
  dark/reduced-motion/forced-colors checks and same-origin coverage request log.
- Rehashed semantic mutants reject impossible percentages, omitted DC, HTML reason,
  wrong dataset year/schema and unknown-to-numeric-zero substitution. Corrupt hash,
  dataset/index 404, invalid JSON and unknown index schema preserve the saved view.
  A post-load 404 retains a nondefault valid view and URL. A delayed old request
  deliberately ignores abort and still cannot replace the newer selection.
- Scripts disabled at a nondefault URL keep the explicitly labelled default 2026
  map and 51-row table. Measured zero, quarantine and unknown fills are distinct.
- Browser planted black ground, absent rendered year and mismatched year all make
  their computed-style/rendered-year predicates fail.
- Full site gate: PASS, including clean-copy selftest and six existing controls.

Tests surfaced a reader bug: NY/VT supplemental evidence can be nonnull with a null
statewide denominator. Validation now honors A's actual contract. Forced-color
emulation initially painted the section black; the fixed-white coverage canvas now
preserves the explicit white requirement, while native controls retain system
forced-color treatment and pressed buttons also use an underline/thicker border.

Reviewed local captures: desktop, phone and phone table. Phone table widths and
sentence-case full state names were improved after inspection; captures were
regenerated and reviewed. Binary artifacts remain in the local capture directory
listed in the checker README. The committed browser-checks.json is the factual
text report, including the two limits below.

Limits: unchanged 320px whole-page overflow exists in section 05/contact, outside
this lease; coverage itself fits. macOS native select popup keystrokes cannot be
verified with this CDP driver. Buttons activate by keyboard; all state/year changes,
focus retention and live announcements pass, but full native-popup keyboard-only
acceptance remains pending. No contact form submission or CAPTCHA solving occurred.
