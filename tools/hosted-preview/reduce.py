"""Reduce a saved /v1/data-availability answer to the hosted-preview snapshot.

The site has no build step. An operator saves the public endpoint's answer, runs
this script, formats the output with Prettier, reviews the diff and commits
plans/data/hosted-preview.json. The gate then checks that every hosted-preview
sentence on the pages agrees with it.
"""

import argparse
import json
import re
import sys

SOURCE = "https://openplans.openhra.com/v1/data-availability"
KNOWN = {"available", "unsupported", "unknown", "quarantined", "not_applicable"}


def reduce(rows, as_of):
    if not isinstance(rows, list) or not rows:
        raise ValueError("expected a non-empty list of availability rows")
    catalog, years, providers, formularies = set(), set(), set(), set()
    for row in rows:
        state, year = row.get("state"), row.get("plan_year")
        if not (isinstance(state, str) and re.fullmatch("[A-Z]{2}", state)):
            raise ValueError("row without a two-letter state")
        if not isinstance(year, int):
            raise TypeError("row without an integer plan year")
        for key in ("catalog_status", "provider_status", "formulary_status"):
            if row.get(key) not in KNOWN:
                raise ValueError(f"unexpected {key}: {row.get(key)!r}")
        if row["catalog_status"] == "available":
            catalog.add(state)
            years.add(year)
        # Anything other than unknown counts as evidence the copy must mention.
        if row["provider_status"] != "unknown":
            providers.add(state)
        if row["formulary_status"] != "unknown":
            formularies.add(state)
    return {
        "schema_version": 1,
        "source": SOURCE,
        "as_of": as_of,
        "catalog_states": sorted(catalog),
        "catalog_years": sorted(years),
        "provider_evidence_states": sorted(providers),
        "formulary_evidence_states": sorted(formularies),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("saved", help="saved JSON answer from " + SOURCE)
    parser.add_argument("--as-of", required=True, help="UTC date it was saved")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", args.as_of):
        parser.error("--as-of must be YYYY-MM-DD")
    with open(args.saved, encoding="utf-8") as handle:
        snapshot = reduce(json.load(handle), args.as_of)
    json.dump(snapshot, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
