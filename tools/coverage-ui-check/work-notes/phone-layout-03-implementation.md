# Implementation — phone layout and keyboard

Changed plans/style.css only in production: verification cell wrapping, constrained scroll region, contact grid zero minimum/track, status wrapping and expanding only the contact widget grid into the gutters below 360px while preserving normal text gutters. Kept original contact widget 304px minimum and all markup, copy, scripts, ids and white ground.

Extended existing browser.mjs rather than adding a dependency: strict pageFits assertion across six widths and script-disabled saved view, same-assertion planted overflow rejection, contact widget dimensions, verification-region semantics, Tab/Shift+Tab, Space/Enter, native select type-ahead, selected map/detail, focus retention/ring and polite atomic status in the accessibility tree.

The verification table retains a 420px minimum width inside its scroll region so headings and counts remain readable. ArrowRight scrolling is verified by keyboard.

Removed historical branch baseline allowance (incubation removed that ref; baseline overflow should no longer be accepted). Native popup arrow input alone was a CDP/platform limitation; closed-select type-ahead works, so no runtime or markup rewrite was needed.

No deviations from design.
