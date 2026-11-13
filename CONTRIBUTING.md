# Contributing

Read and follow the [Code of Conduct](CODE_OF_CONDUCT.md) in issues, pull
requests and other community spaces. Report security problems as described in
[SECURITY.md](SECURITY.md), not in a public issue.

This repository holds the static sources of <https://www.openhra.com/> and
<https://plans.openhra.com/>. The OpenPlans service itself lives in
[openhra/openplans](https://github.com/openhra/openplans).

## Before you change anything

- Read [AGENTS.md](AGENTS.md) for the project rules and
  [DEVELOPMENT.md](DEVELOPMENT.md) for the pinned tools and protected files.
- Branch from `develop` and open the pull request against `develop`. Maintainers
  merge checked branches into `develop`; `main` only moves to a checked
  `develop` commit.
- Keep the sites static: no trackers, analytics, frameworks or build step.
- Put no email address in any file. The contact form reveals the address only
  after its captcha check, and its scripts must keep working.
- State only what the projects actually do. Link a public source for every
  factual correction. Missing evidence stays `unknown`.

## Checks

Run `scripts/install-tools.sh` once, then `scripts/ci.sh`. It must print `PASS`.
It runs the full site gate with a synthetic policy and the exporter tests. Run
`npm run format:check` and `npm run lint` while you work; the gate runs both.
Add a negative control for any new check, so the same check accepts the valid
case and rejects a broken copy. Say in the pull request which checks you ran and
which you skipped.

## New files

`scripts/public-paths.json` lists every public file. Add new public source or
tooling there, in sorted order. Keep private notes, captures and installed tools
out of it.
