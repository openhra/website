# Repository first

The public repository is the project's main page. The website explains what the project does, states its limits and points to the source. Keep code, the README, operational documentation, issues and any future releases together in the repository.

## Page hierarchy

- OpenPlans: the first navigation action and filled hero action open `https://github.com/openhra/openplans`. Put the name and purpose before the action, with the publication status beside it. The site's secondary action opens the repository README.
- OpenHRA: the first navigation action and filled hero action open `https://github.com/openhra`. The project directory leads with OpenPlans. Its name and primary action open its repository; the project website is a secondary text link.
- Home logos and the keyboard skip link remain navigation utilities. "First call to action" means the first action in the navigation menu, hero and project entry. Document order must match visual order, including on phones.
- Use descriptive labels: "Repository", "Browse repositories", "Read the README", "Project website". Avoid naming the hosting service. Open links in the same tab so visitors choose when to open another.

## What stays on the websites

Keep a short purpose statement, current development status, capabilities, known coverage limits and source provenance. State that unknown data stays unknown. Give the native and compatibility APIs, container operation and data sources a sentence each. Link each summary to the repository README. Keep the reference manual there.

On OpenPlans, keep these inherited blocks verbatim apart from the owner-approved display-name casing: the validation section (including its dated table), the publisher section (including the exact User-Agent), the NLM and GeoNames attribution, Contact and the footer notices. They are useful to someone who never visits the repository. Preserve the contact IDs, scripts and verification behaviour on both pages. Keep publisher and Contact links in the navigation; a data publisher should not have to browse source to understand a request.

OpenHRA keeps a brief explanation of individual coverage HRAs, the repository directory, working principles and Contact. It does not duplicate project setup or API documentation.

## What belongs in the repository

The README should explain the project's purpose, development status, supported coverage and first successful local run, with links to deeper documentation. Detailed endpoint lists, authentication, configuration, bootstrap commands, storage needs, source inventories and parser behaviour belong in version-controlled documentation beside the code. Keep executable examples there so reviewers can check code and instruction changes together.

This lane removes the duplicated endpoint list, command block and source table from the website. It does not publish or modify the separate source repository. Copy those details into its README/docs during repository preparation. Until then, use the existing site revision as their source.

## Links now and later

The owner supplied the public repository destination. The repository is still being prepared. Do not invent a default branch, file path or heading. Current documentation links use the repository root's `#readme` fragment, without assuming a branch or document filename. It may have no content yet. Keep the status note beside the link to explain that. The project name and main action always use the repository root without a fragment.

When documentation is public, replace each summary link with its specific verified destination:

| Site summary | Destination to confirm in the source repository |
| --- | --- |
| Two APIs, same answers | API reference document or README API heading |
| Run it yourself | Installation/quickstart document or README setup heading |
| Data sources | Source inventory and provenance document |
| Current coverage | Supported datasets and limitations document |

Follow links as an anonymous visitor before publishing them. Use the actual default branch and existing heading anchors. Prefer a stable README heading as the entry to a changing document tree. Check those destinations when documentation moves. Match link labels to their targets. Until deeper paths are verified, say "Read the README", not "API reference".

Add issue and release links once those destinations are public and useful. Do not fill their absence with placeholders or fabricated release numbers. The inherited User-Agent version identifies the fetcher. It does not establish a software release.

## Honest status

Keep "In development" and "Public repository being prepared" visible. Do not infer public availability from the source URL, validation figures or the licence label. No stars, contributor counts, downloads, versions, release badges, adoption claims or readiness claims. Retain the date attached to validation evidence; it describes that run, not a certification or a promise about future data.

When the repository becomes public and populated, remove the preparation note only after checking it. The development status remains until the project owner changes it.

## Brand inside the repository

`repo/readme-header-light.svg` reuses the shared path-drawn OpenPlans lock-up, [P] letter mark and semantic colours. The hand-authored SVG includes its own white background, title and description. There are no remote fonts or linked images. A compact header names the project and its purpose; important README content stays as searchable text below it.

`repo/social-preview.svg` is the editable 1280 × 640 source for `repo/social-preview.png`. It uses a fixed white palette, generous margins that allow cropping and the existing OpenPlans purpose line. It carries no metrics, badges or claims of availability. The PNG is a delivery asset. The site does not request it.

See `repo/README.md` for the single-image snippet and upload guidance. The proof page in `repo/index.html` shows the fixed-white header and social image. The page and artwork stay white under both OS settings; the dark header is retired.

No badges by default. If a real, useful build or licence badge is later proposed, it must reflect a verifiable current fact and have a text equivalent. Do not introduce third-party badge requests into these websites. Never use decorative badges that imply popularity, endorsement, security certification or quality.

## Verification and handoff

Keep B1's root-relative sister-site handoff: copy `brand/openhra/index.html` and `brand/openhra/style.css` to that site's root, with the shared `brand/` assets and styles. Copy `brand/openhra/favicon.svg` to its root `favicon.svg` so the organisation uses [H], while OpenPlans uses [P]. Do not alter its contact implementation or security policy. No deployment is part of this lane.

Check both pages at 1280 px and 390 px, under light and dark OS settings, with both pages staying white. Verify repository actions occur first, all local images load, nothing overflows, keyboard focus remains visible, and protected content matches the previous revision byte for byte. Check source files for address patterns without printing any matched values. Keep captures and the short evidence report outside the repository in `_reports/brand3/`.
