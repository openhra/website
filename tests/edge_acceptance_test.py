"""Synthetic loopback servers exercise the outside client without live traffic."""

import contextlib
import copy
import importlib.util
import io
import json
import os
import select
import ssl
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "edge_acceptance", ROOT / "tools/edge-acceptance/probe.py"
)
probe = importlib.util.module_from_spec(SPEC)
# dataclasses on Python 3.9 consult sys.modules.
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)
SENTINEL = "synthetic-response-body-DO-NOT-LOG"


def tool():
    return {
        "isError": False,
        "structuredContent": {
            "status": "ok",
            "error": None,
            "data": {"synthetic": True},
        },
    }


class Fake(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, mode="good"):
        super().__init__(("127.0.0.1", 0), Handler)
        self.mode = mode
        self.guard = threading.Lock()
        self.active = 0
        self.peak = 0
        self.calls = 0
        self.counts = {}
        self.disconnects = 0
        self.mid_disconnects = 0
        self.rate_enabled = True
        self.refilled = False
        self.envelopes = []


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def send(self, status, body=b"", headers=None):
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def json(self, result=None, status=200, headers=None, error=None):
        value = {"jsonrpc": "2.0", "id": 1}
        value["error" if error else "result"] = error or result
        self.send(
            status,
            json.dumps(value).encode(),
            {"Content-Type": "application/json", **(headers or {})},
        )

    def handle_request(self):
        try:
            self.respond()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def respond(self):
        fake = self.server
        if self.path == "/synthetic-stall":
            time.sleep(0.6)
        if self.headers.get("Host") == "edge-acceptance.invalid":
            if fake.mode == "host":
                self.send(200, SENTINEL.encode())
            else:
                self.close_connection = True
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if self.path == "/healthz":
            if self.command == "HEAD":
                self.send(308, headers={"Location": probe.TARGET + "/healthz"})
            else:
                self.send(200, b'{"status":"ok","db":"ok"}')
            return
        if self.path.startswith("/v1/plans?"):
            self.send(200, b'{"plans":[{"synthetic":true}]}')
            return
        if self.path != "/mcp":
            status = (
                200
                if fake.mode == "routes"
                or (
                    fake.mode == "compat-post"
                    and self.path.startswith("/compat/")
                    and self.command == "POST"
                )
                else 404
            )
            self.send(status, SENTINEL.encode())
            return
        origin = self.headers.get("Origin")
        if origin and origin != probe.ORIGIN:
            self.send(403)
            return
        cors = (
            {
                "Access-Control-Allow-Origin": probe.ORIGIN,
                "Vary": "Origin",
                "Access-Control-Expose-Headers": "WWW-Authenticate, Retry-After",
            }
            if origin
            else {}
        )
        if self.command == "OPTIONS":
            self.send(
                204,
                headers={
                    **cors,
                    "Access-Control-Allow-Methods": "POST",
                    "Access-Control-Allow-Headers": "Content-Type, MCP-Protocol-Version, Mcp-Method, Mcp-Name, Accept",
                },
            )
            return
        if self.command in ("GET", "DELETE"):
            self.send(
                200 if fake.mode == "get200" and self.command == "GET" else 405,
                SENTINEL.encode(),
            )
            return
        if length > 65536:
            self.send(200 if fake.mode == "oversize" else 413, SENTINEL.encode())
            return
        source = self.headers.get("X-Synthetic-Source", "single")
        if fake.mode == "forwarded" and self.headers.get("X-Forwarded-For"):
            source = self.headers["X-Forwarded-For"]
        with fake.guard:
            fake.calls += 1
            count = fake.counts.get(source, 0) + 1
            fake.counts[source] = count
            refill = (
                fake.mode == "refill"
                and self.headers.get("X-Forwarded-For")
                and not fake.refilled
            )
            if refill:
                fake.refilled = True
        if fake.rate_enabled and count > 10 and not refill:
            self.send(
                429,
                SENTINEL.encode(),
                {} if fake.mode == "retry" else {"Retry-After": "60"},
            )
            return
        value = json.loads(body)
        params = value.get("params", {})
        revision = self.headers["MCP-Protocol-Version"]
        if revision == probe.MODERN:
            meta = params.get("_meta", {})
            if (
                meta.get("io.modelcontextprotocol/protocolVersion") != probe.MODERN
                or meta.get("io.modelcontextprotocol/clientCapabilities") != {}
                or "io.modelcontextprotocol/clientInfo" not in meta
                or self.headers["Mcp-Method"] != value["method"]
            ):
                self.send(400, SENTINEL.encode())
                return
            if (
                value["method"] == "tools/call"
                and self.headers["Mcp-Name"] != params["name"]
            ):
                self.send(400)
                return
        with fake.guard:
            fake.envelopes.append((revision, value["method"]))
        if value["method"] == "initialize":
            self.json({"protocolVersion": probe.LEGACY, "capabilities": {}})
        elif value["method"] == "server/discover":
            self.json({"serverInfo": {"name": "synthetic"}})
        elif value["method"] == "notifications/initialized":
            self.send(202)
        elif value["method"] == "tools/list":
            self.json({"tools": [{"name": "lookup_geography"}]}, headers=cors)
        elif value["method"] == "tools/call":
            token = params.get("_meta", {}).get("progressToken")
            if token is None:
                self.json(tool(), headers={} if fake.mode == "cors" else cors)
            else:
                with fake.guard:
                    rejected = fake.active >= 4
                    if not rejected:
                        fake.active += 1
                        fake.peak = max(fake.peak, fake.active)
                if rejected:
                    self.json(
                        status=429,
                        error={"code": -32000, "message": "Concurrency limit exceeded"},
                        headers={"Retry-After": "1"},
                    )
                    return
                try:
                    self.sse(token)
                finally:
                    with fake.guard:
                        fake.active -= 1
        else:
            self.send(400)

    def sse(self, token):
        def event(value):
            return b"data: " + json.dumps(value).encode() + b"\n\n"

        progress = event(
            {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {"progressToken": token, "progress": 0},
            }
        )
        final = event({"jsonrpc": "2.0", "id": 1, "result": tool()})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            if self.server.mode != "buffer":
                self.wfile.write(progress)
                self.wfile.flush()
            until = time.monotonic() + 0.14
            if (
                self.server.mode != "buffer"
                and select.select([self.connection], [], [], 0.1)[0]
            ) and not self.connection.recv(1):
                with self.server.guard:
                    self.server.mid_disconnects += 1
            time.sleep(max(0, until - time.monotonic()))
            self.wfile.write(
                progress + final if self.server.mode == "buffer" else final
            )
            self.wfile.flush()
            if not self.rfile.read(1):
                with self.server.guard:
                    self.server.disconnects += 1
        except (BrokenPipeError, ConnectionResetError):
            with self.server.guard:
                self.server.disconnects += 1
        self.close_connection = True

    do_GET = handle_request
    do_HEAD = handle_request
    do_POST = handle_request
    do_DELETE = handle_request
    do_OPTIONS = handle_request


@contextlib.contextmanager
def server(mode="good"):
    fake = Fake(mode)
    thread = threading.Thread(target=fake.serve_forever, daemon=True)
    thread.start()
    try:
        yield fake, probe.Client(f"http://127.0.0.1:{fake.server_port}")
    finally:
        fake.shutdown()
        fake.server_close()
        thread.join(timeout=2)


class AcceptanceTests(unittest.TestCase):
    def suite(self, client):
        return probe.Suite(client, "linux", time.time() + 1)

    def assert_safe(self, output):
        self.assertNotIn(SENTINEL, output)
        self.assertNotIn("192.0.2.", output)
        self.assertNotIn("Traceback", output)

    def basics(self, mode):
        with server(mode) as (fake, client):
            # Disable the fake's burst cap for the regular matrix. Rate has its own test.
            original = client.open

            def open_request(*args, **kwargs):
                with fake.guard:
                    fake.counts.clear()
                return original(*args, **kwargs)

            client.open = open_request
            suite = self.suite(client)
            with mock.patch.object(client, "unknown_sni") as sni:
                suite.basics()
                self.assertEqual(sni.call_count, 2)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = suite.report()
            self.assert_safe(output.getvalue())
            return result, suite.rows, output.getvalue(), fake.envelopes

    def test_both_envelopes_json_denials_and_headers(self):
        # Python 3.12 closes a framed response on its last byte. Model that lifecycle
        # on older interpreters too, so the next read cannot touch the released socket.
        with server() as (_, client):
            original_open = client.open

            def open_closing_response(*args, **kwargs):
                wire = original_open(*args, **kwargs)
                response = wire[1]
                original_read = response.read1

                def read_and_close(size):
                    part = original_read(size)
                    if response.length == 0:
                        response.close()
                    return part

                response.read1 = read_and_close
                return wire

            with mock.patch.object(client, "open", side_effect=open_closing_response):
                reply = client.request("GET", "/healthz")
            self.assertEqual(reply.status, 200)
            self.assertEqual(reply.json(), {"status": "ok", "db": "ok"})

        result, rows, _, envelopes = self.basics("good")
        self.assertTrue(result["ok"], rows)
        for revision in (probe.MODERN, probe.LEGACY):
            self.assertIn((revision, "tools/list"), envelopes)
            self.assertIn((revision, "tools/call"), envelopes)
        self.assertIn((probe.MODERN, "server/discover"), envelopes)
        self.assertIn((probe.LEGACY, "initialize"), envelopes)
        self.assertIn((probe.LEGACY, "notifications/initialized"), envelopes)
        self.assertLessEqual(result["requests"], 40)

    def test_get_200_mutant_fails(self):
        result, rows, output, _ = self.basics("get200")
        self.assertFalse(result["ok"])
        self.assertIn(("GET /mcp is 405", False), [row[:2] for row in rows])
        self.assertIn("| GET /mcp is 405 | FAIL |", output)

    def test_cors_known_failure_is_still_a_failure(self):
        result, rows, output, _ = self.basics("cors")
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                row[0] == "allowed-Origin POST headers" and not row[1] and row[3]
                for row in rows
            )
        )
        self.assertIn("Tracked MCP3b known failure", output)
        self.assertIn("| allowed-Origin POST headers | FAIL |", output)

    def test_oversize_host_and_routes_mutants_fail(self):
        for mode in ("oversize", "host", "routes", "compat-post"):
            with self.subTest(mode=mode):
                result, _, _, _ = self.basics(mode)
                self.assertFalse(result["ok"])

    def test_stream_arrival_and_disconnect(self):
        with server() as (fake, client):
            reply, proof = client.stream(
                "search_providers", {"name": "synthetic"}, "synthetic-progress"
            )
            self.assertEqual(reply.status, 200)
            self.assertGreaterEqual(proof["lead_ms"], 25)
            _, proof = client.stream(
                "search_providers",
                {"name": "synthetic-disconnect"},
                "synthetic-progress",
                True,
            )
            self.assertTrue(proof["disconnected"])
            deadline = time.monotonic() + 1
            while not fake.mid_disconnects and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreater(fake.mid_disconnects, 0)

    def test_buffered_sse_mutant_fails_stream_and_disconnect(self):
        with server("buffer") as (_, client):
            for disconnect in (False, True):
                with self.assertRaises(probe.CheckFailed):
                    client.stream(
                        "search_providers",
                        {"name": "synthetic"},
                        "synthetic-progress",
                        disconnect,
                    )
            suite = self.suite(client)
            suite.streaming()
            self.assertFalse(suite.rows[0][1])
            self.assertFalse(suite.rows[1][1])

    def test_rate_and_forwarded_bucket_isolation(self):
        for mode in ("good", "refill"):
            with server(mode) as (_, client):
                suite = self.suite(client)
                suite.rate()
                self.assertTrue(all(row[1] for row in suite.rows), suite.rows)
                self.assertLessEqual(client.requests, 19)
        for mode in ("retry", "forwarded"):
            with server(mode) as (_, client):
                suite = self.suite(client)
                suite.rate()
                self.assertTrue(any(not row[1] for row in suite.rows), suite.rows)

    def test_two_sources_reach_application_concurrency(self):
        with server() as (fake, _):
            clients = [
                probe.Client(
                    f"http://127.0.0.1:{fake.server_port}",
                    {"X-Synthetic-Source": source},
                )
                for source in ("linux", "macos")
            ]
            epoch = time.time() + 0.15
            suites = [
                probe.Suite(client, source, epoch, round_interval=0.3)
                for source, client in zip(("linux", "macos"), clients)
            ]
            # Two rounds are enough to prove cross-source overlap on the fake; production uses six.
            with (
                mock.patch.object(probe, "ROUNDS", 2),
                probe.ThreadPoolExecutor(max_workers=2) as pool,
            ):
                list(pool.map(lambda suite: suite.concurrency(), suites))
            self.assertTrue(
                all(suite.sample_ok and suite.samples == 6 for suite in suites)
            )
            self.assertGreater(sum(suite.denials for suite in suites), 0)
            self.assertEqual(fake.peak, 4)

    def test_late_rendezvous_fails_without_requests(self):
        with server() as (_, client):
            suite = probe.Suite(client, "linux", time.time() - 1)
            with self.assertRaises(probe.CheckFailed):
                suite.concurrency()
            self.assertEqual(client.requests, 0)

    def test_budget_and_response_bounds(self):
        with server() as (_, client):
            client.requests = probe.MAX_REQUESTS
            with self.assertRaisesRegex(probe.CheckFailed, "budget"):
                client.request("GET", "/healthz")
        with (
            server("get200") as (_, client),
            mock.patch.object(probe, "MAX_RESPONSE", 8),
            self.assertRaisesRegex(probe.CheckFailed, "byte cap"),
        ):
            client.request("GET", "/mcp")

    def test_tls_refusal_is_not_hostname_verification_failure(self):
        client = probe.Client()
        with (
            mock.patch.object(probe.socket, "create_connection") as connection,
            mock.patch.object(probe.ssl, "create_default_context") as context,
        ):
            raw = connection.return_value.__enter__.return_value
            ctx = context.return_value
            error = ssl.SSLError()
            error.reason = "TLSV1_UNRECOGNIZED_NAME"
            ctx.wrap_socket.side_effect = error
            client.unknown_sni("edge-acceptance.invalid")
            self.assertFalse(ctx.check_hostname)
            self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)
            ctx.wrap_socket.assert_called_with(
                raw, server_hostname="edge-acceptance.invalid"
            )
            ctx.wrap_socket.side_effect = ssl.SSLCertVerificationError()
            with self.assertRaises(probe.CheckFailed):
                client.unknown_sni("edge-acceptance.invalid")
            ctx.wrap_socket.side_effect = None
            with self.assertRaises(probe.CheckFailed):
                client.unknown_sni(None)
        self.assertEqual(client.requests, 3)

    def test_report_requires_both_sources_and_a_real_app_denial(self):
        report = {
            "source": "linux",
            "ok": True,
            "samples_ok": True,
            "samples": 18,
            "app_denials": 1,
            "requests": 79,
            "failed": 0,
        }
        reports = {
            "linux": json.dumps(report),
            "macos": json.dumps({**report, "source": "macos", "app_denials": 0}),
        }
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(probe.aggregate(dict(reports)))
            with self.assertRaises(probe.CheckFailed):
                probe.aggregate({"linux": reports["linux"]})
            for field, value in (
                ("app_denials", 0),
                ("ok", False),
                ("samples_ok", False),
                ("samples", 17),
            ):
                mutant = copy.deepcopy(report)
                mutant[field] = value
                self.assertFalse(
                    probe.aggregate({**reports, "linux": json.dumps(mutant)})
                )
            self.assertFalse(
                probe.concurrency_error(
                    probe.Reply(429, {"retry-after": "60"}, b"<html>edge</html>")
                )
            )
            self.assertFalse(
                probe.concurrency_error(
                    probe.Reply(
                        429,
                        {},
                        b'{"error":{"code":-32000,"message":"Concurrency limit exceeded"}}',
                    )
                )
            )

    def test_complete_cli_matrix_against_fake_and_request_budget(self):
        class FastClient(probe.Client):
            def open(self, *args, **kwargs):
                self.mcp_interval = 0
                return super().open(*args, **kwargs)

        for mode, expected in (("good", 0), ("get200", 1), ("buffer", 1)):
            with (
                self.subTest(mode=mode),
                server(mode) as (fake, _),
                tempfile.TemporaryDirectory() as directory,
            ):
                fake.rate_enabled = False
                client = FastClient(f"http://127.0.0.1:{fake.server_port}")
                suite = probe.Suite(
                    client, "linux", time.time() + 0.1, round_interval=0.3
                )
                real_rate = suite.rate

                def rate(fake=fake, run=real_rate):
                    with fake.guard:
                        fake.rate_enabled = True
                        fake.counts.clear()
                    run()

                suite.rate = rate
                output_path = Path(directory) / "outputs"
                output = io.StringIO()
                with (
                    mock.patch.object(probe, "Client", return_value=client),
                    mock.patch.object(probe, "Suite", return_value=suite),
                    mock.patch.object(
                        client,
                        "unknown_sni",
                        side_effect=lambda _, client=client: client.reserve(),
                    ),
                    mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}),
                    contextlib.redirect_stdout(output),
                ):
                    code = probe.main(
                        ["probe", "--source", "linux", "--epoch", str(suite.epoch)]
                    )
                self.assertEqual(code, expected, output.getvalue())
                self.assert_safe(output.getvalue())
                key, value = output_path.read_text().strip().split("=", 1)
                result = json.loads(value)
                self.assertEqual(key, "linux")
                self.assertEqual(result["ok"], mode == "good")
                self.assertTrue(result["samples_ok"])
                self.assertEqual(result["samples"], 18)
                self.assertLessEqual(result["requests"], probe.MAX_REQUESTS)
                self.assertGreater(result["requests"], 60)

    def test_socket_deadline_covers_stalled_headers(self):
        with server() as (_, client), mock.patch.object(probe, "TIMEOUT", 0.15):
            started = time.monotonic()
            with self.assertRaises((OSError, probe.http.client.HTTPException)):
                client.request("GET", "/synthetic-stall")
            self.assertLess(time.monotonic() - started, 0.5)

    def test_report_command_fails_for_missing_peer_without_a_secret(self):
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(probe.main(["report"]), 1)
        self.assertIn("FAIL", output.getvalue())
        self.assert_safe(output.getvalue())

    def test_optional_report_needs_no_secret(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(probe.alert(False))

    def test_workflow_is_manual_pinned_read_only_and_has_two_sources(self):
        workflow = json.loads(
            (ROOT / ".github/workflows/edge-acceptance.yml").read_text()
        )
        watchdog = json.loads(
            (ROOT / ".github/workflows/edge-watchdog.yml").read_text()
        )
        self.assertEqual(workflow["on"], {"workflow_dispatch": {}})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        jobs = workflow["jobs"]
        self.assertEqual(jobs["probe"]["strategy"]["max-parallel"], 2)
        self.assertFalse(jobs["probe"]["strategy"]["fail-fast"])
        matrix = jobs["probe"]["strategy"]["matrix"]["include"]
        self.assertEqual({entry["source"] for entry in matrix}, {"linux", "macos"})
        self.assertEqual(len({entry["runner"] for entry in matrix}), 2)
        for job in jobs.values():
            self.assertLessEqual(job["timeout-minutes"], 10)
            for step in job["steps"]:
                if "uses" in step:
                    self.assertEqual(step, watchdog["jobs"]["probe"]["steps"][0])
        self.assertEqual(jobs["report"]["if"], "${{ always() }}")
        self.assertIn("probe", jobs["report"]["needs"])
        self.assertEqual(set(jobs["probe"]["outputs"]), {"linux", "macos"})
        text = json.dumps(workflow)
        self.assertNotIn("continue-on-error", text)
        self.assertNotIn("GITHUB_TOKEN", text)
        self.assertEqual(text.count("secrets."), 1)
        policy = json.loads((ROOT / "scripts/public-paths.json").read_text())["files"]
        for path in (
            ".github/workflows/edge-acceptance.yml",
            "tools/edge-acceptance/probe.py",
            "tools/edge-acceptance/README.md",
            "tests/edge_acceptance_test.py",
        ):
            self.assertIn(path, policy)


if __name__ == "__main__":
    unittest.main()
