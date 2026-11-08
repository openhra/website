# Tests — phone layout and keyboard

## Executed

- `git merge develop`: Already up to date (base/develop 6907ff4496d2f7a20bf628ed88cf469217e7925a).
- `OPENPLANS_DENYLIST_FILE=<repo>/tools/publication-denylist.txt website/tools/gate.sh --full`: PASS.
- `tools/gate.sh`: PASS (includes the full website gate).
- `COVERAGE_PREVIEW_URL=http://127.0.0.1:8785/ COVERAGE_CAPTURE_DIR=<scratch>/openplans-w5-ui node website/tools/coverage-ui-check/browser.mjs`: PASS (306 selections, responsive/appearance, keyboard, fallback, hashes and race controls).
- `git diff --check`: PASS.

## Acceptance

- [x] No page-level horizontal scroll at 320, 360, 390, 768 and 1280px (also 1440px); scrollWidth/clientWidth respectively 305/305, 345/345, 375/375, 753/753, 1265/1265, 1425/1425 with a 15px desktop scrollbar.
- [x] Verification table remains a labelled focusable scroll region, with wrapping cells and readable 420px table minimum; ArrowRight scrolls it from the keyboard.
- [x] Full 304px contact widget fits, with normal text gutters, unchanged flow/ids and white ground. CSS-only production changes.
- [x] Coverage Tab/Shift+Tab order, Space/Enter layer buttons, both native years and native state changes AK/DC/HI/TX by keyboard. No synthetic changes in keyboard proof.
- [x] Focus stays on each control, with a visible 3px teal ring/5px offset and control in viewport. Live status contents update and accessibility tree exposes polite/atomic status.
- [x] Planted 1000px-wide element at 320px fails the same pageFits assertion; removal restores PASS. Existing semantic/hash/fallback/race/static negative controls also pass.
- [x] Both required gates PASS; no remote/public checkout modification.

## Evidence and limits

Committed phone-layout-browser-checks.json records the browser assertions. Local PNGs under <scratch>/openplans-w5-ui were visually reviewed at 320px for verification and contact. No binaries are committed.

Assumed supported native closed-select type-ahead is sufficient keyboard operation on this Mac; CDP popup-arrow input alone does not change the native popup selection. This required a checker correction, not a site runtime rewrite. No screen-reader speech recording or successful live CAPTCHA/contact submission was performed; local preview renders the unchanged unavailable-contact status. No owner answer was needed.
