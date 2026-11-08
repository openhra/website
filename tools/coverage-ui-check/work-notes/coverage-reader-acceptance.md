# Coverage reader acceptance and handoff

- [x] Scanner checker passes; 306 state/layer/year detail, table, fill and as-of
  comparisons match committed JSON. Unknown data remains unknown.
- [x] Browser log contains only local script/index/dataset coverage requests.
  Contact scripts, IDs, handler and CSP are unchanged against main.
- [ ] Complete keyboard-only year/state selection still needs a native-popup
  pass. Button activation, native full-name options, pressed states, state/year
  change results, focus and polite announcements pass automated checks; macOS CDP
  does not operate native select popups. See browser-checks.json.
- [ ] The requested whole-page no-overflow condition at 320px is not met by the
  existing verification table/contact area. The branch and A baseline both measure
  324px scroll width at 305px client width. No coverage element overflows; all other
  requested widths, 200% desktop equivalent, white ground, OS dark, reduced motion,
  forced colors, readable status text/patterns and 44px controls pass. Desktop/phone/
  table captures were inspected and refined.
- [x] Disabled JS, index/dataset 404, malformed/unknown-schema JSON and bad hashes
  retain the dated default; later failure retains the last valid nondefault view.
  Request-ID gating defeats a slow old response even when abort is ignored.
  Zero/quarantine/unknown fills are distinct.
- [x] Visible Census attribution, exact original 51 geographic paths, all inset/
  small-state labels, full-name native picker; no new remote assets.
- [x] Full tools/gate.sh --full prints PASS. Separate UI checker passes, including
  default parity, semantic/visual negative controls and protected-content/CSP checks.
  Main and A are merged locally; no publishing/push is performed by B.
- [x] Owner year-reference implementation: public page section 06 has a visible
  “Coverage for plan year 2026” title; 2026/2027 switches update title, SVG image
  name, legend, caption and shareable year/layer URL. As-of dates stay visible.
  Missing 2027 premium public sources say “not published yet in this snapshot” and
  retain Unknown/nulls. Rendered missing/mismatched year controls reject false views.

Follow-ups for C/owner:

1. Resolve the pre-existing 320px section 05/contact overflow with an appropriate
   lease; B deliberately did not alter those protected areas.
2. Complete the native year/state popup keyboard pass, including DC/AK/HI.
3. Integrate scanner/UI checks into the shared gate and publish through the existing
   site deployment process. This branch prepares the public page but does not deploy.
4. If externally audited publication status is required, have A/C encode
   source_not_published in absent 2027 source records. The reader currently qualifies
   its publication wording to the committed snapshot and makes no fresh CMS claim.

No input or refresh schedule was created. A's separate validated runs and incomplete
federal serving evidence remain explicit rather than being promoted to serving claims.
