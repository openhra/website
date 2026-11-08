# GitHub and agents redesign

November 8, 2026. Local implementation for both OpenHRA sites.

## Direction

GitHub is the home of the work. Every main navigation and hero action opens the relevant repository or organisation. Repository cards make the contents explicit: source code, documentation, issues and releases. The release link says there is no release yet. No popularity counters or client endorsements.

MCP is the next integration being built, and the main feature to explain. Every feature block labels it **In development**. Connection examples describe planned endpoints, not a running service. The sample exchange is illustrative, contains no invented plan, person, price or coverage result, and explains what happens when evidence is missing.

## OpenHRA information architecture

1. Header: [H] wordmark, GitHub, planned MCP, principles, Contact.
2. Hero: "Open source. For health benefits." Explain individual coverage HRAs and the public-data purpose. GitHub leads. The [H] construction grid identifies the organisation's repository card.
3. Repositories: OpenPlans is the first project, with code, docs, issues and unreleased status. Show the public clone command and point to its README for setup.
4. MCP preview: "Agents need the source, too." Describe the planned read-only Model Context Protocol server, stateless Streamable HTTP and explicit unknowns. GitHub remains the primary action; the OpenPlans connection preview is secondary.
5. Principles, Contact and footer. Keep Contact and affiliation wording unchanged.

## OpenPlans information architecture

1. Header: [P] endorsed wordmark, GitHub, MCP in development, coverage, publishers and Contact.
2. Hero: "Health plan data. For apps. And agents." Explain the existing self-hosted API and planned MCP separately. Repository card lists code, docs, issues and release status. GitHub is the filled action; README is secondary.
3. Section 01: planned MCP. A short explanation sits alongside a clearly labelled sample agent exchange. Follow with the twelve planned tools, grouped by their purpose, then a connection preview. Public HTTP JSON, local HTTP URL and stdio command each carry their own development status. No executable client selector or simulated live chat.
4. Section 02: data integrity, preserving the existing unknown and provenance rules.
5. Section 03: existing native and compatibility API summary.
6. Section 04: clone and run. Copy the README bootstrap command, explain prerequisites and an empty database, and link back to setup in the README. This is source-based setup, not a released package or hosted MCP launch.
7. Sections 05 and 06: keep the Verification table and entire coverage section byte for byte, including saved table, geometry, IDs and scripts.
8. Source summary and attribution, publishers, Contact, footer. Preserve attribution, publisher, Contact and footer text verbatim.

The coverage section keeps its ordinal and position relative to Verification. Earlier sections gain agent detail without changing the map's data or behavior.

## Visual direction

Use the existing white ground, teal, system fonts and [H]/[P] paths. No new images, fonts, libraries or remote scripts. Hero typography is large but short; repository cards have a teal top rule and practical links. MCP gets a spacious two-column editorial layout, a white example panel and a ruled tool directory. Code alone uses the permitted pale code background. Section rules and generous whitespace divide the long page.

Phone content follows document order. Cards, tool groups and connection panels stack. Long identifiers and commands wrap instead of forcing a wider page. Keep the full 304px verification placeholder at 320px. Preserve focus indicators and the coverage table's independent keyboard scroll region. Existing brand tokens supply AA text contrast.

## Copy and constraints

New copy follows the unslop pass: concrete verbs, short paragraphs, sentence case, no invented metrics, no promotional claims and no decorative jargon. Legal, licence and affiliation text is excluded from the copy pass.

The owner explicitly requested GitHub naming, a tool list and setup snippets. Those choices supersede earlier repository-first guidance that avoided the hosting service's name and kept every command off the website. Detailed operational documentation remains in the repository. The supplied project README is the source for the run command; the clone command uses the owner-supplied public repository URL.

No release date is promised. The HTTP endpoint and stdio command are planned interfaces and may change before release. Public hosting and publication are separate owner actions.

## Validation

Capture both sites with headless Chrome at 1280, 390 and 320 CSS pixels. Review screenshots and iterate. Check page width, images, heading order, GitHub action order, light ground under dark OS preference, keyboard focus and the planned JSON config. Exercise coverage selection after the redesign. Save reproducible capture/check tooling and its report alongside the screenshots.

Extend the site gate with MCP status and interface checks, including isolated mutants that remove a status, mislabel an endpoint, change a planned tool or make a repository action secondary. Update the earlier coverage-only change guard to protect the inherited coverage, Verification, publishers, attribution and Contact blocks while allowing this authorised redesign. Run the full website and repository gates after merging develop.
