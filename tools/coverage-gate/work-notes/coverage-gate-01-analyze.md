# Analyze — coverage publication gate

Scope: integrate the existing scanner and reader checks into the offline site
gate. Data, scanner, site presentation and legal/contact files are read-only.

Reuse: A's `check_release` owns schema, arithmetic, roster classification, hashes,
privacy and data budgets. B's static checker owns default-fragment/data parity,
Census geometry, safe DOM, CSS/reader budgets and protected-site comparisons.
Existing full-gate controls incorrectly supplied unsupported CLI arguments and
therefore did not exercise their claimed failures. The unfinished-tag parser also
missed its own HTML mutation once those arguments were removed.

Gaps: selected-input/scanner binding, prior-publication comparison, explicit
heading/title/caption year checks and end-to-end diagnostic-checked mutations.
No external research or new metric implementation is needed. No open questions;
the unattended brief authorizes sensible decisions within the stated lease.

TODO: [x] Analyze; [x] Design; [x] Implement; [x] Test; [x] Simplify.
