// Execute the production reader against committed data with a small DOM fixture.
// Real layout, keyboard and accessibility checks live in browser.mjs.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";
const root =
  process.argv[2] ||
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const source = fs.readFileSync(path.join(root, "plans/coverage.js"), "utf8");
const dataRoot = path.join(root, "plans/data/coverage");
const records = JSON.parse(
  fs.readFileSync(path.join(dataRoot, "premiums-2026.json")),
);
const codes = Object.keys(records.states);
// Display names from the page, for the checks on table order and row text.
const pageNames = Object.fromEntries(
  [
    ...fs
      .readFileSync(path.join(root, "plans/index.html"), "utf8")
      .matchAll(/<option value="([A-Z]{2})"[^>]*>([^<]*)<\/option>/g),
  ].map((m) => [m[1], m[2]]),
);
const assert = (ok, message) => {
  if (!ok) throw Error(message);
};
class Element {
  constructor(text = "") {
    this.text = text;
    this.childNodes = [];
    this.options = [];
    this.dataset = {};
    this.attrs = {};
    this.events = {};
    this.disabled = true;
    this.value = "TX";
  }
  get textContent() {
    return (
      this.text +
      this.childNodes
        .map((n) => (typeof n === "string" ? n : n.textContent))
        .join("")
    );
  }
  set textContent(value) {
    this.text = String(value);
    this.childNodes = [];
  }
  append(...nodes) {
    this.childNodes.push(...nodes);
  }
  replaceChildren(...nodes) {
    this.text = "";
    this.childNodes = nodes;
    this.options = nodes;
  }
  setAttribute(key, value) {
    this.attrs[key] = value;
  }
  getAttribute(key) {
    return this.attrs[key];
  }
  addEventListener(type, fn) {
    this.events[type] = fn;
  }
  createCaption() {
    const n = new Element();
    this.append(n);
    return n;
  }
  createTHead() {
    const n = new Element();
    this.append(n);
    return n;
  }
  createTBody() {
    return this.createTHead();
  }
  insertRow() {
    return this.createTHead();
  }
  insertCell() {
    return this.createTHead();
  }
  querySelector() {
    return this.title;
  }
}
async function fixture(search, native = false, named = false) {
  const ids = Object.fromEntries(
    [
      "state",
      "year",
      "state-name",
      "metric",
      "fraction",
      "breakdown",
      "observed",
      "reasons",
      "detail-scope",
      "provenance",
      "message",
      "table",
      "title",
      "view",
      "date",
      "legend-title",
      "scope",
      "svg-title",
      "download",
      "summary",
      "full-page",
      "share",
      "share-message",
    ].map((id) => [id, new Element()]),
  );
  // Like the page, the first option is the all-states summary. State names are
  // codes unless named; options stay in code order so the reader must sort.
  ids.state.options = [
    { value: "ALL", textContent: "All states" },
    ...codes.map((code) => ({
      value: code,
      textContent: named ? pageNames[code] : code,
    })),
  ];
  const layers = ["providers", "prescriptions", "premiums"].map((layer) => {
    const e = new Element();
    e.dataset.coverageLayer = layer;
    return e;
  });
  const paths = Object.fromEntries(
    codes.map((code) => {
      const e = new Element();
      e.dataset.state = code;
      e.title = new Element();
      return [code, e];
    }),
  );
  const component = {
    querySelector(selector) {
      if (selector.startsWith("#coverage-")) return ids[selector.slice(10)];
      return paths[selector.match(/data-state="([A-Z]+)"/)?.[1]] || null;
    },
    querySelectorAll(selector) {
      return selector === "[data-coverage-layer]"
        ? layers
        : Object.values(paths);
    },
  };
  const location = {
    href: "https://plans.openhra.com/availability" + search,
    origin: "https://plans.openhra.com",
    search,
  };
  const events = {},
    copied = [],
    shared = [];
  const navigator = {
    clipboard: { writeText: async (text) => copied.push(text) },
  };
  if (native) navigator.share = async (value) => shared.push(value);
  const context = {
    document: {
      querySelector: () => component,
      createElement: () => new Element(),
      createDocumentFragment: () => new Element(),
      createTextNode: (text) => new Element(text),
    },
    location,
    navigator,
    history: {
      replaceState(a, b, url) {
        location.href = String(url);
        location.search = new URL(url).search;
      },
    },
    window: {
      addEventListener: (key, fn) => {
        events[key] = fn;
      },
    },
    fetch: async (name) => {
      assert(
        /^data\/coverage\/(?:index|(?:providers|prescriptions|premiums)-[0-9]{4})\.json$/.test(
          name,
        ),
        "unexpected fetch path",
      );
      const bytes = fs.readFileSync(
        path.join(dataRoot, name.replace("data/coverage/", "")),
      );
      return {
        ok: true,
        arrayBuffer: async () =>
          bytes.buffer.slice(
            bytes.byteOffset,
            bytes.byteOffset + bytes.byteLength,
          ),
      };
    },
    URL,
    URLSearchParams,
    TextDecoder,
    AbortController,
    crypto: webcrypto,
    Date,
    console,
  };
  vm.runInNewContext(source, context);
  async function wait(predicate) {
    for (let i = 0; i < 150; i++) {
      if (predicate()) return;
      await new Promise((r) => setTimeout(r, 5));
    }
    throw Error("selection did not render: " + ids.message.textContent);
  }
  await wait(() => !ids.share.disabled);
  return { ids, paths, layers, location, events, copied, shared, wait };
}
function selected(f, layer, year, state) {
  const { ids, location } = f;
  assert(
    ids.state.value === state &&
      ids.year.value == year &&
      ids["state-name"].textContent.includes(state),
    "URL state ignored on load or history",
  );
  assert(
    f.layers.find((b) => b.dataset.coverageLayer === layer).attrs[
      "aria-pressed"
    ] === true,
    "URL layer ignored",
  );
  const params = new URL(location.href).searchParams;
  assert(
    params.get("state") === state &&
      params.get("year") === String(year) &&
      params.get("layer") === layer,
    "URL selection not replaced",
  );
}
try {
  const f = await fixture("?layer=providers&year=2026&state=DC");
  selected(f, "providers", 2026, "DC");
  assert(
    f.ids.metric.textContent === "Unknown, not yet measured" &&
      !f.ids.fraction.textContent.includes("0 /") &&
      f.paths.DC.attrs.fill === "url(#coverage-unknown)",
    "unknown state rendered as measured",
  );
  assert(
    f.ids.summary.textContent.includes("Providers: 3 of 51 states measured") &&
      f.ids.summary.textContent.includes("Premiums: 49 of 51 states measured"),
    "measured summary disagrees with data",
  );
  await f.ids.share.events.click();
  const sharedURL = new URL(f.copied[0]);
  assert(
    sharedURL.pathname === "/availability" &&
      sharedURL.searchParams.get("layer") === "providers" &&
      sharedURL.searchParams.get("year") === "2026" &&
      sharedURL.searchParams.get("state") === "DC",
    "share link drops selection",
  );
  assert(
    f.ids["share-message"].textContent === "Link copied",
    "clipboard confirmation absent",
  );
  f.ids.state.value = "TX";
  f.ids.state.events.change();
  selected(f, "providers", 2026, "TX");
  assert(f.ids["share-message"].textContent === "", "stale copy confirmation");
  await f.layers
    .find((b) => b.dataset.coverageLayer === "premiums")
    .events.click();
  selected(f, "premiums", 2026, "TX");
  f.location.href =
    "https://plans.openhra.com/availability?layer=prescriptions&year=2027&state=HI";
  f.location.search = new URL(f.location.href).search;
  await f.events.popstate();
  selected(f, "prescriptions", 2027, "HI");
  assert(
    f.ids.metric.textContent === "Unknown, not yet measured",
    "2027 unknown coerced to value",
  );
  const n = await fixture("?layer=premiums&year=2027&state=FL", true);
  selected(n, "premiums", 2027, "FL");
  await n.ids.share.events.click();
  assert(
    n.shared.length === 1 &&
      n.copied.length === 0 &&
      new URL(n.shared[0].url).searchParams.get("state") === "FL",
    "native share selection",
  );
  const fallback = await fixture("?layer=invalid&year=9999&state=ZZ");
  assert(
    fallback.ids.state.value === "ALL" &&
      fallback.ids["state-name"].textContent ===
        "All states · Premiums · Plan year 2026" &&
      fallback.ids.metric.textContent === "49 of 51 measured" &&
      fallback.ids.breakdown.textContent === "Not yet measured: NY and VT." &&
      !new URL(fallback.location.href).searchParams.has("state"),
    "invalid or missing state must open the all-states summary",
  );
  assert(
    Object.values(fallback.paths).every((p) => p.dataset.selected === false),
    "all-states summary must not highlight one state",
  );
  await fallback.ids.share.events.click();
  assert(
    !new URL(fallback.copied[0]).searchParams.has("state"),
    "all-states share link must not name a state",
  );
  const providers = await fixture("?layer=providers&year=2026");
  assert(
    providers.ids.state.value === "ALL" &&
      providers.ids.summary.textContent.includes(
        "Providers: 3 of 51 states measured, in FL, NC and TX. Quarantined: GA.",
      ) &&
      providers.ids.breakdown.textContent ===
        "Measured: FL, NC and TX. Quarantined: GA.",
    "summary must name the few measured and quarantined states",
  );
  const named = await fixture("?layer=premiums&year=2026", false, true);
  const rows = named.ids.table.childNodes[0].childNodes[2].childNodes;
  const shown = rows.map((row) => row.childNodes[0].textContent);
  assert(
    shown.length === 51 &&
      shown.join("|") ===
        shown
          .slice()
          .sort((a, b) => a.localeCompare(b, "en"))
          .join("|"),
    "table rows not sorted by state name",
  );
  const notes = rows.map((row) => row.childNodes[2].textContent);
  const run = notes.find((text) => /[^.] State observation:/.test(text));
  assert(
    !run &&
      notes.some((text) =>
        text.includes("statewide denominator unverified. State observation:"),
      ),
    "missing period before State observation: " + run,
  );
  console.log(
    "PASS: coverage selection URL load/replace/history, measured counts, native share, clipboard confirmation, unknown states, table order by name and row sentences",
  );
} catch (error) {
  console.error("FAIL: coverage selection: " + error.message);
  process.exitCode = 1;
}
