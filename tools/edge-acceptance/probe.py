#!/usr/bin/env python3
"""Run the manual public edge matrix. Output contains checks and counts only."""

import argparse
import datetime
import http.client
import json
import os
import socket
import ssl
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

TARGET = "https://openplans.openhra.com"
ORIGIN = TARGET
MODERN = "2026-07-28"
LEGACY = "2025-11-25"
MAX_REQUESTS = 80  # Two sources, plus at most one optional signed report.
MAX_RESPONSE = 262144
MAX_CATALOG_RESPONSE = (
    8 * 1024 * 1024
)  # A native 50-plan page includes source evidence.
TIMEOUT = 10
ROUNDS = 4
CONCURRENCY_WORKERS = 4  # The edge permits four simultaneous /mcp calls per source.
ROUND_INTERVAL = 6
MIN_PROGRESS_LEAD = 0.025
RATE_REQUESTS = 19
RATE_WORKERS = 3  # Below nginx's four simultaneous /mcp connections per source.


class CheckFailed(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise CheckFailed(reason)


def envelope(method, params=None, revision=MODERN, progress=None, request_id=1):
    params = dict(params or {})
    if revision == MODERN:
        params["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": MODERN,
            "io.modelcontextprotocol/clientInfo": {
                "name": "synthetic-edge-acceptance",
                "version": "1",
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        }
    if progress is not None:
        params.setdefault("_meta", {})["progressToken"] = progress
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": revision,
        "Mcp-Method": method,
    }
    if method == "tools/call":
        headers["Mcp-Name"] = params["name"]
    return json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    ).encode(), headers


@dataclass
class Reply:
    status: int
    headers: dict
    body: bytes

    def json(self):
        return json.loads(self.body)


def event_message(event):
    lines = [
        line[5:].lstrip() for line in event.split(b"\n") if line.startswith(b"data:")
    ]
    return json.loads(b"\n".join(lines)) if lines else None


def rpc_result(reply, request_id=1, allow_sse=False):
    require(reply.status == 200, "expected HTTP 200")
    content_type = reply.headers.get("content-type", "").split(";")[0]
    if allow_sse and content_type == "text/event-stream":
        # Legacy stateless responses may use SSE even for a single result.
        events = reply.body.replace(b"\r\n", b"\n").split(b"\n\n")
        require(not events[-1].strip(), "incomplete SSE response")
        messages = [
            message
            for event in events[:-1]
            if (message := event_message(event)) is not None
        ]
        require(
            all(isinstance(m, dict) and m.get("jsonrpc") == "2.0" for m in messages),
            "invalid SSE RPC envelope",
        )
        results = [m for m in messages if "id" in m]
        require(len(results) == 1, "expected one SSE result")
        value = results[0]
    else:
        require(content_type == "application/json", "expected JSON")
        value = reply.json()
    require(
        value.get("jsonrpc") == "2.0" and value.get("id") == request_id,
        "response envelope or request ID differs",
    )
    require(
        "error" not in value and isinstance(value.get("result"), dict),
        "RPC returned an error",
    )
    return value["result"]


def tool_result(result):
    require(result.get("isError") is not True, "tool returned an error")
    value = result.get("structuredContent", {})
    require(
        value.get("status") == "ok" and value.get("error") is None,
        "tool did not return structured status ok",
    )
    require(isinstance(value.get("data"), dict), "tool data is missing")


def retry_after(reply):
    value = reply.headers.get("retry-after", "")
    return reply.status == 429 and value.isdigit() and 0 < int(value) <= 300


def concurrency_error(reply):
    if not retry_after(reply):
        return False
    try:
        error = reply.json().get("error", {})
        return (
            error.get("code") == -32000
            and error.get("message") == "Concurrency limit exceeded"
        )
    except (ValueError, AttributeError):
        return False


def error_kind(reply):
    """Only fixed labels leave the client, never remote error text or bodies."""
    try:
        error = reply.json().get("error")
        if isinstance(error, dict):
            if (
                error.get("code") == -32000
                and error.get("message") == "Rate limit exceeded"
            ):
                return "app-rate"
            return "rpc-error"
        return "json-response"
    except (ValueError, AttributeError):
        return "non-json-response"


class Client:
    """No redirects, cookies or retries. Each socket has a deadline and byte cap."""

    def __init__(self, target=TARGET, extra_headers=None):
        parsed = urlsplit(target)
        require(
            parsed.scheme in ("http", "https") and parsed.hostname,
            "invalid probe target",
        )
        require(
            not parsed.username and not parsed.password and parsed.path in ("", "/"),
            "invalid target",
        )
        require(
            parsed.scheme == "https" or parsed.hostname == "127.0.0.1",
            "HTTP is for loopback tests only",
        )
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.secure = parsed.scheme == "https"
        self.extra_headers = extra_headers or {}
        self.requests = 0
        self.mcp_interval = 0
        self.next_mcp = 0
        self.lock = threading.Lock()

    def reserve(self):
        with self.lock:
            require(self.requests < MAX_REQUESTS, "request budget exhausted")
            self.requests += 1

    def open(self, method, path, body=None, headers=None, plain=False):
        self.reserve()
        if path == "/mcp" and self.mcp_interval:
            with self.lock:
                due = max(time.monotonic(), self.next_mcp)
                self.next_mcp = due + self.mcp_interval
            time.sleep(max(0, due - time.monotonic()))
        started = time.monotonic()
        cls = (
            http.client.HTTPSConnection
            if self.secure and not plain
            else http.client.HTTPConnection
        )
        conn = cls(
            self.host, 80 if plain and self.secure else self.port, timeout=TIMEOUT
        )
        deadline = None
        try:
            conn.connect()
            sock = conn.sock

            def expire():
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            deadline = threading.Timer(
                max(0.001, TIMEOUT - (time.monotonic() - started)), expire
            )
            deadline.daemon = True
            deadline.start()
            sock.settimeout(max(0.001, TIMEOUT - (time.monotonic() - started)))
            conn.request(
                method,
                path,
                body,
                {**self.extra_headers, **(headers or {}), "Connection": "close"},
            )
            response = conn.getresponse()
            return conn, response, sock, started, deadline
        except Exception:
            if deadline is not None:
                deadline.cancel()
            conn.close()
            raise

    def request(
        self, method, path, body=None, headers=None, plain=False, *, max_response=None
    ):
        max_response = MAX_RESPONSE if max_response is None else max_response
        conn, response, sock, started, deadline = self.open(
            method, path, body, headers, plain
        )
        try:
            data = bytearray()
            # The final Content-Length read may close the response and release sock.
            while not response.isclosed():
                left = TIMEOUT - (time.monotonic() - started)
                require(left > 0, "response deadline exceeded")
                sock.settimeout(left)
                part = response.read1(min(65536, max_response + 1 - len(data)))
                if not part:
                    break
                data.extend(part)
                require(len(data) <= max_response, "response byte cap exceeded")
            return Reply(
                response.status,
                {k.lower(): v for k, v in response.getheaders()},
                bytes(data),
            )
        finally:
            deadline.cancel()
            response.close()
            conn.close()

    def rpc(self, method, params=None, revision=MODERN, headers=None):
        body, base = envelope(method, params, revision)
        return self.request("POST", "/mcp", body, {**base, **(headers or {})})

    def stream(self, name, arguments, token, disconnect=False, incremental=True):
        body, headers = envelope(
            "tools/call", {"name": name, "arguments": arguments}, progress=token
        )
        headers["Accept-Encoding"] = "gzip"
        conn, response, sock, started, deadline = self.open(
            "POST", "/mcp", body, headers
        )
        try:
            reply = Reply(
                response.status, {k.lower(): v for k, v in response.getheaders()}, b""
            )
            if response.status != 200:
                # Error bodies are parsed only to distinguish the app from the edge.
                reply.body = response.read(MAX_RESPONSE + 1)
                require(len(reply.body) <= MAX_RESPONSE, "response byte cap exceeded")
                return reply, None
            require(
                reply.headers.get("content-type", "").split(";")[0]
                == "text/event-stream",
                "expected request-scoped SSE",
            )
            require(
                reply.headers.get("x-accel-buffering") == "no",
                "SSE buffering header missing",
            )
            require(
                reply.headers.get("content-encoding") in (None, "identity"),
                "SSE must not be compressed",
            )
            pending = b""
            total = 0
            progress_at = None
            final_at = None
            while True:
                left = TIMEOUT - (time.monotonic() - started)
                require(left > 0, "stream deadline exceeded")
                sock.settimeout(left)
                chunk = response.read1(65536)
                arrived = time.monotonic()
                if not chunk:
                    break
                total += len(chunk)
                require(total <= MAX_RESPONSE, "stream byte cap exceeded")
                pending = (pending + chunk).replace(b"\r\n", b"\n")
                # Parse the entire read before allowing disconnect, so coalesced finals cannot pass.
                while b"\n\n" in pending:
                    event, pending = pending.split(b"\n\n", 1)
                    message = event_message(event)
                    if message is None:
                        continue
                    require(message.get("jsonrpc") == "2.0", "invalid SSE RPC envelope")
                    if message.get("method") == "notifications/progress":
                        require(
                            message.get("params", {}).get("progressToken") == token,
                            "progress token differs",
                        )
                        progress_at = progress_at or arrived
                    elif "id" in message:
                        require(
                            message.get("id") == 1 and "error" not in message,
                            "SSE result differs or failed",
                        )
                        tool_result(message.get("result", {}))
                        final_at = arrived
                if disconnect and progress_at is not None:
                    require(final_at is None, "stream completed before disconnect")
                    # Closing both wrappers tears down the request, without reading the final event.
                    return reply, {"disconnected": True}
                if final_at is not None:
                    require(progress_at is not None, "progress event missing")
                    if incremental:
                        require(
                            final_at - progress_at >= MIN_PROGRESS_LEAD,
                            "no measurable incremental progress before final result",
                        )
                    return reply, {"lead_ms": round((final_at - progress_at) * 1000)}
            raise CheckFailed("stream ended without required progress and result")
        finally:
            deadline.cancel()
            response.close()
            conn.close()

    def unknown_host(self):
        try:
            self.request("GET", "/healthz", headers={"Host": "edge-acceptance.invalid"})
        except (http.client.RemoteDisconnected, ConnectionResetError):
            return
        raise CheckFailed("unknown Host received an HTTP response")

    def unknown_sni(self, name):
        self.reserve()
        context = ssl.create_default_context()
        # Do not mistake a hostname verification failure for SNI refusal.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((self.host, self.port), timeout=TIMEOUT) as raw:
            try:
                with context.wrap_socket(raw, server_hostname=name):
                    pass
            except ssl.SSLError as error:
                require(
                    getattr(error, "reason", None)
                    in (
                        "TLSV1_UNRECOGNIZED_NAME",
                        "SSLV3_ALERT_HANDSHAKE_FAILURE",
                        "TLSV1_ALERT_INTERNAL_ERROR",
                        "UNEXPECTED_EOF_WHILE_READING",
                    ),
                    "unexpected TLS failure",
                )
                return
            except ConnectionResetError:
                return
        raise CheckFailed("unknown or absent SNI completed a TLS handshake")


class Suite:
    def __init__(self, client, source, epoch, round_interval=ROUND_INTERVAL):
        self.client = client
        self.source = source
        self.epoch = epoch
        self.round_interval = round_interval
        self.rows = []
        self.denials = 0
        self.samples = 0
        self.sample_ok = False
        self.run_id = uuid.uuid4().hex[:12]

    def check(self, name, operation, known=False):
        try:
            operation()
        except CheckFailed as error:
            self.rows.append((name, False, str(error), known))
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RuntimeError,
            http.client.HTTPException,
        ):
            # Exception messages can contain remote data, URLs or TLS names.
            self.rows.append(
                (name, False, "request failed or response malformed", known)
            )
        else:
            self.rows.append((name, True, "", known))

    def concurrency(self):
        require(
            0 < self.epoch - time.time() <= 360,
            "rendezvous missing or late; rerun all jobs, including preparation and both sources",
        )
        for round_id in range(ROUNDS):
            due = self.epoch + round_id * self.round_interval
            while time.time() < due:
                time.sleep(min(0.1, due - time.time()))
            require(time.time() - due < 0.5, "missed synchronized concurrency round")
            gate = threading.Barrier(CONCURRENCY_WORKERS)

            def sample(index, gate=gate, round_id=round_id):
                gate.wait(timeout=TIMEOUT)
                args = {
                    # Plan discovery reads the scoped catalog before filtering.
                    # A unique query bypasses the generation-keyed response cache.
                    "query": f"synthetic-edge-{self.source}-{self.run_id}-{round_id}-{index}",
                    "entity": "plan",
                    "location": {"county": "48201"},
                    "year": 2026,
                    "limit": 1,
                }
                started = time.monotonic()
                reply, proof = self.client.stream(
                    "search",
                    args,
                    f"{self.source}-{round_id}-{index}",
                    incremental=False,
                )
                return reply, proof, round((time.monotonic() - started) * 1000)

            with ThreadPoolExecutor(max_workers=CONCURRENCY_WORKERS) as pool:
                replies = list(pool.map(sample, range(CONCURRENCY_WORKERS)))
            for index, (reply, proof, elapsed_ms) in enumerate(replies):
                self.samples += 1
                if concurrency_error(reply):
                    self.denials += 1
                else:
                    require(
                        reply.status == 200 and proof is not None,
                        "sample failed without app concurrency error: "
                        f"round={round_id + 1} sample={index + 1} "
                        f"HTTP={reply.status} kind={error_kind(reply)} elapsed_ms={elapsed_ms}",
                    )
        self.sample_ok = True

    def basics(self):
        c = self.client

        def health():
            reply = c.request("GET", "/healthz")
            require(
                reply.status == 200 and reply.json().get("db") == "ok",
                "health is not db=ok",
            )

        self.check("trusted TLS and health", health)

        def redirect():
            reply = c.request("HEAD", "/healthz", plain=True)
            require(
                reply.status == 308
                and reply.headers.get("location") == TARGET + "/healthz",
                "canonical HTTP redirect differs",
            )

        self.check("canonical HTTP redirect", redirect)

        def catalog():
            reply = c.request(
                "GET",
                "/v1/plans?county=48201&year=2026",
                max_response=MAX_CATALOG_RESPONSE,
            )
            require(
                reply.status == 200 and bool(reply.json().get("plans")),
                "catalog query returned no plans",
            )

        self.check("native public catalog", catalog)

        for revision in (MODERN, LEGACY):

            def initialize(revision=revision):
                # Modern MCP replaces initialize with metadata plus server/discover.
                if revision == MODERN:
                    result = rpc_result(c.rpc("server/discover"))
                    require(bool(result), "modern discovery result is empty")
                else:
                    result = rpc_result(
                        c.rpc(
                            "initialize",
                            {
                                "protocolVersion": LEGACY,
                                "clientInfo": {
                                    "name": "synthetic-edge-acceptance",
                                    "version": "1",
                                },
                                "capabilities": {},
                            },
                            LEGACY,
                        ),
                        allow_sse=True,
                    )
                    require(
                        result.get("protocolVersion") == LEGACY,
                        "legacy negotiation differs",
                    )

            self.check(revision + " initialize/discover", initialize)

            if revision == LEGACY:

                def initialized():
                    body = b'{"jsonrpc":"2.0","method":"notifications/initialized"}'
                    _, headers = envelope("notifications/initialized", revision=LEGACY)
                    reply = c.request("POST", "/mcp", body, headers)
                    require(
                        reply.status in (200, 202, 204),
                        "initialized notification refused",
                    )

                self.check("legacy initialized notification", initialized)

            def listing(revision=revision):
                result = rpc_result(
                    c.rpc("tools/list", revision=revision), allow_sse=revision == LEGACY
                )
                names = {tool["name"] for tool in result.get("tools", [])}
                require("lookup_geography" in names, "catalog tool missing")
                require(
                    not names & {"quote_premiums", "estimate_premiums"},
                    "personalized or removed tool advertised",
                )

            self.check(revision + " list catalog tools", listing)

            def call(revision=revision):
                reply = c.rpc(
                    "tools/call",
                    {"name": "lookup_geography", "arguments": {"zip": "77002"}},
                    revision,
                )
                tool_result(rpc_result(reply, allow_sse=revision == LEGACY))

            label = " JSON call" if revision == MODERN else " tool call (JSON or SSE)"
            self.check(revision + label, call)

        def cors():
            reply = c.rpc(
                "tools/call",
                {"name": "lookup_geography", "arguments": {"zip": "77002"}},
                headers={"Origin": ORIGIN},
            )
            tool_result(rpc_result(reply))
            require(
                reply.headers.get("access-control-allow-origin") == ORIGIN,
                "allowed-Origin POST lacks ACAO",
            )
            exposed = {
                v.strip().lower()
                for v in reply.headers.get("access-control-expose-headers", "").split(
                    ","
                )
            }
            require(
                {"www-authenticate", "retry-after"} <= exposed,
                "allowed-Origin POST lacks exposed headers",
            )
            require(
                "origin"
                in {
                    v.strip().lower() for v in reply.headers.get("vary", "").split(",")
                },
                "POST must vary by Origin",
            )

        self.check("allowed-Origin POST headers", cors, known=True)

        for method in ("GET", "DELETE"):

            def denied(method=method):
                reply = c.request(method, "/mcp")
                require(reply.status == 405, "method is not denied with 405")

            self.check(method + " /mcp is 405", denied)

        def preflight():
            reply = c.request(
                "OPTIONS",
                "/mcp",
                headers={
                    "Origin": ORIGIN,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type, MCP-Protocol-Version, Mcp-Method, Mcp-Name, Accept",
                },
            )
            require(
                reply.status == 204
                and reply.headers.get("access-control-allow-origin") == ORIGIN,
                "allowed preflight differs",
            )
            require(
                reply.headers.get("access-control-allow-methods") == "POST",
                "preflight methods differ",
            )
            allowed = {
                v.strip().lower()
                for v in reply.headers.get("access-control-allow-headers", "").split(
                    ","
                )
            }
            require(
                {
                    "content-type",
                    "mcp-protocol-version",
                    "mcp-method",
                    "mcp-name",
                    "accept",
                }
                <= allowed,
                "preflight header allowlist incomplete",
            )

        self.check("OPTIONS exact allowlist", preflight)
        for origin in (
            "https://edge-acceptance.invalid",
            "http://openplans.openhra.com",
            "https://openplans.openhra.com:444",
        ):

            def hostile(origin=origin):
                for method in ("OPTIONS", "POST"):
                    body, headers = envelope("tools/list")
                    reply = c.request(
                        method,
                        "/mcp",
                        body if method == "POST" else None,
                        {**headers, "Origin": origin},
                    )
                    require(reply.status == 403, "hostile Origin did not return 403")
                    require(
                        "access-control-allow-origin" not in reply.headers,
                        "hostile Origin received ACAO",
                    )

            label = ("host", "scheme", "port")[
                (
                    "https://edge-acceptance.invalid",
                    "http://openplans.openhra.com",
                    "https://openplans.openhra.com:444",
                ).index(origin)
            ]
            self.check("hostile Origin " + label, hostile)

        def oversized():
            reply = c.request(
                "POST", "/mcp", b" " * 65537, {"Content-Type": "application/json"}
            )
            require(reply.status == 413, "65537-byte body did not return 413")

        self.check("body over 64 KiB", oversized)

        def forwarding():
            reply = c.rpc(
                "tools/call",
                {"name": "lookup_geography", "arguments": {"zip": "77002"}},
                headers={
                    "X-Forwarded-For": "192.0.2.77, 198.51.100.77",
                    "X-Forwarded-Proto": "http",
                    "X-Forwarded-Host": "edge-acceptance.invalid",
                    "X-Forwarded-Port": "9",
                },
            )
            tool_result(rpc_result(reply))

        self.check("forged forwarding preserves catalog call", forwarding)

        paths = (
            "/v1/premium-estimates",
            "/v1/premium-estimates/",
            "/v1/benchmark/",
            "/v1/cache-stats",
            "/v1/cache-stats/",
            "/compat/v1/plans/medical/search",
            "/.env",
            "/.git/config",
            "/api/v1/repos",
            "/user/login",
        )
        for path in paths:

            def hidden(path=path):
                reply = c.request("GET", path)
                require(reply.status == 404, "protected path did not return 404")

            self.check("denied " + path, hidden)
        self.check("GET /v1/benchmark", self.public_benchmark)
        self.check("GET /compat/v1/carriers", self.compat_carriers)
        self.check("POST /compat/v1/plans/medical/search", self.compat_search)
        for path in (
            "/v1/premium-estimates",
            "/v1/premium-estimates/",
        ):

            def post_hidden(path=path):
                reply = c.request(
                    "POST", path, b"{}", {"Content-Type": "application/json"}
                )
                require(reply.status == 404, "protected POST did not return 404")

            self.check("denied POST " + path, post_hidden)
        self.check("unknown Host gets no HTTP response", c.unknown_host)
        self.check(
            "unknown SNI refuses handshake",
            lambda: c.unknown_sni("edge-acceptance.invalid"),
        )
        self.check("absent SNI refuses handshake", lambda: c.unknown_sni(None))

    def public_benchmark(self):
        reply = self.client.request(
            "GET", "/v1/benchmark?county=48201&year=2026&ages=40"
        )
        require(reply.status == 200, "benchmark did not return HTTP 200")
        value = reply.json()
        require(isinstance(value, dict), "benchmark response is not an object")
        require(
            isinstance(value.get("status"), str)
            and isinstance(value.get("benchmark_plan_ids"), list)
            and isinstance(value.get("lowest_silver_plans"), list),
            "benchmark response shape is incomplete",
        )

    def compat_carriers(self):
        reply = self.client.request(
            "GET", "/compat/v1/carriers?state=TX&year=2026&page=1&per_page=1"
        )
        require(reply.status == 200, "compatibility carriers did not return HTTP 200")
        value = reply.json()
        require(
            isinstance(value, dict)
            and isinstance(value.get("carriers"), list)
            and isinstance(value.get("meta"), dict)
            and type(value["meta"].get("total")) is int
            and value["meta"]["total"] >= 0,
            "compatibility carriers response shape is incomplete",
        )

    def compat_search(self):
        reply = self.client.request(
            "POST",
            "/compat/v1/plans/medical/search",
            json.dumps(
                {
                    "fips_code": "48201",
                    "market": "individual",
                    "applicants": [{"age": 35, "smoker": False, "child": False}],
                    "per_page": 1,
                }
            ).encode(),
            {"Content-Type": "application/json"},
        )
        require(reply.status == 200, "compatibility search did not return HTTP 200")
        value = reply.json()
        require(
            isinstance(value, dict)
            and isinstance(value.get("plans"), list)
            and isinstance(value.get("meta"), dict)
            and type(value["meta"].get("total")) is int
            and value["meta"]["total"] >= 0,
            "compatibility search response shape is incomplete",
        )

    def streaming(self):
        def stream(disconnect):
            # Cold plan reads do measurable work; empty name searches often finish
            # before the first packet. Distinct limits avoid cross-runner cache hits.
            limit = (1 if self.source == "linux" else 3) + int(disconnect)
            reply, proof = self.client.stream(
                "search_plans",
                {"location": {"county": "48201"}, "year": 2026, "limit": limit},
                "synthetic-progress-" + self.source,
                disconnect,
            )
            require(reply.status == 200 and proof is not None, "SSE request failed")

        self.check("progress SSE arrives incrementally", lambda: stream(False))
        self.check("client disconnects mid-SSE", lambda: stream(True))
        self.check(
            "request succeeds after disconnect",
            lambda: rpc_result(self.client.rpc("tools/list")),
        )

    def rate(self):
        # One bounded burst fills the real bucket, then rotates forged headers.
        # Fresh serial TLS requests can refill a 1r/s + burst=10 bucket indefinitely.
        replies = []

        def exhaust():
            def attempt(i):
                forged = i >= RATE_REQUESTS - RATE_WORKERS
                reply = self.client.rpc(
                    "tools/list",
                    headers={
                        "X-Forwarded-For": f"192.0.2.{i + 1}",
                        "X-Real-IP": f"192.0.2.{i + 1}",
                        "X-Forwarded-Proto": "https",
                        "X-Forwarded-Host": "openplans.openhra.com",
                        "X-Forwarded-Port": "443",
                    }
                    if forged
                    else {},
                )
                return forged, reply

            with ThreadPoolExecutor(max_workers=RATE_WORKERS) as pool:
                split = RATE_REQUESTS - RATE_WORKERS
                replies.extend(pool.map(attempt, range(split)))
                replies.extend(pool.map(attempt, range(split, RATE_REQUESTS)))
            for _, reply in replies:
                if reply.status == 429:
                    require(
                        retry_after(reply), "rate response lacks bounded Retry-After"
                    )
                    require(
                        not concurrency_error(reply),
                        "rate burst hit app concurrency instead",
                    )
                else:
                    rpc_result(reply)
            require(
                any(not forged and reply.status == 429 for forged, reply in replies),
                "bounded burst did not observe rate 429",
            )

        self.check("source rate 429 and Retry-After", exhaust)

        def forged():
            require(bool(self.rows[-1][1]), "source throttling was not observed")
            require(
                any(forged and retry_after(reply) for forged, reply in replies),
                "rotated forwarded addresses escaped source throttling",
            )

        self.check("forwarded addresses cannot evade source rate", forged)

    def report(self):
        print("| Check | Result | Detail |")
        print("| --- | --- | --- |")
        for name, ok, detail, known in self.rows:
            if known and not ok:
                detail = "Tracked MCP3b known failure; " + detail
            print(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
        print(
            f"requests: {self.client.requests}/{MAX_REQUESTS}; app concurrency denials: {self.denials}"
        )
        print(
            "Host follow-up: confirm SQL cancellation and retained-log privacy after this run."
        )
        return {
            "source": self.source,
            "ok": all(row[1] for row in self.rows),
            "samples_ok": self.sample_ok,
            "samples": self.samples,
            "app_denials": self.denials,
            "requests": self.client.requests,
            "failed": sum(not row[1] for row in self.rows),
        }

    def run(self):
        # Sampling starts with fresh buckets. Other checks precede the final rate burst.
        self.check("synchronized four-call catalog rounds", self.concurrency)
        self.client.mcp_interval = 1.1
        self.basics()
        self.streaming()
        self.client.mcp_interval = 0
        self.rate()
        return self.report()


def aggregate(reports):
    require(
        isinstance(reports, dict) and set(reports) == {"linux", "macos"},
        "both runner reports are required",
    )
    for source in ("linux", "macos"):
        report = json.loads(reports[source])
        require(report.get("source") == source, "runner report source differs")
        require(
            type(report.get("ok")) is bool and type(report.get("samples_ok")) is bool,
            "invalid report status",
        )
        require(
            all(
                type(report.get(key)) is int
                for key in ("samples", "app_denials", "requests", "failed")
            ),
            "invalid report counters",
        )
        require(
            0
            <= report["app_denials"]
            <= report["samples"]
            <= ROUNDS * CONCURRENCY_WORKERS,
            "invalid concurrency counts",
        )
        require(
            0 < report["requests"] <= MAX_REQUESTS and report["failed"] >= 0,
            "invalid request counters",
        )
        reports[source] = report
    checks = {
        "both outside matrices": all(
            r["ok"] and r["failed"] == 0 for r in reports.values()
        ),
        "both synchronized sources sampled": all(
            r["samples_ok"] and r["samples"] == ROUNDS * CONCURRENCY_WORKERS
            for r in reports.values()
        ),
        "application concurrency 429 with Retry-After": any(
            r["app_denials"] > 0 for r in reports.values()
        ),
        "total request budget": sum(r["requests"] for r in reports.values())
        <= MAX_REQUESTS * 2,
    }
    print("| Check | Result |")
    print("| --- | --- |")
    for name, ok in checks.items():
        print(f"| {name} | {'PASS' if ok else 'FAIL'} |")
    if not all(checks.values()):
        print(
            "Rerun all jobs to create a fresh rendezvous and sample both sources together. "
            "A failed-job-only rerun cannot pass the paired concurrency check."
        )
    return all(checks.values())


def alert(ok):
    if not os.environ.get("OPENHRA_ALERT_SECRET"):
        print("Optional signed report: not configured")
        return True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alerts"))
    from send import main as send_alert

    event = {
        "event_id": str(uuid.uuid4()),
        "source": "watchdog",
        "check": "edge-acceptance.public",
        "severity": "info" if ok else "warning",
        "status": "ok" if ok else "fail",
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": "Manual outside acceptance passed"
        if ok
        else "Manual outside acceptance needs attention",
    }
    with tempfile.TemporaryDirectory(prefix="edge-acceptance-") as directory:
        path = Path(directory) / "event.json"
        path.write_text(json.dumps(event))
        return send_alert(["--event", str(path)]) == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "probe", "report"))
    parser.add_argument("--source", choices=("linux", "macos"))
    parser.add_argument("--epoch", type=float)
    args = parser.parse_args(argv)
    try:
        if args.mode == "plan":
            epoch = int(time.time()) + 240
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write(f"epoch={epoch}\n")
            print(
                "Outside runners have a four-minute rendezvous window; a late runner fails."
            )
            return 0
        if args.mode == "probe":
            require(
                args.source is not None and args.epoch is not None,
                "source and epoch are required",
            )
            result = Suite(Client(), args.source, args.epoch).run()
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write(
                    args.source + "=" + json.dumps(result, separators=(",", ":")) + "\n"
                )
            return 0 if result["ok"] else 1
        try:
            ok = aggregate(json.loads(os.environ.get("EDGE_REPORTS", "{}")))
        except (CheckFailed, ValueError, TypeError, KeyError):
            print("| Check | Result |")
            print("| --- | --- |")
            print("| Runner reports present and valid | FAIL |")
            ok = False
        delivered = alert(ok)
        print("edge acceptance: " + ("PASS" if ok and delivered else "FAIL"))
        return 0 if ok and delivered else 1
    except (
        CheckFailed,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        http.client.HTTPException,
    ):
        print(
            "edge acceptance: FAIL (configuration or request failed; remote details withheld)"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
