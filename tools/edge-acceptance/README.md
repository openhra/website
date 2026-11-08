# Manual outside acceptance

Run **Manual outside edge acceptance** with `workflow_dispatch` in the extracted website repository. It targets `https://openplans.openhra.com`. This workflow has no schedule and uses read-only checkout permissions. It needs no configured secret. If `OPENHRA_ALERT_SECRET` exists, the final job sends one summary through `tools/alerts/send.py`.

The preparation job runs the local fake-server tests and sets a rendezvous four minutes ahead. Linux and macOS jobs each open three MCP calls in six synchronized rounds, six seconds apart. This stays below the edge's four-connection limit per source while trying to reach the application's four-call limit across sources. The jobs assume separate hosted runner pools have distinct outbound addresses. They do not look up, log or retain those addresses. A late runner fails the check. The final job requires both reports and an application concurrency error with `Retry-After`. An edge-generated 429 does not count as application concurrency evidence.

Each runner then checks the native catalog, modern metadata discovery/list/call, legacy initialize/list/call, JSON, incremental progress SSE, mid-stream client disconnect, exact CORS policy, method and body limits, protected routes, hostile Host and SNI, and forged forwarding headers. Modern revision `2026-07-28` uses `server/discover` with `_meta` protocolVersion, clientInfo and clientCapabilities keys under `io.modelcontextprotocol/`. It has no legacy initialize exchange. Revision `2025-11-25` uses initialize and the initialized notification before list/call.

Regular MCP checks are paced to avoid consuming the burst allowance. Rate tests run last. A concurrent burst with rotated forged addresses must still hit throttling after the real source bucket is exhausted. A normal one-token-per-second refill may admit a call. The external test proves that spoofing cannot evade this bucket and does not break a canonical tool call. It cannot inspect the backend's rewritten header values; the router's isolated adapter tests cover those values.

A stream passes only when a matching progress event arrives at least 25 ms before the final tool result in separate reads. A fast response with no measurable gap fails because it does not prove incremental delivery. Disconnect closes the socket after progress and before any final event in that read. The result reports the client action. An operator must confirm SQL cancellation and retained-log privacy on the host after the outside run. This client has no host access and creates no SQL lock to prolong calls. If ordinary synthetic reads finish too quickly to expose concurrency, the final table prints FAIL. Do not treat an unobserved limit as a pass.

The allowed-Origin POST check is tracked as the MCP3b known failure. Missing `Access-Control-Allow-Origin`, exposed headers or `Vary: Origin` still prints FAIL and fails the workflow. There is no skip, allowed-failure flag or automatic waiver. Deploy the application fix and rerun the matrix.

Every runner has a hard cap of 80 target requests, including TLS refusal attempts, and a ten-minute job timeout. A complete run uses at most 160 target requests plus one optional signed report. Sockets have ten-second timeouts; response bodies are capped at 256 KiB and are never printed or saved. Requests use synthetic search markers and public geography only. There are no household estimates, real bearer credentials, arbitrary target inputs, redirects or retries.

Run offline tests from the website root:

```sh
python3 -B -m unittest discover -s tests -p 'edge_acceptance*.py'
```

The fakes test both protocol envelopes and reject buffered SSE, successful GET, oversized-body acceptance, accessible private routes, a successful hostile Host, missing CORS headers, missing Retry-After and forwarding-based rate evasion. TLS refusal tests ensure certificate hostname errors cannot masquerade as refused SNI. These tests run in the preparation job and in `tools/gate.sh`, including the full gate.

A passing workflow provides outside-client evidence. Confirm SQL cancellation and retained-log privacy on the host before closing deployment acceptance.
