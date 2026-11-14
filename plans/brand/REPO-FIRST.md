# Repository first

The public repository is the project's home. The website explains what the project does, states its limits and points to the source. Code, complete documentation, issues and releases belong together on GitHub.

## Page hierarchy

- OpenPlans leads its navigation and hero actions with `https://github.com/openhra/openplans`. The secondary hero action opens the README. Keep the current release link beside the main action.
- OpenHRA leads with `https://github.com/openhra`. Its first project is OpenPlans, whose name and filled action open the project repository. The project website is a secondary text link.
- Home logos and keyboard skip links remain navigation utilities. The first content action in a navigation menu, hero or project entry goes to GitHub. Document order matches visual order on phones.
- Name GitHub directly. Use descriptive actions such as "Open on GitHub", "Read the README" and "Follow on GitHub". Open links in the same tab.
- Repository cards show code, docs, issues and releases. The release entry links to the current tagged release. Update its label and destination when a new release ships.

The November 8, 2026 owner direction adds GitHub naming, MCP tools and setup snippets to the websites. It supersedes the earlier instruction to omit the hosting service's name and keep all commands off the website. The design notes are in `docs/redesign-2026-11/`. The `w10/` review records the public preview update.

## MCP is a public preview

MCP is the main feature on the project site. The live endpoint is `https://openplans.openhra.com/mcp`. Label it "Public preview" wherever MCP appears. The hosted preview serves the public catalog, quotes by age and ZIP and household quotes for Texas and Florida in 2026 and 2027. Call that the hosted preview's scope, and name the self-hosted scope next to it. Self-hosted copies load the other federal-platform states and the state exchanges. The 15 public tools are read-only and anonymous, over stateless Streamable HTTP.

List all 15 public tools, `quote_premiums` and `check_ichra_affordability` included. Every tool is open on the public endpoint, and an operator can require a token for household quotes. Provider and drug results may be `unknown`. Missing evidence never means "not covered".

Show the live URL as selectable text with a local copy button and an accessible "Copied" announcement. Include the live client configuration, HTTP headers and the stdio option for your own copy. Protocol 2026-07-28 and 2025-11-25 clients are served. Browser clients can connect through CORS from the allowed origin. Keep the detailed setup instructions in the repository.

Coverage is limited and an outside acceptance run is pending. OpenPlans v0.4.6 is available. The public MCP endpoint remains a Public preview. The agent exchange remains an illustrative example, with no live request or invented result. Never invent a price, coverage result, user, client endorsement or usage count.

OpenHRA introduces the public preview, shows the endpoint and its limits, and links to OpenPlans for the full tool list and connection details.

## What stays on the websites

Keep the purpose, current status, public sources, coverage limits and unknown-data rule. Give the native and compatibility APIs a short explanation. Show the public clone command and a run command copied from the README, with prerequisites and a link to the complete setup steps. A source bootstrap command does not establish a release or hosted MCP availability.

OpenPlans preserves the Verification section and dated table, the coverage section and saved data, the publisher section and exact User-Agent, NLM and GeoNames attribution, Contact and footer notices. Preserve the contact IDs, scripts, handlers and verification behavior on both pages. Publisher and Contact links stay in navigation.

OpenHRA keeps an explanation of individual coverage HRAs, the repository directory, working principles and Contact. Avoid duplicating the full project manual.

## Repository documentation

The README owns the first successful local run, supported data and links to operational guides. Authentication, configuration, bootstrap options, storage needs, parser behavior and source inventories stay beside the code. Check website command excerpts when the README changes.

The owner supplied the public repository destinations. Before publication, verify links as an anonymous visitor, including issues, releases and any deeper documentation URLs. Do not infer a release from a User-Agent version, licence label or successful validation run.

## Brand assets

`repo/readme-header-light.svg` uses the [P] lock-up and white ground. Important README content stays as searchable text below it. `repo/social-preview.svg` is the editable source for its PNG export. Neither asset has metrics, badges or availability claims. No remote fonts or images.

See `repo/README.md` for the image snippet and upload guidance. The proof page in `repo/index.html` shows the exports. Assets stay white under both OS settings. Do not introduce decorative popularity or certification badges.

## Site copies and checks

The deployed page sources are `plans/index.html` and `openhra/index.html`. Keep shared tokens, `brand/site.css` and `mcp-copy.js` aligned between the sites. The nested `plans/brand/openhra/` files are handoff copies of the organisation page and styles, with its [H] favicon. They are not a third project site.

Review both pages at desktop and phone widths, including 320px. Check repository action order, images, links, headings, visible focus, no horizontal page overflow and white ground under dark OS preference. Preserve protected content byte for byte. The November redesign captures and browser report live in `docs/redesign-2026-11/`. Publication remains a separate owner action.
