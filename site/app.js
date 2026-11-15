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
// The list is ours, not the API's: rows are keyed by request id and keep their element for as long as they are
// on screen. A poll never reorders the list. It changes outcomes in place and puts new shoppers in a short
// queue; a trickle takes one shopper from the queue at a time, at most one a second, and slides the list down
// one row (FLIP, transforms only). When more than a few are waiting, the oldest waiting shoppers are skipped.
const feed = [];                 // {r, el, sig, move}, newest first
const queue = [];                // rows waiting to enter, oldest first
const passed = new Set();        // request ids we saw: on screen, queued or skipped
const latest = new Map();        // request id -> newest version of the row
let feedKey = "", gap = 1250, lastIn = 0, trickleT = 0;
const QUEUE = 4, MIN_GAP = 1000, MAX_GAP = 1500;
const MOVE = { duration: 650, easing: "cubic-bezier(.45, .05, .25, 1)" };
const maxRows = () => narrow() ? 7 : 16;
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
function rowOf(r) {
  const el = document.createElement("div");
  el.className = "row";
  fill(el, r);
  return { r, el, sig: sig(r), move: null };
}

function stream(rows) {
  const box = $("rows"), max = maxRows();
  while (feed.length > max) feed.pop().el.remove();          // the layout changed to a phone
  if (!rows.length && !feed.length) { box.innerHTML = '<p class="empty">Waiting for the first shopper.</p>'; return; }
  const key = rows.map((r) => r.rid + sig(r)).join();
  if (key === feedKey) return;                               // the server cache did not change
  feedKey = key;
  latest.clear();
  rows.forEach((r) => latest.set(r.rid, r));

  if (!feed.length) {                                        // first fill: no motion, newest on top
    box.innerHTML = "";
    rows.slice(0, max).forEach((r) => { const f = rowOf(r); feed.push(f); box.append(f.el); });
    rows.forEach((r) => passed.add(r.rid));
    return;
  }
  // 1. rows on screen: change the outcome in place
  feed.forEach((f) => {
    const r = latest.get(f.r.rid);
    if (!r) return;
    const s = sig(r);
    if (s !== f.sig) { f.r = r; f.sig = s; fill(f.el, r); flash(f.el); }
  });
  // 2. new shoppers, not older than the top row, wait in the queue oldest first; beyond a few, the oldest are skipped
  const top = feed[0].r.ts;
  rows.filter((r) => !passed.has(r.rid) && r.ts >= top).forEach((r) => queue.push(r));
  rows.forEach((r) => passed.add(r.rid));
  queue.sort((a, b) => a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0);
  queue.splice(0, Math.max(0, queue.length - QUEUE));
  if (passed.size > 600) { passed.clear(); [...latest.keys(), ...feed.map((f) => f.r.rid), ...queue.map((r) => r.rid)].forEach((id) => passed.add(id)); }
  // spread the queue over about one data refresh (5 s), never faster than one row a second
  gap = Math.min(MAX_GAP, Math.max(MIN_GAP, 4500 / Math.max(1, queue.length)));
  trickle();
}

function trickle() {
  if (trickleT || !queue.length) return;
  trickleT = setTimeout(() => {
    trickleT = 0;
    enter();
    trickle();
  }, Math.max(0, lastIn + gap - performance.now()));
}

function enter() {
  const q = queue.shift();
  if (!q) return;
  lastIn = performance.now();
  const box = $("rows"), max = maxRows(), r = latest.get(q.rid) || q;
  const animate = !still && !document.hidden;
  const before = new Map();
  if (animate) feed.forEach((f) => before.set(f, f.el.getBoundingClientRect().top));   // where they are, motion in flight included
  const boxTop = animate ? box.getBoundingClientRect().top : 0;

  const f = rowOf(r);
  feed.unshift(f);
  box.prepend(f.el);
  const leaving = [];
  while (feed.length > max) leaving.push(feed.pop());
  if (!animate) { leaving.forEach((l) => l.el.remove()); return; }

  // the bottom row leaves the flow where it is, then slides out under the bottom edge while it fades
  leaving.forEach((l) => {
    if (l.move) l.move.cancel();
    Object.assign(l.el.style, { position: "absolute", left: 0, right: 0, top: (before.get(l) - boxTop) + "px" });
  });
  feed.forEach((g) => { if (g.move) { g.move.cancel(); g.move = null; } });
  const pitch = f.el.offsetHeight;                           // the one layout read after all the writes
  const after = feed.map((g) => g.el.getBoundingClientRect().top);
  feed.forEach((g, i) => {
    if (!before.has(g)) return;
    const dy = before.get(g) - after[i];
    if (Math.abs(dy) > .5) g.move = g.el.animate([{ transform: `translateY(${dy}px)` }, { transform: "translateY(0)" }], MOVE);
  });
  // the new row comes down from under the column header while the rows below make room for it
  f.move = f.el.animate([{ transform: `translateY(${-pitch}px)`, opacity: 0 }, { opacity: .4, offset: .5 }, { transform: "translateY(0)", opacity: 1 }], MOVE);
  leaving.forEach((l) => {
    l.el.animate([{ transform: "translateY(0)", opacity: 1 }, { transform: `translateY(${pitch}px)`, opacity: 0 }], MOVE)
      .finished.then(() => l.el.remove(), () => l.el.remove());
  });
}
// a hidden tab gets no motion; when it is shown again, drop what piled up and carry on
document.addEventListener("visibilitychange", () => { if (!document.hidden) { queue.splice(0, Math.max(0, queue.length - 1)); trickle(); } });
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

// ---------- 4 the fleet ----------
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
  main: { t: "Orchestrator agent", d: "Decides and plans. Hands work to the other agents." },
  builders: { t: "Builder agents", d: "Write and test code." },
  analysts: { t: "Analyst agents", d: "Get only the data, not our beliefs." },
  workers: { t: "Insight workers", d: "Run in parallel. Ask a question, query RawTree through MCP, record a verdict." },
  rawtree: { t: "RawTree", d: "Shared memory. Every event, answer, question, finding and verdict is a row that any agent can query with SQL or through MCP.", k: "mem" },
  source: { t: "Data stream", d: "Events arrive all the time and their pattern drifts." },
  service: { t: "Live service", d: "Answers each event. Strategies share the traffic." },
  operator: { t: "Operator", d: "An unattended loop that moves live traffic to winners." },
};
// Two views of the same structure: only the "here" lines, the edge words and the numbers change.
const VIEWS = {
  shop: {
    h: {
      main: "here: the main Claude Code session",
      builders: "here: strategies, model trainers, SQL",
      analysts: "here: subagent 1, \"fresh eyes\"",
      workers: "here: workers w1, w2 and w3",
      source: "here: a simulated shop, 3 shoppers a second",
      service: "here: a router on a small VM",
      operator: "here: a check every 15 min, ran overnight",
    },
    words: {},
  },
  fleet: {
    h: {
      main: "example: one session that owns the fleet brief",
      builders: "example: alert thresholds, anomaly models, SQL",
      analysts: "example: a fresh look at raw readings",
      workers: "example: \"which sensors drifted since the last firmware?\"",
      source: "example: a fleet of sensors streaming readings",
      service: "example: thresholds and anomaly models served to the devices",
      operator: "example: favours rules technicians confirm",
    },
    words: { events: "readings", "10 products": "alerts", feedback: "incidents", "moves traffic": "moves devices" },
    values: { source: "example, not running" },
  },
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
// Draw boxes and arrows into an <svg>. Edge: [from, side, to, side, label, loop, labelBeside, bothWays].
function drawGraph(el, L, nodes, prefix, words = {}, flow = true) {
  const tall = L.box[0] < L.box[1];
  el.innerHTML = "";
  el.setAttribute("viewBox", `0 0 ${L.box[0]} ${L.box[1]}`);
  const defs = svg("defs", {}, el);
  const mk = svg("marker", { id: prefix + "-arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 8, markerHeight: 8, orient: "auto-start-reverse" }, defs);
  svg("path", { d: "M0,1 L10,5 L0,9 z", class: "arrow" }, mk);
  const edges = svg("g", {}, el), labels = [];
  L.edges.forEach(([a, as, b, bs, label, loop, beside, both], i) => {
    const p = anchor(L.nodes[a], as), q = anchor(L.nodes[b], bs);
    const straight = (p[2] === 0 && q[2] === 0 && p[0] === q[0]) || (p[3] === 0 && q[3] === 0 && p[1] === q[1] && p[2] !== q[2]);
    const k = straight ? 0 : tall ? 38 : Math.min(60, Math.hypot(q[0] - p[0], q[1] - p[1]) / 2);
    const d = `M${p[0]},${p[1]} C${p[0] + p[2] * k},${p[1] + p[3] * k} ${q[0] + q[2] * k},${q[1] + q[3] * k} ${q[0]},${q[1]}`;
    const path = svg("path", { d, class: "edge" + (loop ? " loop" : ""), id: `${prefix}-e${i}`, "marker-end": `url(#${prefix}-arrow)` }, edges);
    if (both) path.setAttribute("marker-start", `url(#${prefix}-arrow)`);
    if (label) {
      const m = path.getPointAtLength(path.getTotalLength() / 2);
      labels.push([beside ? { x: m.x + 10, y: m.y + 4, class: "elbl" } : { x: m.x, y: m.y - 8, "text-anchor": "middle", class: "elbl" }, words[label] || label]);
    }
    if (flow && !still && !tall) {   // one slow dot per edge shows the direction of flow
      const c = svg("circle", { r: 3, class: "flow" }, edges);
      const am = svg("animateMotion", { dur: "4s", repeatCount: "indefinite", begin: (-i * .37) + "s" }, c);
      svg("mpath", { href: `#${prefix}-e${i}` }, am);
    }
  });
  for (const id in nodes) {
    const [x, y, w, h] = L.nodes[id], n = nodes[id], pad = 16;
    const g = svg("g", { class: "node " + (n.k || "") }, el);
    svg("rect", { x, y, width: w, height: h, rx: 12 }, g);
    svg("text", { x: x + pad, y: y + (n.k ? 36 : 28), class: "t" }, g).textContent = n.t;
    const yy = wrap(g, n.d, "d", x + pad, y + (n.k ? 62 : 49), w - 2 * pad, 13.5, 18);
    if (n.h) wrap(g, n.h, "h", x + pad, yy + 3, w - 2 * pad, 12.5, 16);
    svg("text", { x: x + pad, y: y + h - 14, class: "v", id: `${prefix}-v-${id}`, "data-x": x + pad }, g);
  }
  labels.forEach(([attrs, label]) => (svg("text", attrs, el).textContent = label));
}
function setValues(prefix, values) {
  for (const id in values) {
    const t = $(`${prefix}-v-${id}`);
    if (!t || t.dataset.s === values[id]) continue;
    t.dataset.s = values[id];
    const lines = (values[id] || "").split("\n");
    t.textContent = "";
    lines.forEach((l, i) => (svg("tspan", { x: t.dataset.x, dy: i ? 17 : -(lines.length - 1) * 17 }, t).textContent = l));
  }
}
let layoutKey = "";
function diagram(values) {
  const tall = narrow(), L = tall ? TALL : WIDE;
  const key = tall ? "tall" : "wide";
  if (key !== layoutKey) {
    layoutKey = key;
    for (const v in VIEWS) {
      const nodes = {};
      for (const id in NODES) nodes[id] = { ...NODES[id], h: VIEWS[v].h[id] };
      drawGraph($("diagram-" + v), L, nodes, v, VIEWS[v].words);
      if (VIEWS[v].values) setValues(v, VIEWS[v].values);
    }
  }
  setValues("shop", values);   // live numbers only in the view of what is running
}
const VIEW_NOTE = {
  shop: "Live: the blue numbers are read from RawTree every 5 seconds.",
  fleet: "Example only, nothing here is running. The roles, RawTree and the loop are the same; the stream is a fleet of devices.",
};
document.querySelector(".viewpick").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-view]");
  if (!b) return;
  const v = b.dataset.view;
  document.querySelectorAll(".viewpick button").forEach((x) => x.setAttribute("aria-pressed", x === b));
  for (const k in VIEWS) $("diagram-" + k).classList.toggle("on", k === v);
  $("agents-sec").dataset.view = v;
  text("viewnote", VIEW_NOTE[v]);
});

// ---------- 3 the final strategy: one left-to-right pass, and the retraining loop under it ----------
const MODEL_NODES = {
  shopper: { t: "Shopper arrives", d: "Page, device, new or returning, and what they viewed in the last minutes." },
  cands: { t: "Candidates", d: "Recently viewed products, best sellers in their subcategories and categories, overall best sellers. Up to 30 from each." },
  score: { t: "Model scores", d: "click chance × purchase chance × trend boost × price-cut boost", h: "about 34 inputs per candidate" },
  top: { t: "Top 10 shown", d: "Highest score first. Products the shopper already bought are never shown." },
  fb: { t: "Feedback in RawTree", d: "Every product shown, and whether it was clicked or bought." },
  retrain: { t: "Retrain every 20 min", d: "On our own feedback only, then pushed to the server.", k: "mem" },
};
const MODEL_WIDE = {
  box: [1290, 316],
  nodes: {
    shopper: [12, 12, 222, 156], cands: [276, 12, 222, 156], score: [540, 12, 222, 156], top: [804, 12, 222, 156], fb: [1056, 12, 222, 156],
    retrain: [700, 210, 290, 100],
  },
  edges: [
    ["shopper", "r.5", "cands", "l.5"], ["cands", "r.5", "score", "l.5"], ["score", "r.5", "top", "l.5"], ["top", "r.5", "fb", "l.5"],
    ["fb", "b.5", "retrain", "r.5", "", 1], ["retrain", "l.5", "score", "b.5", "new model", 1],
  ],
};
const MODEL_TALL = {
  box: [380, 1004],
  nodes: {
    shopper: [30, 6, 320, 118], cands: [30, 164, 320, 136], score: [30, 340, 320, 136], top: [30, 516, 320, 118], fb: [30, 674, 320, 118],
    retrain: [30, 846, 320, 126],
  },
  edges: [
    ["shopper", "b.5", "cands", "t.5"], ["cands", "b.5", "score", "t.5"], ["score", "b.5", "top", "t.5"], ["top", "b.5", "fb", "t.5"],
    ["fb", "b.5", "retrain", "t.5", "", 1], ["retrain", "r.5", "score", "r.5", "", 1],
  ],
};
let modelKey = "";
function model() {
  const key = narrow() ? "tall" : "wide";
  if (key === modelKey) return;
  modelKey = key;
  drawGraph($("model"), key === "tall" ? MODEL_TALL : MODEL_WIDE, MODEL_NODES, "model");
}
// ---------- 6 what was tested ----------
const FIGURES = [
  ["People and agents", [
    ["developers", "developer", "sets the goal and decides what ships"],
    ["sessions", "orchestrator sessions", "the developer talks to one agent at a time"],
    ["subagents", "subagents started", "builders, analysts and insight workers"],
    ["tool_calls", "agent tool calls", "every file read, query and test an agent ran"],
  ]],
  ["Ideas tested", [
    ["hypothesis_files", "hypotheses written down", "each with a claim, a test and a verdict"],
    ["strategy_files", "strategies built", "one file each, every one able to take live traffic"],
    ["arms", "strategies on live traffic", "sharing the shoppers in the last 15 minutes"],
    ["journal_entries", "journal entries", "one dated line per decision and promotion"],
  ]],
  ["Memory in RawTree", [
    ["sql_files", "SQL files run in RawTree", "features, reports and hypothesis tests"],
    ["insights", "insights in RawTree", "question, finding and verdict, stored as rows"],
    ["rawtree", "RawTree queries by agents", "through MCP, Python and the CLI combined"],
    ["questions", "questions open", "written by agents, waiting for a worker"],
  ]],
];
function figures(v) {
  const box = $("figures");
  const has = ([k]) => v[k] != null && v[k] !== "";
  const groups = FIGURES.map(([name, figs]) => [name, figs.filter(has)]).filter(([, figs]) => figs.length);
  const keys = groups.map(([, figs]) => figs.map((i) => i[0]).join()).join("|");
  if (box.dataset.keys !== keys) {
    box.dataset.keys = keys;
    box.innerHTML = groups.map(([name, figs]) => `<div class="grp"><h3 class="mono">${name}</h3><dl class="tiles">` +
      figs.map(([k, label, note]) => `<div class="fig"><dt><b>${label}</b><span>${note.replace(/\{(\w+)\}/g, (_, k) => fmt(v[k]))}</span></dt><dd class="mono" id="f-${k}">–</dd></div>`).join("") +
      "</dl></div>").join("");
    groups.forEach(([, figs]) => figs.forEach(([k]) => delete shown["f-" + k]));
  }
  groups.forEach(([, figs]) => figs.forEach(([k]) => count("f-" + k, Number(v[k]))));
}

// ---------- 7 insights ----------
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
const KINDS = [
  ["agent_trace", "Agent traces", "Every tool call an agent made: who, which tool, tokens, failures", "a trace loader"],
  ["insight", "Agent findings", "A question, the finding and a verdict, with the MCP calls it took", "insight workers"],
  ["question", "Questions asked", "Questions an agent left for a worker to answer", "agents"],
  ["claim", "Work claims", "A worker reserves a question so two never take the same one", "insight workers"],
  ["arms", "Traffic splits", "Every change to which strategy gets which share of shoppers", "the router"],
  ["operator", "Operator decisions", "The overnight loop's reading of each strategy and what it kept or retired", "the operator"],
  ["lease", "Single-writer lock", "A heartbeat that proves only one process answers the shop", "the router"],
  ["explore", "Exploration log", "Lists shown to the exploration share, so models learn about products the champion skips", "the router"],
  ["leaderboard", "Leaderboard copies", "Every public leaderboard refresh, to read our own live tests", "a logger"],
  ["block", "Test blocks", "The result of each early timed A/B block", "a logger"],
];
function kinds(rows) {
  const body = $("kinds");
  if (!body || !rows || !rows.length) return;
  const by = Object.fromEntries(rows.map((r) => [r.kind, r]));
  const known = new Set(KINDS.map((k) => k[0]));
  const other = rows.filter((r) => !known.has(r.kind)).reduce((n, r) => n + Number(r.n || 0), 0);
  const list = KINDS.filter(([k]) => by[k]).map(([k, name, what, who]) => [k, name, what, who, by[k].n, by[k].last]);
  if (other) list.push(["other", "Tests and probes", "Checks of the key, the client and the tools", "the developer", other, ""]);
  const keys = list.map((r) => r[0]).join();
  if (body.dataset.keys !== keys) {
    body.dataset.keys = keys;
    body.innerHTML = list.map(([k, name, what, who]) => `<tr><th scope="row">${esc(name)}</th><td>${esc(what)}</td><td>${esc(who)}</td><td class="num mono" id="kn-${k}">–</td><td class="num mono" id="kl-${k}"></td></tr>`).join("");
  }
  list.forEach(([k, , , , n, last]) => { count("kn-" + k, Number(n)); text("kl-" + k, last ? last.slice(5) : ""); });
}

function prod(p) {
  const el = $("dp-live");
  if (!el || !p || !p.ts) return;
  const age = Number(p.age);
  const since = p.started ? p.started.slice(5, 16) : "";
  text("dp-live", `heartbeat ${isNaN(age) ? "-" : age < 60 ? age + " s" : Math.round(age / 60) + " min"} ago${since ? " · this process since " + since + " UTC" : ""}`);
  el.classList.toggle("stale", !(age < 120));
}
const CH_COL = ["var(--ink)", "#4f7cc4", "#7fb08f", "#c9a24a", "#b36b6b"];
function champ(arms) {
  const bar = $("ch-bar"), leg = $("ch-legend");
  if (!bar || !arms || !arms.length) return;
  const total = arms.reduce((n, a) => n + a.n, 0);
  const keys = arms.map((a) => a.label).join();
  if (bar.dataset.keys !== keys) {
    bar.dataset.keys = keys;
    bar.innerHTML = arms.map((a, i) => `<span style="background:${CH_COL[i % CH_COL.length]}" id="chb-${i}"></span>`).join("");
    leg.innerHTML = arms.map((a, i) => `<span><i style="background:${CH_COL[i % CH_COL.length]}"></i>${esc(a.label || "unlabelled")} <b id="chl-${i}"></b></span>`).join("");
  }
  arms.forEach((a, i) => { $("chb-" + i).style.flexGrow = a.n; text("chl-" + i, `${Math.round(100 * a.n / total)}%`); });
  text("ch-total", `· ${fmt(total)} shoppers`);
}
function results(a) {
  if (!a) return;
  const body = $("res-traces");
  if (body && a.traces && a.traces.length) {
    body.innerHTML = a.traces.map((r) => `<tr><th scope="row">${esc(r.who)}</th><td class="num mono">${fmt(r.calls)}</td><td class="num mono">${fmt(r.agents)}</td><td class="num mono">${fmt(r.rawtree)}</td><td class="num mono">${fmt(r.errors)}</td><td class="num mono">${fmt(r.out_tokens / 1e6, 2)} M</td></tr>`).join("");
  }
  const hours = a.trace_hours || [];
  if (hours.length && $("res-hours").dataset.n !== String(hours.length)) {
    $("res-hours").dataset.n = String(hours.length);
    const max = Math.max(...hours.map((x) => x.calls));
    $("res-hours").innerHTML = hours.map((x) => `<span title="${esc(x.h.slice(5, 13))}:00 UTC, ${x.calls} calls, ${x.rawtree} on RawTree"><i style="height:${100 * x.calls / max}%"></i><b style="height:${100 * x.rawtree / max}%"></b></span>`).join("");
    text("res-hours-axis", `calls per hour, ${hours[0].h.slice(5, 13)}:00 to ${hours[hours.length - 1].h.slice(5, 13)}:00 UTC · dark: calls that queried RawTree`);
  }
  const rank = (a.rank || []).filter((x) => x.snaps >= 10);
  if (rank.length && $("res-rank").dataset.n !== String(rank.length)) {
    $("res-rank").dataset.n = String(rank.length);
    $("res-rank").innerHTML = rank.map((x) => `<span title="${esc(x.h.slice(5, 13))}:00 UTC, rank ${x.rank}"><i style="height:${100 * (43 - x.rank) / 42}%"></i><em>${Math.round(x.rank)}</em></span>`).join("");
    const best = rank.reduce((m, x) => x.rank < m.rank ? x : m, rank[0]);
    text("res-rank-axis", `hourly average of ${fmt(rank.reduce((n, x) => n + x.snaps, 0))} copies · best hour ${best.h.slice(5, 13)}:00 UTC, about ${Math.round(best.rank)}th of 42`);
  }
  const au = a.audit || [];
  if (au.length && $("res-audit").dataset.n !== String(au.length)) {
    $("res-audit").dataset.n = String(au.length);
    $("res-audit").innerHTML = au.slice(0, 4).map((x) => `<li title="${esc(x.f)}"><b>${esc(x.q)}</b>${esc(x.f.length > 240 ? x.f.slice(0, x.f.lastIndexOf(" ", 230)) + "…" : x.f)}<span>${esc(x.v)} · ${x.mcp} RawTree MCP calls</span></li>`).join("");
  }
  const v = a.verdicts || {};
  const total = (v.supported || 0) + (v.rejected || 0) + (v.open || 0);
  if (total) {
    $("res-verdicts").innerHTML = [["supported", "the data backed the idea"], ["rejected", "the data said no"], ["open", "needs another question"]]
      .map(([k, d]) => `<div><dd class="mono">${fmt(v[k] || 0)}</dd><dt><b>${k}</b>${d}</dt></div>`).join("") +
      `<p class="res-note">${Math.round(100 * (v.rejected || 0) / total)}% of ideas were rejected by the data before they cost live traffic.</p>`;
  }
}
function render(d) {
  results(d.analysis);
  prod(d.prod);
  champ(d.arms);
  kinds(d.scratch);
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
  model();
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
  figures({ ...s, arms, insights, rawtree: s.rawtree_agent_calls, questions: d.questions_open });
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
