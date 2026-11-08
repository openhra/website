# Simplification — coverage publication gate

Retained A as the single arithmetic/classification implementation and B as the
table/geometry implementation. Removed unused parsed-markup attribute storage,
an unused import and an unused conditional site-check parameter.
Cached previous state JSON once per dataset during refresh comparisons. No new
metric, schema, data correction, runtime code, dependency or scheduler was added.

Full gate remains PASS after the simplification. The runbook records the UI
checker's pinned November 8 date rather than weakening that assertion or editing
outside the lease. Later snapshot publication needs the owning UI lease to update
that expectation alongside the fallback dates.
