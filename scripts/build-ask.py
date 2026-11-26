#!/usr/bin/env python3
"""Build plans/data/ask/ask.json from a /v1/data-availability body (stdlib only).

Usage: build-ask.py BODY.json OUT.json --fetched-at ISO_TIME --source-url URL [--synthetic]
       build-ask.py --empty OUT.json

Refresh at release: curl -s https://openplans.openhra.com/v1/data-availability -o body.json, then
run the first form with the fetch time (UTC) and that URL.

Each row of the body counts once per family. Status buckets:
  answered     the family status is "available" (or "complete" for drug sources)
  partial      the family status is "partial"
  unsupported  the family status is "unsupported": not in the public source
  unknown      every other value, kept by raw value in `statuses` and by reason code in `reasons`
"""

import argparse
import json
import sys
from pathlib import Path

# (id, label, status key, reason path)
FAMILIES = (
    ("premiums", "Premiums", "premium_status", ("premium_reason",)),
    ("benefits", "Benefits and plan catalog", "catalog_status", ()),
    ("drugs", "Drugs", "drug_status", ("drug_coverage", "reason")),
    ("providers", "Providers", "provider_status", ("provider_coverage", "reason")),
)
ANSWERED = {"available", "complete"}
# Words for the values the code produces. A value not listed here is shown as its code.
STATUS_WORDS = {
    "unknown": "Unknown",
    "not_yet_verified": "Unknown, not yet verified",
    "unavailable": "Source unavailable",
    "stale": "Evidence out of date",
    "conflicted": "Sources disagree",
    "failed": "Source could not be read",
    "access_denied": "Publisher restricts access",
}
REASON_WORDS = {
    "source_set_not_validated": "Source files not yet validated",
    "source_set_not_active": "Validated source files are not the active set",
    "source_set_not_available": "No source files found",
    "discovery_incomplete": "Some source files could not be read",
    "source_access_denied": "Publisher restricts access",
    "unresolved_rating_area": "Rating areas could not be resolved",
}


def reason_of(row, path):
    value = row
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, str) and value else None


def build(body, fetched_at, source_url, synthetic):
    cells = {}
    for row in body:
        for fid, _label, skey, rpath in FAMILIES:
            cell = cells.setdefault(
                (str(row["state"]), int(row["plan_year"]), fid),
                {
                    "answered": 0,
                    "partial": 0,
                    "unsupported": 0,
                    "unknown": 0,
                    "statuses": {},
                    "reasons": {},
                },
            )
            status = row.get(skey)
            status = status if isinstance(status, str) and status else "unknown"
            cell["statuses"][status] = cell["statuses"].get(status, 0) + 1
            if status in ANSWERED:
                cell["answered"] += 1
                continue
            cell[status if status in ("partial", "unsupported") else "unknown"] += 1
            code = reason_of(row, rpath)
            if code:
                cell["reasons"][code] = cell["reasons"].get(code, 0) + 1
    rows = [
        {"state": s, "year": y, "family": f, **cells[(s, y, f)]}
        for (s, y, f) in sorted(
            cells, key=lambda k: (k[0], k[1], [x[0] for x in FAMILIES].index(k[2]))
        )
    ]
    seen_status = {k for r in rows for k in r["statuses"]}
    seen_reason = {k for r in rows for k in r["reasons"]}
    return {
        "schema_version": 1,
        "source": "data-availability",
        "fetched_at": fetched_at,
        "source_url": source_url,
        "synthetic": synthetic,
        "families": [{"id": f[0], "label": f[1]} for f in FAMILIES],
        "status_words": {
            k: STATUS_WORDS[k] for k in sorted(seen_status) if k in STATUS_WORDS
        },
        "reason_words": {
            k: REASON_WORDS[k] for k in sorted(seen_reason) if k in REASON_WORDS
        },
        "rows": rows,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("body", nargs="?")
    p.add_argument("out")
    p.add_argument("--fetched-at")
    p.add_argument("--source-url")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--empty", action="store_true")
    a = p.parse_args()
    if a.empty:
        a.out, a.body = a.out if not a.body else a.body, None
        data = build([], None, None, False)
    else:
        if not a.body or not a.fetched_at or not a.source_url:
            p.error("body, --fetched-at and --source-url are required")
        body = json.loads(Path(a.body).read_text(encoding="utf-8"))
        if not isinstance(body, list):
            sys.exit("body must be the /v1/data-availability array")
        data = build(body, a.fetched_at, a.source_url, a.synthetic)
    Path(a.out).write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
