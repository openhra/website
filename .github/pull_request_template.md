## What changed?

Describe the problem, the change and how you checked it. Include screenshots for
visible changes, with private data removed.

## Checklist

- [ ] This pull request targets `develop` and follows [AGENTS.md](https://github.com/openhra/website/blob/main/AGENTS.md) and [DEVELOPMENT.md](https://github.com/openhra/website/blob/main/DEVELOPMENT.md).
- [ ] I ran `scripts/ci.sh` and it printed `PASS`. This runs `tools/gate.sh --full` and the exporter tests with a synthetic policy. Publication still requires the external policy.
- [ ] I ran `npm run format:check` and `npm run lint`, which also run in the full gate.
- [ ] I added or updated checks where needed, including negative controls for new checks, and reported any checks I skipped.
- [ ] I added new public files to `scripts/public-paths.json` and kept private notes and installed tools out of the export.
- [ ] I kept the contact flow, security headers and protected files within the rules in the contribution guides.
- [ ] I kept the sites static, with no trackers, analytics, frameworks or site build step.
- [ ] I updated docs for changes to behavior or setup and linked public sources for factual corrections. Missing evidence stays `unknown`.
- [ ] I included no secrets, local environment files, personal health information, household data or contact addresses.
- [ ] I followed the [Code of Conduct](https://github.com/openhra/website/blob/main/CODE_OF_CONDUCT.md).
