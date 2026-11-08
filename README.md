# OpenHRA websites

Source of the two public OpenHRA sites. Static HTML and CSS, one small serverless function each for
the contact form, no build step.

| Folder | Site | What it is |
|---|---|---|
| `openhra/` | <https://www.openhra.com/> | OpenHRA: open building blocks for health benefits |
| `plans/` | <https://plans.openhra.com/> | OpenPlans project page; the project itself lives in [openhra/openplans](https://github.com/openhra/openplans) |

The shared brand system (tokens, marks, logos, guide) lives in `plans/brand/`; start with
[`plans/brand/BRAND.md`](plans/brand/BRAND.md) and [`plans/brand/REPO-FIRST.md`](plans/brand/REPO-FIRST.md).

## Contact form

Each site's `api/contact.js` returns the contact address only after a server-side reCAPTCHA check.
The address and keys are deployment environment variables (`CONTACT_EMAIL`, `RECAPTCHA_SITE_KEY`,
`RECAPTCHA_SECRET_KEY`); they are never committed. Do not put an email address in any file.

## Preview locally

Serve a site folder with any static file server, for example `python3 -m http.server -d plans 8000`.
The contact form needs the serverless function and shows "not available" locally.

## Rules

See [AGENTS.md](AGENTS.md).
