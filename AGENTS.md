# OpenHRA websites: agent rules

Incubated in the private repository’s `website/`; promoted by `scripts/export-public.sh`; lanes never edit the public clone.

Agent-neutral rules for Claude Code, Codex or a person. Claude reads this through `CLAUDE.md`.

- **This repository is public.** Write every file, commit message and branch name for strangers.
- **Git: develop-flow.** Branch from `develop`, merge after checks, `main` only fast-forwards to a
  checked `develop` commit. Never rewrite or force-push. Commits use the OpenHRA noreply identity.
- **No email addresses** anywhere in files. The contact flow (`contact.js`, `api/contact.js`, the
  `contact*` element ids and the two deferred script tags) must keep working.
- **Names.** Write OpenHRA and OpenPlans in visible text. Technical identifiers stay lowercase
  (repository paths, the `openplans/0.1` User-Agent, domains).
- **No private company names** in visible text, docs or SVG metadata; label links by function
  ("Repository", "Source code"). Insurer names from public data are fine.
- **Brand:** white backgrounds only for now, teal identity, [H] and [P] marks; follow
  `plans/brand/BRAND.md`.
- **No trackers, analytics, frameworks or build steps.** Keep the Content-Security-Policy in each
  `vercel.json` as strict as it is.
- **Facts only.** Copy states only what the projects actually do; no invented users, numbers or
  claims.

## Code style

Use names that explain the value or action. Keep functions focused, and use
comments to explain constraints or decisions that the code cannot express.
Prefer an early return or named helper to a nested conditional expression.

Run `npm run format:check` and `npm run lint` before committing. The full gate
runs both checks. Keep browser globals out of API handlers and Node globals out
of browser scripts. Fix lint findings in the code; inline lint exceptions fail
the gate. Preserve the generated and legal files listed in `.prettierignore`.
