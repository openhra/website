# W7 acceptance report

- [x] Landing default uses the most measured dataset, Premiums 2026 with 49 states.
  Layer summaries show measured-state counts. Unknown reads as not yet measured.
  The full table is collapsed and the full-page link is above the controls.
- [x] Full scanner refresh passed at `2026-11-08T16:33:27Z`. The newer reviewed
  federal artifacts have unchanged catalog pointers. All six datasets reported
  zero count or status changes. No additional FL or NC issuer presence qualifies.
- [x] `/availability` has the map, layer/year/state controls, state detail, full
  table, methodology and dated evidence. It shares coverage.js with the landing
  page. Existing cleanUrls hosting configuration provides the route.
- [x] Both pages restore and replace URL selections and handle back/forward.
  Share uses the full-page deep link, native sharing or clipboard copy with a
  visible polite confirmation. Social metadata uses the existing 36 KiB preview.
- [x] Keyboard selection, focus and accessibility-tree live status passed. Both
  pages fit at 1280, 390 and 320. The screenshots in this directory were inspected.
- [x] Changed explanatory copy received the unslop pass. Legal, affiliation and
  contact copy and hosting security headers remain unchanged. Privacy and content
  checks passed. No email addresses, private volume paths or private vendor names
  were introduced.
- [x] `website/tools/gate.sh --full` printed `PASS`.
- [x] Root `tools/gate.sh` printed `PASS` after merging develop. The reference-capture mock passed 52
  tests. OpenPlans passed 1,010 tests, with 8 tests skipped across 3 skipped files.
  The website checks passed, including 28 scanner tests, 51 publication mutation
  controls and all 10 UI mutation controls.

## Requested negative controls

Each isolated mutant failed its intended check: ignored initial URL state, share
URL without the selection, missing clipboard confirmation, an unknown state shown
as a measured number, and the availability page missing from the gate page list.
Clean sources passed afterward. Additional browser response, hash, timing and
layout controls passed. `browser-checks.json` records the real-browser results.

## Decisions

"Most measured states" takes priority over "latest year with data." That selects
2026 with 49 states rather than 2027 with 29. The newest year breaks a tie. Controls
replace the current history entry as requested; browser navigation restores the
selection from the destination entry.

The reader budget is 24 KiB for the shared validation, URL and sharing code. Its
actual size is under 19 KiB. The scanner still rejects unreviewed federal reports;
only the two reviewed afternoon report hashes were added to its allowlist.

## Manual follow-ups

1. Check the operating-system share sheet and screen-reader speech on the owner's
   target devices. Browser tests stub sharing and clipboard APIs and inspect the
   accessibility tree; they do not claim those manual device checks.
2. Promotion and deployment remain with the orchestrator. This lane did not push,
   change remotes or deploy.
