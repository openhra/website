#!/usr/bin/env python3
"""Dependency-free structural and semantic validation of a coverage release."""

import argparse
import re
import sys
from pathlib import Path, PurePosixPath

from model import (
    ACTORS,
    ISSUER_BUCKETS,
    LAYERS,
    RATE_BUCKETS,
    STATES,
    Invalid,
    encoded,
    integer,
    issuer_result,
    loads,
    percentage,
    public_url,
    require,
    safe_text,
    sha,
    timestamp,
)


def validate(value, schema, definitions, at="value"):
    """The deliberately small, closed JSON Schema vocabulary used by schema.json."""
    supported = {
        "$ref",
        "type",
        "enum",
        "anyOf",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "uniqueItems",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "format",
    }
    require(set(schema) <= supported, "schema: unsupported keyword")
    if "$ref" in schema:
        ref = schema["$ref"]
        require(
            ref.startswith("#/$defs/") and ref[8:] in definitions,
            "schema: unsupported reference",
        )
        return validate(value, definitions[ref[8:]], definitions, at)
    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                validate(value, option, definitions, at)
                return
            except Invalid as exc:
                errors.append(str(exc))
        raise Invalid(
            at + ": no supported schema alternative (" + "; ".join(errors) + ")"
        )
    if "enum" in schema:
        require(
            any(type(value) is type(v) and value == v for v in schema["enum"]),
            at + ": unsupported enum value",
        )
    if "type" in schema:
        types = {
            "object": dict,
            "array": list,
            "integer": int,
            "string": str,
            "boolean": bool,
            "null": type(None),
        }
        require(schema["type"] in types, "schema: unsupported type")
        require(type(value) is types[schema["type"]], at + ": wrong type")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        require(
            set(schema.get("required", [])) <= set(value),
            at + ": missing required field",
        )
        additional = schema.get("additionalProperties", False)
        for key, v in value.items():
            if key in props:
                validate(v, props[key], definitions, at + "." + key)
            else:
                require(isinstance(additional, dict), at + ": unexpected field " + key)
                validate(v, additional, definitions, at + "." + key)
    elif isinstance(value, list):
        if schema.get("uniqueItems"):
            require(
                len({encoded(v) for v in value}) == len(value),
                at + ": duplicate array item",
            )
        for v in value:
            validate(v, schema["items"], definitions, at + "[]")
    elif isinstance(value, str):
        require(
            len(value) >= schema.get("minLength", 0)
            and len(value) <= schema.get("maxLength", sys.maxsize),
            at + ": string length",
        )
        if "pattern" in schema:
            require(
                re.fullmatch(schema["pattern"], value),
                at + ": unsupported string format",
            )
        if "format" in schema:
            require(schema["format"] == "utc", "schema: unsupported format")
            timestamp(value)
    elif type(value) is int:
        require(
            schema.get("minimum", -sys.maxsize)
            <= value
            <= schema.get("maximum", sys.maxsize),
            at + ": integer bounds",
        )


def schemas():
    source = loads(Path(__file__).with_name("schema.json").read_bytes())
    require(
        set(source) == {"$schema", "title", "description", "$defs", "anyOf"}
        and source["$schema"] == "https://json-schema.org/draft/2020-12/schema",
        "schema: malformed or unsupported definition",
    )
    return source["$defs"]


def check_record(r, layer, as_of):
    n, d, p = (r[k] for k in ("numerator", "denominator", "percent_tenths"))
    c = r["counts"]
    if r["observed_at"] is not None:
        require(
            timestamp(r["observed_at"]) <= as_of, "record: observation later than as_of"
        )
    if d is None:
        require(
            n is None
            and p is None
            and c is None
            and r["status"] == "unknown"
            and r["reason_codes"],
            "record: unknown denominator semantics",
        )
        require(
            r["serving_basis"] == "unverified",
            "record: unknown denominator serving basis",
        )
        return
    require(
        r["provenance_ids"] and r["evidence"] and r["observed_at"],
        "lineage: known denominator requires provenance, ledger and observation",
    )
    buckets = RATE_BUCKETS if layer == "premiums" else ISSUER_BUCKETS
    require(
        c is not None and set(c) == set(buckets) and sum(c.values()) == d,
        "buckets: partition must sum to denominator",
    )
    if d == 0:
        require(
            r["status"] == "not_applicable"
            and n is None
            and p is None
            and r["reason_codes"] == ["inventory_empty"],
            "record: zero denominator requires proven empty inventory",
        )
    elif n is None:
        require(
            p is None
            and r["status"] == "unknown"
            and c["unknown"] == d
            and r["reason_codes"],
            "record: absent evidence must be unknown with all units unassessed",
        )
    else:
        require(
            p == percentage(n, d), "percentage: exact integer half-up rounding mismatch"
        )
        require(
            n
            == (
                c["verified"]
                if layer == "premiums"
                else c["active_complete"] + c["active_partial"]
            ),
            "buckets: numerator is active/verified units only",
        )
        expected = "quarantined" if c["quarantined"] == d else "measured"
        require(
            r["status"] == expected and not r["reason_codes"],
            "record: quarantine/measured status mismatch",
        )
        require(
            r["serving_basis"]
            == ("active_catalog" if layer == "premiums" else "active_source_sets"),
            "record: measured serving basis mismatch",
        )


def check_inventory(inv, index, state, year):
    sid = inv["source_id"]
    require(sid in index["provenance"], "lineage: unknown public source")
    require(
        index["provenance"][sid]["vintage"] == year,
        "lineage: public source year mismatch",
    )
    require(
        inv["issuers"] == sorted(set(inv["issuers"])),
        "lineage: duplicate/unsorted public issuer roster",
    )
    require(
        inv["rows"] > 0 and inv["base_plans"] > 0 and inv["issuers"],
        "inventory: empty source cannot establish positive catalog",
    )
    require(
        not inv["member"].startswith("/")
        and ".." not in PurePosixPath(inv["member"]).parts
        and inv["member"].lower().endswith(".csv"),
        "lineage: invalid public member",
    )


def check_scope(scope, record, index, layer, year, state, ledger):
    require(
        scope["state"] == state and scope["year"] == year and scope["layer"] == layer,
        "lineage: state/year/layer mismatch",
    )
    require(
        scope["observed_at"] == record["observed_at"], "lineage: observation mismatch"
    )
    inv = scope["inventory"]
    check_inventory(inv, index, state, year)
    require(
        record["provenance_ids"] == [inv["source_id"]], "lineage: provenance mismatch"
    )
    require(
        scope["input_ids"] == sorted(set(scope["input_ids"]))
        and set(scope["input_ids"]) <= set(ledger["inputs"]),
        "lineage: missing selected input hashes",
    )
    require(
        inv["source_id"] in scope["input_ids"]
        and ledger["inputs"][inv["source_id"]]
        == index["provenance"][inv["source_id"]]["sha256"],
        "lineage: public archive hash mismatch",
    )
    if layer != "premiums":
        roster = scope["roster"]
        require(
            [r["issuer_id"] for r in roster] == inv["issuers"],
            "roster: public denominator contains withheld or duplicate issuer",
        )
        for r in roster:
            require(
                timestamp(r["observed_at"]) <= timestamp(scope["observed_at"]),
                "issuer: observation later than scope",
            )
            actor = {
                "active_validated": "undetermined",
                "attempt_failed": "undetermined",
                "unassessed": "undetermined",
                "publisher_denied": "publisher_access",
                "adapter_unavailable": "importer_limit",
                "budget_limit": "importer_limit",
                "source_invalid": "source_validation",
            }[r["reason_code"]]
            require(
                r["actor"] == actor,
                "issuer: quarantine actor conflicts with observation; adapter failure is not publisher denial",
            )
            active = r["classification"] in ("active_complete", "active_partial")
            require(
                r["active_pointer"] is active and r["positive_association"] is active,
                "issuer: ACTIVE pointer and positive association required; quarantined is not active",
            )
            if active:
                require(
                    r["validation_status"] == "ACTIVE"
                    and r["snapshot_sha256"]
                    and r["association_state"] == state
                    and r["association_year"] == year,
                    "issuer: positive association state/year mismatch",
                )
                require(
                    r["reason_code"] == "active_validated",
                    "issuer: ACTIVE source requires validated-source observation",
                )
            else:
                require(
                    r["association_state"] is None and r["association_year"] is None,
                    "issuer: non-active association forbidden",
                )
                if r["classification"] == "quarantined":
                    require(
                        r["validation_status"] == "QUARANTINED"
                        and r["snapshot_sha256"],
                        "issuer: quarantine validation required",
                    )
                    require(
                        r["reason_code"] not in ("unassessed", "active_validated"),
                        "issuer: quarantine reason contradicts validation",
                    )
                elif r["classification"] == "unknown":
                    require(
                        r["validation_status"] is None
                        and r["snapshot_sha256"] is None
                        and r["reason_code"] == "unassessed",
                        "issuer: unknown unit must remain unassessed",
                    )
                else:
                    raise Invalid(
                        "issuer: not_imported requires an audited valid-source adapter; unsupported in v1"
                    )
        expected = issuer_result(roster, scope["assessed"])
        require(
            expected == scope["result"]
            and all(record[k] == v for k, v in expected.items()),
            "issuer: roster/buckets/result mismatch",
        )
        require(
            record["warnings"] == scope["warnings"], "issuer: warning lineage mismatch"
        )
        quarantines = {
            a: sum(
                r["classification"] == "quarantined" and r["actor"] == a for r in roster
            )
            for a in ACTORS
        }
        for actor, n in quarantines.items():
            require(
                sum(
                    w["count"]
                    for w in record["warnings"]
                    if w["code"] == "quarantined_sources" and w["actor"] == actor
                )
                == n,
                "issuer: quarantine actor count mismatch",
            )
        require(
            sum(
                w["count"]
                for w in record["warnings"]
                if w["code"] == "partial_active_sources"
            )
            == expected["counts"]["active_partial"],
            "issuer: partial-active warning mismatch",
        )
    else:
        check_inventory(scope["plan_inventory"], index, state, year)
        require(
            inv["issuers"] == scope["plan_inventory"]["issuers"],
            "premium: rate/plan roster mismatch",
        )
        rec, serving = scope["reconciliation"], scope["serving"]
        if rec is not None:
            require(
                rec["verified"] == inv["rows"]
                and rec["report_id"] in scope["input_ids"],
                "premium: reconciliation source count/hash lineage mismatch",
            )
        if serving is not None:
            require(
                rec
                and serving["catalog_sha256"] == rec["catalog_sha256"]
                and serving["report_id"] in scope["input_ids"],
                "premium: selected serving catalog mismatch",
            )
            require(
                state not in ("NY", "VT"),
                "premium: supplemental NY/VT rows cannot be promoted",
            )
            if state == "OR":
                require(
                    "/marketplace-puf/" in index["provenance"][inv["source_id"]]["url"],
                    "premium: OR SHOP cannot replace federal catalog",
                )
        if record["numerator"] is not None:
            require(
                rec is not None
                and serving is not None
                and record["numerator"] == inv["rows"],
                "premium: measured rows require independent reconciliation and ACTIVE serving evidence",
            )
        elif record["denominator"] is not None:
            require(
                record["denominator"] == inv["rows"] and not serving,
                "premium: unassessed denominator mismatch",
            )
        else:
            require(
                state in ("NY", "VT")
                and record["reason_codes"] == ["supplemental_catalog"],
                "premium: unexplained withheld denominator",
            )


def check_release(root):
    root = Path(root).resolve(strict=True)
    definitions = schemas()
    files = [p for p in root.rglob("*") if p.is_file()]
    require(
        not any(p.is_symlink() for p in root.rglob("*")), "release: symlink rejected"
    )
    require(
        sum(p.stat().st_size for p in files) <= 2 * 1024**2,
        "budget: release exceeds 2 MiB",
    )

    def read(name, kind, budget):
        path = root / name
        require(
            path.is_file() and path.resolve().is_relative_to(root),
            "release: missing or escaped file",
        )
        data = path.read_bytes()
        require(len(data) <= budget, "budget: " + kind + " exceeded")
        value = loads(data)
        safe_text(value)
        validate(value, definitions[kind], definitions, kind)
        require(
            data == encoded(value),
            "serialization: expected canonical UTF-8, sorted keys and LF",
        )
        return value, data

    index, _ = read("index.json", "index", 16 * 1024)
    require(
        index["state_codes"] == list(STATES),
        "index: exact sorted 51-state set required",
    )
    as_of = timestamp(index["as_of"])
    require(
        as_of <= timestamp(index["generated_at"]), "index: generated_at before as_of"
    )
    require(
        index["population"] == "separate_validated_runs",
        "index: unsupported serving snapshot claim",
    )
    for sid, p in index["provenance"].items():
        require(
            re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", sid), "provenance: unsafe source id"
        )
        public_url(p["url"])
        require(
            timestamp(p["retrieved_at"]) <= as_of, "provenance: retrieval after cutoff"
        )
    expected = {(layer, year) for layer in LAYERS for year in (2026, 2027)}
    require(
        len(index["datasets"]) == 6
        and {(d["layer"], d["year"]) for d in index["datasets"]} == expected,
        "index: exactly six unique layer/year datasets required",
    )
    advertised = {"index.json"}
    ledgers = {}
    referenced_scopes = {}
    for d in index["datasets"]:
        layer, year = d["layer"], d["year"]
        require(
            d["path"] == f"{layer}-{year}.json", "index: dataset path scope mismatch"
        )
        dataset, raw = read(d["path"], "dataset", 64 * 1024)
        advertised.add(d["path"])
        require(
            len(raw) == d["bytes"] and sha(raw) == d["sha256"],
            "hash: dataset digest/bytes mismatch",
        )
        require(
            dataset["layer"] == layer
            and dataset["year"] == year
            and dataset["as_of"] == index["as_of"],
            "dataset: scope or timestamp mismatch",
        )
        require(
            dataset["unit"] == ("rate_rows" if layer == "premiums" else "issuers"),
            "dataset: wrong metric unit",
        )
        for state, record in dataset["states"].items():
            check_record(record, layer, as_of)
            require(
                set(record["provenance_ids"]) <= set(index["provenance"]),
                "lineage: missing provenance id",
            )
            evidence = record["evidence"]
            if evidence is None:
                require(
                    record["denominator"] is None
                    and record["observed_at"] is None
                    and not record["provenance_ids"],
                    "lineage: unexplained evidence omission",
                )
                continue
            path = evidence["path"]
            if path not in ledgers:
                ledger, data = read(path, "ledger", 256 * 1024)
                require(
                    sha(data) == evidence["sha256"]
                    and path == "evidence/" + sha(data) + ".json",
                    "hash: evidence ledger content address mismatch",
                )
                ledgers[path] = ledger
            ledger = ledgers[path]
            advertised.add(path)
            require(
                ledger["layer"] == layer
                and ledger["year"] == year
                and ledger["as_of"] == index["as_of"],
                "lineage: ledger scope/timestamp mismatch",
            )
            require(state in ledger["scopes"], "lineage: state ledger absent")
            referenced_scopes.setdefault(path, set()).add(state)
            scope = ledger["scopes"][state]
            require(
                evidence["input_ids"] == scope["input_ids"],
                "lineage: selected input ids mismatch",
            )
            check_scope(scope, record, index, layer, year, state, ledger)
    for path, states in referenced_scopes.items():
        ledger = ledgers[path]
        require(
            set(ledger["scopes"]) == states,
            "lineage: unreferenced or withheld scope in ledger",
        )
        require(
            set(ledger["inputs"])
            == {i for s in ledger["scopes"].values() for i in s["input_ids"]},
            "lineage: unexplained selected input hashes",
        )
    # Empty ledgers establish the absence of selected evidence for a layer/year.
    for p in files:
        name = p.relative_to(root).as_posix()
        if name not in advertised:
            require(
                re.fullmatch(r"evidence/[0-9a-f]{64}\.json", name),
                "release: unadvertised file",
            )
            ledger, data = read(name, "ledger", 256 * 1024)
            require(
                not ledger["scopes"]
                and not ledger["inputs"]
                and name == "evidence/" + sha(data) + ".json"
                and ledger["as_of"] == index["as_of"],
                "release: unreferenced nonempty ledger",
            )
    return index


def count_diff(previous, current):
    lines = []
    for year in (2026, 2027):
        for layer in LAYERS:
            name = f"{layer}-{year}.json"
            new = loads((Path(current) / name).read_bytes())["states"]
            old_path = Path(previous) / name if previous else None
            if old_path is not None:
                require(
                    not old_path.is_symlink(),
                    "diff: symlink in previous release rejected",
                )
            old = (
                loads(old_path.read_bytes())["states"]
                if old_path and old_path.is_file()
                else {}
            )
            changed = [
                s
                for s in STATES
                if any(
                    new[s][k] != old.get(s, {}).get(k)
                    for k in ("numerator", "denominator", "status", "counts")
                )
            ]
            measured = sum(r["status"] == "measured" for r in new.values())
            lines.append(
                f"{layer}/{year}: {measured} measured; {len(changed)} count/status changes"
                + (" (" + ",".join(changed) + ")" if changed else "")
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    try:
        check_release(args.release)
        if args.previous:
            print(count_diff(args.previous, args.release))
        print(
            "PASS: coverage schema, 6 datasets, 51 states, arithmetic, lineage, privacy and budgets"
        )
    except (Invalid, OSError, KeyError, TypeError) as exc:
        print(
            "FAIL: "
            + (
                str(exc)
                if isinstance(exc, Invalid)
                else "malformed or unreadable release"
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
