# OpenHRA websites

This repository holds the two public OpenHRA sites. Both use static HTML and CSS, with one small
serverless function per site for the contact form. There is no build step.

| Folder | Site | What it is |
|---|---|---|
| `openhra/` | <https://www.openhra.com/> | OpenHRA: open building blocks for health benefits |
| `plans/` | <https://plans.openhra.com/> | OpenPlans project page; the project itself lives in [openhra/openplans](https://github.com/openhra/openplans) |

Shared brand tokens, marks, logos and the guide live in `plans/brand/`. Start with
[`plans/brand/BRAND.md`](plans/brand/BRAND.md) and [`plans/brand/REPO-FIRST.md`](plans/brand/REPO-FIRST.md).

## Contact form

Each site's `api/contact.js` returns the contact address only after a server-side reCAPTCHA check.
Deployment environment variables hold the address and keys: `CONTACT_EMAIL`, `RECAPTCHA_SITE_KEY`
and `RECAPTCHA_SECRET_KEY`. Never commit their values. Do not put an email address in any file.

## Preview locally

Serve a site folder with any static file server, for example `python3 -m http.server -d plans 8000`.
The contact form needs the serverless function and shows "not available" locally.

## Rules

See [AGENTS.md](AGENTS.md).

## Checks

Run `tools/gate.sh` for the offline site checks. Use `tools/gate.sh --full` to include the negative-control self-test. To scan all publishable files for case-insensitive policy patterns, set `OPENPLANS_DENYLIST_FILE` to a newline-delimited regex list.

## Promote committed source

Develop the sites in the private incubator's `website/` directory. Lanes never edit the public
clone directly. After committing, run `scripts/export-public.sh <destination>` with
`OPENPLANS_DENYLIST_FILE` pointing to an external publication policy. The policy is required,
nonempty and never bundled with the sites.

The exporter refuses uncommitted website changes, archives HEAD, and runs the full offline gate
on a disposable copy. It then syncs the untouched archive with deletion of stale public files.
The destination's root `.git`, `.vercel`, `.lanes` and `.env*` entries are preserved. Choose the
destination carefully: other files there are replaced. A final audit includes untracked files
and rejects private host paths, email addresses, policy matches and symlinks. Exporting changes
files only; committing and publishing the destination are separate owner actions.

Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-export.py` for export integration tests.
They use disposable Git repositories and run the real exporter, including its isolated full gate.
They are separate from `tools/gate.sh --full` to avoid recursive export/gate invocations.
The optional pair `--import-ref <original-import-commit> --public-source <local-public-checkout>`
also verifies the archived import has zero diff against public commit `a055916` in a temporary
clone. The final export includes the later incubator tooling changes as well as the original sites.
