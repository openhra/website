/* Reads one static JSON file from this origin and shows what the data can answer. */
(() => {
  "use strict";
  // Pure: rows for one selection. state and year are "ALL" or a value from the data.
  function summarize(data, state, year) {
    const out = data.families.map((f) => ({
      id: f.id,
      label: f.label,
      answered: 0,
      partial: 0,
      unsupported: 0,
      unknown: 0,
      statuses: {},
      reasons: {},
    }));
    const byId = Object.fromEntries(out.map((f) => [f.id, f]));
    for (const r of data.rows) {
      if (state !== "ALL" && r.state !== state) continue;
      if (year !== "ALL" && String(r.year) !== String(year)) continue;
      const f = byId[r.family];
      if (!f) continue;
      for (const k of ["answered", "partial", "unsupported", "unknown"])
        f[k] += r[k];
      for (const k of ["statuses", "reasons"])
        for (const [code, n] of Object.entries(r[k]))
          f[k][code] = (f[k][code] || 0) + n;
    }
    return out;
  }
  // A code with no listed words is shown as the code itself.
  const words = (map, code) => (map && map[code]) || code;
  // Without a page, expose the pure parts so tests can load this file.
  if (typeof document === "undefined") {
    globalThis.askPage = { summarize, words };
    return;
  }
  const root = document.querySelector("#ask");
  if (!root) return;
  const el = (tag, text, attrs) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    return Object.assign(e, attrs || {});
  };
  const message = root.querySelector("#ask-message");
  const stateSel = root.querySelector("#ask-state");
  const yearSel = root.querySelector("#ask-year");
  const table = root.querySelector("#ask-table");
  const detail = root.querySelector("#ask-detail");
  const date = root.querySelector("#ask-date");
  let data = null;
  function render() {
    const rows = summarize(data, stateSel.value, yearSel.value);
    table.replaceChildren();
    const head = el("tr");
    for (const h of [
      "Question",
      "Answered",
      "Partial",
      "Not in the public source",
      "Unknown",
    ])
      head.append(el("th", h, { scope: "col" }));
    const thead = el("thead");
    thead.append(head);
    table.append(thead);
    const body = el("tbody");
    for (const f of rows) {
      const tr = el("tr");
      tr.append(el("th", f.label, { scope: "row" }));
      for (const k of ["answered", "partial", "unsupported", "unknown"])
        tr.append(el("td", String(f[k])));
      body.append(tr);
    }
    table.append(body);
    detail.replaceChildren();
    for (const f of rows) {
      const codes = Object.entries(f.reasons).sort((a, b) => b[1] - a[1]);
      const others = Object.entries(f.statuses).filter(
        ([k]) =>
          k !== "available" &&
          k !== "complete" &&
          k !== "partial" &&
          k !== "unsupported",
      );
      if (!codes.length && !others.length) continue;
      detail.append(el("h3", f.label + ": why unknown"));
      const ul = el("ul");
      for (const [k, n] of others.sort((a, b) => b[1] - a[1]))
        ul.append(el("li", words(data.status_words, k) + ": " + n));
      for (const [k, n] of codes)
        ul.append(el("li", words(data.reason_words, k) + ": " + n));
      detail.append(ul);
    }
  }
  function fill(select, values, label) {
    select.replaceChildren(el("option", label, { value: "ALL" }));
    for (const v of values)
      select.append(el("option", String(v), { value: String(v) }));
    select.disabled = false;
  }
  fetch("data/ask/ask.json")
    .then((r) => {
      if (!r.ok) throw new Error("status " + r.status);
      return r.json();
    })
    .then((json) => {
      data = json;
      if (!data.rows.length) {
        message.textContent =
          "No availability snapshot is published yet. Nothing is shown rather than a guess.";
        return;
      }
      const uniq = (k) => [...new Set(data.rows.map((r) => r[k]))].sort();
      fill(stateSel, uniq("state"), "All states");
      fill(yearSel, uniq("year"), "All plan years");
      stateSel.addEventListener("change", render);
      yearSel.addEventListener("change", render);
      date.textContent =
        (data.synthetic ? "Synthetic example data. " : "") +
        "Fetched " +
        data.fetched_at +
        " from " +
        data.source_url +
        ".";
      message.textContent = "";
      render();
    })
    .catch(() => {
      message.textContent = "The availability file could not be loaded.";
    });
})();
