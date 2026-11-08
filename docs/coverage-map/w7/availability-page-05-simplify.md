# Availability simplification

The pages keep one coverage.js implementation. The existing table generator now
handles the two saved default layers. No second data model or service was added.

Removed an initial selection object that was always replaced by URL/default
resolution. Removed a redundant dataset-cache update during paint because the
selected bytes must match the already validated index hash. Kept per-selection
validation and request ordering.

The existing cleanUrls hosting setting already serves /availability. Removed an
unnecessary rewrite, preserving the hosting configuration and security headers
byte for byte. The local preview implements extensionless static HTML routing so
the browser can test the actual share destination.

The copy pass shortened the introduction and measured-state summary and moved the
full-page link and share action above the controls. Legal, affiliation and contact
copy were excluded from that pass and remain unchanged.

The production selection fixture and full browser checks passed after simplification.
