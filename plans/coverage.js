/* Offline publication reader. Coverage fetches are limited to this origin's static JSON. */
(() => {
  "use strict";
  const root = document.querySelector("#availability");
  if (!root) return;
  const $ = (id) => root.querySelector("#coverage-" + id);
  const buttons = [...root.querySelectorAll("[data-coverage-layer]")];
  // The national summary is the default view; it is not a state code.
  const ALL_STATES = "ALL";
  const states = Object.fromEntries(
    [...$("state").options]
      .filter((o) => o.value !== ALL_STATES)
      .map((o) => [o.value, o.textContent]),
  );
  const codes = Object.keys(states).sort();
  const labels = {
    providers: "Providers",
    prescriptions: "Prescriptions",
    premiums: "Premiums",
  };
  const reasons = {
    report_absent: "Import report absent",
    denominator_unverified: "Denominator unverified",
    supplemental_catalog:
      "Supplemental catalog only; statewide denominator unverified",
    source_not_published: "Source not published yet",
    catalog_adapter_gap: "Catalog adapter unavailable",
    serving_evidence_absent: "Serving evidence absent",
    inventory_empty: "Proven empty inventory",
  };
  const actors = {
    publisher_access: "publisher restricted access",
    source_validation: "source validation",
    importer_limit: "importer limitation",
    undetermined: "undetermined cause",
  };
  const warningLabels = {
    quarantined_sources: "quarantined",
    failed_refresh: "failed refresh",
    partial_active_sources: "active with limits",
  };
  const scope =
    "Published exchange inventory, all products including dental and SHOP.";
  let index,
    current,
    defaults,
    wanted,
    serial = 0,
    controller;
  const datasets = new Map();
  const require = (value) => {
    if (!value) throw Error("Invalid static coverage snapshot");
  };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const keys = (o, expected) =>
    require(
      o &&
        typeof o === "object" &&
        !Array.isArray(o) &&
        same(Object.keys(o).sort(), expected.slice().sort()),
    );
  const unique = (a) => Array.isArray(a) && new Set(a).size === a.length;
  const integer = (n) => require(Number.isSafeInteger(n) && n >= 0);
  const hash = (h) =>
    require(typeof h === "string" && /^[a-f0-9]{64}$/.test(h));
  const time = (t) => {
    require(
      typeof t === "string" &&
        /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z$/.test(t) &&
        Number.isFinite(Date.parse(t)),
    );
    return Date.parse(t);
  };
  const date = (t) =>
    new Date(t).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      timeZone: "UTC",
    });
  const metric = (r) =>
    r.status === "measured"
      ? (r.percent_tenths / 10).toFixed(1) + "%"
      : {
          unknown: "Unknown, not yet measured",
          quarantined: "Quarantined",
          not_applicable: "Not applicable",
        }[r.status];
  const unit = (layer) =>
    layer === "premiums"
      ? "rate rows imported and checked"
      : "issuers with active " +
        (layer === "providers" ? "network" : "formulary") +
        " data";
  const publicURL = (value) => {
    const u = new URL(value);
    require(
      u.protocol === "https:" &&
        !u.username &&
        !u.password &&
        !u.search &&
        !u.hash &&
        !u.port &&
        u.hostname.includes(".") &&
        !/[\s%@\\]/.test(value),
    );
  };
  function header(d) {
    require(
      d.schema_version === 1 &&
        d.metric_version === "exchange-source-availability-v1" &&
        d.scope === "published_exchange_inventory_all_products",
    );
    time(d.as_of);
  }
  function validateIndex(i) {
    keys(i, [
      "schema_version",
      "metric_version",
      "as_of",
      "generated_at",
      "scope",
      "population",
      "state_codes",
      "datasets",
      "provenance",
      "scanner",
    ]);
    header(i);
    require(
      time(i.generated_at) >= time(i.as_of) &&
        i.population === "separate_validated_runs" &&
        same(i.state_codes, codes),
    );
    keys(i.scanner, ["version", "source_commit", "inputs_digest"]);
    hash(i.scanner.inputs_digest);
    require(
      /^[a-f0-9]{40}$/.test(i.scanner.source_commit) &&
        typeof i.scanner.version === "string",
    );
    require(
      i.provenance &&
        typeof i.provenance === "object" &&
        !Array.isArray(i.provenance),
    );
    for (const [id, p] of Object.entries(i.provenance)) {
      require(/^[a-z][a-z0-9_-]{0,39}$/.test(id));
      const fields = ["url", "title", "vintage", "retrieved_at", "sha256"];
      keys(p, p.member === undefined ? fields : [...fields, "member"]);
      publicURL(p.url);
      hash(p.sha256);
      integer(p.vintage);
      require(
        time(p.retrieved_at) <= time(i.as_of) &&
          typeof p.title === "string" &&
          p.title.length > 0,
      );
    }
    require(Array.isArray(i.datasets) && i.datasets.length > 0);
    const ids = new Set(),
      years = new Set();
    for (const d of i.datasets) {
      keys(d, ["layer", "year", "path", "sha256", "bytes"]);
      integer(d.year);
      integer(d.bytes);
      hash(d.sha256);
      require(
        Object.hasOwn(labels, d.layer) &&
          d.year >= 2026 &&
          d.year <= 2100 &&
          d.path === `${d.layer}-${d.year}.json` &&
          d.bytes > 0 &&
          d.bytes <= 65536,
      );
      require(!ids.has(d.path));
      ids.add(d.path);
      years.add(d.year);
    }
    require(
      [...years].every((y) =>
        Object.keys(labels).every((l) => ids.has(`${l}-${y}.json`)),
      ) && ids.has("providers-2026.json"),
    );
  }
  function validateData(d, entry) {
    keys(d, [
      "schema_version",
      "metric_version",
      "as_of",
      "layer",
      "year",
      "unit",
      "scope",
      "states",
    ]);
    header(d);
    require(
      d.year === entry.year &&
        d.layer === entry.layer &&
        d.as_of === index.as_of &&
        d.unit === (d.layer === "premiums" ? "rate_rows" : "issuers"),
    );
    keys(d.states, codes);
    for (const r of Object.values(d.states)) {
      keys(r, [
        "numerator",
        "denominator",
        "percent_tenths",
        "status",
        "counts",
        "reason_codes",
        "warnings",
        "observed_at",
        "provenance_ids",
        "evidence",
        "serving_basis",
      ]);
      const n = r.numerator,
        den = r.denominator,
        p = r.percent_tenths,
        c = r.counts;
      require(
        ["measured", "unknown", "quarantined", "not_applicable"].includes(
          r.status,
        ),
      );
      require(
        unique(r.reason_codes) &&
          r.reason_codes.every((x) => Object.hasOwn(reasons, x)) &&
          unique(r.provenance_ids) &&
          r.provenance_ids.every(
            (x) =>
              Object.hasOwn(index.provenance, x) &&
              index.provenance[x].vintage === d.year,
          ),
      );
      require(Array.isArray(r.warnings));
      for (const w of r.warnings) {
        keys(w, ["code", "actor", "count"]);
        require(
          Object.hasOwn(warningLabels, w.code) &&
            Object.hasOwn(actors, w.actor),
        );
        integer(w.count);
      }
      if (r.observed_at !== null) require(time(r.observed_at) <= time(d.as_of));
      if (r.evidence !== null) {
        require(r.observed_at && r.provenance_ids.length);
        keys(r.evidence, ["input_ids", "path", "sha256"]);
        hash(r.evidence.sha256);
        require(
          r.evidence.path === `evidence/${r.evidence.sha256}.json` &&
            unique(r.evidence.input_ids) &&
            r.evidence.input_ids.length &&
            r.evidence.input_ids.every((x) =>
              /^[a-z][a-z0-9_-]{0,39}$/.test(x),
            ),
        );
      } else
        require(
          den === null && r.observed_at === null && !r.provenance_ids.length,
        );
      if (den === null) {
        require(
          n === null &&
            p === null &&
            c === null &&
            r.status === "unknown" &&
            r.reason_codes.length &&
            r.serving_basis === "unverified",
        );
        continue;
      }
      integer(den);
      require(r.evidence);
      keys(
        c,
        d.layer === "premiums"
          ? ["verified", "quarantined", "unknown", "not_imported"]
          : [
              "active_complete",
              "active_partial",
              "quarantined",
              "unknown",
              "not_imported",
            ],
      );
      let sum = 0n;
      for (const v of Object.values(c)) {
        integer(v);
        sum += BigInt(v);
      }
      require(sum === BigInt(den));
      if (den === 0) {
        require(
          n === null &&
            p === null &&
            r.status === "not_applicable" &&
            same(r.reason_codes, ["inventory_empty"]),
        );
        continue;
      }
      if (n === null) {
        require(
          p === null &&
            r.status === "unknown" &&
            c.unknown === den &&
            r.reason_codes.length &&
            r.serving_basis === "unverified",
        );
        continue;
      }
      integer(n);
      integer(p);
      require(
        n <= den &&
          p <= 1000 &&
          BigInt(p) === (2000n * BigInt(n) + BigInt(den)) / (2n * BigInt(den)),
      );
      require(
        n ===
          (d.layer === "premiums"
            ? c.verified
            : c.active_complete + c.active_partial) &&
          r.status === (c.quarantined === den ? "quarantined" : "measured") &&
          !r.reason_codes.length &&
          r.serving_basis ===
            (d.layer === "premiums" ? "active_catalog" : "active_source_sets"),
      );
    }
  }
  async function read(path, limit, signal, entry) {
    const response = await fetch("data/coverage/" + path, {
      signal,
      credentials: "omit",
      redirect: "error",
      cache: "no-cache",
    });
    require(response.ok);
    const raw = await response.arrayBuffer();
    require(raw.byteLength <= limit);
    if (entry) {
      const digest = [
        ...new Uint8Array(await crypto.subtle.digest("SHA-256", raw)),
      ]
        .map((x) => x.toString(16).padStart(2, "0"))
        .join("");
      require(raw.byteLength === entry.bytes && digest === entry.sha256);
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
  }
  function notes(r, d) {
    let text = r.reason_codes.map((x) => reasons[x]);
    if (
      d.year === 2027 &&
      d.layer === "premiums" &&
      r.denominator === null &&
      !r.provenance_ids.length &&
      r.reason_codes.includes("denominator_unverified")
    )
      text.unshift("Source not published yet in this snapshot");
    text = text.concat(
      r.warnings.map(
        (w) =>
          `${w.count} ${warningLabels[w.code]}${w.code === "partial_active_sources" ? "" : ": " + actors[w.actor]}`,
      ),
    );
    return text.join("; ") || "No recorded source limitations.";
  }
  function breakdown(r) {
    if (!r.counts) return "Inventory and source counts are unknown.";
    const c = r.counts;
    return (
      (c.active_complete === undefined
        ? `${c.verified} verified; `
        : `${c.active_complete} active complete; ${c.active_partial} active with limits; `) +
      `${c.quarantined} quarantined; ${c.unknown} unknown; ${c.not_imported} not imported.`
    );
  }
  function fraction(r, layer) {
    return r.denominator === null
      ? "Denominator unverified"
      : `${r.numerator === null ? "Unknown" : r.numerator} / ${r.denominator} ${unit(layer)}`;
  }
  function fill(r) {
    if (r.status === "unknown") return "url(#coverage-unknown)";
    if (r.status === "quarantined") return "url(#coverage-quarantine)";
    if (r.percent_tenths === null || r.percent_tenths === 0) return "white";
    if (r.percent_tenths < 250) return "var(--teal-100)";
    if (r.percent_tenths < 500) return "var(--teal-300)";
    if (r.percent_tenths < 750) return "var(--teal-600)";
    return "var(--teal-800)";
  }
  function link() {
    const url = new URL("/availability", location.origin);
    url.searchParams.set("layer", current.layer);
    url.searchParams.set("year", current.year);
    if ($("state").value !== ALL_STATES)
      url.searchParams.set("state", $("state").value);
    return url;
  }
  function remember() {
    const url = new URL(location.href),
      selected = link();
    for (const key of ["layer", "year", "state"]) {
      const value = selected.searchParams.get(key);
      if (value === null) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    }
    history.replaceState(null, "", url);
    if ($("full-page")) $("full-page").href = selected.href;
    $("share-message").textContent = "";
  }
  function fromURL() {
    const params = new URLSearchParams(location.search),
      year = Number(params.get("year")),
      layer = params.get("layer");
    const choice = index.datasets.some(
      (d) => d.year === year && d.layer === layer,
    )
      ? { year, layer }
      : defaults;
    return {
      ...choice,
      state: Object.hasOwn(states, params.get("state"))
        ? params.get("state")
        : ALL_STATES,
    };
  }
  async function share() {
    const url = link().href;
    try {
      if (navigator.share) {
        await navigator.share({ title: "OpenPlans data availability", url });
        $("share-message").textContent = "Link shared";
      } else {
        await navigator.clipboard.writeText(url);
        $("share-message").textContent = "Link copied";
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        const a = document.createElement("a");
        a.href = url;
        a.textContent = "Copy this selection link";
        $("share-message").replaceChildren(
          document.createTextNode("Sharing unavailable. "),
          a,
        );
      }
    }
  }
  function names(d, status) {
    const found = codes
      .filter((s) => d.states[s].status === status)
      .map((s) => states[s])
      .sort();
    return found.length > 1
      ? found.slice(0, -1).join(", ") + " and " + found.at(-1)
      : found.join("");
  }
  function count(d, status) {
    return codes.filter((s) => d.states[s].status === status).length;
  }
  // Name the states when only a few are measured, so readers need not guess.
  function few(d, status) {
    const n = count(d, status);
    return n && n <= 5 ? names(d, status) : "";
  }
  function summary(year) {
    const lines = Object.keys(labels).map((layer) => {
      const d = datasets.get(`${layer}-${year}`),
        measured = few(d, "measured"),
        held = few(d, "quarantined");
      return (
        `${labels[layer]}: ${count(d, "measured")} of ${codes.length} states measured` +
        (measured ? `, in ${measured}` : "") +
        (held ? `. Quarantined: ${held}` : "")
      );
    });
    $("summary").textContent =
      lines.join(". ") +
      ". Includes DC. Unknown states are not yet measured, which is not zero.";
  }
  function national(layer, year) {
    const d = current,
      unknown = count(d, "unknown"),
      listed = [
        ["Measured", few(d, "measured")],
        ["Quarantined", few(d, "quarantined")],
        ["Not yet measured", few(d, "unknown")],
      ].filter(([, text]) => text);
    $("state-name").textContent =
      `All states · ${labels[layer]} · Plan year ${year}`;
    $("metric").textContent =
      `${count(d, "measured")} of ${codes.length} measured`;
    $("fraction").textContent =
      `${count(d, "measured")} measured; ${count(d, "quarantined")} quarantined; ${unknown} not yet measured. Includes DC.`;
    $("breakdown").textContent =
      listed.map(([label, text]) => `${label}: ${text}.`).join(" ") ||
      "Pick a state for its counts.";
    $("observed").textContent = "Figures as of " + date(d.as_of);
    $("reasons").textContent =
      "Pick a state for its counts, limits and sources.";
    $("detail-scope").textContent = $("scope").textContent;
    const a = document.createElement("a");
    a.href = `data/coverage/${layer}-${year}.json`;
    a.textContent = "All state records (JSON)";
    $("provenance").replaceChildren(a);
    for (const p of root.querySelectorAll("[data-state]"))
      p.dataset.selected = false;
    remember();
    $("message").textContent =
      `${labels[layer]}, plan year ${year}. All states: ${count(d, "measured")} of ${codes.length} measured. Figures as of ${date(d.as_of)}.`;
  }
  function selection() {
    const { layer, year } = current,
      state = $("state").value,
      r = current.states[state];
    if (state === ALL_STATES) return national(layer, year);
    $("state-name").textContent =
      `${states[state]} · ${labels[layer]} · Plan year ${year}`;
    $("metric").textContent = metric(r);
    $("fraction").textContent = fraction(r, layer);
    $("breakdown").textContent = breakdown(r);
    $("observed").textContent =
      "State observation: " + (r.observed_at ? date(r.observed_at) : "Unknown");
    $("reasons").textContent = notes(r, current);
    $("detail-scope").textContent =
      scope +
      " Unit: " +
      unit(layer) +
      ". " +
      (layer === "premiums"
        ? "Source rows, not household quote support."
        : "Issuer presence, not network or drug completeness.");
    const links = document.createDocumentFragment();
    for (const id of r.provenance_ids) {
      const p = index.provenance[id],
        a = document.createElement("a");
      a.href = p.url;
      a.textContent = `${p.title} (${p.vintage}; retrieved ${date(p.retrieved_at)}; SHA-256 ${p.sha256})`;
      links.append(a, document.createElement("br"));
    }
    if (r.evidence) {
      const a = document.createElement("a");
      a.href = "data/coverage/" + r.evidence.path;
      a.textContent =
        "Static evidence ledger (JSON), SHA-256 " + r.evidence.sha256;
      links.append(a);
    }
    if (!links.childNodes.length)
      links.append(
        document.createTextNode(
          "No published inventory evidence in this snapshot for this state, layer and year.",
        ),
      );
    $("provenance").replaceChildren(links);
    for (const p of root.querySelectorAll("[data-state]"))
      p.dataset.selected = p.dataset.state === state;
    remember();
    $("message").textContent =
      `${labels[layer]}, plan year ${year}. ${states[state]}: ${metric(r)}. Figures as of ${date(current.as_of)}. Table and detail use the same snapshot.`;
  }
  function paint(d) {
    const { layer, year } = d;
    const table = document.createElement("table"),
      caption = table.createCaption();
    caption.textContent = `${labels[layer]} · Plan year ${year} · Figures as of ${date(d.as_of)}. Dated snapshot. Separate validated runs. ${scope} Unit: ${unit(layer)}.`;
    const tr = table.createTHead().insertRow();
    for (const label of ["State", "Data and count", "Status and limits"]) {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      tr.append(th);
    }
    const body = table.createTBody();
    for (const [s, name] of Object.entries(states)) {
      const r = d.states[s],
        row = body.insertRow(),
        th = document.createElement("th");
      th.scope = "row";
      th.textContent = name;
      row.append(th);
      row.insertCell().textContent = `${metric(r)}; ${fraction(r, layer)}`;
      row.insertCell().textContent = `${breakdown(r)} ${notes(r, d)} State observation: ${r.observed_at ? date(r.observed_at) : "Unknown"}.`;
    }
    // Everything above is detached; commit all visible values in this one task.
    current = d;
    wanted = { ...wanted, layer, year };
    $("state").value = wanted.state;
    summary(year);
    $("table").replaceChildren(table);
    $("title").textContent = `Coverage for plan year ${year}`;
    $("view").textContent =
      `${labels[layer]} · ${layer === defaults.layer && year === defaults.year ? "Default" : "Selected"} view`;
    $("date").textContent =
      `Figures as of ${date(d.as_of)} · Dated snapshot` +
      (Date.now() - time(d.as_of) > 7 * 86400000
        ? " (more than 7 days old)"
        : "");
    $("legend-title").textContent =
      `${labels[layer]} · Plan year ${year} · ${unit(layer)}`;
    $("scope").textContent =
      `${scope} Unit: ${unit(layer)}${layer === "premiums" ? "." : " ÷ all issuers in the published catalog."} ${layer === "premiums" ? "This does not measure household quote support." : "Presence does not establish network or formulary completeness."}`;
    $("svg-title").textContent =
      `${labels[layer]} source availability, plan year ${year}`;
    for (const [s, r] of Object.entries(d.states)) {
      const path = root.querySelector(`[data-state="${s}"]`);
      path.setAttribute("fill", fill(r));
      path.querySelector("title").textContent =
        `${states[s]}: ${metric(r)}, plan year ${year}`;
      const callout = root.querySelector(`[data-callout="${s}"] rect`);
      if (callout) callout.setAttribute("fill", fill(r));
    }
    $("year").value = year;
    for (const b of buttons)
      b.setAttribute("aria-pressed", b.dataset.coverageLayer === layer);
    $("download").href = `data/coverage/${layer}-${year}.json`;
    $("download").textContent = `Download ${labels[layer]} / ${year} JSON`;
    selection();
  }
  async function load(next) {
    wanted = next;
    const id = ++serial;
    if (controller) controller.abort();
    controller = new AbortController();
    try {
      const entry = index.datasets.find(
        (d) => d.layer === next.layer && d.year === next.year,
      );
      require(entry);
      const data = await read(entry.path, 65536, controller.signal, entry);
      validateData(data, entry);
      if (id !== serial) return;
      paint(data);
    } catch {
      if (id !== serial) return;
      wanted = current
        ? { layer: current.layer, year: current.year, state: $("state").value }
        : { ...defaults, state: ALL_STATES };
      $("year").value = wanted.year;
      if (current) remember();
      $("message").textContent =
        "Coverage selection could not be loaded or validated. The last valid dated map, detail and table remain visible; controls reflect that view.";
    }
  }
  (async () => {
    index = await read("index.json", 16384);
    validateIndex(index);
    const options = [...new Set(index.datasets.map((d) => d.year))]
      .sort()
      .map((y) => {
        const o = document.createElement("option");
        o.value = y;
        o.textContent = y;
        return o;
      });
    $("year").replaceChildren(...options);
    await Promise.all(
      index.datasets.map(async (entry) => {
        const data = await read(entry.path, 65536, undefined, entry);
        validateData(data, entry);
        datasets.set(`${entry.layer}-${entry.year}`, data);
      }),
    );
    const ranked = [...datasets.values()].sort(
      (a, b) =>
        Object.values(b.states).filter((r) => r.status === "measured").length -
          Object.values(a.states).filter((r) => r.status === "measured")
            .length ||
        b.year - a.year ||
        a.layer.localeCompare(b.layer),
    );
    defaults = { layer: ranked[0].layer, year: ranked[0].year };
    await load(fromURL());
    // Invalid initial data leaves the saved controls disabled and the fallback intact.
    if (!current) return;
    for (const b of buttons) {
      b.disabled = false;
      b.addEventListener("click", () =>
        load({ ...wanted, layer: b.dataset.coverageLayer }),
      );
    }
    $("year").disabled = false;
    $("year").addEventListener("change", () =>
      load({ ...wanted, year: Number($("year").value) }),
    );
    $("state").disabled = false;
    $("state").addEventListener("change", () => {
      wanted.state = $("state").value;
      selection();
    });
    $("share").disabled = false;
    $("share").addEventListener("click", share);
    window.addEventListener("popstate", () => load(fromURL()));
  })().catch(() => {
    $("message").textContent =
      "Coverage controls unavailable: the static snapshot could not be validated. Saved Premiums / plan year 2026, figures as of November 8, 2026, remain below.";
  });
})();
