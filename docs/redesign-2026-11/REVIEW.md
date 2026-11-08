# Redesign review

November 8, 2026.

## Delivered

Both sites now lead with GitHub. OpenHRA explains the organisation and introduces the planned agent support. OpenPlans carries the twelve planned MCP tools, illustrative exchange, public and local connection previews, and source-based setup commands. All MCP blocks state that development is ongoing. The endpoint is planned, not hosted; no release is claimed.

The design uses the existing marks, white ground and teal tokens. New copy received an unslop pass. Legal, licence, attribution and affiliation text was excluded. Verification, the coverage section, publisher text and Contact remain intact. No data, coverage reader, contact handler, contact script or security policy was changed.

The nested organisation handoff copies and shared styles match the live page sources. The repository-first guide now describes the current owner direction.

## Visual review

Headless Chrome captured both sites at 1280, 390 and 320 CSS pixels, with desktop scrollbars present. Files named `plans-<width>.png` and `openhra-<width>.png` show the first viewport. The `-full`, `-mcp` and OpenPlans `-connect` captures show the rest of the design. `browser-checks.json` records the checks.

The first review found a lone Contact item on a second navigation row. Phone navigation now uses a small grid, and the shorter Publishers label avoids wrapping at 320px. The final captures show clear headings, readable repository rows, visible development labels and connection snippets that wrap inside the page. The long coverage table remains fully expanded, as required by the existing reader contract.

The narrowest viewport has 305px of usable width after its scrollbar. Both pages fit that width. The 304px contact placeholder fits without scaling or cropping. The verification table retains its separate focusable scroll region.

## Validation evidence

- Website full gate: `PASS`, with the external publication denylist supplied.
- Repository gate: `PASS`.
- Browser review: `PASS` for both sites at all three requested widths, heading order, landmarks, local images, local anchors, visible MCP labels and keyboard skip-link focus.
- Minimum measured visible HTML text contrast: 5.72:1 on OpenPlans and 6.12:1 on OpenHRA. The existing brand tokens remain unchanged.
- Dark OS preference keeps both pages white. Both pages also fit at 320px with JavaScript disabled.
- Thirty coverage selections across all three layers, both years and five states passed after the redesign. Existing offline coverage checks also passed, including the 51-state saved table and Census geometry.
- The protected-content check compares the complete coverage, Verification, publisher, contact, attribution and footer blocks with the baseline. It also checks both sites' contact scripts, handlers, tokens and security policies. All passed.
- Shared CSS and organisation handoff copies match their page sources.

The new MCP check rejects ten isolated mutants: removed status on either site, removed local development status, removed planned-endpoint label, false hosted status, removed example label, missing tool, wrong public endpoint, false release status and a displaced GitHub hero action. Each failed for its expected diagnostic. Browser checks also reject a planted 1000px-wide element on each phone page. Mutants never alter production files.

The full website gate retains its seven general negative controls, 51 coverage publication controls, five saved-reader controls and 28 scanner tests.

## Reproduce the browser review

Serve `website/plans` on loopback port 8786 and `website/openhra` on 8787. Start a separate headless Chrome with a disposable profile and loopback debugging port 9286. Run:

```sh
node website/docs/redesign-2026-11/review-browser.mjs
```

The script accepts `PLANS_PREVIEW`, `OPENHRA_PREVIEW` and `REDESIGN_CDP` for other loopback ports. It needs Node with built-in WebSocket support. The static sites need no new dependency or build step.

Run the checks from the repository root:

```sh
OPENPLANS_DENYLIST_FILE="<external-policy-file>" website/tools/gate.sh --full
tools/gate.sh
```

## Limits and owner follow-up

1. The local static preview blocks the existing external CAPTCHA script. Its full widget, serverless API and address reveal need a deployment smoke check. No challenge was solved or form submitted. Source and geometry preservation passed.
2. No MCP connection was attempted. The service is explicitly unreleased and unhosted in this design. Validate the final client configuration and replace development wording only after release and hosting are confirmed.
3. Public GitHub destinations came from the brief. Verify repository, issue, release and documentation access as an anonymous visitor before publication. Nothing was deployed, pushed or exported to a public checkout.

The implementation assumes OpenHRA should introduce MCP and link to the detailed OpenPlans tool and connection sections, rather than duplicate the project manual on both sites. The bootstrap command is copied from the project README and is labelled as requiring its setup steps first.
