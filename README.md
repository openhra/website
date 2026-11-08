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

Run `tools/gate.sh` for the offline site checks. Use `tools/gate.sh --full` to include the negative-control self-test. To scan tracked files for case-insensitive terms, set `OPENPLANS_DENYLIST_FILE` to a newline-delimited list.
