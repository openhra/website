"""Public coverage contract and deterministic value helpers (standard library only)."""

import datetime as dt
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit

VERSION = "1.0.0"
METRIC = "exchange-source-availability-v1"
SCOPE = "published_exchange_inventory_all_products"
STATES = dict(
    zip(
        [
            "AK",
            "AL",
            "AR",
            "AZ",
            "CA",
            "CO",
            "CT",
            "DC",
            "DE",
            "FL",
            "GA",
            "HI",
            "IA",
            "ID",
            "IL",
            "IN",
            "KS",
            "KY",
            "LA",
            "MA",
            "MD",
            "ME",
            "MI",
            "MN",
            "MO",
            "MS",
            "MT",
            "NC",
            "ND",
            "NE",
            "NH",
            "NJ",
            "NM",
            "NV",
            "NY",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VA",
            "VT",
            "WA",
            "WI",
            "WV",
            "WY",
        ],
        [
            "Alaska",
            "Alabama",
            "Arkansas",
            "Arizona",
            "California",
            "Colorado",
            "Connecticut",
            "District of Columbia",
            "Delaware",
            "Florida",
            "Georgia",
            "Hawaii",
            "Iowa",
            "Idaho",
            "Illinois",
            "Indiana",
            "Kansas",
            "Kentucky",
            "Louisiana",
            "Massachusetts",
            "Maryland",
            "Maine",
            "Michigan",
            "Minnesota",
            "Missouri",
            "Mississippi",
            "Montana",
            "North Carolina",
            "North Dakota",
            "Nebraska",
            "New Hampshire",
            "New Jersey",
            "New Mexico",
            "Nevada",
            "New York",
            "Ohio",
            "Oklahoma",
            "Oregon",
            "Pennsylvania",
            "Rhode Island",
            "South Carolina",
            "South Dakota",
            "Tennessee",
            "Texas",
            "Utah",
            "Virginia",
            "Vermont",
            "Washington",
            "Wisconsin",
            "West Virginia",
            "Wyoming",
        ],
    )
)
LAYERS = ("premiums", "providers", "prescriptions")
ISSUER_BUCKETS = (
    "active_complete",
    "active_partial",
    "quarantined",
    "unknown",
    "not_imported",
)
RATE_BUCKETS = ("verified", "quarantined", "unknown", "not_imported")
REASONS = (
    "report_absent",
    "denominator_unverified",
    "supplemental_catalog",
    "source_not_published",
    "catalog_adapter_gap",
    "serving_evidence_absent",
    "inventory_empty",
)
ACTORS = ("publisher_access", "source_validation", "importer_limit", "undetermined")
WARNINGS = ("quarantined_sources", "failed_refresh", "partial_active_sources")


class Invalid(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Invalid(reason)


def integer(value, label="count"):
    require(
        type(value) is int and 0 <= value <= 9007199254740991,
        label + ": expected nonnegative safe integer",
    )
    return value


def timestamp(value):
    require(
        isinstance(value, str)
        and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value),
        "timestamp: expected ISO UTC",
    )
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Invalid("timestamp: invalid date") from None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "JSON: duplicate object key")
        result[key] = value
    return result


def loads(data):
    try:
        return json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                Invalid("JSON: nonfinite number")
            ),
        )
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, Invalid):
            raise
        raise Invalid("JSON: malformed or truncated input") from None


def percentage(n, d):
    integer(n)
    integer(d)
    require(
        d > 0 and n <= d,
        "percentage: require 0 <= numerator <= denominator and positive denominator",
    )
    return (2000 * n + d) // (2 * d)


def public_url(value):
    require(isinstance(value, str), "source URL: expected string")
    try:
        p = urlsplit(value)
        port = p.port
    except ValueError:
        raise Invalid("source URL: malformed host or port") from None
    require(
        p.scheme == "https"
        and p.hostname
        and not p.username
        and not p.password
        and not p.query
        and not p.fragment
        and not port,
        "source URL: require public HTTPS without credentials, query or fragment",
    )
    require(
        p.hostname not in ("localhost",)
        and "." in p.hostname
        and not p.hostname.endswith((".local", ".internal")),
        "source URL: private host",
    )
    try:
        ipaddress.ip_address(p.hostname)
    except ValueError:
        pass
    else:
        raise Invalid("source URL: literal IP host is unsupported")
    require(not re.search(r"[%@\s\\]", value), "source URL: unsafe encoding")
    return value


def safe_text(value):
    """Reject private material even when injected into an otherwise valid field."""
    if isinstance(value, dict):
        for k, v in value.items():
            safe_text(k)
            safe_text(v)
    elif isinstance(value, list):
        for v in value:
            safe_text(v)
    elif isinstance(value, str):
        require(
            not (
                value.startswith("/")
                or re.search(
                    r"(?:^|\s)/(?:private|var|opt|etc|mnt|Volumes|Users|home|tmp)/",
                    value,
                )
            ),
            "privacy: private absolute path",
        )
        require(
            not re.search(
                r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}|(?:/(?:Volumes|Users|home|tmp)/|[A-Za-z]:\\)|(?:postgres(?:ql)?|mysql|mongodb)://|(?:api[_-]?key|password|secret|token)=",
                value,
                re.IGNORECASE,
            ),
            "privacy: private path, address or secret",
        )


def blank_state(reason="denominator_unverified"):
    return {
        "numerator": None,
        "denominator": None,
        "percent_tenths": None,
        "status": "unknown",
        "counts": None,
        "reason_codes": [reason],
        "warnings": [],
        "observed_at": None,
        "provenance_ids": [],
        "evidence": None,
        "serving_basis": "unverified",
    }


def issuer_result(roster, assessed):
    counts = dict.fromkeys(ISSUER_BUCKETS, 0)
    for row in roster:
        require(row["classification"] in counts, "issuer: unsupported classification")
        counts[row["classification"]] += 1
    d = len(roster)
    if not d:
        return {
            "numerator": None,
            "denominator": 0,
            "percent_tenths": None,
            "status": "not_applicable",
            "counts": counts,
            "reason_codes": ["inventory_empty"],
        }
    n = counts["active_complete"] + counts["active_partial"] if assessed else None
    status = (
        "unknown"
        if n is None
        else ("quarantined" if counts["quarantined"] == d else "measured")
    )
    return {
        "numerator": n,
        "denominator": d,
        "percent_tenths": percentage(n, d) if n is not None else None,
        "status": status,
        "counts": counts,
        "reason_codes": [] if assessed else ["report_absent"],
    }
