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

## Export committed source

Develop the sites in the incubator's `website/` directory. After committing, run
`scripts/export-public.sh <staging-directory>` with `OPENPLANS_DENYLIST_FILE`
pointing to an external, nonempty regex policy. The policy is never bundled.
Python 3.9 or later, Git, Node and rsync must be available.

The destination must be outside every Git checkout and either empty or owned by
an earlier successful export. The exporter creates `.website-export-owned` as a
staging control file. Keep it out of public commits and deployment uploads. Do
not add it to an existing directory to bypass the ownership check. Stale files
are removed only from owned staging. Any nested Git metadata, hosting link,
environment file or symlink stops the export before replacement. Shared clones,
lane worktrees and ignored directories inside checkouts are rejected.

`scripts/public-paths.json` lists every public file. Add a path there when adding
public source or tooling. Design captures, private docs, work notes and installed
dependencies are excluded. `tests/reference/map.svg` holds the unchanged Census
geometry used by the offline tests. Source audits read only the selected files;
`tools/check-neutral.py <tree> --artifact` also rejects unexpected files and
directories throughout a bare artifact. Use that strict check before adding the
staging control file or after removing it from a disposable copy.

The exporter pins HEAD, reads its policy and payload from that commit, and runs
`tools/gate.sh --full` on a separate copy. It audits the assembled file set and
checks bytes and modes against the committed selection before replacing staging.
Failures leave the source and previous destination intact. Exporting does not
commit, publish or deploy. The release coordinator owns those later stages.

Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-export.py` for disposable
export tests. They exercise the real exporter and standalone full gate, including
rejection of unsafe destinations and files planted after assembly. They stay
separate from the full gate to avoid recursive export calls. The optional pair
`--import-ref <original-import-commit> --public-source <local-public-checkout>`
replays the historical import proof in a disposable clone; it does not export to
or modify that reference checkout.
