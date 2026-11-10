"""Offline sender checks. Every request is intercepted before network access."""

import contextlib
import hashlib
import hmac
import importlib.util
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "alert_sender", Path(__file__).resolve().parents[1] / "tools/alerts/send.py"
)
sender = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sender)
SECRET = "synthetic-sender-secret-DO-NOT-LOG"


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.body = b'{ "summary": "Synthetic test" }\n'
        self.event = Path(self.tmp.name) / "event.json"
        self.event.write_bytes(self.body)
        self.key = Path(self.tmp.name) / "secret"
        self.key.write_text(SECRET + "\n")

    def run_sender(self, extra=(), env=None, status=204, error=None):
        output, errors = io.StringIO(), io.StringIO()
        response = mock.MagicMock()
        response.__enter__.return_value.status = status
        opener = mock.Mock()
        opener.open.return_value = response
        opener.open.side_effect = error
        with (
            mock.patch.dict(os.environ, env or {}, clear=True),
            mock.patch.object(
                sender.urllib.request, "build_opener", return_value=opener
            ) as build,
            mock.patch.object(sender.time, "time", return_value=1800000000),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            code = sender.main(["--event", str(self.event), *extra])
        text = output.getvalue() + errors.getvalue()
        self.assertNotIn(SECRET, text)
        self.assertNotIn("sha256=", text)
        return code, text, opener, build

    def test_file_and_env_secret_sign_exact_bytes(self):
        for extra, env in [
            (["--secret-file", str(self.key)], {}),
            ([], {"OPENHRA_ALERT_SECRET": SECRET}),
        ]:
            code, text, opener, build = self.run_sender(extra, env)
            self.assertEqual(code, 0)
            self.assertEqual(text, "alert sender: accepted\n")
            request = opener.open.call_args.args[0]
            self.assertEqual(request.data, self.body)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.full_url, "https://plans.openhra.com/api/alerts")
            self.assertEqual(request.get_header("X-openhra-timestamp"), "1800000000")
            expected = (
                "sha256="
                + hmac.new(
                    SECRET.encode(), b"1800000000." + self.body, hashlib.sha256
                ).hexdigest()
            )
            self.assertEqual(request.get_header("X-openhra-signature"), expected)
            self.assertEqual(opener.open.call_args.kwargs, {"timeout": 10})
            self.assertIsInstance(build.call_args.args[0], sender.NoRedirect)

    def test_file_takes_precedence_over_environment(self):
        code, _, opener, _ = self.run_sender(
            ["--secret-file", str(self.key)],
            {"OPENHRA_ALERT_SECRET": "synthetic-other"},
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            opener.open.call_args.args[0].get_header("X-openhra-signature"),
            sender.sign(self.body, 1800000000, SECRET.encode()),
        )

    def test_invalid_inputs_do_not_attempt_network(self):
        for extra in [
            [],
            ["--secret-file", str(self.key) + "-missing"],
            ["--secret-file", str(self.key), "--url", "http://localhost/api/alerts"],
            [
                "--secret-file",
                str(self.key),
                "--url",
                "https://user:password@localhost/api/alerts",
            ],
            [
                "--secret-file",
                str(self.key),
                "--url",
                "https://localhost/api/alerts#fragment",
            ],
        ]:
            code, _, opener, build = self.run_sender(extra)
            self.assertEqual(code, 1)
            build.assert_not_called()
            opener.open.assert_not_called()
        for body in [b"{", b"[]", b"null", b" " * 8193, b"\xff"]:
            self.event.write_bytes(body)
            code, _, opener, _ = self.run_sender(["--secret-file", str(self.key)])
            self.assertEqual(code, 1)
            opener.open.assert_not_called()

    def test_stdin_and_size_boundary(self):
        self.event.write_bytes(b"{}" + b" " * 8190)
        self.assertEqual(self.run_sender(["--secret-file", str(self.key)])[0], 0)
        with mock.patch.object(
            sender.sys, "stdin", mock.Mock(buffer=io.BytesIO(self.body))
        ):
            self.assertEqual(
                self.run_sender(["--event", "-", "--secret-file", str(self.key)])[0], 0
            )

    def test_failures_are_sanitized_and_redirects_refused(self):
        for status in [200, 301, 409, 500]:
            self.assertEqual(
                self.run_sender(["--secret-file", str(self.key)], status=status)[0], 1
            )
        for error in [
            urllib.error.HTTPError("https://localhost", 401, SECRET, {}, None),
            urllib.error.URLError(SECRET),
            TimeoutError(SECRET),
        ]:
            code, text, _, _ = self.run_sender(
                ["--secret-file", str(self.key)], error=error
            )
            self.assertEqual(code, 1)
            self.assertNotIn(SECRET, text)
        self.assertIsNone(
            sender.NoRedirect().redirect_request(
                None, None, 307, None, {}, "https://localhost"
            )
        )


WORKFLOW = json.loads(
    (
        Path(__file__).resolve().parents[1] / ".github/workflows/edge-watchdog.yml"
    ).read_text()
)
HEARTBEAT_STEP = WORKFLOW["jobs"]["probe"]["steps"][2]
HEARTBEAT_SCRIPT = (
    HEARTBEAT_STEP["run"].split("python3 - <<'PY'\n", 1)[1].rsplit("PY\n", 1)[0]
)


class HeartbeatWatchdogTests(unittest.TestCase):
    def exercise(
        self,
        age=120,
        previous="success",
        query_status=200,
        event_status=204,
        reply=None,
        threshold=None,
        script=HEARTBEAT_SCRIPT,
        query_error=False,
        history_error=False,
        enabled="on",
        storage="durable-shared",
    ):
        events, queries, requests = [], [], []
        env = {
            "OPENHRA_ALERT_SECRET": SECRET,
            "GITHUB_TOKEN": "synthetic-github-token-DO-NOT-LOG",
            "GITHUB_REPOSITORY": "synthetic/fixture",
            "GITHUB_RUN_ID": "2",
        }
        if threshold is not None:
            env["OPENHRA_HEARTBEAT_MAX_AGE_SECONDS"] = threshold
        if enabled is not None:
            env["OPENHRA_HEARTBEAT_CHECK"] = enabled

        def response(status, value):
            result = mock.MagicMock()
            result.status = status
            result.read.side_effect = io.BytesIO(json.dumps(value).encode()).read
            result.__enter__.return_value = result
            return result

        def transport(request, timeout):
            requests.append((request, timeout))
            if request.full_url == "https://plans.openhra.com/api/alerts":
                value = json.loads(request.data)
                if value.get("action") == "heartbeat-age":
                    queries.append(value)
                    if query_error:
                        raise TimeoutError(SECRET)
                    return response(
                        query_status,
                        {"storage_kind": storage, "age_seconds": age}
                        if reply is None
                        else reply,
                    )
                events.append(value)
                return response(event_status, None)
            if history_error:
                raise TimeoutError(SECRET)
            if request.full_url.endswith(
                "/actions/workflows/edge-watchdog.yml/runs?per_page=10"
            ):
                return response(
                    200,
                    {
                        "workflow_runs": [
                            {"id": 2, "status": "completed"},
                            {"id": 3, "status": "in_progress"},
                            {"id": 1, "status": "completed"},
                        ]
                    },
                )
            if request.full_url.endswith("/actions/runs/1/jobs?per_page=100"):
                return response(
                    200,
                    {
                        "jobs": [
                            {
                                "steps": [
                                    {
                                        "name": "Check public edge and signed alert delivery",
                                        "conclusion": "failure",
                                    },
                                    {
                                        "name": HEARTBEAT_STEP["name"],
                                        "conclusion": previous,
                                    },
                                ]
                            }
                        ]
                    },
                )
            raise AssertionError("unexpected watchdog request")

        output, errors = io.StringIO(), io.StringIO()
        opener = mock.Mock(open=transport)
        with (
            tempfile.TemporaryDirectory(prefix="synthetic-heartbeat-") as directory,
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.dict(sys.modules, {"send": sender}),
            mock.patch.object(
                sys,
                "path",
                [str(Path(__file__).resolve().parents[1] / "tools/alerts"), *sys.path],
            ),
            mock.patch("urllib.request.build_opener", return_value=opener) as build,
            mock.patch(
                "socket.create_connection",
                side_effect=AssertionError("network forbidden"),
            ),
            mock.patch("time.time", return_value=1800000000),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            code = 0
            script_path = Path(directory) / "watchdog.py"
            script_path.write_text(script)
            try:
                runpy.run_path(str(script_path), run_name="__main__")
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else 1
        text = output.getvalue() + errors.getvalue()
        for sensitive in (SECRET, env["GITHUB_TOKEN"], "sha256="):
            self.assertNotIn(sensitive, text)
        if build.called:
            self.assertIsInstance(build.call_args.args[0], sender.NoRedirect)
        else:
            self.assertEqual(requests, [])
        ids = []
        for request, timeout in requests:
            self.assertEqual(timeout, 10)
            if request.data is None:
                self.assertEqual(
                    request.get_header("Authorization"), "Bearer " + env["GITHUB_TOKEN"]
                )
                continue
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.get_header("X-openhra-timestamp"), "1800000000")
            expected = (
                "sha256="
                + hmac.new(
                    SECRET.encode(), b"1800000000." + request.data, hashlib.sha256
                ).hexdigest()
            )
            self.assertEqual(request.get_header("X-openhra-signature"), expected)
            self.assertIsNone(request.get_header("Authorization"))
            ids.append(json.loads(request.data)["event_id"])
        self.assertEqual(
            len(ids), len(set(ids)), "queries and events need distinct replay IDs"
        )
        if not events:
            self.assertEqual(code, 0)
            self.assertIn("::notice::", text)
        for value in events:
            self.assertEqual(value["source"], "watchdog")
            self.assertEqual(value["check"], "edge-watchdog.heartbeat")
        return code, events, queries

    def test_workflow_runs_heartbeat_even_after_edge_failure(self):
        self.assertEqual(
            HEARTBEAT_STEP["if"],
            "${{ !cancelled() && vars.OPENHRA_HEARTBEAT_CHECK == 'on' }}",
        )
        self.assertEqual(
            HEARTBEAT_STEP["env"]["OPENHRA_HEARTBEAT_CHECK"],
            "${{ vars.OPENHRA_HEARTBEAT_CHECK }}",
        )
        self.assertEqual(
            HEARTBEAT_STEP["env"]["OPENHRA_ALERT_SECRET"],
            "${{ secrets.OPENHRA_ALERT_SECRET }}",
        )
        self.assertEqual(
            HEARTBEAT_STEP["env"]["OPENHRA_HEARTBEAT_MAX_AGE_SECONDS"],
            "${{ vars.OPENHRA_HEARTBEAT_MAX_AGE_SECONDS || '1800' }}",
        )

    def test_default_off_makes_no_heartbeat_call(self):
        for enabled in (None, "", "off", "ON"):
            self.assertEqual(self.exercise(enabled=enabled, age=1801), (0, [], []))

    def test_non_durable_storage_never_alerts(self):
        for storage in ("instance-memory", "unknown", "durable", None, True):
            for age in (0, 1801, None, "invalid"):
                with self.subTest(storage=storage, age=age):
                    code, events, queries = self.exercise(storage=storage, age=age)
                    self.assertEqual((code, events), (0, []))
                    self.assertEqual(len(queries), 1)
        for case in (
            {"reply": {}},
            {"reply": []},
            {"reply": {"age_seconds": 1801}},
            {"query_status": 401},
            {"query_status": 409},
            {"query_status": 503},
            {"query_error": True},
            {"reply": {"storage_kind": "durable-shared", "extra": "x" * 2048}},
            {"storage": "instance-memory", "threshold": "invalid"},
        ):
            with self.subTest(case=case):
                code, events, _ = self.exercise(**case)
                self.assertEqual((code, events), (0, []))

    def test_fresh_boundary_and_configurable_threshold(self):
        for age, threshold in [(0, None), (120, None), (1800, None), (1801, "3600")]:
            code, events, queries = self.exercise(age=age, threshold=threshold)
            self.assertEqual(code, 0)
            self.assertEqual([value["severity"] for value in events], ["info"])
            self.assertEqual(events[0]["status"], "ok")
            self.assertEqual(len(queries), 1)
            self.assertEqual(set(queries[0]), {"action", "event_id"})

    def test_stale_missing_malformed_and_rejected_reads_warn_and_fail(self):
        cases = [
            {"age": 1801},
            {"age": None},
            {"age": -1},
            {"age": True},
            {"age": "0"},
            {"reply": {"storage_kind": "durable-shared", "age_seconds": 0, "extra": 1}},
            {"threshold": "0"},
            {"threshold": "-1"},
            {"threshold": "bad"},
            {"threshold": "1.5"},
        ]
        for case in cases:
            with self.subTest(case=case):
                code, events, _ = self.exercise(**case)
                self.assertEqual(code, 1)
                self.assertEqual([value["severity"] for value in events], ["warning"])
                self.assertEqual(events[0]["status"], "fail")

    def test_recovery_uses_previous_heartbeat_step(self):
        for previous in ("failure", "timed_out"):
            code, events, _ = self.exercise(previous=previous)
            self.assertEqual(code, 0)
            self.assertEqual(events[0]["severity"], "recovery")
            self.assertEqual(events[0]["summary"], "Validator heartbeat recovered")
        for previous in ("success", "skipped", None):
            self.assertEqual(self.exercise(previous=previous)[1][0]["severity"], "info")
        self.assertEqual(self.exercise(history_error=True)[0], 0)
        self.assertEqual(self.exercise(event_status=500)[0], 1)

    def test_planted_workflow_mutants_fail_contract(self):
        cases = [
            ("0 <= age <= threshold", "True", {"age": 1801}, 1, "warning"),
            ("type(age) is int", "True", {"age": True}, 1, "warning"),
            ("'1800'", "'18000'", {"age": 1801}, 1, "warning"),
            ("fresh = False", "fresh = True", {"threshold": "invalid"}, 1, "warning"),
            (
                "'recovery' if recovered else 'info'",
                "'info'",
                {"previous": "failure"},
                0,
                "recovery",
            ),
        ]
        for before, after, options, expected_code, expected_severity in cases:
            with self.subTest(mutation=before):
                self.assertIn(before, HEARTBEAT_SCRIPT)
                mutated = HEARTBEAT_SCRIPT.replace(before, after)
                with self.assertRaises(AssertionError):
                    code, events, _ = self.exercise(script=mutated, **options)
                    self.assertEqual(code, expected_code)
                    self.assertEqual(events[0]["severity"], expected_severity)

    def test_planted_enablement_and_storage_mutants_fail_contract(self):
        for before, after, options, expected in (
            (
                "os.environ.get('OPENHRA_HEARTBEAT_CHECK') != 'on'",
                "False",
                {"enabled": None, "age": 1801},
                (0, [], []),
            ),
            (
                "evidence.get('storage_kind') != 'durable-shared'",
                "False",
                {"storage": "instance-memory", "age": 1801},
                None,
            ),
        ):
            self.assertIn(before, HEARTBEAT_SCRIPT)
            with self.assertRaises(AssertionError):
                code, events, queries = self.exercise(
                    script=HEARTBEAT_SCRIPT.replace(before, after), **options
                )
                if expected is None:
                    self.assertEqual((code, events), (0, []))
                else:
                    self.assertEqual((code, events, queries), expected)


if __name__ == "__main__":
    unittest.main()
