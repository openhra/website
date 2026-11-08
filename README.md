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

Run `tools/gate.sh` for the offline site checks. The full gate includes the
negative-control suites and requires `OPENPLANS_DENYLIST_FILE` to point to an
external, nonempty regex policy. No policy is bundled with the site.

Run `scripts/ci.sh` for public contributor checks. It creates a temporary synthetic
policy, runs the unchanged `tools/gate.sh --full`, then runs the disposable
exporter suite with `scripts/test-export.py --public`. It ignores any inherited
policy and removes its fixture on exit. A public CI pass proves the checks run;
it does not approve publication. The publication gate and exporter still require
an external policy. Private release validation must supply the private policy.

The extracted-root workflow at `.github/workflows/ci.yml` runs on pull requests,
pushes to `develop`, `main` and `release/**`, and manual dispatch. Required checks
are `website-linux`, `website-macos`, `website-python39` and `website-required`.
The final job runs even if a dependency fails or skips, and accepts only a
successful result for every required platform job. Configure branch protection
to require these checks. Hosted results belong to the tested commit.

`.node-version` and `.python-version` pin the primary runtimes. Python 3.9.25 is
also tested on Linux to retain compatibility with existing tooling. The workflow
pins action revisions and uses hosted runners with read-only repository access.
It needs Git and rsync, with no npm or Python package install and no site build.
It uses no deployment credentials and does not deploy.

The workflow uses JSON syntax, which YAML accepts. This lets the standard-library
checker `python3 scripts/check-ci.py --selftest` verify commands, runtime inputs,
action pins and required jobs without installing a YAML parser. Its negative
controls reject missing jobs and failed, skipped, pending or canceled results.

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

Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-export.py --public` for disposable
export tests. They exercise the real exporter and standalone full gate, including
rejection of unsafe destinations and files planted after assembly. They stay
separate from the full gate to avoid recursive export calls. Without `--public`, the optional pair
`--import-ref <original-import-commit> --public-source <local-public-checkout>`
replays the historical import proof in a disposable clone; it does not export to
or modify that reference checkout.
