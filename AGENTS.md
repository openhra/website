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
