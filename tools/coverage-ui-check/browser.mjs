// Drive the local page in the shared headed agent-browser session; no dependencies.
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import os from "node:os";
import { fileURLToPath } from "node:url";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const url = process.env.COVERAGE_PREVIEW_URL || "http://127.0.0.1:8779/";
if (!["127.0.0.1", "localhost"].includes(new URL(url).hostname))
  throw Error("Local preview only");
const out = process.env.COVERAGE_CAPTURE_DIR || "/tmp/openplans-coverage-ui";
await fs.mkdir(out, { recursive: true });
const endpoint = execFileSync(
  "agent-browser",
  [
    "--headed",
    "--profile",
    path.join(os.homedir(), "agent-browser"),
    "get",
    "cdp-url",
  ],
  { encoding: "utf8" },
).trim();
const origin = endpoint.replace(/^ws/, "http").replace(/\/devtools\/.*$/, "");
const tabs = await (await fetch(origin + "/json/list")).json();
const target = tabs.find(
  (t) => t.type === "page" && t.url.startsWith(new URL(url).origin),
);
if (!target) throw Error("Open the local preview in agent-browser first");
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let sequence = 0;
const pending = new Map(),
  requests = [],
  loaded = new Set();
ws.addEventListener("message", (e) => {
  const msg = JSON.parse(e.data);
  if (msg.method === "Page.lifecycleEvent" && msg.params.name === "load")
    loaded.add(msg.params.loaderId);
  if (pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
  if (msg.method === "Network.requestWillBeSent") {
    const p = msg.params,
      stack = p.initiator.stack?.callFrames || [];
    if (
      p.request.url.includes("/coverage.js") ||
      p.request.url.includes("/data/coverage/") ||
      stack.some((f) => f.url.endsWith("/coverage.js"))
    )
      requests.push({
        url: p.request.url,
        initiator: stack.map((f) => f.url).filter(Boolean),
      });
  }
});
const call = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, (msg) =>
      msg.error
        ? reject(Error(JSON.stringify(msg.error)))
        : resolve(msg.result),
    );
    ws.send(JSON.stringify({ id, method, params }));
  });
const evaluate = async (expression) => {
  const r = await call("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (r.exceptionDetails)
    throw Error(
      r.exceptionDetails.text +
        ": " +
        r.exceptionDetails.exception?.description,
    );
  return r.result.value;
};
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const wait = async (expression) => {
  for (let i = 0; i < 160; i++) {
    if (await evaluate(expression)) return;
    await pause(25);
  }
  throw Error("Timed out: " + expression);
};
const assert = (condition, message) => {
  if (!condition) throw Error(message);
};
const navigate = async (suffix = "") => {
  const r = await call("Page.navigate", { url: url + suffix });
  for (let i = 0; i < 200 && !loaded.has(r.loaderId); i++) await pause(25);
  assert(loaded.has(r.loaderId), "navigation did not finish");
};
const ready = () => wait('!document.querySelector("#coverage-state").disabled');
const click = async (layer) => {
  await evaluate(
    `document.querySelector('[data-coverage-layer="${layer}"]').click()`,
  );
  await wait(
    `document.querySelector('#coverage-download').getAttribute('href').endsWith('${layer}-'+document.querySelector('#coverage-year').value+'.json') && document.querySelector('[data-coverage-layer="${layer}"]').getAttribute('aria-pressed')==='true'`,
  );
};
const reports = [];
const pageFits = async () => {
  const size = await evaluate(
    "({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})",
  );
  assert(
    size.scroll <= size.client,
    "page-level horizontal overflow: " + JSON.stringify(size),
  );
  return size;
};
try {
  await call("Page.enable");
  await call("Page.setLifecycleEventsEnabled", { enabled: true });
  await call("Network.enable");
  await call("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await navigate();
  await ready();
  // Check every selected record, table cell, map fill and date against the committed data.
  let selections = 0;
  for (const year of [2026, 2027]) {
    await evaluate(
      `document.querySelector('#coverage-year').value='${year}';document.querySelector('#coverage-year').dispatchEvent(new Event('change'))`,
    );
    await wait(
      `document.querySelector('#coverage-title').textContent==='Coverage for plan year ${year}'`,
    );
    for (const layer of ["providers", "prescriptions", "premiums"]) {
      await click(layer);
      const data = JSON.parse(
        await fs.readFile(
          path.join(root, `plans/data/coverage/${layer}-${year}.json`),
          "utf8",
        ),
      );
      selections += await evaluate(`(()=>{
    const d=${JSON.stringify(data)}, $=s=>document.querySelector('#coverage-'+s), rows=[...$('table').querySelectorAll('tbody tr')], codes=Object.keys(d.states), names=Object.fromEntries([...$('state').options].map(o=>[o.value,o.textContent]));
    const fail=m=>{throw Error(m)}, date=t=>new Date(t).toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'});
    if(rows.length!==51||!$('title').textContent.includes(d.year)||!$('legend-title').textContent.includes(d.year)||!$('table').querySelector('caption').textContent.includes('Plan year '+d.year)||!$('date').textContent.includes(date(d.as_of)))fail('year/date parity');
    for(const [i,s]of codes.entries()){
     const r=d.states[s];$('state').value=s;$('state').dispatchEvent(new Event('change'));
     const metric=r.status==='measured'?(r.percent_tenths/10).toFixed(1)+'%':({unknown:'Unknown, not yet measured',quarantined:'Quarantined',not_applicable:'Not applicable'})[r.status];
     if($('metric').textContent!==metric||!$('state-name').textContent.includes(names[s])||!$('state-name').textContent.includes(d.year))fail(s+' detail');
     if(rows[i].cells[0].textContent!==names[s]||!rows[i].cells[1].textContent.startsWith(metric+';'))fail(s+' table');
     if(r.denominator!==null&&!rows[i].cells[1].textContent.includes((r.numerator===null?'Unknown':r.numerator)+' / '+r.denominator+' '))fail(s+' fraction');
     if(r.observed_at&&!rows[i].cells[2].textContent.includes(date(r.observed_at)))fail(s+' observation');
     for(const [key,value]of Object.entries(r.counts||{})){
      const label={active_complete:'active complete',active_partial:'active with limits',quarantined:'quarantined',unknown:'unknown',not_imported:'not imported',verified:'verified'}[key];
      if(!rows[i].cells[2].textContent.includes(value+' '+label)||!$('breakdown').textContent.includes(value+' '+label))fail(s+' '+key);
     }
     const fill=document.querySelector('[data-state="'+s+'"]').getAttribute('fill');
     if(r.status==='unknown'&&fill!=='url(#coverage-unknown)'||r.status==='quarantined'&&fill!=='url(#coverage-quarantine)'||r.status==='measured'&&fill.startsWith('url'))fail(s+' fill');
     if(!$('message').textContent.includes(names[s])||!$('message').textContent.includes(d.year))fail('announcement');
    }
    if(new URL(location.href).searchParams.get('year')!==String(d.year)||new URL(location.href).searchParams.get('layer')!==d.layer)fail('share URL');
    return codes.length;
   })()`);
      // Keep exhaustive synthetic state changes below Chrome history IPC throttling.
      await pause(3500);
    }
  }
  assert(selections === 306, "all selections");
  reports.push({ selectionParity: selections });
  await navigate("?year=2027&layer=premiums");
  await ready();
  assert(
    await evaluate(
      `document.querySelector('#coverage-title').textContent.endsWith('2027')&&document.querySelector('[data-coverage-layer="premiums"]').getAttribute('aria-pressed')==='true'&&document.querySelector('#coverage-table').textContent.includes('not published yet')`,
    ),
    "share restore/unpublished",
  );
  reports.push({
    shareURLRestored: true,
    unpublishedStatesRemainUnknown: true,
  });
  // Responsive/appearance checks include the entire existing page, not just the map.
  for (const width of [320, 360, 390, 768, 1280, 1440]) {
    await call("Emulation.setDeviceMetricsOverride", {
      width,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });
    const result = await evaluate(
      `(()=>{const c=document.querySelector('.coverage'),s=getComputedStyle(c),map=c.querySelector('svg');return {width:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,white:s.backgroundColor,mapWhite:getComputedStyle(map).backgroundColor,states:c.querySelectorAll('[data-state]').length,controls:[...c.querySelectorAll('button,select')].every(e=>e.getBoundingClientRect().height>=44),gutter:parseFloat(getComputedStyle(c.querySelector('.wrap')).paddingLeft),coverageRight:c.getBoundingClientRect().right,coverageOverflow:[...c.querySelectorAll('*')].filter(e=>!(e instanceof SVGElement)).some(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1)}})()`,
    );
    await pageFits();
    result.pageNoOverflow = true;
    result.contactWidget = await evaluate(
      `(()=>{const r=document.querySelector('#contact-captcha').getBoundingClientRect();return {width:r.width,left:r.left,right:r.right}})()`,
    );
    assert(
      result.contactWidget.width >= 304 &&
        result.contactWidget.left >= 0 &&
        result.contactWidget.right <= result.client,
      "contact widget cropped or shrunk " + width,
    );
    assert(
      await evaluate(
        `(()=>{const e=document.querySelector('.verification .table');return e.tabIndex===0&&e.getAttribute('role')==='region'&&getComputedStyle(e).overflowX==='auto'&&[...e.querySelectorAll('th,td')].every(cell=>getComputedStyle(cell).whiteSpace==='normal'&&getComputedStyle(cell).overflowWrap==='anywhere')})()`,
      ),
      "verification scroll region/cell wrapping",
    );
    assert(
      !result.coverageOverflow,
      "component overflow " + width + ": " + JSON.stringify(result),
    );
    assert(
      result.white === "rgb(255, 255, 255)" &&
        result.mapWhite === "rgb(255, 255, 255)" &&
        result.controls &&
        result.states === 51,
      "white/controls " + width,
    );
    if (width < 760) assert(result.gutter === 16, "phone gutter");
    reports.push(result);
  }
  for (const features of [
    [{ name: "prefers-color-scheme", value: "dark" }],
    [{ name: "prefers-reduced-motion", value: "reduce" }],
    [{ name: "forced-colors", value: "active" }],
  ]) {
    await call("Emulation.setEmulatedMedia", { features });
    assert(
      await evaluate(
        `getComputedStyle(document.querySelector('.coverage')).backgroundColor==='rgb(255, 255, 255)'&&[...document.querySelectorAll('.coverage button,.coverage select')].every(e=>getComputedStyle(e).visibility==='visible')`,
      ),
      "appearance controls/white " +
        JSON.stringify(features) +
        " " +
        JSON.stringify(
          await evaluate(
            `({bg:getComputedStyle(document.querySelector('.coverage')).backgroundColor,visible:[...document.querySelectorAll('.coverage button,.coverage select')].map(e=>getComputedStyle(e).visibility)})`,
          ),
        ),
    );
    reports.push({ media: features[0].name, pass: true });
  }
  await call("Emulation.setEmulatedMedia", { features: [] });
  // 200% desktop browser zoom via CDP device metrics: 1440 physical pixels / 2.
  await call("Emulation.setDeviceMetricsOverride", {
    width: 720,
    height: 550,
    deviceScaleFactor: 2,
    mobile: false,
  });
  assert(
    await evaluate(
      "document.documentElement.scrollWidth<=document.documentElement.clientWidth",
    ),
    "200% overflow",
  );
  reports.push({ zoom200: { physicalWidth: 1440, cssWidth: 720, pass: true } });
  // The same assertion must reject planted page overflow at the smallest width.
  await call("Emulation.setDeviceMetricsOverride", {
    width: 320,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await pageFits();
  await evaluate(
    `{const wide=document.createElement('div');wide.id='overflow-negative';wide.style.width='1000px';wide.style.height='1px';document.body.append(wide)}`,
  );
  let overflowRejected = false;
  try {
    await pageFits();
  } catch (error) {
    if (!error.message.startsWith("page-level horizontal overflow:"))
      throw error;
    overflowRejected = true;
  } finally {
    await evaluate(`document.querySelector('#overflow-negative').remove()`);
  }
  assert(overflowRejected, "wide element was accepted");
  await pageFits();
  reports.push({
    negative: "planted wide element at 320px",
    rejected: overflowRejected,
  });
  // Tab order and native closed-select type-ahead: no synthetic change events.
  await navigate();
  await ready();
  const key = async (name, code = name, vk = 0, modifiers = 0) => {
    for (const type of ["keyDown", "keyUp"])
      await call("Input.dispatchKeyEvent", {
        type,
        key: name,
        code,
        windowsVirtualKeyCode: vk,
        modifiers,
        ...(type === "keyDown" && (name.length === 1 || name === "Enter")
          ? { text: name === "Enter" ? "\r" : name }
          : {}),
      });
  };
  const focused = async (selector) =>
    assert(
      await evaluate(
        `document.activeElement===document.querySelector(${JSON.stringify(selector)})`,
      ),
      "unexpected keyboard focus: " + selector,
    );
  const focusVisible = async () =>
    assert(
      await evaluate(
        `(()=>{const e=document.activeElement,s=getComputedStyle(e),r=e.getBoundingClientRect();return e.matches(':focus-visible')&&s.outlineStyle==='solid'&&parseFloat(s.outlineWidth)>=3&&s.outlineOffset==='5px'&&s.outlineColor==='rgb(11, 98, 88)'&&r.left>=0&&r.right<=document.documentElement.clientWidth&&r.top>=0&&r.bottom<=innerHeight})()`,
      ),
      "focus ring missing or control offscreen",
    );
  const layerSelector = (layer) => '[data-coverage-layer="' + layer + '"]';
  await evaluate(`document.querySelector('.verification .table').focus()`);
  await key("ArrowRight", "ArrowRight", 39);
  await wait(`document.querySelector('.verification .table').scrollLeft>0`);
  await focused(".verification .table");
  reports.push({ verificationRegionKeyboardScroll: true });
  await key("Tab", "Tab", 9);
  await focused("#coverage-full-page");
  await key("Tab", "Tab", 9);
  await focused("#coverage-share");
  await focusVisible();
  for (const layer of ["providers", "prescriptions", "premiums"]) {
    await key("Tab", "Tab", 9);
    await focused(layerSelector(layer));
    await focusVisible();
    await key(
      layer === "prescriptions" ? "Enter" : " ",
      layer === "prescriptions" ? "Enter" : "Space",
      layer === "prescriptions" ? 13 : 32,
    );
    await wait(
      `document.querySelector('${layerSelector(layer)}').getAttribute('aria-pressed')==='true'`,
    );
    await focused(layerSelector(layer));
    assert(
      await evaluate(
        `document.querySelector('#coverage-message').textContent.startsWith('${layer[0].toUpperCase() + layer.slice(1)}, plan year 2026.')`,
      ),
      "layer announcement",
    );
  }
  await key("Tab", "Tab", 9);
  await focused("#coverage-year");
  await focusVisible();
  const typeAhead = async (text) => {
    // Native select search buffers expire after one second on Chrome/macOS.
    await pause(1100);
    for (const char of text)
      await key(
        char,
        char === " "
          ? "Space"
          : /\d/.test(char)
            ? "Digit" + char
            : "Key" + char.toUpperCase(),
        char.toUpperCase().charCodeAt(0),
      );
  };
  for (const year of [2027, 2026]) {
    await typeAhead(String(year));
    await wait(
      `document.querySelector('#coverage-year').value==='${year}'&&document.querySelector('#coverage-title').textContent.endsWith('${year}')`,
    );
    await focused("#coverage-year");
    await focusVisible();
    assert(
      await evaluate(
        `document.querySelector('#coverage-message').textContent.includes('plan year ${year}')`,
      ),
      "year announcement",
    );
  }
  await key("Tab", "Tab", 9);
  await focused("#coverage-state");
  await focusVisible();
  const keyboardStates = [];
  for (const [state, name] of [
    ["AK", "Alaska"],
    ["DC", "District of Columbia"],
    ["HI", "Hawaii"],
    ["TX", "Texas"],
  ]) {
    await typeAhead(name);
    await wait(
      `document.querySelector('#coverage-state').value==='${state}'&&document.querySelector('#coverage-message').textContent.includes('${name}:')`,
    );
    await focused("#coverage-state");
    await focusVisible();
    keyboardStates.push(state);
    assert(
      await evaluate(
        `document.querySelector('[data-state="${state}"]').dataset.selected==='true'&&document.querySelector('#coverage-state-name').textContent.startsWith('${name} · Premiums · Plan year 2026')`,
      ),
      "keyboard state detail/map",
    );
  }
  assert(
    await evaluate(
      `(()=>{const e=document.querySelector('#coverage-message');return e.getAttribute('role')==='status'&&e.getAttribute('aria-live')==='polite'&&e.getAttribute('aria-atomic')==='true'})()`,
    ),
    "live status semantics",
  );
  const { nodes } = await call("Accessibility.getFullAXTree");
  assert(
    nodes.some(
      (n) =>
        n.role?.value === "status" &&
        n.properties?.some(
          (p) => p.name === "live" && p.value.value === "polite",
        ) &&
        n.properties?.some(
          (p) => p.name === "atomic" && p.value.value === true,
        ),
    ),
    "live status absent from accessibility tree",
  );
  await key("Tab", "Tab", 9);
  await focused(".coverage-map > p a");
  await key("Tab", "Tab", 9, 8);
  await focused("#coverage-state");
  await key("Tab", "Tab", 9, 8);
  await focused("#coverage-year");
  reports.push({
    keyboard: {
      tabOrder: [
        "validation region",
        "full page",
        "share",
        "providers",
        "prescriptions",
        "premiums",
        "year",
        "state",
        "map attribution",
      ],
      reverseTab: true,
      buttonsSpaceAndEnter: true,
      nativeYearTypeAhead: [2027, 2026],
      nativeStateTypeAhead: keyboardStates,
      focusVisible: true,
      focusPreserved: true,
      liveStatusAX: true,
      announcementsUpdated: true,
    },
  });
  // Both pages restore all three URL parameters, replace state, and share the full-page link.
  for (const page of ["", "availability"]) {
    await navigate(page + "?layer=prescriptions&year=2026&state=NC");
    await ready();
    assert(
      await evaluate(
        `document.querySelector('#coverage-state').value==='NC'&&document.querySelector('#coverage-state-name').textContent==='North Carolina · Prescriptions · Plan year 2026'`,
      ),
      "URL state ignored on " + page,
    );
    await evaluate(
      `{history.pushState(null,'','?layer=premiums&year=2027&state=FL');dispatchEvent(new PopStateEvent('popstate'))}`,
    );
    await wait(
      `document.querySelector('#coverage-state-name').textContent==='Florida · Premiums · Plan year 2027'`,
    );
    await evaluate(`history.back()`);
    await wait(
      `document.querySelector('#coverage-state-name').textContent==='North Carolina · Prescriptions · Plan year 2026'`,
    );
    await evaluate(`history.forward()`);
    await wait(
      `document.querySelector('#coverage-state-name').textContent==='Florida · Premiums · Plan year 2027'`,
    );
    await evaluate(
      `{Object.defineProperty(navigator,'share',{configurable:true,value:undefined});Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.copiedSelection=value}}});document.querySelector('#coverage-share').click()}`,
    );
    await wait(
      `document.querySelector('#coverage-share-message').textContent==='Link copied'`,
    );
    assert(
      await evaluate(
        `(()=>{const u=new URL(window.copiedSelection);return u.pathname==='/availability'&&u.searchParams.get('layer')==='premiums'&&u.searchParams.get('year')==='2027'&&u.searchParams.get('state')==='FL'})()`,
      ),
      "clipboard link lost selection",
    );
    const tree = await call("Accessibility.getFullAXTree");
    assert(
      tree.nodes.some(
        (n) =>
          n.role?.value === "status" &&
          n.properties?.some(
            (p) => p.name === "live" && p.value.value === "polite",
          ),
      ),
      "share confirmation absent from accessibility tree",
    );
    await evaluate(
      `{Object.defineProperty(navigator,'share',{configurable:true,value:async value=>{window.nativeSelection=value.url}});document.querySelector('#coverage-share').click()}`,
    );
    await wait(
      `document.querySelector('#coverage-share-message').textContent==='Link shared'`,
    );
    assert(
      await evaluate(`window.nativeSelection===window.copiedSelection`),
      "native share lost selection",
    );
    reports.push({
      page: page || "landing",
      URLStateRestored: true,
      backForwardRestored: true,
      shareClipboardSelection: true,
      copyConfirmation: true,
      nativeShareSelection: true,
    });
  }
  // A document-start fetch wrapper mutates temporary response bytes, not production files.
  async function withInit(source, test) {
    const { identifier } = await call("Page.addScriptToEvaluateOnNewDocument", {
      source,
    });
    try {
      await test();
    } finally {
      await call("Page.removeScriptToEvaluateOnNewDocument", { identifier });
    }
  }
  const injector = (mutation) => `{
  const original=window.fetch.bind(window);let changed;window.fetch=async (input,options)=>{
   const url=String(input);const response=await original(input,options);
   if(url.endsWith('index.json')){
    const i=await response.json();const entry=i.datasets.find(d=>d.path==='providers-2026.json');
    const d=await (await original('data/coverage/providers-2026.json')).json();
    ${mutation}
    changed=JSON.stringify(d);const raw=new TextEncoder().encode(changed);
    entry.bytes=raw.length;entry.sha256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('');
    return new Response(JSON.stringify(i),{status:200});
   }
   if(url.endsWith('providers-2026.json')&&changed)return new Response(changed,{status:200});return response;
  };
 }`;
  async function fallback(label) {
    await navigate();
    await wait(
      `document.querySelector('#coverage-message').textContent.includes('could not')||document.querySelector('#coverage-message').textContent.includes('unavailable')`,
    );
    assert(
      await evaluate(
        `document.querySelector('#coverage-state').disabled&&document.querySelectorAll('#coverage-table tbody tr').length===51&&document.querySelector('#coverage-table').textContent.includes('203592/203592 (100.0%)')&&document.querySelector('#coverage-title').textContent==='Coverage for plan year 2026'&&document.querySelector('[data-state="GA"]').getAttribute('fill')==='var(--teal-800)'`,
      ),
      "fallback " + label,
    );
    reports.push({ negative: label, rejected: true });
  }
  for (const [label, mutation] of [
    ["impossible percent", "d.states.TX.percent_tenths=1001;"],
    ["omitted state", "delete d.states.DC;"],
    [
      "HTML reason",
      `d.states.AK.reason_codes=['<img src=x onerror=alert(1)>'];`,
    ],
    ["wrong year", "d.year=2027;"],
    ["wrong schema", "d.schema_version=999;"],
    [
      "unknown replaced by numeric zero",
      "d.states.AK.numerator=0;d.states.AK.percent_tenths=0;",
    ],
  ])
    await withInit(injector(mutation), () => fallback(label));
  await withInit(
    `{const f=window.fetch.bind(window);window.fetch=async(...args)=>String(args[0]).endsWith('providers-2026.json')?new Response('{}',{status:200}):f(...args);}`,
    () => fallback("corrupt dataset hash"),
  );
  for (const [label, body] of [
    ["dataset 404", "new Response('',{status:404})"],
    ["invalid JSON", "new Response('{',{status:200})"],
  ])
    await withInit(
      `{const f=window.fetch.bind(window);window.fetch=async(...args)=>String(args[0]).endsWith('providers-2026.json')?${body}:f(...args);}`,
      () => fallback(label),
    );
  await withInit(
    `{const f=window.fetch.bind(window);window.fetch=async(...args)=>{const r=await f(...args);if(String(args[0]).endsWith('index.json')){const i=await r.json();i.schema_version=999;return new Response(JSON.stringify(i))}return r}}`,
    () => fallback("index schema"),
  );
  await withInit(
    `{const f=window.fetch.bind(window);window.fetch=async(...args)=>String(args[0]).endsWith('index.json')?new Response('',{status:404}):f(...args);}`,
    () => fallback("index 404"),
  );
  // Later failure must retain the previously validated non-default data and its URL.
  await navigate("?year=2027&layer=premiums");
  await ready();
  const previous = await evaluate(
    `document.querySelector('#coverage-table').textContent`,
  );
  await evaluate(
    `{const f=window.fetch.bind(window);window.fetch=async(...a)=>String(a[0]).endsWith('providers-2027.json')?new Response('',{status:404}):f(...a);document.querySelector('[data-coverage-layer="providers"]').click()}`,
  );
  await wait(
    `document.querySelector('#coverage-message').textContent.includes('could not')`,
  );
  assert(
    await evaluate(
      `document.querySelector('#coverage-table').textContent===${JSON.stringify(previous)}&&document.querySelector('#coverage-title').textContent.endsWith('2027')&&document.querySelector('[data-coverage-layer="premiums"]').getAttribute('aria-pressed')==='true'&&new URL(location.href).searchParams.get('layer')==='premiums'`,
    ),
    "later failure replaced valid snapshot",
  );
  reports.push({ negative: "later selection 404", retainedLastValid: true });
  // Ignore abort on purpose, so request-id gating itself must reject the old response.
  await navigate();
  await ready();
  await evaluate(
    `{const f=window.fetch.bind(window);window.fetch=async(input,options)=>{if(String(input).endsWith('providers-2026.json')){await new Promise(r=>setTimeout(r,700));return f(input)}return f(input,options)};document.querySelector('[data-coverage-layer="providers"]').click();document.querySelector('[data-coverage-layer="prescriptions"]').click()}`,
  );
  await wait(
    `document.querySelector('[data-coverage-layer="prescriptions"]').getAttribute('aria-pressed')==='true'`,
  );
  await pause(900);
  assert(
    await evaluate(
      `document.querySelector('#coverage-download').getAttribute('href').endsWith('prescriptions-2026.json')&&new URL(location.href).searchParams.get('layer')==='prescriptions'`,
    ),
    "old request replaced new selection",
  );
  reports.push({
    negative: "delayed old fetch ignores abort",
    newestWon: true,
  });
  await call("Emulation.setScriptExecutionDisabled", { value: true });
  await navigate("?year=2027&layer=premiums");
  await call("Emulation.setScriptExecutionDisabled", { value: false });
  assert(
    await evaluate(
      `document.querySelector('#coverage-state').disabled&&document.querySelectorAll('#coverage-table tbody tr').length===51&&document.querySelector('#coverage-title').textContent.endsWith('2026')`,
    ),
    "no-script fallback",
  );
  await pageFits();
  reports.push({
    negative: "scripts disabled with nondefault URL",
    datedDefaultRetained: true,
  });
  await navigate();
  await ready();
  // Planted visual negatives prove the computed-style and rendered year checks can fail.
  await evaluate(
    `document.querySelector('.coverage').style.backgroundColor='black'`,
  );
  assert(
    !(await evaluate(
      `getComputedStyle(document.querySelector('.coverage')).backgroundColor==='rgb(255, 255, 255)'`,
    )),
    "white negative did not fail",
  );
  await evaluate(
    `document.querySelector('.coverage').style.removeProperty('background-color');document.querySelector('#coverage-title').textContent='Coverage'`,
  );
  assert(
    !(await evaluate(
      `document.querySelector('#coverage-title').textContent==='Coverage for plan year 2026'`,
    )),
    "missing-year negative did not fail",
  );
  await evaluate(
    `document.querySelector('#coverage-title').textContent='Coverage for plan year 2027'`,
  );
  assert(
    !(await evaluate(
      `document.querySelector('#coverage-title').textContent==='Coverage for plan year '+document.querySelector('#coverage-year').value`,
    )),
    "mismatched-year negative did not fail",
  );
  reports.push({
    negative: "white ground and rendered year absent/mismatched",
    detected: true,
  });
  // A measured zero has a white fill; quarantine and unknown retain their distinct patterns.
  await withInit(
    injector(
      `Object.assign(d.states.FL,{numerator:0,percent_tenths:0,warnings:[],counts:{active_complete:0,active_partial:0,quarantined:0,unknown:26,not_imported:0}});`,
    ),
    async () => {
      await navigate("?layer=providers&year=2026");
      await ready();
      assert(
        await evaluate(
          `document.querySelector('[data-state="FL"]').getAttribute('fill')==='white'&&document.querySelector('[data-state="GA"]').getAttribute('fill')==='url(#coverage-quarantine)'&&document.querySelector('[data-state="AK"]').getAttribute('fill')==='url(#coverage-unknown)'`,
        ),
        "zero/quarantine/unknown distinction",
      );
    },
  );
  reports.push({ zeroQuarantineUnknownDistinct: true });
  await withInit(
    `Date.now=()=>Date.parse('2026-11-16T13:00:00Z')`,
    async () => {
      await navigate();
      await ready();
      assert(
        await evaluate(
          `document.querySelector('#coverage-date').textContent.includes('more than 7 days old')`,
        ),
        "stale date",
      );
    },
  );
  reports.push({ snapshotAgeOver7DaysLabelled: true });
  for (const page of ["", "availability"])
    for (const width of [1280, 390, 320]) {
      const height = width === 1280 ? 1200 : 1800;
      await call("Emulation.setDeviceMetricsOverride", {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await navigate(page);
      await ready();
      await pageFits();
      await evaluate(
        `document.querySelector('#availability').scrollIntoView()`,
      );
      const name = (page ? "availability" : "landing") + "-" + width;
      const shot = await call("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
      });
      await fs.writeFile(
        path.join(out, name + ".png"),
        Buffer.from(shot.data, "base64"),
      );
      reports.push({
        page: page || "landing",
        width,
        noOverflow: true,
        capture: name + ".png",
      });
    }
  await evaluate(`document.querySelector('#coverage-table').scrollIntoView()`);
  const tableShot = await call("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  await fs.writeFile(
    path.join(out, "availability-table-320.png"),
    Buffer.from(tableShot.data, "base64"),
  );
  const uniqueRequests = [...new Set(requests.map((r) => r.url))];
  assert(
    uniqueRequests.every((u) => new URL(u).origin === new URL(url).origin),
    "remote coverage request",
  );
  reports.push({
    coverageRequests: uniqueRequests,
    coverageRequestsSameOrigin: true,
  });
  await fs.writeFile(
    path.join(out, "browser-checks.json"),
    JSON.stringify(reports, null, 2) + "\n",
  );
  console.log(JSON.stringify(reports, null, 2));
  console.log(
    "PASS: coverage browser checks (306 selections, responsive/appearance, keyboard, fallback, hashes and race controls)",
  );
} finally {
  ws.close();
}
