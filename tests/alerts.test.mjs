import assert from "node:assert/strict";
import { createHmac, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { Readable } from "node:stream";
import test from "node:test";

const source = readFileSync(
  new URL("../plans/api/alerts.js", import.meta.url),
  "utf8",
);
const { default: entrypoint, handler } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
const secret = "synthetic-secret-DO-NOT-LOG-42";
const baseTime = 1800000000;
let clock = baseTime;
const logs = [];
const event = (overrides = {}) => ({
  event_id: randomUUID(),
  source: "acme-validate",
  check: "edge-01.trust",
  severity: "warning",
  status: "unknown",
  at: "2026-11-08T12:00:00.000Z",
  summary: "Synthetic check has no outside evidence.",
  details: { age_seconds: 5401, service_id: "edge-01" },
  ...overrides,
});
const sign = (body, timestamp) =>
  "sha256=" +
  createHmac("sha256", secret)
    .update(timestamp + ".")
    .update(body)
    .digest("hex");

async function invoke(value = event(), options = {}) {
  const body = options.body ?? Buffer.from(JSON.stringify(value));
  const timestamp = String(options.timestamp ?? clock);
  const req = Readable.from(options.chunks ?? [body]);
  req.method = options.method ?? "POST";
  req.headers = {
    "x-openhra-timestamp": timestamp,
    "x-openhra-signature": sign(body, timestamp),
    "x-forwarded-for": "synthetic-client-ip-DO-NOT-LOG",
    ...options.headers,
  };
  req.body = { summary: "synthetic-parsed-body-DO-NOT-LOG" };
  const res = {
    headers: {},
    code: null,
    body: undefined,
    setHeader(key, value) {
      this.headers[key] = value;
    },
    status(code) {
      this.code = code;
      return this;
    },
    json(value) {
      this.body = value;
      return this;
    },
    end() {
      return this;
    },
  };
  const before = logs.length;
  await handler(req, res);
  assert.equal(res.headers["Cache-Control"], "no-store");
  if (res.code !== 204 && !options.concurrent)
    assert.equal(logs.length, before, "rejected input must not be logged");
  return res;
}

test("alert receiver offline contract and rejection controls", async (t) => {
  const previousSecret = process.env.OPENHRA_ALERT_SECRET;
  const previousNow = Date.now;
  const previousConsole = {
    log: console.log,
    warn: console.warn,
    error: console.error,
  };
  process.env.OPENHRA_ALERT_SECRET = secret;
  Date.now = () => clock * 1000;
  for (const level of ["log", "warn", "error"])
    console[level] = (...args) => logs.push({ level, args });
  try {
    await t.test(
      "fetch entry point bypasses body parsing and passes exact bytes to the handler",
      async () => {
        const body = Buffer.from(JSON.stringify(event(), null, 2) + "\n");
        const response = await entrypoint.fetch(
          new Request("https://localhost/api/alerts", {
            method: "POST",
            body,
            headers: {
              "Content-Type": "application/json",
              "X-OpenHRA-Timestamp": String(clock),
              "X-OpenHRA-Signature": sign(body, String(clock)),
            },
          }),
        );
        assert.equal(response.status, 204);
        assert.equal(response.headers.get("Cache-Control"), "no-store");
        assert.equal(await response.text(), "");
        const rejected = await entrypoint.fetch(
          new Request("https://localhost/api/alerts"),
        );
        assert.equal(rejected.status, 405);
        assert.equal(rejected.headers.get("Allow"), "POST");
        assert.deepEqual(await rejected.json(), {
          error: "method_not_allowed",
        });
      },
    );
    await t.test(
      "all severities log exactly one validated JSON line",
      async () => {
        for (const [severity, level] of [
          ["info", "log"],
          ["recovery", "log"],
          ["warning", "warn"],
          ["critical", "error"],
        ]) {
          const value = event({
            severity,
            summary: "Synthetic newline\nand Unicode 雪.",
          });
          const before = logs.length;
          const response = await invoke(value);
          assert.equal(response.code, 204);
          assert.equal(response.body, undefined);
          assert.equal(logs.length, before + 1);
          const log = logs.at(-1);
          assert.equal(log.level, level);
          assert.equal(log.args.length, 1);
          assert.equal(log.args[0].split("\n").length, 1);
          const { received_at, ...record } = JSON.parse(log.args[0]);
          assert.deepEqual(record, value);
          assert.ok(Number.isFinite(Date.parse(received_at)));
        }
      },
    );
    await t.test(
      "all sender source and status enums, optional details",
      async () => {
        for (const source of [
          "acme-validate",
          "acme-renew",
          "edge",
          "openplans",
          "signoz",
          "watchdog",
        ]) {
          for (const status of ["ok", "fail", "unknown"]) {
            const value = event({ source, status });
            delete value.details;
            assert.equal((await invoke(value)).code, 204);
          }
        }
      },
    );
    await t.test(
      "raw whitespace and split UTF-8 bytes are signed unchanged",
      async () => {
        const value = event({ summary: "Synthetic 雪." });
        const body = Buffer.from(JSON.stringify(value, null, 2) + "\n");
        assert.equal(
          (
            await invoke(value, {
              body,
              chunks: [...body].map((byte) => Buffer.from([byte])),
            })
          ).code,
          204,
        );
        assert.equal(
          (
            await invoke(value, {
              body: Buffer.from(JSON.stringify(value)),
              headers: {
                "x-openhra-signature": sign(body, String(clock)),
              },
            })
          ).code,
          401,
        );
      },
    );
    await t.test(
      "bad, missing and malformed signatures and timestamps fail without logging",
      async () => {
        for (const signature of [
          undefined,
          "",
          "sha256=" + "0".repeat(64),
          "sha256=ab",
          "sha256=" + "z".repeat(64),
          ["sha256=" + "0".repeat(64)],
        ]) {
          assert.equal(
            (
              await invoke(event(), {
                headers: { "x-openhra-signature": signature },
              })
            ).code,
            401,
          );
        }
        for (const timestamp of [
          undefined,
          "",
          "NaN",
          "1e9",
          "1800000000.0",
          ["1800000000"],
        ]) {
          assert.equal(
            (
              await invoke(event(), {
                headers: { "x-openhra-timestamp": timestamp },
              })
            ).code,
            401,
          );
        }
        for (const offset of [-301, 301])
          assert.equal(
            (await invoke(event(), { timestamp: clock + offset })).code,
            401,
          );
        for (const offset of [-300, 300])
          assert.equal(
            (await invoke(event(), { timestamp: clock + offset })).code,
            204,
          );
      },
    );
    await t.test("wrong methods and unset secret fail closed", async () => {
      for (const method of [
        "GET",
        "HEAD",
        "PUT",
        "OPTIONS",
        "DELETE",
        "PATCH",
      ]) {
        const res = await invoke(event(), { method });
        assert.equal(res.code, 405);
        assert.equal(res.headers.Allow, "POST");
      }
      delete process.env.OPENHRA_ALERT_SECRET;
      const res = await invoke();
      assert.equal(res.code, 503);
      assert.deepEqual(res.body, { error: "not_configured" });
      process.env.OPENHRA_ALERT_SECRET = secret;
    });
    await t.test(
      "8 KiB byte limit covers declared, undeclared and misleading lengths",
      async () => {
        const body = Buffer.from(JSON.stringify(event()));
        const exact = Buffer.concat([
          body,
          Buffer.alloc(8192 - body.length, " "),
        ]);
        assert.equal((await invoke(null, { body: exact })).code, 204);
        const large = Buffer.concat([exact, Buffer.from(" ")]);
        for (const headers of [
          {},
          { "content-length": "1" },
          { "content-length": String(large.length) },
        ]) {
          assert.equal(
            (
              await invoke(null, {
                body: large,
                chunks: [large.subarray(0, 8192), large.subarray(8192)],
                headers,
              })
            ).code,
            413,
          );
        }
        assert.equal(
          (await invoke(event({ summary: "雪".repeat(3000) }))).code,
          413,
        );
      },
    );
    await t.test(
      "closed schema rejects unknown keys, invalid types and nested details",
      async () => {
        const mutations = [
          { extra: "synthetic-unvalidated-DO-NOT-LOG" },
          { received_at: "2026-11-08T00:00:00Z" },
          { event_id: "not-a-uuid" },
          { event_id: null },
          { source: "other" },
          { severity: "ok" },
          { status: "pass" },
          { check: "" },
          { check: "a".repeat(65) },
          { check: "space id" },
          { check: 1 },
          { summary: "x".repeat(281) },
          { summary: 42 },
          { at: "tomorrow" },
          { at: "2026-02-30T00:00:00Z" },
          { at: "2026-11-08" },
          { at: "2026-11-08T24:00:00Z" },
          { at: "2026-11-08T00:00:00+24:00" },
          { details: null },
          { details: [] },
          { details: { nested: {} } },
          { details: { flag: true } },
          { details: { null: null } },
          {
            details: Object.fromEntries(
              Array.from({ length: 21 }, (_, i) => ["k" + i, i]),
            ),
          },
        ];
        for (const mutation of mutations)
          assert.equal((await invoke(event(mutation))).code, 400);
        for (const key of Object.keys(event()).filter(
          (key) => key !== "details",
        )) {
          const value = event();
          delete value[key];
          assert.equal((await invoke(value)).code, 400);
        }
        for (const value of [null, [], true, "text", 42])
          assert.equal((await invoke(value)).code, 400);
        assert.equal(
          (await invoke(null, { body: Buffer.from("{") })).code,
          400,
        );
        assert.equal(
          (await invoke(null, { body: Buffer.from([0xff]) })).code,
          400,
        );
        assert.equal(
          (
            await invoke(null, {
              body: Buffer.from(
                JSON.stringify(event()).replace("5401", "1e999"),
              ),
            })
          ).code,
          400,
        );
        assert.equal(
          (
            await invoke(
              event({
                summary: "雪".repeat(280),
                check: "x".repeat(64),
                at: "2024-02-29T12:34:56.123456+01:00",
                details: Object.fromEntries(
                  Array.from({ length: 20 }, (_, i) => ["k" + i, i]),
                ),
              }),
            )
          ).code,
          204,
        );
      },
    );
    await t.test(
      "Python sender signs the same exact bytes as the Node receiver",
      async () => {
        const body = Buffer.from(
          JSON.stringify(event({ source: "watchdog" }), null, 2) + "\n",
        );
        const python = spawnSync(
          "python3",
          [
            "-c",
            'import os, sys; sys.path.insert(0, sys.argv[1]); from send import sign; print(sign(sys.stdin.buffer.read(), sys.argv[2], os.environ["OPENHRA_ALERT_SECRET"].encode()))',
            new URL("../tools/alerts/", import.meta.url).pathname,
            String(clock),
          ],
          { input: body, encoding: "utf8" },
        );
        assert.equal(python.status, 0);
        assert.equal(
          (
            await invoke(null, {
              body,
              headers: { "x-openhra-signature": python.stdout.trim() },
            })
          ).code,
          204,
        );
      },
    );
    await t.test(
      "replays include UUID case variants, concurrent sends and future skew lifetime",
      async () => {
        const value = event({ event_id: randomUUID().toUpperCase() });
        assert.equal(
          (await invoke(value, { timestamp: baseTime + 300 })).code,
          204,
        );
        assert.equal((await invoke(value)).code, 409);
        assert.equal(
          (await invoke({ ...value, event_id: value.event_id.toLowerCase() }))
            .code,
          409,
        );
        clock = baseTime + 301;
        assert.equal((await invoke(value)).code, 409);
        clock = baseTime + 601;
        assert.equal((await invoke(value)).code, 204);
        const concurrent = event();
        const before = logs.length;
        const responses = await Promise.all(
          Array.from({ length: 3 }, () =>
            invoke(concurrent, { concurrent: true }),
          ),
        );
        assert.deepEqual(
          responses.map((res) => res.code).sort(),
          [204, 409, 409],
        );
        assert.equal(logs.length, before + 1);
      },
    );
    await t.test(
      "logs never contain the planted secret, signature, IP header or unvalidated content",
      () => {
        const output = logs.map((log) => log.args.join(" ")).join("\n");
        for (const forbidden of [
          secret,
          "sha256=",
          "synthetic-client-ip-DO-NOT-LOG",
          "synthetic-parsed-body-DO-NOT-LOG",
          "synthetic-unvalidated-DO-NOT-LOG",
        ]) {
          assert.equal(output.includes(forbidden), false);
        }
      },
    );
  } finally {
    Date.now = previousNow;
    Object.assign(console, previousConsole);
    if (previousSecret === undefined) delete process.env.OPENHRA_ALERT_SECRET;
    else process.env.OPENHRA_ALERT_SECRET = previousSecret;
  }
});
