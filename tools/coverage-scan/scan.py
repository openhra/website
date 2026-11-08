#!/usr/bin/env python3
"""Offline scanner: selected evidence → checked, deterministic static release."""
import argparse
import csv
import ctypes
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from inputs import Bundle
from model import (Invalid, LAYERS, METRIC, RATE_BUCKETS, SCOPE, STATES, VERSION,
                   blank_state, encoded, loads, percentage, require, sha, timestamp)


def table(dataset):
    lines = ['<table>', '<caption>Providers · 2026 · Snapshot from ' + dataset['as_of'][:10] +
             '. Separate validated runs. Published exchange inventory, all products including dental and SHOP. '
             'Unit: issuers with active network data.</caption>',
             '<thead><tr><th scope="col">State</th><th scope="col">Active issuers</th><th scope="col">Status and limits</th></tr></thead>', '<tbody>']
    for s, name in STATES.items():
        r = dataset["states"][s]
        n, d, p = (r[k] for k in ("numerator", "denominator", "percent_tenths"))
        value = "Unknown" if n is None else f"{n}/{d} ({p // 10}.{p % 10}%)"
        if r["status"] == "not_applicable":
            value = "Not applicable"
        label = r["status"].replace("_", " ").capitalize()
        if r["counts"]:
            c = r["counts"]
            label += f'; {c["active_partial"]} active with limits; {c["quarantined"]} quarantined; {c["unknown"]} unknown; {c["not_imported"]} not imported'
        if r["observed_at"]:
            label += "; observed " + r["observed_at"][:10]
        actor_labels = {"publisher_access": "publisher restricted access", "source_validation": "source validation", "importer_limit": "importer limitation", "undetermined": "undetermined cause"}
        for warning in r["warnings"]:
            if warning["code"] == "quarantined_sources":
                label += f'; {warning["count"]} quarantined: {actor_labels[warning["actor"]]}'
        lines.append(f'<tr><th scope="row">{name}</th><td>{value}</td><td>{label}</td></tr>')
    return ("\n".join(lines + ["</tbody>", "</table>"]) + "\n").encode()


def release(bundle, scopes, as_of, generated_at):
    require(timestamp(as_of) <= timestamp(generated_at), "timestamps: generated_at before as_of")
    files, datasets = {}, []
    for y in (2026, 2027):
        for layer in LAYERS:
            selected = sorted((s for s in scopes if s["year"] == y and s["layer"] == layer), key=lambda s: s["state"])
            input_ids = sorted({i for s in selected for i in s["input_ids"]})
            ledger = dict(schema_version=1, metric_version=METRIC, as_of=as_of, layer=layer, year=y,
                          inputs={i: bundle.input_hashes[i] for i in input_ids}, scopes={s["state"]: s for s in selected})
            ledger_bytes = encoded(ledger)
            ledger_hash = sha(ledger_bytes)
            ledger_path = "evidence/" + ledger_hash + ".json"
            files[ledger_path] = ledger_bytes
            records = {s: blank_state() for s in STATES}
            for s in selected:
                state = s["state"]
                r = records[state]
                r.update(observed_at=s["observed_at"], provenance_ids=[s["inventory"]["source_id"]])
                if layer != "premiums":
                    r.update(s["result"])
                    r["warnings"] = s["warnings"]
                    r["serving_basis"] = "active_source_sets" if s["assessed"] else "unverified"
                elif state in ("NY", "VT"):
                    r["reason_codes"] = ["supplemental_catalog"]
                else:
                    d = s["inventory"]["rows"]
                    verified = s["reconciliation"] is not None and s["serving"] is not None
                    n = d if verified else None
                    r.update(numerator=n, denominator=d, percent_tenths=percentage(n, d) if verified else None,
                             status="measured" if verified else "unknown", counts=dict.fromkeys(RATE_BUCKETS, 0),
                             reason_codes=[] if verified else ["report_absent" if s["reconciliation"] is None else "serving_evidence_absent"],
                             serving_basis="active_catalog" if verified else "unverified")
                    r["counts"]["verified" if verified else "unknown"] = d
                r["evidence"] = dict(path=ledger_path, sha256=ledger_hash, input_ids=sorted(s["input_ids"]))
            data = dict(schema_version=1, metric_version=METRIC, as_of=as_of, layer=layer, year=y,
                        unit="rate_rows" if layer == "premiums" else "issuers", scope=SCOPE, states=records)
            path = f"{layer}-{y}.json"
            content = encoded(data)
            files[path] = content
            datasets.append(dict(layer=layer, year=y, path=path, sha256=sha(content), bytes=len(content)))
            if layer == "providers" and y == 2026:
                fragment = table(data)
    datasets.sort(key=lambda d: (d["year"], d["layer"]))
    index = dict(schema_version=1, metric_version=METRIC, as_of=as_of, generated_at=generated_at, scope=SCOPE,
                 population=bundle.selection["population"], state_codes=list(STATES), datasets=datasets,
                 provenance=bundle.provenance, scanner=dict(version=VERSION, source_commit=bundle.selection["source_commit"],
                 inputs_digest=sha(encoded(dict(selection=bundle.selection, inputs=bundle.input_hashes)))))
    files["index.json"] = encoded(index)
    return files, fragment


def exchange_directories(stage, output):
    """Atomically swap two sibling directories; fail closed if unsupported."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        swap = libc.renamex_np
        swap.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = swap(os.fsencode(stage), os.fsencode(output), 2)  # RENAME_SWAP
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        swap = libc.renameat2
        swap.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = swap(-100, os.fsencode(stage), -100, os.fsencode(output), 2)  # RENAME_EXCHANGE
    else:
        raise Invalid("output: atomic directory exchange unavailable on this platform")
    require(result == 0, "output: atomic directory exchange failed; previous release preserved")


def publish(output, files):
    from check import check_release, count_diff
    output = Path(output).absolute()
    require(not output.is_symlink(), "output: symlink rejected")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".coverage-stage-", dir=output.parent))
    try:
        for name, data in files.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        check_release(stage)
        diff = count_diff(output if output.exists() else None, stage)
        if output.exists():
            exchange_directories(stage, output)
        else:
            stage.rename(output)
        return diff
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--table-output", default=Path(__file__).with_name("default-providers-2026.html"), type=Path, help="Tooling output path for the Providers/2026 HTML fragment")
    args = parser.parse_args()
    try:
        require("OPENPLANS_DATA_DIR" in os.environ, "OPENPLANS_DATA_DIR is required")
        root = Path(os.environ["OPENPLANS_DATA_DIR"]).resolve(strict=True)
        output = args.output.resolve()
        require(not output.is_relative_to(root) and not root.is_relative_to(output), "output: overlaps read-only input root")
        require(not args.table_output.resolve().is_relative_to(root), "table output: overlaps read-only input root")
        require(not args.table_output.resolve().is_relative_to(output), "table output: must be outside the static release")
        bundle = Bundle(root, loads(args.selection.read_bytes()), args.as_of)
        files, fragment = release(bundle, bundle.reconcile(), args.as_of, args.generated_at)
        diff = publish(args.output, files)
        args.table_output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.table_output.with_name("." + args.table_output.name + ".tmp")
        tmp.write_bytes(fragment)
        tmp.replace(args.table_output)
        print(diff)
        print("PASS: coverage scan (6 datasets, 51 states each)")
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, csv.Error, zipfile.BadZipFile) as exc:
        # Untrusted paths and raw parser messages must not be echoed.
        print("FAIL: " + (str(exc) if isinstance(exc, Invalid) else "malformed, unsupported or unreadable selected evidence"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
