import copy
import csv
import io
import json
import socket
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from check import check_record, check_release, check_scope, schemas, validate
from inputs import Bundle, inventory, relative_file, sbe_declaration
from model import Invalid, encoded, loads, percentage, sha, timestamp
from scan import publish, release, table

FIXTURE = json.loads((Path(__file__).parent / "fixtures/scopes.json").read_text())
AS_OF = FIXTURE["as_of"]


class Evidence:
    """Small handwritten source/report recipe; never derived from scanner output."""
    def __init__(self, root):
        self.root = root
        self.selection = dict(schema_version=1, source_commit="a" * 40, population="separate_validated_runs",
                              sources={}, reports={}, premium_scopes=[], issuer_scopes=[])
        for scope in FIXTURE["scopes"]:
            state = scope["state"]
            ids = [str(10000 + n) for n in range(scope["denominator"])]
            self.source(state, ids)
            for layer in ("providers", "prescriptions"):
                kind = "provider" if layer == "providers" else "drug"
                complete, partial, quarantined, unknown = scope[layer]
                classifications = ["complete"] * complete + ["partial"] * partial + ["unknown"] * quarantined
                rows, manifest, active = [], [], []
                for i, completeness in zip(ids, classifications):
                    is_active = completeness != "unknown"
                    snapshot = f"{'provider' if kind == 'provider' else 'formulary'}:{i}:2026:{state}:fixture"
                    rows.append(dict(issuer=i, state=state, year=2026, snapshot_id=snapshot,
                                     status="ACTIVE" if is_active else "QUARANTINED", completeness=completeness,
                                     edges=2 if is_active else 0, expected_children=1, complete_children=1 if is_active else 0, reason="catalog_not_available" if state == "GA" else "index_connect_timeout"))
                    manifest.append(dict(issuer_id=i, state=state, plan_year=2026, kind=kind,
                                         snapshot_id=snapshot, status=completeness, reason=rows[-1]["reason"],
                                         validation_state=rows[-1]["status"]))
                    if is_active:
                        active.append(dict(issuer_id=i, kind=kind, snapshot_id=snapshot))
                rid = state.lower() + "_" + layer
                aid = rid + "_audit"
                self.report(rid, dict(state=state, year=2026, kind="providers" if layer == "providers" else "formulary",
                                     issuers=rows, running=False), "issuer-v1")
                self.report(aid, dict(manifest=manifest, active=active), "audit-v1")
                self.selection["issuer_scopes"].append(dict(state=state, year=2026, source=state.lower(), plan_member="plans.csv",
                    layer=layer, report=rid, audit=aid, observed_at=AS_OF, unassessed_issuers=ids[-unknown:] if unknown else []))

    def source(self, state, ids):
        path = self.root / (state.lower() + ".zip")
        rows = [[2026, state, i, i + state + "0000001"] for i in ids]
        out = io.StringIO(newline="")
        writer = csv.writer(out)
        writer.writerow(["BusinessYear", "StateCode", "IssuerId", "StandardComponentId"])
        writer.writerows(rows)
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("plans.csv", out.getvalue())
            z.writestr("rates.csv", out.getvalue())
        sid = state.lower()
        self.selection["sources"][sid] = dict(path=path.name, sha256=sha(path.read_bytes()),
            url=f"https://download.cms.gov/marketplace-puf/2026/{sid}-fixture.zip", title="Public fixture", vintage=2026,
            retrieved_at=AS_OF, members=[dict(name="plans.csv", kind="plans")])

    def report(self, rid, data, fmt):
        path = self.root / (rid + ".json")
        path.write_bytes(encoded(data))
        self.selection["reports"][rid] = dict(path=path.name, sha256=sha(path.read_bytes()), format=fmt, finalized=True)

    def mutate_report(self, rid, edit):
        spec = self.selection["reports"][rid]
        path = self.root / spec["path"]
        value = json.loads(path.read_bytes())
        edit(value)
        path.write_bytes(encoded(value))
        spec["sha256"] = sha(path.read_bytes())

    def bundle(self):
        return Bundle(self.root, self.selection, AS_OF)

    def premium(self, state="OR", serving=True):
        ids = ["20000", "20001"]
        self.source(state, ids)
        sid = state.lower()
        self.selection["sources"][sid]["members"].append(dict(name="rates.csv", kind="rates"))
        row = dict(state=state, year=2026, generated_at=AS_OF, passed=True,
                   premiums=dict(passed=True, mismatch_count=0, mismatches=[], raw_rows=2, stored_rows=2),
                   base_ids=dict(passed=True, actual=2, expected=2, only_actual=[], only_expected=[]),
                   variant_ids=dict(passed=True, actual=2, expected=2, only_actual=[], only_expected=[]),
                   import_id=f"puf-2026-{state}-fixture")
        rid = sid + "_premium"
        self.report(rid, dict(year=2026, passed=True, results=[row]), "federal-v1")
        active_id = sid + "_serving"
        if serving:
            self.report(active_id, dict(schema_version=1, catalogs=[dict(state=state, year=2026,
                import_id=row["import_id"], status="ACTIVE", source_sha256=self.selection["sources"][sid]["sha256"], observed_at=AS_OF)]), "serving-v1")
        spec = dict(state=state, year=2026, source=sid, plan_source=sid, rate_member="rates.csv", plan_member="plans.csv",
                    report=rid, serving_report=active_id if serving else None, observed_at=AS_OF)
        self.selection["premium_scopes"].append(spec)
        return spec


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "input"
        self.root.mkdir()
        self.e = Evidence(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        bundle = self.e.bundle()
        return release(bundle, bundle.reconcile(), AS_OF, AS_OF)

    def test_golden_report_figures_and_quarantine(self):
        files, fragment = self.build()
        for layer, pctkey in [("providers", "provider_tenths"), ("prescriptions", "prescription_tenths")]:
            data = loads(files[layer + "-2026.json"])
            for f in FIXTURE["scopes"]:
                r = data["states"][f["state"]]
                self.assertEqual(r["denominator"], f["denominator"])
                self.assertEqual(r["numerator"], sum(f[layer][:2]))
                self.assertEqual(r["percent_tenths"], f[pctkey])
                self.assertEqual(r["status"], "quarantined" if f["state"] == "GA" else "measured")
            self.assertIsNone(data["states"]["DC"]["denominator"])
        self.assertEqual(fragment.count(b'<th scope="row">'), 51)
        self.assertIn(b"Georgia</th><td>0/16 (0.0%)</td><td>Quarantined", fragment)
        target = self.base / "output"
        publish(target, files)
        self.assertTrue(check_release(target))

    def test_fixed_runs_identical_no_network_or_input_writes(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            first, html1 = self.build()
            second, html2 = self.build()
        self.assertEqual(first, second)
        self.assertEqual(html1, html2)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        target = self.base / "output"
        publish(target, first)
        self.assertIn("0 count/status changes", publish(target, second))

    def test_all_negative_record_controls(self):
        files, _ = self.build()
        data = loads(files["providers-2026.json"])
        definitions = schemas()
        mutations = [
            ("percentage", lambda d: d["states"]["TX"].update(percent_tenths=500), "rounding"),
            ("delete DC", lambda d: d["states"].pop("DC"), "required field"),
            ("zero denominator", lambda d: d["states"]["TX"].update(denominator=0), "partition"),
            ("fractional count", lambda d: d["states"]["TX"].update(numerator=14.5), "schema alternative"),
            ("private absolute path", lambda d: d["states"]["TX"].update(observed_at="/private/tmp/fixture"), "ISO UTC"),
        ]
        for name, edit, reason in mutations:
            with self.subTest(name=name):
                mutant = copy.deepcopy(data)
                edit(mutant)
                with self.assertRaisesRegex(Invalid, reason):
                    validate(mutant, definitions["dataset"], definitions, "dataset")
                    for record in mutant["states"].values():
                        check_record(record, "providers", timestamp(AS_OF))

    def test_duplicate_json_key_and_truncated_report(self):
        with self.assertRaisesRegex(Invalid, "duplicate object key"):
            loads('{"TX":{},"TX":{}}')
        spec = self.e.selection["reports"]["tx_providers"]
        p = self.root / spec["path"]
        p.write_bytes(p.read_bytes()[:-2])
        spec["sha256"] = sha(p.read_bytes())
        with self.assertRaisesRegex(Invalid, "malformed or truncated"):
            self.e.bundle()

    def test_report_negative_controls(self):
        cases = [
            ("withheld denied issuer", "tx_providers", lambda r: r["issuers"].pop(), "roster mismatch"),
            ("duplicate TX issuer", "tx_providers", lambda r: r["issuers"].append(copy.deepcopy(r["issuers"][0])), "duplicate report issuer"),
            ("association year", "tx_providers", lambda r: r["issuers"][0].update(year=2027), "state/year mismatch"),
            ("association state", "tx_providers", lambda r: r["issuers"][0].update(state="FL"), "state/year mismatch"),
            ("positive association absent", "tx_providers", lambda r: r["issuers"][0].update(edges=0), "positive same-state/year"),
            ("fractional edges", "tx_providers", lambda r: r["issuers"][0].update(edges=2.5), "safe integer"),
            ("quarantine counted ACTIVE", "ga_providers", lambda r: r["issuers"][0].update(status="ACTIVE", edges=1, completeness="complete"), "ACTIVE pointer absent"),
            ("failed refresh displaces pointer", "tx_providers_audit", lambda r: r["active"][0].update(snapshot_id="failed-refresh"), "ACTIVE pointer absent"),
            ("GA importer blamed on publisher", "ga_providers_audit", lambda r: r["manifest"][0].update(status="access_denied"), "adapter failure is not publisher denial"),
        ]
        for name, rid, edit, reason in cases:
            with self.subTest(name=name):
                original = (self.root / self.e.selection["reports"][rid]["path"]).read_bytes()
                self.e.mutate_report(rid, edit)
                with self.assertRaisesRegex(Invalid, reason):
                    self.e.bundle().reconcile()
                self.e.report(rid, json.loads(original), self.e.selection["reports"][rid]["format"])

    def test_remove_denied_issuer_from_both_reports_fails(self):
        self.e.mutate_report("tx_providers", lambda r: r["issuers"].pop())
        self.e.mutate_report("tx_providers_audit", lambda r: r["manifest"].pop())
        with self.assertRaisesRegex(Invalid, "withheld issuer"):
            self.e.bundle().reconcile()

    def test_failed_refresh_preserves_prior_valid_active_pointer(self):
        self.e.mutate_report("tx_providers_audit", lambda r: r["manifest"][0].update(status="failed", snapshot_id="later-failed-refresh"))
        data = loads(self.build()[0]["providers-2026.json"])
        r = data["states"]["TX"]
        self.assertEqual(r["numerator"], 14)
        self.assertIn(dict(code="failed_refresh", actor="undetermined", count=1), r["warnings"])

    def test_absent_report_is_unknown_not_zero(self):
        s = self.e.selection["issuer_scopes"][0]
        for key in ("audit", "report"):
            self.e.selection["reports"].pop(s[key])
            s[key] = None
        r = loads(self.build()[0]["providers-2026.json"])["states"]["TX"]
        self.assertEqual(r["denominator"], 32)
        self.assertIsNone(r["numerator"])
        self.assertIsNone(r["percent_tenths"])
        self.assertEqual(r["counts"]["unknown"], 32)
        self.assertEqual(r["status"], "unknown")

    def test_premium_active_serving_and_missing_pointer(self):
        self.e.premium()
        r = loads(self.build()[0]["premiums-2026.json"])["states"]["OR"]
        self.assertEqual((r["numerator"], r["denominator"], r["percent_tenths"]), (2, 2, 1000))
        self.e.selection["reports"].pop("or_serving")
        self.e.selection["premium_scopes"][0]["serving_report"] = None
        r = loads(self.build()[0]["premiums-2026.json"])["states"]["OR"]
        self.assertIsNone(r["numerator"])
        self.assertEqual(r["reason_codes"], ["serving_evidence_absent"])

    def test_reconciled_premium_without_serving_evidence_stays_null(self):
        self.e.premium(serving=False)
        files, _ = self.build()
        record = loads(files["premiums-2026.json"])["states"]["OR"]
        ledger = loads(files[record["evidence"]["path"]])
        scope = ledger["scopes"]["OR"]
        self.assertEqual(scope["reconciliation"]["verified"], 2)
        self.assertIsNone(scope["serving"])
        self.assertEqual(record["denominator"], 2)
        self.assertEqual(record["counts"], dict(verified=0, quarantined=0, unknown=2, not_imported=0))
        self.assertEqual(record["status"], "unknown")
        self.assertEqual(record["serving_basis"], "unverified")
        self.assertEqual(record["reason_codes"], ["serving_evidence_absent"])
        self.assertIsNone(record["numerator"])
        self.assertIsNone(record["percent_tenths"])
        # Even a self-consistent 2/2 record cannot replace absent pointer lineage.
        record.update(numerator=2, percent_tenths=1000, status="measured",
                      counts=dict(verified=2, quarantined=0, unknown=0, not_imported=0),
                      reason_codes=[], serving_basis="active_catalog")
        with self.assertRaisesRegex(Invalid, "independent reconciliation and ACTIVE serving evidence"):
            check_scope(scope, record, loads(files["index.json"]), "premiums", 2026, "OR", ledger)

    def p6d_pointer_fixture(self):
        spec = self.e.premium(serving=False)
        rid = spec["report"]
        self.e.mutate_report(rid, lambda r: r.update(states=["OR"]))
        report = loads((self.root / self.e.selection["reports"][rid]["path"]).read_bytes())
        self.e.report("p6d_pointer", report, "p6d-pointer-v1")
        spec["serving_report"] = "p6d_pointer"
        return spec, self.e.selection["reports"][rid]["sha256"]

    def test_reviewed_p6d_pointer_and_reconciliation_bind_same_artifact(self):
        spec, digest = self.p6d_pointer_fixture()
        # Substitute the handwritten artifact only inside this test. Production
        # accepts the separately reviewed historical artifact, never these bytes.
        with patch("inputs.P6D_POINTER_REPORTS", {2026: digest}):
            files, _ = self.build()
            record = loads(files["premiums-2026.json"])["states"]["OR"]
            self.assertEqual((record["numerator"], record["denominator"], record["percent_tenths"]), (2, 2, 1000))
            ledger = loads(files[record["evidence"]["path"]])
            self.assertEqual(ledger["scopes"]["OR"]["serving"]["report_id"], "p6d_pointer")
            target = self.base / "p6d-release"
            publish(target, files)
            self.assertTrue(check_release(target))
            self.e.mutate_report(spec["report"], lambda r: r.update(extra="different reconciliation artifact"))
            with self.assertRaisesRegex(Invalid, "pointer/reconciliation artifact mismatch"):
                self.build()

    def test_unreviewed_p6d_pointer_artifact_is_rejected(self):
        self.p6d_pointer_fixture()
        # A passing federal-shaped report is insufficient even when the operator
        # opts into serving evidence and updates the selection to its real hash.
        with self.assertRaisesRegex(Invalid, "unreviewed P6d pointer artifact"):
            self.build()

    def test_p6d_pointer_requires_explicit_selection(self):
        spec, digest = self.p6d_pointer_fixture()
        self.e.selection["reports"].pop("p6d_pointer")
        spec["serving_report"] = None
        with patch("inputs.P6D_POINTER_REPORTS", {2026: digest}):
            record = loads(self.build()[0]["premiums-2026.json"])["states"]["OR"]
        self.assertIsNone(record["numerator"])
        self.assertEqual(record["reason_codes"], ["serving_evidence_absent"])

    def test_premium_scope_negative_controls(self):
        spec = self.e.premium()
        with self.subTest("OR double counting"):
            self.e.selection["premium_scopes"].append(copy.deepcopy(spec))
            with self.assertRaisesRegex(Invalid, "federal/SHOP double counting"):
                self.e.bundle().reconcile()
            self.e.selection["premium_scopes"].pop()
        with self.subTest("source year changed"):
            spec["year"] = 2027
            with self.assertRaisesRegex(Invalid, "year member mismatch"):
                self.e.bundle().reconcile()
            spec["year"] = 2026
        with self.subTest("wrong serving source hash"):
            self.e.mutate_report("or_serving", lambda r: r["catalogs"][0].update(source_sha256="b" * 64))
            with self.assertRaisesRegex(Invalid, "catalog/source pointer mismatch"):
                self.e.bundle().reconcile()

    def test_ny_vt_supplemental_cannot_be_promoted(self):
        for state in ("NY", "VT"):
            with self.subTest(state=state):
                e = Evidence(self.root)
                e.premium(state)
                with self.assertRaisesRegex(Invalid, "supplemental or SHOP catalog forbidden"):
                    e.bundle().reconcile()

    def test_path_url_hash_and_format_boundaries(self):
        for path in ("../escape", "/private/fixture", "C:\\fixture"):
            with self.subTest(path=path), self.assertRaisesRegex(Invalid, "input path"):
                relative_file(self.root, path)
        outside = self.base / "outside"
        outside.write_text("fixture")
        (self.root / "escape").symlink_to(outside)
        with self.assertRaisesRegex(Invalid, "symlink escape"):
            relative_file(self.root, "escape")
        for url in ("https://example.com/source?token=fixture", "http://example.com/source", "https://localhost/source", "https://127.0.0.1/source"):
            original = self.e.selection["sources"]["tx"]["url"]
            self.e.selection["sources"]["tx"]["url"] = url
            with self.subTest(url=url), self.assertRaisesRegex(Invalid, "source URL"):
                self.e.bundle()
            self.e.selection["sources"]["tx"]["url"] = original
        self.e.selection["sources"]["tx"]["sha256"] = "b" * 64
        with self.assertRaisesRegex(Invalid, "archive hash mismatch"):
            self.e.bundle()

    def test_release_tampering_and_failed_publication_preserves_snapshot(self):
        files, fragment = self.build()
        target = self.base / "output"
        publish(target, files)
        old = (target / "index.json").read_bytes()
        broken = dict(files)
        data = loads(broken["providers-2026.json"])
        data["states"]["TX"]["percent_tenths"] = 500
        broken["providers-2026.json"] = encoded(data)
        with self.assertRaisesRegex(Invalid, "dataset digest"):
            publish(target, broken)
        self.assertEqual(old, (target / "index.json").read_bytes())
        self.assertTrue(check_release(target))

    def test_previous_snapshot_symlink_is_not_read(self):
        files, _ = self.build()
        target = self.base / "output"
        publish(target, files)
        outside = self.base / "private.json"
        outside.write_bytes(b"not-public-evidence")
        (target / "providers-2026.json").unlink()
        (target / "providers-2026.json").symlink_to(outside)
        with self.assertRaisesRegex(Invalid, "symlink in previous release"):
            publish(target, files)
        self.assertEqual(outside.read_bytes(), b"not-public-evidence")

    def test_unknown_schema_and_extra_field_fail_closed(self):
        definitions = schemas()
        files, _ = self.build()
        index = loads(files["index.json"])
        for mutate in (lambda x: x.update(schema_version=2), lambda x: x.update(extra="unsupported"), lambda x: x.update(schema_version=True)):
            mutant = copy.deepcopy(index)
            mutate(mutant)
            with self.assertRaises(Invalid):
                validate(mutant, definitions["index"], definitions)
        with self.assertRaisesRegex(Invalid, "unsupported keyword"):
            validate(1, {"unsupported": True}, definitions)

    def test_semantic_checker_rejects_rehashed_mutants(self):
        files, _ = self.build()

        def write_mutant(edit, state="TX", dataset_edit=None, ledger_edit=None):
            mutated = dict(files)
            data = loads(mutated["providers-2026.json"])
            oldpath = data["states"][state]["evidence"]["path"]
            ledger = loads(mutated[oldpath])
            edit(ledger["scopes"][state])
            if ledger_edit:
                ledger_edit(ledger)
            raw = encoded(ledger)
            newpath = "evidence/" + sha(raw) + ".json"
            del mutated[oldpath]
            mutated[newpath] = raw
            for r in data["states"].values():
                if r["evidence"] and r["evidence"]["path"] == oldpath:
                    r["evidence"].update(path=newpath, sha256=sha(raw))
            if dataset_edit:
                dataset_edit(data)
            mutated["providers-2026.json"] = encoded(data)
            index = loads(mutated["index.json"])
            for d in index["datasets"]:
                if d["path"] == "providers-2026.json":
                    d.update(sha256=sha(mutated[d["path"]]), bytes=len(mutated[d["path"]]))
            mutated["index.json"] = encoded(index)
            target = self.base / "mutant"
            if target.exists():
                import shutil
                shutil.rmtree(target)
            for name, content in mutated.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            return target

        cases = [
            ("missing positive association", lambda s: s["roster"][0].update(positive_association=False), "TX", "positive association required"),
            ("wrong positive state", lambda s: s["roster"][0].update(association_state="FL"), "TX", "association state/year"),
            ("wrong positive year", lambda s: s["roster"][0].update(association_year=2027), "TX", "association state/year"),
            ("displaced active pointer", lambda s: s["roster"][0].update(active_pointer=False), "TX", "ACTIVE pointer"),
            ("withheld denied issuer", lambda s: s["roster"].pop(), "TX", "withheld or duplicate issuer"),
            ("quarantine falsely active", lambda s: s["roster"][0].update(active_pointer=True), "GA", "quarantined is not active"),
            ("unproved not imported", lambda s: s["roster"][-1].update(classification="not_imported"), "TX", "audited valid-source adapter"),
            ("unknown falsely validated", lambda s: s["roster"][-1].update(validation_status="ACTIVE"), "TX", "unknown unit must remain unassessed"),
            ("wrong publisher attribution", lambda s: s["roster"][0].update(actor="publisher_access"), "GA", "adapter failure is not publisher denial"),
        ]
        for name, edit, state, reason in cases:
            with self.subTest(name=name):
                target = write_mutant(edit, state)
                with self.assertRaisesRegex(Invalid, reason):
                    check_release(target)
        with self.assertRaisesRegex(Invalid, "public archive hash mismatch"):
            check_release(write_mutant(lambda _: None, ledger_edit=lambda l: l["inputs"].update(tx="b" * 64)))

    def test_no_report_premium_is_unknown_with_known_inventory(self):
        spec = self.e.premium(serving=False)
        self.e.selection["reports"].pop(spec["report"])
        spec["report"] = None
        files, _ = self.build()
        r = loads(files["premiums-2026.json"])["states"]["OR"]
        self.assertEqual(r["denominator"], 2)
        self.assertEqual(r["counts"]["unknown"], 2)
        self.assertIsNone(r["numerator"])
        self.assertEqual(r["reason_codes"], ["report_absent"])

    def test_round_half_up_and_bounds(self):
        self.assertEqual(percentage(1, 16), 63)
        self.assertEqual(percentage(14, 32), 438)
        for n, d in ((1, 0), (3, 2), (-1, 5), (1.5, 2), (True, 3)):
            with self.assertRaises(Invalid):
                percentage(n, d)

    def test_handwritten_public_csv_and_malformed_row(self):
        fixture = Path(__file__).parent / "fixtures/plan.csv"
        archive = self.root / "handwritten.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("plans.csv", fixture.read_bytes())
        digest, states = inventory(archive, "plans.csv", 2026, "plans")
        self.assertEqual(states["TX"]["issuers"], ["10000", "10001"])
        self.assertEqual(states["TX"]["rows"], 2)
        self.assertEqual(len(digest), 64)
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("plans.csv", fixture.read_bytes().rsplit(b",", 1)[0])
        with self.assertRaisesRegex(Invalid, "malformed/truncated CSV row"):
            inventory(archive, "plans.csv", 2026, "plans")

    def test_serving_declaration_checks_actual_state_membership(self):
        states = "CA CO CT DC GA ID IL KY MA MD ME MN NJ NM NV PA RI VA WA".split()
        text = "Nineteen individual-exchange state catalogs serve. Oregon is SHOP-only. NY/VT bundles are validated supplemental.\n"
        for state in states + ["NY", "VT", "OR"]:
            basis = "Federal individual preserved" if state == "OR" else "P8 preserved" if state in ("NY", "VT") else "SBE"
            text += f"| [{state}](https://example.com/{state}.zip) | {basis} | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 |\n"
        parsed = sbe_declaration(text)
        self.assertEqual(len(parsed), 22)
        self.assertEqual(parsed["CA"]["basis"], "SBE")
        self.assertNotIn("TX", parsed)
        with self.assertRaisesRegex(Invalid, "duplicate or invalid SBE scope"):
            sbe_declaration(text + text.splitlines()[1] + "\n")
        with self.assertRaisesRegex(Invalid, "22 scopes and 19 serving"):
            sbe_declaration("\n".join(line for line in text.splitlines() if "[CA]" not in line))
        with self.assertRaisesRegex(Invalid, "scope precedence contradiction"):
            sbe_declaration(text.replace("Federal individual preserved", "P8 preserved"))

    def test_audited_filesystem_and_network_boundary(self):
        selection = self.root / "selection.json"
        selection.write_bytes(encoded(self.e.selection))
        script = r'''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from inputs import Bundle
from model import loads
from scan import release, publish
import check, encodings.utf_8_sig
tools, root, output = (Path(v).resolve() for v in sys.argv[1:])
def audit(event, args):
    if event.startswith('socket.'):
        raise AssertionError('network access forbidden')
    if event == 'open' and not isinstance(args[0], int):
        path = Path(args[0]).resolve()
        allowed = path.is_relative_to(root) or path.is_relative_to(tools) or path.is_relative_to(output.parent)
        if not allowed:
            raise AssertionError('read outside declared roots')
        flags = args[2]
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            if path.is_relative_to(root) or path.is_relative_to(tools):
                raise AssertionError('write to read-only root')
sys.addaudithook(audit)
bundle = Bundle(root, loads((root / 'selection.json').read_bytes()), '2026-11-08T13:00:00Z')
files, fragment = release(bundle, bundle.reconcile(), '2026-11-08T13:00:00Z', '2026-11-08T13:00:00Z')
publish(output, files)
print('boundary: PASS')
'''
        result = subprocess.run([sys.executable, "-B", "-c", script, str(TOOLS), str(self.root), str(self.base / "output")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("boundary: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
