# Availability page design

Both pages load the same coverage.js. The compact landing section keeps the map and controls, with its full table behind a native disclosure. The full page exposes the table and methodology. Both retain a dated Premiums 2026 fallback when scripts or data loading fail.

Load and validate all six small datasets once to calculate measured-state counts and choose the default. Cache validated records for subsequent selections. URL state contains layer, year and state. Control changes replace the current history entry; popstate restores entries created by navigation. Share always links to the full page.

Extend the existing table generator for Premiums while retaining the Providers fallback page. Extend offline checks with isolated source mutations for URL restoration, sharing, confirmation, unknown values and the required full-page gate list. Browser checks exercise the real reader and native keyboard controls.

New availability.html is necessary because the landing page cannot hold the requested full table and methodology compactly. A small dependency-free DOM fixture tests selection behavior offline; the existing browser suite supplies real-browser checks and captures.

No open questions.
