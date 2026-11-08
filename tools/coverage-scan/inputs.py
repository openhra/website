"""Explicit input selection and read-only public-file/report reconciliation.

Legacy reports are read privately and projected onto a small safe ledger. No raw
records, error strings, database metadata or paths cross this module's boundary.
"""
import csv
import hashlib
import io
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from model import (STATES, encoded, integer, issuer_result, loads,
                   public_url, require, sha, timestamp)


def relative_file(root, name):
    require(isinstance(name, str) and name and "\\" not in name, "input path: expected relative POSIX path")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and ":" not in name, "input path: escape rejected")
    target = (root / name).resolve()
    require(target.is_relative_to(root) and target.is_file(), "input path: missing file or symlink escape")
    return target


def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def exact_keys(obj, keys, label):
    require(isinstance(obj, dict) and set(obj) == set(keys.split()), label + ": unexpected or missing fields")


def csv_key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def inventory(path, member, year, kind):
    """Hash every member byte; retain public row identity digests, never row data."""
    require(kind in ("plans", "rates"), "inventory: unsupported member kind")
    require(isinstance(member, str) and not PurePosixPath(member).is_absolute() and ".." not in PurePosixPath(member).parts and member.lower().endswith(".csv"), "inventory: unsafe CSV member")
    by_state = {}
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), "inventory: duplicate archive member")
        require(member in archive.namelist(), "inventory: selected member absent")
        info = archive.getinfo(member)
        require(info.file_size <= 4 * 1024**3, "inventory: member budget exceeded")
        digest = hashlib.sha256()
        with archive.open(member) as raw:
            for chunk in iter(lambda: raw.read(1024 * 1024), b""):
                digest.update(chunk)
        with archive.open(member) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), strict=True)
            require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "inventory: duplicate or absent CSV header")
            keys = {csv_key(k): k for k in reader.fieldnames}
            require(len(keys) == len(reader.fieldnames), "inventory: ambiguous normalized header")
            require(all(k in keys for k in ("businessyear", "statecode", "issuerid")), "inventory: required scope columns absent")
            plan_key = next((keys[k] for k in ("standardcomponentid", "planid") if k in keys), None)
            require(plan_key, "inventory: plan row identity absent")
            for line, row in enumerate(reader, 2):
                require(None not in row and all(v is not None for v in row.values()), "inventory: malformed/truncated CSV row")
                y, state, issuer = (row[keys[k]].strip() for k in ("businessyear", "statecode", "issuerid"))
                require(y == str(year), "inventory: source year membership mismatch")
                require(state in STATES and re.fullmatch(r"\d{5}", issuer), "inventory: invalid state or issuer")
                plan = row[plan_key].strip()
                require(re.fullmatch(r"\d{5}[A-Z]{2}\d{7}(?:-\d{2})?", plan) and plan[:5] == issuer and plan[5:7] == state, "inventory: plan identity scope mismatch")
                entry = by_state.setdefault(state, dict(rows=0, issuers=set(), plans=set(), digest=hashlib.sha256()))
                entry["rows"] += 1
                entry["issuers"].add(issuer)
                entry["plans"].add(plan[:14])
                # Physical row identity plus all original cells, including empty rate cells.
                entry["digest"].update(encoded([line, list(row.values())]))
    return digest.hexdigest(), {s: dict(rows=v["rows"], issuers=sorted(v["issuers"]),
                                      base_plans=len(v["plans"]), rows_sha256=v["digest"].hexdigest())
                                for s, v in by_state.items()}


class Bundle:
    def __init__(self, root, selection, as_of):
        self.root = Path(root).resolve(strict=True)
        self.as_of = timestamp(as_of)
        exact_keys(selection, "schema_version source_commit population sources reports premium_scopes issuer_scopes", "selection")
        require(type(selection["schema_version"]) is int and selection["schema_version"] == 1, "selection: unsupported schema")
        require(re.fullmatch(r"[0-9a-f]{40}", selection["source_commit"] or ""), "selection: source_commit must be full implementation/base commit")
        require(selection["population"] == "separate_validated_runs", "selection: single serving snapshot is not supported without an audited adapter")
        require(all(isinstance(selection[k], dict) for k in ("sources", "reports")) and all(isinstance(selection[k], list) for k in ("premium_scopes", "issuer_scopes")), "selection: unsupported collection types")
        self.selection = selection
        self.provenance, self.members, self.reports, self.input_hashes = {}, {}, {}, {}
        self.used_sources, self.used_reports = set(), set()
        for rid, spec in sorted(selection["reports"].items()):
            require(re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", rid) and rid not in self.input_hashes, "report: unsafe or duplicate identifier")
            exact_keys(spec, "path sha256 format finalized", "report")
            require(spec["finalized"] is True, "report: only finalized selections allowed")
            require(not re.search(r"mutant|before-recovery|interrupted|checkpoint|synthetic", spec["path"], re.I), "report: historical or synthetic evidence rejected")
            require(spec["format"] in ("federal-v1", "sbe-v1", "issuer-v1", "audit-v1", "sbe-declaration-v1", "serving-v1"), "report: unsupported format")
            data = relative_file(self.root, spec["path"]).read_bytes()
            require(len(data) <= 16 * 1024**2, "report: input budget exceeded")
            require(sha(data) == spec["sha256"], "report: hash mismatch")
            if spec["format"] == "sbe-declaration-v1":
                value = data.decode("utf-8")
                require("Nineteen individual-exchange state catalogs serve" in value and "Oregon is SHOP-only" in value and "NY/VT bundles are validated supplemental" in value, "serving: unsupported SBE declaration")
            else:
                value = loads(data)
                require(isinstance(value, dict), "report: expected object")
            self.reports[rid] = (spec["format"], value)
            self.input_hashes[rid] = spec["sha256"]
        for sid, spec in sorted(selection["sources"].items()):
            require(re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", sid) and sid not in self.input_hashes, "source: unsafe identifier")
            exact_keys(spec, "path sha256 url title vintage retrieved_at members", "source")
            path = relative_file(self.root, spec["path"])
            require(zipfile.is_zipfile(path), "source: expected ZIP archive")
            require(hash_file(path) == spec["sha256"], "source: archive hash mismatch")
            initial_stat = path.stat()
            require(timestamp(spec["retrieved_at"]) <= self.as_of, "source: retrieved after as_of")
            require(spec["vintage"] in (2026, 2027), "source: unsupported vintage")
            self.provenance[sid] = {k: spec[k] for k in ("url", "title", "vintage", "retrieved_at", "sha256")}
            public_url(spec["url"])
            self.input_hashes[sid] = spec["sha256"]
            for m in spec["members"]:
                exact_keys(m, "name kind", "member")
                key = (sid, m["name"])
                require(key not in self.members, "source: duplicate member selection")
                member_sha, scopes = inventory(path, m["name"], spec["vintage"], m["kind"])
                self.members[key] = dict(kind=m["kind"], sha256=member_sha, scopes=scopes, year=spec["vintage"])
            final_stat = path.stat()
            require((initial_stat.st_size, initial_stat.st_mtime_ns, initial_stat.st_ino) == (final_stat.st_size, final_stat.st_mtime_ns, final_stat.st_ino), "source: archive changed during scan")

    def report(self, rid, fmt):
        require(rid in self.reports and self.reports[rid][0] == fmt, "report: missing or unsupported selected report")
        self.used_reports.add(rid)
        return self.reports[rid][1]

    def member(self, sid, name, state, year, kind):
        require((sid, name) in self.members, "inventory: unselected member")
        member = self.members[(sid, name)]
        require(member["year"] == year and member["kind"] == kind, "inventory: layer/year member mismatch")
        require(state in member["scopes"], "inventory: state absent from source year")
        self.used_sources.add(sid)
        return dict(source_id=sid, member=name, member_sha256=member["sha256"], **member["scopes"][state])

    def observed(self, value):
        require(timestamp(value) <= self.as_of, "evidence: observed after as_of")
        return value

    def premiums(self, spec):
        exact_keys(spec, "state year source plan_source rate_member plan_member report serving_report observed_at", "premium scope")
        s, y, sid = spec["state"], spec["year"], spec["source"]
        require(s in STATES and type(y) is int and y in (2026, 2027), "premium: invalid scope")
        rate = self.member(sid, spec["rate_member"], s, y, "rates")
        plans = self.member(spec["plan_source"], spec["plan_member"], s, y, "plans")
        require(rate["issuers"] == plans["issuers"], "premium: rate/plan issuer inventory mismatch")
        observed = self.observed(spec["observed_at"])
        ids = sorted({sid, spec["plan_source"]})
        result = dict(state=s, year=y, layer="premiums", observed_at=observed, inventory=rate,
                      plan_inventory=plans, input_ids=ids, reconciliation=None, serving=None)
        if spec["report"] is None:
            return result
        rid = spec["report"]
        fmt = self.reports.get(rid, (None,))[0]
        require(fmt in ("federal-v1", "sbe-v1"), "premium: unsupported report adapter")
        report = self.report(rid, fmt)
        require(not (s == "OR" and fmt == "sbe-v1"), "premium: OR SHOP rows cannot join federal denominator")
        require(report["year"] == y, "premium: report year mismatch")
        rows = report["results"] if fmt == "federal-v1" else report["states"]
        require(len({r["state"] for r in rows}) == len(rows), "premium: duplicate report state")
        require(report.get("passed") is True if fmt == "federal-v1" else report.get("status") == "PASS", "premium: aggregate validation failed")
        matches = [r for r in rows if r["state"] == s]
        require(len(matches) == 1, "premium: report state missing")
        row = matches[0]
        require(row["year"] == y, "premium: state year mismatch")
        if fmt == "federal-v1":
            p = row["premiums"]
            require(row["passed"] is True and p["passed"] is True and integer(p["mismatch_count"]) == 0 and p["mismatches"] == [], "premium: reconciliation failed")
            for key in ("base_ids", "variant_ids"):
                v = row[key]
                require(v["passed"] is True and integer(v["actual"]) == integer(v["expected"]) and not v["only_actual"] and not v["only_expected"], "premium: plan identity reconciliation failed")
            require(row["base_ids"]["expected"] == plans["base_plans"], "premium: public base plan identity count mismatch")
            require(integer(p["raw_rows"]) == rate["rows"] == integer(p["stored_rows"]), "premium: public/raw/stored row mismatch")
        else:
            require(row["status"] == "PASS" and integer(row["mismatches"]) == 0, "premium: reconciliation failed")
            require(row["sha256"] == self.provenance[sid]["sha256"], "premium: source hash mismatch")
            require(integer(row["rates_checked"]) == rate["rows"] == integer(row["counts"]["rate"]), "premium: checked/source row mismatch")
            require(integer(row["issuers"]) == len(plans["issuers"]) and integer(row["base_plans"]) == plans["base_plans"], "premium: plan inventory mismatch")
        import_id = row["import_id"]
        require(isinstance(import_id, str) and import_id.startswith(f"puf-{y}-{s}-"), "premium: catalog identity scope mismatch")
        result["input_ids"].append(rid)
        result["reconciliation"] = dict(verified=rate["rows"], mismatches=0, catalog_sha256=sha(import_id.encode()),
                                         digest=sha(encoded(row)), report_id=rid)
        serving_id = spec["serving_report"]
        if serving_id is not None:
            if self.reports.get(serving_id, (None,))[0] == "sbe-declaration-v1":
                self.report(serving_id, "sbe-declaration-v1")
                require(fmt == "sbe-v1" and y == 2026 and s not in ("NY", "VT", "OR"), "serving: supplemental or SHOP catalog cannot replace serving catalog")
                result["serving"] = dict(catalog_sha256=sha(import_id.encode()), basis="active_catalog", report_id=serving_id)
            else:
                serving = self.report(serving_id, "serving-v1")
                exact_keys(serving, "schema_version catalogs", "serving report")
                require(type(serving["schema_version"]) is int and serving["schema_version"] == 1, "serving: unsupported schema")
                candidates = [c for c in serving["catalogs"] if c["state"] == s and c["year"] == y]
                require(len(candidates) == 1, "serving: missing or duplicate catalog pointer")
                c = candidates[0]
                exact_keys(c, "state year import_id status source_sha256 observed_at", "serving pointer")
                self.observed(c["observed_at"])
                require(c["status"] == "ACTIVE" and c["import_id"] == import_id and c["source_sha256"] == self.provenance[sid]["sha256"], "serving: active catalog/source pointer mismatch")
                require(s not in ("NY", "VT") and not (s == "OR" and fmt == "sbe-v1"), "serving: supplemental or SHOP catalog forbidden")
                result["serving"] = dict(catalog_sha256=sha(import_id.encode()), basis="active_catalog", report_id=serving_id)
            result["input_ids"].append(serving_id)
        result["input_ids"] = sorted(set(result["input_ids"]))
        return result

    def issuers(self, spec):
        exact_keys(spec, "state year source plan_member layer report audit observed_at unassessed_issuers", "issuer scope")
        s, y, layer = spec["state"], spec["year"], spec["layer"]
        require(s in STATES and type(y) is int and y in (2026, 2027) and layer in ("providers", "prescriptions"), "issuer: invalid scope")
        inv = self.member(spec["source"], spec["plan_member"], s, y, "plans")
        ids = [spec["source"]]
        rows = {}
        warnings = []
        observed = self.observed(spec["observed_at"])
        if spec["audit"] is not None:
            audit = self.report(spec["audit"], "audit-v1")
            ids.append(spec["audit"])
            if "attribution" in audit:
                require(all(integer(audit["attribution"].get(k, 0)) == 0 for k in ("logical_edge_mismatches", "wrong_issuer", "wrong_state", "wrong_year")), "issuer: audit reports contradictory association attribution")
            kind = "provider" if layer == "providers" else "drug"
            manifest = [m for m in audit["manifest"] if m["kind"] == kind]
            require(manifest, "issuer: audit contains no assessed issuer evidence")
            require(all(m["state"] == s and m["plan_year"] == y for m in manifest), "issuer: manifest state/year mismatch")
            require(len({m["issuer_id"] for m in manifest}) == len(manifest), "issuer: duplicate manifest issuer")
            mapped = {m["issuer_id"]: m for m in manifest}
            # A public catalog member absent from every report is unknown, never removed.
            require(set(mapped) <= set(inv["issuers"]), "issuer: manifest issuer outside public roster")
            require(isinstance(spec["unassessed_issuers"], list) and len(set(spec["unassessed_issuers"])) == len(spec["unassessed_issuers"]) and set(mapped).isdisjoint(spec["unassessed_issuers"]) and set(mapped) | set(spec["unassessed_issuers"]) == set(inv["issuers"]), "issuer: public/report roster reconciliation failed (withheld issuer)")
            if spec["report"] is not None:
                report = self.report(spec["report"], "issuer-v1")
                ids.append(spec["report"])
                require(report["state"] == s and report["year"] == y and report["kind"] == ("providers" if layer == "providers" else "formulary"), "issuer: report scope mismatch")
                require(report.get("running") is False and not report.get("not_run", []), "issuer: interrupted/incomplete report")
                reports = report["issuers"]
                require(len({r["issuer"] for r in reports}) == len(reports), "issuer: duplicate report issuer")
                require({r["issuer"] for r in reports} == set(mapped), "issuer: report/manifest roster mismatch (withheld issuer)")
            else:
                require(s == "GA" and y == 2026 and not audit.get("active"), "issuer: source report absent; active evidence cannot be inferred")
                reports = [dict(issuer=m["issuer_id"], state=s, year=y, snapshot_id=m["snapshot_id"],
                                status=m.get("validation_state"), completeness="unknown", edges=0, reason=m["reason"]) for m in manifest]
                require(all(r["status"] == "QUARANTINED" for r in reports), "issuer: quarantine validation absent")
            active = {(a["issuer_id"], a["snapshot_id"]) for a in audit.get("active", []) if a["kind"] == kind}
            for r in reports:
                issuer = r["issuer"]
                m = mapped[issuer]
                require(r["state"] == s and r["year"] == y, "issuer: association state/year mismatch")
                row_observed = self.observed(m.get("updated_at", observed))
                require(timestamp(row_observed) <= timestamp(observed), "issuer: source observation later than state observation")
                require(r["status"] in ("ACTIVE", "QUARANTINED"), "issuer: unsupported source validation state")
                require(isinstance(r["snapshot_id"], str) and r["snapshot_id"].startswith(f"{'provider' if layer == 'providers' else 'formulary'}:{issuer}:{y}:{s}:"), "issuer: snapshot pointer state/year mismatch")
                edges = integer(r["edges"], "issuer edges")
                is_active = r["status"] == "ACTIVE"
                # TX's recovered final audit records manifest pointers; other audits
                # additionally export the explicit active-set table.
                pointer = (issuer, r["snapshot_id"]) in active if "active" in audit else (
                    r["status"] == "ACTIVE" and m["snapshot_id"] == r["snapshot_id"] and m["status"] in ("complete", "partial"))
                if "provider_reports" in audit and layer == "providers":
                    corroborated = [a for a in audit["provider_reports"] if a["issuer"] == issuer]
                    require(len(corroborated) == 1 and all(corroborated[0][k] == r[k] for k in ("state", "year", "status", "snapshot_id", "edges")), "issuer: final audit/report source validation mismatch")
                if is_active:
                    require(pointer, "issuer: ACTIVE pointer absent or displaced by failed refresh")
                    require(edges > 0, "issuer: positive same-state/year plan association required")
                    require(r["completeness"] in ("complete", "partial"), "issuer: active completeness absent")
                    expected_children = integer(r["expected_children"], "expected children")
                    complete_children = integer(r["complete_children"], "complete children")
                    require(expected_children > 0 and 0 < complete_children <= expected_children, "issuer: advertised-child validation absent")
                    if r["completeness"] == "complete":
                        require(expected_children == complete_children, "issuer: complete source has unvalidated advertised children")
                    classification = "active_" + r["completeness"]
                    if m["snapshot_id"] != r["snapshot_id"] or m["status"] == "failed":
                        warnings.append(dict(code="failed_refresh", actor="undetermined", count=1))
                else:
                    require(not pointer, "issuer: QUARANTINED source cannot be an ACTIVE pointer")
                    classification = "quarantined"
                reason = r.get("reason", "") or ""
                actor = "undetermined"
                reason_code = "active_validated" if is_active else "attempt_failed"
                if not is_active:
                    if m["status"] == "access_denied":
                        actor = "publisher_access"
                        reason_code = "publisher_denied"
                    elif "catalog_not_available" in reason or any(t in reason for t in ("budget", "worker", "host_not_allowed")):
                        actor = "importer_limit"
                        reason_code = "adapter_unavailable" if "catalog_not_available" in reason or "host_not_allowed" in reason else "budget_limit"
                    elif any(t in reason for t in ("invalid_schema", "hash_mismatch", "invalid_json")):
                        actor = "source_validation"
                        reason_code = "source_invalid"
                if "catalog_not_available" in reason:
                    require(actor == "importer_limit", "issuer: adapter failure is not publisher denial")
                rows[issuer] = dict(issuer_id=issuer, classification=classification, validation_status=r["status"],
                                    snapshot_sha256=sha(r["snapshot_id"].encode()), active_pointer=pointer,
                                    positive_association=is_active and edges > 0, association_state=s if is_active else None,
                                    association_year=y if is_active else None, actor=actor, reason_code=reason_code, observed_at=row_observed)
                if not is_active:
                    warnings.append(dict(code="quarantined_sources", actor=actor, count=1))
        else:
            require(spec["report"] is None, "issuer: report without audit is unsupported")
        roster = [rows.get(i, dict(issuer_id=i, classification="unknown", validation_status=None,
                                  snapshot_sha256=None, active_pointer=False, positive_association=False,
                                  association_state=None, association_year=None, actor="undetermined", reason_code="unassessed", observed_at=self.provenance[spec["source"]]["retrieved_at"])) for i in inv["issuers"]]
        counts = defaultdict(int)
        for w in warnings:
            counts[(w["code"], w["actor"])] += w["count"]
        partial = sum(r["classification"] == "active_partial" for r in roster)
        if partial:
            counts[("partial_active_sources", "undetermined")] = partial
        return dict(state=s, year=y, layer=layer, inventory=inv, roster=roster, observed_at=observed,
                    input_ids=sorted(ids), assessed=spec["audit"] is not None,
                    warnings=[dict(code=c, actor=a, count=n) for (c, a), n in sorted(counts.items())],
                    result=issuer_result(roster, spec["audit"] is not None))

    def reconcile(self):
        scopes = []
        for spec in self.selection["premium_scopes"]:
            scopes.append(self.premiums(spec))
        for spec in self.selection["issuer_scopes"]:
            scopes.append(self.issuers(spec))
        keys = [(s["layer"], s["year"], s["state"]) for s in scopes]
        require(len(keys) == len(set(keys)), "selection: duplicate scope (including federal/SHOP double counting)")
        require(self.used_sources == set(self.provenance) and self.used_reports == set(self.reports), "selection: unused inputs; select only final relevant evidence")
        return scopes
