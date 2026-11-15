// quick2query live: polls /api/live every 3 s and updates the page in place. No framework.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const narrow = () => innerWidth < 760;
const fmt = (n, d = 0) => n == null || isNaN(n) ? "–" : Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const svg = (tag, attrs = {}, parent) => {
  const el = document.createElementNS(NS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(el);
  return el;
};
const text = (id, s) => { const el = $(id); if (el && el.textContent !== s) el.textContent = s; };

// ---------- numbers: set directly the first time, count to the new value after that ----------
const shown = {};
function count(id, to, d = 0, suffix = "") {
  const el = $(id);
  if (to == null || isNaN(to)) { el.textContent = "–"; return; }
  const from = shown[id];
  shown[id] = to;
  if (still || from == null || from === to || document.hidden) { el.textContent = fmt(to, d) + suffix; return; }
  const t0 = performance.now(), dur = 500;
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e, d) + suffix;
    if (k < 1 && shown[id] === to) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ---------- category colours: fixed for the ten we know, a stable hash for any other ----------
const PALETTE = ["#a3845f", "#8bc28c", "#e39a5c", "#5fb3c4", "#c7604f", "#b07aa1", "#dcb74a", "#3f7a62", "#9fb3cc", "#d88aa0"];
const KNOWN = ["Home & Garden", "Pets", "Electronics", "Books & Media", "Toys & Baby", "Sports & Outdoors", "Home & Kitchen", "Computers & Gaming", "Fashion", "Beauty & Health"];
function colour(cat) {
  const i = KNOWN.indexOf(cat);
  if (i >= 0) return PALETTE[i];
  let h = 0;
  for (const ch of cat) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return `hsl(${h % 360} 35% 62%)`;
}
const CHECK = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ROUTE = { home: "home page", new: "new shopper", returning: "returning" };

// ---------- 1 the stream ----------
// The list is ours, not the API's: rows are keyed by request id and keep their element for as long as they
// are on screen. Each update admits a few new shoppers on top, moves the others down once (FLIP), drops the
// oldest, and changes a row's outcome in place.
const feed = [];                 // {r, el, sig}, newest first
const passed = new Set();        // request ids we saw and did not admit
let feedKey = "", paused = false, held = null;
const maxRows = () => narrow() ? 7 : 16;
const perUpdate = () => narrow() ? 2 : 4;
const sig = (r) => `${r.label}|${r.items.length}|${r.feedback ? 1 : 0}|${r.items.findIndex((i) => i.clicked)}|${r.items.findIndex((i) => i.bought)}`;

function chip(it) {
  const unknown = it.c === "?";
  const what = `${it.p} · ${unknown ? "not in the catalogue yet" : it.c}${it.clicked ? " · clicked" : ""}${it.bought ? " · bought" : ""}`;
  return `<span class="chip${unknown ? " unknown" : ""}${it.clicked ? " clicked" : ""}${it.bought ? " bought" : ""}"${unknown ? "" : ` style="background:${colour(it.c)}"`} title="${esc(what)}">${it.bought ? CHECK : ""}</span>`;
}
function fill(el, r) {
  const clicked = r.items.findIndex((it) => it.clicked), bought = r.items.findIndex((it) => it.bought);
  const chips = r.items.length ? r.items.map(chip).join("") : '<span class="chip wait"></span>'.repeat(10);
  const out = !r.items.length ? ["answering", 1] : !r.feedback ? ["waiting for feedback", 1]
    : bought >= 0 ? [`<b>bought</b> the product in slot ${bought + 1}`, 0]
    : clicked >= 0 ? [`<b>clicked</b> slot ${clicked + 1}, did not buy`, 0] : ["no click", 0];
  el.innerHTML = `<span>${esc(r.ts)}</span><span class="rid">${esc(r.id)}</span><span>${ROUTE[r.route] || esc(r.route)}</span><span class="lab">${esc(r.label || "–")}</span>` +
    `<span class="chips">${chips}</span><span class="out${out[1] ? " pending" : ""}">${out[0]}</span><span class="lat">${r.feedback && r.latency ? fmt(r.latency) + " ms" : ""}</span>`;
}
function flash(el) {
  if (still) return;
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
}

function stream(rows) {
  if (paused) { held = rows; return; }
  const box = $("rows"), max = maxRows();
  if (!rows.length && !feed.length) { box.innerHTML = '<p class="empty">Waiting for the first shopper.</p>'; return; }
  const key = rows.map((r) => r.rid + sig(r)).join();
  if (key === feedKey && feed.length <= max) return;      // the server cache did not change
  const fresh = key !== feedKey, firstFill = !feed.length;
  feedKey = key;
  if (firstFill) box.innerHTML = "";
  const animate = !still && !firstFill && !document.hidden;
  const before = new Map();
  if (animate) feed.forEach((f) => before.set(f, f.el.getBoundingClientRect().top));

  // 1. rows on screen: update in place, or let go of one that never got an answer
  const byId = new Map(rows.map((r) => [r.rid, r]));
  const changed = [], leaving = [];
  for (let i = feed.length - 1; i >= 0; i--) {
    const f = feed[i], r = byId.get(f.r.rid);
    if (r) {
      const s = sig(r);
      if (s !== f.sig) { f.r = r; f.sig = s; fill(f.el, r); changed.push(f.el); }
    } else if (!f.r.feedback) { leaving.push(f); feed.splice(i, 1); }
  }
  // 2. admit a few new shoppers, newest first; the rest are passed over for good
  const entering = [];
  if (fresh) {
    const onScreen = new Set(feed.map((f) => f.r.rid));
    const unseen = rows.filter((r) => !onScreen.has(r.rid) && !passed.has(r.rid));
    unseen.slice(0, firstFill ? max : perUpdate()).reverse().forEach((r) => {
      const el = document.createElement("div");
      el.className = "row";
      fill(el, r);
      const f = { r, el, sig: sig(r) };
      feed.unshift(f);
      box.prepend(el);
      entering.push(f);
    });
    rows.forEach((r) => passed.add(r.rid));
    for (const id of passed) if (!byId.has(id)) passed.delete(id);
  }
  // 3. keep a fixed number of rows
  while (feed.length > max) leaving.push(feed.pop());

  if (!animate) { leaving.forEach((f) => f.el.remove()); return; }
  // FLIP: take the leaving rows out of the flow where they were, then let every other row glide to its new place
  const boxTop = box.getBoundingClientRect().top, pitch = feed[0] ? feed[0].el.offsetHeight : 40;
  const opts = { duration: 420, easing: "cubic-bezier(.22,1,.36,1)" };
  leaving.forEach((f) => {
    const top = before.get(f) - boxTop;
    Object.assign(f.el.style, { position: "absolute", left: 0, right: 0, top: top + "px" });
    f.el.animate([{ opacity: 1, transform: "none" }, { opacity: 0, offset: .45 }, { opacity: 0, transform: `translateY(${entering.length * pitch}px)` }], opts)
      .finished.then(() => f.el.remove(), () => f.el.remove());
  });
  feed.forEach((f) => {
    if (!before.has(f)) return;
    const dy = before.get(f) - f.el.getBoundingClientRect().top;
    if (dy) f.el.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], opts);
  });
  entering.forEach((f) => f.el.animate([{ opacity: 0, transform: "translateY(-10px)" }, { opacity: 1, transform: "none" }], { ...opts, delay: 140, fill: "backwards" }));
  changed.forEach(flash);
}
// reading a row should not be a race: hold updates while the mouse is on the list
const feedBox = document.querySelector(".feed");
feedBox.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") { paused = true; $("paused").hidden = false; } });
feedBox.addEventListener("pointerleave", () => {
  if (!paused) return;
  paused = false;
  $("paused").hidden = true;
  if (held) { stream(held); held = null; }
});
$("legend").innerHTML = KNOWN.map((c) => `<li><i style="background:${colour(c)}"></i>${esc(c)}</li>`).join("") + '<li><i class="chip unknown"></i>new, not in the catalogue yet</li>';

// ---------- 2 the feedback ----------
const REFS = [[2.10, "the organisers' reference, 2.10%"], [0.66, "the shop's baseline, about 0.66%"]];   // docs/SIMULATOR.md, Measured
let convKey = "";
function conversion(minutes) {
  const el = $("conv");
  const done = minutes.slice(1, -1);   // the first and the current minute are partial
  const key = done.length + (done[done.length - 1] || {}).m + narrow();
  if (key === convKey) return;
  convKey = key;
  el.innerHTML = "";
  if (done.length < 2) { svg("text", { x: 20, y: 130, class: "lbl" }, el).textContent = "Not enough minutes yet."; return; }
  const W = narrow() ? 400 : 800, H = narrow() ? 280 : 260, L = 40, R = 12, T = 12, B = 30;
  el.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const pts = done.map((m) => ({ t: new Date(m.m.replace(" ", "T") + "Z"), c: m.n ? 100 * m.buys / m.n : 0, n: m.n, b: m.buys }));
  const roll = pts.map((p, i) => {
    const w = pts.slice(Math.max(0, i - 9), i + 1);
    const n = w.reduce((s, x) => s + x.n, 0);
    return n ? 100 * w.reduce((s, x) => s + x.b, 0) / n : 0;
  });
  const ymax = Math.max(4, Math.ceil(Math.max(...pts.map((p) => p.c))));
  const t0 = +pts[0].t, t1 = +pts[pts.length - 1].t;
  const x = (t) => L + (W - L - R) * (t1 > t0 ? (t - t0) / (t1 - t0) : 0);
  const y = (v) => T + (H - T - B) * (1 - v / ymax);
  const g = svg("g", { class: "grid" }, el), ax = svg("g", { class: "axis" }, el);
  for (let v = 0; v <= ymax; v += ymax > 8 ? 2 : 1) {
    svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, g);
    svg("text", { x: L - 8, y: y(v) + 4, "text-anchor": "end" }, ax).textContent = v + "%";
  }
  pts.forEach((p) => {
    if (p.t.getUTCMinutes() % (narrow() ? 60 : 30) === 0) svg("text", { x: x(+p.t), y: H - 8, "text-anchor": "middle" }, ax).textContent = p.t.toISOString().slice(11, 16) + " UTC";
  });
  pts.forEach((p) => svg("circle", { cx: x(+p.t), cy: y(p.c), r: 2, fill: "#2f55a4", "fill-opacity": .32 }, el));
  const refs = svg("g", { class: "ref" }, el);
  REFS.forEach(([v]) => svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, refs));
  const from = Math.min(9, pts.length - 2);   // the average needs a full window
  svg("path", { d: "M" + pts.slice(from).map((p, i) => `${x(+p.t).toFixed(1)},${y(roll[i + from]).toFixed(1)}`).join("L"), fill: "none", stroke: "#0b1e4a", "stroke-width": 2.5, "stroke-linejoin": "round" }, el);
  const last = roll[roll.length - 1];
  svg("circle", { cx: x(t1), cy: y(last), r: 4.5, fill: "#0b1e4a" }, el);
  svg("text", { x: x(t1) - 8, y: y(last) - 12, "text-anchor": "end", class: "big-lbl" }, el).textContent = fmt(last, 2) + "%";
  REFS.forEach(([v, label], i) => (svg("text", i ? { x: W - R - 6, y: y(v) + 15, "text-anchor": "end" } : { x: L + 8, y: y(v) - 6 }, refs).textContent = label));
  const n = done.reduce((s, m) => s + m.n, 0), b = done.reduce((s, m) => s + m.buys, 0);
  text("conv-cap", `${fmt(b)} purchases from ${fmt(n)} shoppers`);
  $("conv-note").innerHTML = `<b>What to notice:</b> the dark line is the share of shoppers who bought, averaged over 10 minutes; each dot is one minute. Over these two hours it is ${fmt(100 * b / n, 2)}%. The dashed lines are the two lists the shop itself provides: its best sellers and its reference recommender.`;
}

let slotKey = "";
function slots(by) {
  const el = $("slots");
  const W = 400, H = 260, L = 10, B = 30, T = 24;
  const vals = Array.from({ length: 10 }, (_, i) => by[i + 1] || 0);
  if (vals.join() === slotKey) return;
  slotKey = vals.join();
  el.innerHTML = "";
  const max = Math.max(1, ...vals), total = vals.reduce((a, b) => a + b, 0);
  const bw = (W - L * 2) / 10;
  vals.forEach((v, i) => {
    const h = (H - T - B) * v / max, x = L + i * bw;
    svg("rect", { x: x + 4, y: H - B - h, width: bw - 8, height: Math.max(h, 1), rx: 3, fill: i === 0 ? "#0b1e4a" : "#2f55a4", "fill-opacity": i === 0 ? 1 : .5 }, el);
    svg("text", { x: x + bw / 2, y: H - B - h - 6, "text-anchor": "middle", class: "lbl" }, el).textContent = fmt(v);
    svg("text", { x: x + bw / 2, y: H - 10, "text-anchor": "middle", class: "lbl" }, el).textContent = i + 1;
  });
  text("slot-cap", total ? `${fmt(total)} clicks` : "no clicks yet");
  if (total) $("slot-note").innerHTML = `<b>What to notice:</b> slot 1 gets ${fmt(100 * vals[0] / total)}% of the clicks and slot 10 gets ${fmt(100 * vals[9] / total)}%. Shoppers look at the first slots most, so the order of the 10 products matters as much as the choice.`;
}

// ---------- 3 the fleet ----------
// A node is [x, y, w, h]. An edge end is a side letter and how far along that side, e.g. "r.2".
const WIDE = {
  box: [1290, 590],
  nodes: {
    dev: [12, 50, 240, 140], main: [12, 280, 240, 180],
    builders: [322, 12, 270, 170], analysts: [322, 210, 270, 170], workers: [322, 408, 270, 170],
    rawtree: [702, 100, 216, 390],
    source: [998, 12, 280, 150], service: [998, 220, 280, 150], operator: [998, 428, 280, 150],
  },
  edges: [
    ["dev", "b.5", "main", "t.5"], ["main", "r.3", "builders", "l.5"], ["main", "r.5", "analysts", "l.5"], ["main", "r.7", "workers", "l.5"],
    ["builders", "r.5", "rawtree", "l.2", "", 0, 0, 1], ["analysts", "r.5", "rawtree", "l.5", "read, write", 0, 0, 1], ["workers", "r.5", "rawtree", "l.8", "", 0, 0, 1],
    ["source", "l.5", "rawtree", "r.15", "events"], ["rawtree", "r.5", "service", "l.5", "features"], ["service", "t.5", "source", "b.5", "10 products", 0, 1],
    ["rawtree", "r.85", "operator", "l.5", "feedback", 1], ["operator", "t.5", "service", "b.5", "moves traffic", 1, 1],
  ],
};
const TALL = {
  box: [380, 1494],
  nodes: {
    dev: [30, 6, 320, 100], main: [30, 140, 320, 150], builders: [30, 324, 320, 126], analysts: [30, 484, 320, 126], workers: [30, 644, 320, 144],
    rawtree: [30, 822, 320, 196], source: [30, 1052, 320, 124], service: [30, 1210, 320, 140], operator: [30, 1384, 320, 104],
  },
  edges: [
    ["dev", "b.5", "main", "t.5"], ["main", "b.5", "builders", "t.5"], ["main", "l.6", "analysts", "l.4"], ["main", "l.4", "workers", "l.4"],
    ["builders", "r.6", "rawtree", "r.3", "", 0, 0, 1], ["analysts", "r.6", "rawtree", "r.5", "", 0, 0, 1], ["workers", "b.5", "rawtree", "t.5", "", 0, 0, 1],
    ["source", "t.5", "rawtree", "b.5"], ["rawtree", "l.6", "service", "l.4"], ["service", "t.5", "source", "b.5"],
    ["rawtree", "r.7", "operator", "r.5", "", 1], ["operator", "t.5", "service", "b.5", "", 1],
  ],
};
const NODES = {
  dev: { t: "Developer", d: "One person. Sets the goal, reviews, decides what ships." },
  main: { t: "Orchestrator agent", d: "Decides and plans. Hands work to the other agents.", h: "here: the main Claude Code session" },
  builders: { t: "Builder agents", d: "Write and test code.", h: "here: strategies, model trainers, SQL" },
  analysts: { t: "Analyst agents", d: "Get only the data, not our beliefs.", h: "here: subagent 1, \"fresh eyes\"" },
  workers: { t: "Insight workers", d: "Run in parallel. Ask a question, query RawTree through MCP, record a verdict.", h: "here: workers w1, w2 and w3" },
  rawtree: { t: "RawTree", d: "Shared memory. Every event, answer, question, finding and verdict is a row that any agent can query with SQL or through MCP.", k: "mem" },
  source: { t: "Data stream", d: "Events arrive all the time and their pattern drifts.", h: "here: a simulated shop, 3 shoppers a second" },
  service: { t: "Live service", d: "Answers each event. Strategies share the traffic.", h: "here: a router on a small VM" },
  operator: { t: "Operator", d: "An unattended loop that moves live traffic to winners.", h: "here: a check every 15 min, ran overnight" },
};
function anchor([x, y, w, h], spec) {
  const side = spec[0], f = parseFloat(spec.slice(1)) || .5;
  return { r: [x + w, y + h * f, 1, 0], l: [x, y + h * f, -1, 0], t: [x + w * f, y, 0, -1], b: [x + w * f, y + h, 0, 1] }[side];
}
function wrap(parent, s, cls, x, y, width, px, lh) {
  const per = Math.floor(width / (px * .5));
  const out = [];
  let line = "";
  for (const w of s.split(" ")) {
    if ((line + " " + w).trim().length > per) { out.push(line); line = w; } else line = (line + " " + w).trim();
  }
  out.push(line);
  const t = svg("text", { x, y, class: cls }, parent);
  out.forEach((l, i) => (svg("tspan", { x, dy: i ? lh : 0 }, t).textContent = l));
  return y + out.length * lh;
}
let layoutKey = "";
function diagram(values) {
  const tall = narrow(), L = tall ? TALL : WIDE, el = $("diagram");
  const key = tall ? "tall" : "wide";
  if (key !== layoutKey) {
    layoutKey = key;
    el.innerHTML = "";
    el.setAttribute("viewBox", `0 0 ${L.box[0]} ${L.box[1]}`);
    const defs = svg("defs", {}, el);
    const mk = svg("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 8, markerHeight: 8, orient: "auto-start-reverse" }, defs);
    svg("path", { d: "M0,1 L10,5 L0,9 z", class: "arrow" }, mk);
    const edges = svg("g", {}, el), labels = [];
    L.edges.forEach(([a, as, b, bs, label, loop, beside, both], i) => {
      const p = anchor(L.nodes[a], as), q = anchor(L.nodes[b], bs);
      const straight = (p[2] === 0 && q[2] === 0 && p[0] === q[0]) || (p[3] === 0 && q[3] === 0 && p[1] === q[1] && p[2] !== q[2]);
      const k = straight ? 0 : tall ? 38 : Math.min(60, Math.hypot(q[0] - p[0], q[1] - p[1]) / 2);
      const d = `M${p[0]},${p[1]} C${p[0] + p[2] * k},${p[1] + p[3] * k} ${q[0] + q[2] * k},${q[1] + q[3] * k} ${q[0]},${q[1]}`;
      const path = svg("path", { d, class: "edge" + (loop ? " loop" : ""), id: "e" + i, "marker-end": "url(#arrow)" }, edges);
      if (both) path.setAttribute("marker-start", "url(#arrow)");
      if (label) {
        const m = path.getPointAtLength(path.getTotalLength() / 2);
        labels.push([beside ? { x: m.x + 10, y: m.y + 4, class: "elbl" } : { x: m.x, y: m.y - 8, "text-anchor": "middle", class: "elbl" }, label]);
      }
      if (!still && !tall) {   // one slow dot per edge shows the direction of flow
        const c = svg("circle", { r: 3, class: "flow" }, edges);
        const am = svg("animateMotion", { dur: "4s", repeatCount: "indefinite", begin: (-i * .37) + "s" }, c);
        svg("mpath", { href: "#e" + i }, am);
      }
    });
    for (const id in NODES) {
      const [x, y, w, h] = L.nodes[id], n = NODES[id], pad = 16;
      const g = svg("g", { class: "node " + (n.k || "") }, el);
      svg("rect", { x, y, width: w, height: h, rx: 12 }, g);
      svg("text", { x: x + pad, y: y + (n.k ? 36 : 28), class: "t" }, g).textContent = n.t;
      let yy = wrap(g, n.d, "d", x + pad, y + (n.k ? 62 : 49), w - 2 * pad, 13.5, 18);
      if (n.h) wrap(g, n.h, "h", x + pad, yy + 3, w - 2 * pad, 12.5, 16);
      svg("text", { x: x + pad, y: y + h - 14, class: "v", id: "v-" + id, "data-x": x + pad }, g);
    }
    labels.forEach(([attrs, label]) => (svg("text", attrs, el).textContent = label));
  }
  for (const id in values) {
    const t = $("v-" + id);
    if (!t || t.dataset.s === values[id]) continue;
    t.dataset.s = values[id];
    const lines = (values[id] || "").split("\n");
    t.textContent = "";
    lines.forEach((l, i) => (svg("tspan", { x: t.dataset.x, dy: i ? 17 : -(lines.length - 1) * 17 }, t).textContent = l));
  }
}

// ---------- 5 what was tested ----------
const FIGURES = [
  ["tool_calls", "agent tool calls", "every file read, query and test an agent ran"],
  ["sessions", "orchestrator sessions", "the developer talks to one agent at a time"],
  ["subagents", "subagents started", "builders, analysts and insight workers"],
  ["hypothesis_files", "hypotheses written down", "each with a claim, a test and a verdict"],
  ["sql_files", "SQL files run in RawTree", "features, reports and hypothesis tests"],
  ["strategy_files", "strategies built", "one file each, every one able to take live traffic"],
  ["arms", "strategies on live traffic", "sharing the shoppers in the last 15 minutes"],
  ["insights", "insights in RawTree", "question, finding and verdict, stored as rows"],
  ["mcp", "RawTree MCP calls", "made by the insight workers to answer their questions"],
  ["journal_entries", "journal entries", "one dated line for every decision and promotion"],
];
function figures(v) {
  const box = $("figures");
  const want = FIGURES.filter(([k]) => v[k] != null && v[k] !== "");
  const keys = want.map((i) => i[0]).join();
  if (box.dataset.keys !== keys) {
    box.dataset.keys = keys;
    box.innerHTML = want.map(([k, label, note]) => `<div class="fig"><dd id="f-${k}">–</dd><dt><b>${label}</b>${note}</dt></div>`).join("");
    want.forEach(([k]) => delete shown["f-" + k]);
  }
  want.forEach(([k]) => count("f-" + k, Number(v[k])));
}

// ---------- 6 insights ----------
// Findings are written in markdown; show them as plain text: no emphasis marks, headings or table rules.
const plain = (s) => s.replace(/\*\*|`|^#+\s*/gm, "").replace(/\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{0,}:?/g, "").replace(/\s*\|\s*\|\s*/g, " | ").replace(/\s+/g, " ").trim();
const cardEls = new Map(), openCards = new Set();
let cardsFirst = true;
function cardBody(r, key) {
  const t = plain(r.finding), long = t.length > 300, isOpen = openCards.has(key);
  const cut = t.slice(0, 280).replace(/\s+\S*$/, "");
  return `<h3>${esc(plain(r.question))}</h3><p>${esc(long && !isOpen ? cut + " …" : t)}</p>` +
    (long ? `<button class="more" type="button" aria-expanded="${isOpen}">${isOpen ? "Show less" : "Read the whole finding"}</button>` : "");
}
function cards(rows) {
  const box = $("cards");
  if (!rows.length) { if (!cardEls.size) box.innerHTML = '<p class="empty">No insight rows yet. One appears here when an agent writes it into team_01.scratch.</p>'; return; }
  rows = rows.slice(0, narrow() ? 5 : 8);
  if (!cardEls.size) box.innerHTML = "";
  const keep = new Set();
  let prev = null;
  rows.forEach((r) => {
    const key = r.ts + r.agent + r.question.slice(0, 40);
    keep.add(key);
    let el = cardEls.get(key);
    if (!el) {
      el = document.createElement("article");
      el.className = "ins";
      el.dataset.key = key;
      const verdict = (r.verdict || "").trim() || "open";
      const how = r.source === "live" ? "written live" : r.source === "backfill" ? "from our notes" : esc(r.source);
      el.innerHTML = `<div class="meta"><span>${esc(r.ts.slice(5))} UTC</span><b>${esc(r.agent)}</b><span>${how}</span>${r.mcp_calls > 0 ? `<span>${r.mcp_calls} MCP calls</span>` : ""}</div>` +
        `<div class="body">${cardBody(r, key)}</div><div class="verdict"><span class="badge v-${esc(verdict.toLowerCase().split(/[^a-z]/)[0])}" title="${esc(verdict)}">${esc(verdict.length > 16 ? verdict.slice(0, 15) + "…" : verdict)}</span></div>`;
      el.row = r;
      cardEls.set(key, el);
      if (!cardsFirst) flash(el);
    }
    const want = prev ? prev.nextSibling : box.firstChild;
    if (want !== el) box.insertBefore(el, want);
    prev = el;
  });
  for (const [key, el] of cardEls) if (!keep.has(key)) { el.remove(); cardEls.delete(key); openCards.delete(key); }
  cardsFirst = false;
}
$("cards").addEventListener("click", (e) => {
  if (!e.target.matches(".more")) return;
  const el = e.target.closest(".ins"), key = el.dataset.key;
  openCards.has(key) ? openCards.delete(key) : openCards.add(key);
  el.querySelector(".body").innerHTML = cardBody(el.row, key);
  el.querySelector(".more").focus();
});

// ---------- poll ----------
let last = null;
function render(d) {
  const age = d.stream_age_s;
  $("dot").className = "dot " + (age != null && age < 20 ? "on" : "stale");
  $("status").innerHTML = age == null ? "starting" : `${age < 20 ? "live" : "stale"} · data ${fmt(age)} s old<span class="wide"> · ${d.now} UTC</span>`;
  const t = d.today || {}, l = d.last15 || {}, s = d.stats || {};
  count("k-n", t.n);
  text("k-ontime", t.n ? `${fmt(100 * t.on_time / t.n, 2)}% inside the deadline` : "");
  count("k-buys", t.buys);
  text("k-rev", t.revenue != null ? `€${fmt(t.revenue)} in sales` : "");
  count("k-conv", l.conversion, 2, "%");
  text("k-conv-n", l.n ? `${fmt(l.buys)} of ${fmt(l.n)} shoppers` : "");
  count("k-p50", l.p50, 0, " ms");
  stream(d.stream);
  conversion(d.minutes);
  slots(d.slots);
  const insights = s.insight_rows_backfill != null ? (s.insight_rows_live || 0) + s.insight_rows_backfill : (s.insight_rows_live ?? d.insights.length);
  const arms = d.arms.length;
  diagram({
    dev: `${s.developers ?? 1} person`,
    main: [s.sessions != null && `${fmt(s.sessions)} sessions`, s.subagents != null && `${fmt(s.subagents)} subagents started`].filter(Boolean).join("\n"),
    builders: `${s.strategy_files} strategies · ${s.sql_files} SQL files`,
    analysts: `${s.hypothesis_files} hypotheses`,
    workers: `${fmt(insights)} insights${s.mcp_calls_total ? " · " + fmt(s.mcp_calls_total) + " MCP calls" : ""}`,
    rawtree: `${fmt(t.n)} answers today\n${fmt(insights)} insight rows\n${fmt(d.questions_open)} questions open`,
    source: `${fmt(t.buys)} purchases today`,
    service: `median answer ${fmt(l.p50)} ms
${arms} strategies live`,
    operator: "",
  });
  text("l-q", d.questions_open != null ? `${fmt(d.questions_open)} open now` : "");
  text("l-sql", `${fmt(s.sql_files)} SQL files`);
  text("l-str", `${fmt(s.strategy_files)} strategies built`);
  text("l-arms", `${arms} on live traffic now`);
  text("l-ins", `${fmt(insights)} verdicts recorded`);
  figures({ ...s, arms, insights, mcp: s.mcp_calls_total });
  text("tested-at", s.generated_at ? `Agent-log counts as of ${s.generated_at.slice(0, 16).replace("T", " ")} UTC.` : "");
  cards(d.insights);
  text("ins-cap", `${fmt(insights)} recorded, ${fmt(d.questions_open)} questions open.`);
  const bad = Object.entries(d.sources).filter(([, v]) => v.error);
  text("sources", bad.length ? "stale: " + bad.map(([k, v]) => `${k} ${fmt(v.age_s)} s`).join(", ") : `${Object.keys(d.sources).length} read-only RawTree queries, refreshed every 5 s and shared by every viewer`);
}
async function tick() {
  try {
    const r = await fetch("/api/live");
    last = await r.json();
  } catch (e) {
    $("dot").className = "dot stale";
    text("status", "reconnecting");
    return;
  }
  render(last);
}
let resizeT;
addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => { if (last) render(last); }, 200); });
tick();
setInterval(tick, 3000);
