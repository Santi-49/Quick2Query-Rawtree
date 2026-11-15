// quick2query live: polls /api/live every 3 s and redraws. No framework.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const fmt = (n, d = 0) => n == null || isNaN(n) ? "–" : Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const svg = (tag, attrs = {}, parent) => {
  const el = document.createElementNS(NS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(el);
  return el;
};

// ---------- numbers that count up ----------
const shown = {};
function count(id, to, d = 0, suffix = "") {
  const el = $(id);
  if (to == null || isNaN(to)) { el.textContent = "–"; return; }
  const from = shown[id] ?? 0;
  shown[id] = to;
  if (still || from === to) { el.textContent = fmt(to, d) + suffix; return; }
  const t0 = performance.now(), dur = 700;
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e, d) + suffix;
    if (k < 1) requestAnimationFrame(step);
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

// ---------- 01 the stream ----------
const seen = new Set();
let first = true;
function stream(rows) {
  const box = $("rows");
  if (!rows.length) { box.innerHTML = '<p class="empty">Waiting for the first shopper.</p>'; return; }
  box.innerHTML = rows.map((r) => {
    const isNew = !first && !seen.has(r.rid);
    const chips = r.items.length
      ? r.items.map((it) => `<span class="chip${it.clicked ? " clicked" : ""}${it.bought ? " bought" : ""}" style="background:${colour(it.c)}" title="${esc(it.p)} · ${esc(it.c)}${it.clicked ? " · clicked" : ""}${it.bought ? " · bought" : ""}">${it.bought ? CHECK : ""}</span>`).join("")
      : Array.from({ length: 10 }, () => '<span class="chip wait"></span>').join("");
    const clicked = r.items.find((it) => it.clicked), bought = r.items.find((it) => it.bought);
    const out = !r.items.length ? "answering" : !r.feedback ? "waiting for feedback"
      : bought ? `<b>bought</b> slot ${r.items.indexOf(bought) + 1} · ${fmt(r.latency)} ms`
      : clicked ? `<b>clicked</b> slot ${r.items.indexOf(clicked) + 1} · ${fmt(r.latency)} ms`
      : `no click · ${fmt(r.latency)} ms`;
    return `<div class="row${isNew ? " new" : ""}"><span>${esc(r.ts)}</span><span class="rid">${esc(r.id)}</span><span><span class="tag ${r.route}">${ROUTE[r.route]}</span></span><span class="lab">${esc(r.label || "–")}</span><span class="chips">${chips}</span><span class="out">${out}</span></div>`;
  }).join("");
  rows.forEach((r) => seen.add(r.rid));
  first = false;
  const cats = [...new Set(rows.flatMap((r) => r.items.map((i) => i.c)))].sort();
  $("legend").innerHTML = cats.map((c) => `<li><i style="background:${colour(c)}"></i>${esc(c)}</li>`).join("") +
    `<li><i style="outline:2px solid #0b1e4a;outline-offset:1px;background:#fff"></i>clicked</li><li><i style="background:#0b1e4a"></i>bought</li>`;
}

// ---------- 02 the feedback ----------
function conversion(minutes) {
  const el = $("conv");
  el.innerHTML = "";
  const done = minutes.slice(1, -1);   // the first and the current minute are partial
  if (done.length < 2) { svg("text", { x: 20, y: 130, class: "lbl" }, el).textContent = "Not enough minutes yet."; return; }
  const narrow = innerWidth < 760, W = narrow ? 400 : 800, H = narrow ? 300 : 260, L = 40, R = 12, T = 12, B = 30;
  el.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const pts = done.map((m) => ({ t: new Date(m.m.replace(" ", "T") + "Z"), c: m.n ? 100 * m.buys / m.n : 0, n: m.n, b: m.buys }));
  const roll = pts.map((p, i) => {
    const w = pts.slice(Math.max(0, i - 9), i + 1);
    const n = w.reduce((s, x) => s + x.n, 0);
    return n ? 100 * w.reduce((s, x) => s + x.b, 0) / n : 0;
  });
  const ymax = Math.max(4, Math.ceil(Math.max(...pts.map((p) => p.c)) ));
  const t0 = +pts[0].t, t1 = +pts[pts.length - 1].t;
  const x = (t) => L + (W - L - R) * (t1 > t0 ? (t - t0) / (t1 - t0) : 0);
  const y = (v) => T + (H - T - B) * (1 - v / ymax);
  const g = svg("g", { class: "grid" }, el), ax = svg("g", { class: "axis" }, el);
  const step = ymax > 8 ? 2 : 1;
  for (let v = 0; v <= ymax; v += step) {
    svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v) }, g);
    svg("text", { x: L - 8, y: y(v) + 4, "text-anchor": "end" }, ax).textContent = v + "%";
  }
  pts.forEach((p) => {
    const d = p.t;
    if (d.getUTCMinutes() % (narrow ? 60 : 30) === 0) svg("text", { x: x(+d), y: H - 8, "text-anchor": "middle" }, ax).textContent = d.toISOString().slice(11, 16);
  });
  svg("path", { d: "M" + pts.map((p) => `${x(+p.t).toFixed(1)},${y(p.c).toFixed(1)}`).join("L"), fill: "none", stroke: "#2f55a4", "stroke-opacity": .28, "stroke-width": 1 }, el);
  pts.forEach((p) => svg("circle", { cx: x(+p.t), cy: y(p.c), r: 1.8, fill: "#2f55a4", "fill-opacity": .35 }, el));
  const area = `M${x(t0)},${y(0)}L` + pts.map((p, i) => `${x(+p.t).toFixed(1)},${y(roll[i]).toFixed(1)}`).join("L") + `L${x(t1)},${y(0)}Z`;
  const defs = svg("defs", {}, el), lg = svg("linearGradient", { id: "cg", x1: 0, x2: 0, y1: 0, y2: 1 }, defs);
  svg("stop", { offset: 0, "stop-color": "#8bc28c", "stop-opacity": .45 }, lg);
  svg("stop", { offset: 1, "stop-color": "#8bc28c", "stop-opacity": 0 }, lg);
  svg("path", { d: area, fill: "url(#cg)" }, el);
  svg("path", { d: "M" + pts.map((p, i) => `${x(+p.t).toFixed(1)},${y(roll[i]).toFixed(1)}`).join("L"), fill: "none", stroke: "#0b1e4a", "stroke-width": 2.5, "stroke-linejoin": "round" }, el);
  const last = roll[roll.length - 1];
  svg("circle", { cx: x(t1), cy: y(last), r: 5, fill: "#0b1e4a" }, el);
  svg("text", { x: x(t1) - 8, y: y(last) - 12, "text-anchor": "end", class: "big-lbl" }, el).textContent = fmt(last, 2) + "%";
  const n = done.reduce((s, m) => s + m.n, 0), b = done.reduce((s, m) => s + m.buys, 0);
  $("conv-cap").textContent = `dots: each minute · line: 10-min rolling · ${fmt(b)} buys / ${fmt(n)} answers`;
}

function slots(by) {
  const el = $("slots");
  el.innerHTML = "";
  const W = 400, H = 260, L = 10, B = 30, T = 24;
  const vals = Array.from({ length: 10 }, (_, i) => by[i + 1] || 0);
  const max = Math.max(1, ...vals), total = vals.reduce((a, b) => a + b, 0);
  const bw = (W - L * 2) / 10;
  vals.forEach((v, i) => {
    const h = (H - T - B) * v / max, x = L + i * bw;
    svg("rect", { x: x + 4, y: H - B - h, width: bw - 8, height: Math.max(h, 1), rx: 4, fill: i === 0 ? "#0b1e4a" : "#2f55a4", "fill-opacity": i === 0 ? 1 : .55 }, el);
    svg("text", { x: x + bw / 2, y: H - B - h - 6, "text-anchor": "middle", class: "lbl" }, el).textContent = fmt(v);
    svg("text", { x: x + bw / 2, y: H - 10, "text-anchor": "middle", class: "lbl" }, el).textContent = i + 1;
  });
  $("slot-cap").textContent = total ? `${fmt(total)} clicks · ${fmt(100 * vals[0] / total)}% on slot 1` : "no clicks yet";
}

// ---------- 03 the agents ----------
const WIDE = {
  box: [1330, 620],
  nodes: {
    dev: [20, 255, 160, 96], main: [240, 240, 200, 126], builders: [500, 40, 220, 110], analysts: [500, 248, 220, 110], workers: [500, 456, 220, 110],
    rawtree: [780, 120, 200, 300], shop: [1120, 70, 190, 110], router: [1120, 290, 190, 110], operator: [800, 500, 250, 84],
  },
};
const TALL = {
  box: [400, 930],
  nodes: {
    dev: [90, 10, 220, 96], main: [60, 140, 280, 104], builders: [4, 300, 124, 116], analysts: [138, 300, 124, 116], workers: [272, 300, 124, 116],
    rawtree: [40, 480, 320, 130], router: [4, 670, 186, 100], shop: [210, 670, 186, 100], operator: [80, 830, 240, 84],
  },
};
const NODES = {
  dev: { t: "Developer", d: "decides, reviews, pitches" },
  main: { t: "Main agent", d: "plans, decides, keeps the journal", k: "core" },
  builders: { t: "Builder subagents", d: "strategies, SQL, tests" },
  analysts: { t: "Fresh-eyes analysts", d: "check without our conclusions" },
  workers: { t: "Insight workers", d: "ask, query, record a verdict" },
  rawtree: { t: "RawTree", d: "shared memory: events, feedback, hypotheses, verdicts", k: "mem" },
  router: { t: "Router on a VM", d: "answers in under 3 s" },
  shop: { t: "Shop", d: "simulated shoppers" },
  operator: { t: "Night operator", d: "reads feedback, moves traffic" },
};
const EDGES = [
  ["dev", "r", "main", "l", "", 0], ["main", "r", "builders", "l", "", 0], ["main", "r", "analysts", "l", "", 0], ["main", "r", "workers", "l", "", 0],
  ["builders", "r", "rawtree", "l", "", 0], ["analysts", "r", "rawtree", "l", "", 0], ["workers", "r", "rawtree", "l", "", 0],
  ["rawtree", "r", "router", "l", "features", 0], ["router", "t", "shop", "b", "10 products", 0], ["shop", "l", "rawtree", "r", "clicks, purchases", 0],
  ["rawtree", "b", "operator", "l", "reads feedback", 1], ["operator", "r", "router", "b", "moves traffic", 1],
];
const TALL_EDGES = [
  ["dev", "b", "main", "t"], ["main", "b", "builders", "t"], ["main", "b", "analysts", "t"], ["main", "b", "workers", "t"],
  ["builders", "b", "rawtree", "t"], ["analysts", "b", "rawtree", "t"], ["workers", "b", "rawtree", "t"],
  ["rawtree", "b", "router", "t"], ["router", "r", "shop", "l"], ["shop", "t", "rawtree", "b"],
  ["rawtree", "r", "operator", "r"], ["operator", "l", "router", "b"],
];
function anchor([x, y, w, h], side) {
  return { r: [x + w, y + h / 2, 1, 0], l: [x, y + h / 2, -1, 0], t: [x + w / 2, y, 0, -1], b: [x + w / 2, y + h, 0, 1] }[side];
}
let layoutKey = "";
function diagram(values) {
  const tall = innerWidth < 760, L = tall ? TALL : WIDE, el = $("diagram");
  const key = tall ? "tall" : "wide";
  if (key !== layoutKey) {
    layoutKey = key;
    el.innerHTML = "";
    el.setAttribute("viewBox", `0 0 ${L.box[0]} ${L.box[1]}`);
    const defs = svg("defs", {}, el), lg = svg("linearGradient", { id: "memgrad", x1: 0, y1: 0, x2: 1, y2: 1 }, defs);
    svg("stop", { offset: 0, "stop-color": "#2f55a4" }, lg);
    svg("stop", { offset: 1, "stop-color": "#5f9c78" }, lg);
    const edges = svg("g", {}, el), labels = [];
    EDGES.forEach((e, i) => {
      const [a, as, b, bs, label, loop] = e;
      const [ta, tas, tb, tbs] = tall ? TALL_EDGES[i] : [a, as, b, bs];
      const p = anchor(L.nodes[ta], tas), q = anchor(L.nodes[tb], tbs);
      const k = tall ? 46 : 70;
      const d = `M${p[0]},${p[1]} C${p[0] + p[2] * k},${p[1] + p[3] * k} ${q[0] + q[2] * k},${q[1] + q[3] * k} ${q[0]},${q[1]}`;
      const path = svg("path", { d, class: "edge" + (loop ? " loop" : ""), id: "e" + i }, edges);
      if (label && !tall) {
        const m = path.getPointAtLength(path.getTotalLength() / 2), upright = Math.abs(q[0] - p[0]) < Math.abs(q[1] - p[1]);
        const side = { "10 products": 1, "moves traffic": 1, "reads feedback": -1 }[label];
        labels.push([side ? { x: m.x + side * 10, y: m.y + 4, "text-anchor": side > 0 ? "start" : "end", class: "elbl" } : { x: m.x, y: m.y - 10, "text-anchor": "middle", class: "elbl" }, label]);
      }
      if (!still) {
        for (let j = 0; j < 2; j++) {
          const c = svg("circle", { r: 3.5, class: "flow" + (loop ? " loop" : "") }, edges);
          const am = svg("animateMotion", { dur: (2.6 + (i % 3) * .5) + "s", repeatCount: "indefinite", begin: (-j * 1.4 - i * .3) + "s" }, c);
          svg("mpath", { href: "#e" + i }, am);
        }
      }
    });
    for (const id in NODES) {
      const [x, y, w, h] = L.nodes[id], n = NODES[id];
      const g = svg("g", { class: "node " + (n.k || "") }, el);
      svg("rect", { x, y, width: w, height: h, rx: 14 }, g);
      const lines = tall && w < 150 ? n.t.split(" ") : [n.t];
      lines.forEach((s, i) => (svg("text", { x: x + 14, y: y + 26 + i * 19, class: "t" }, g).textContent = s));
      if (!tall || w > 150) wrap(svg("text", { x: x + 14, y: y + 26 + 20, class: "d" }, g), n.d, w - 28, x + 14);
      svg("text", { x: x + 14, y: y + h - 14, class: "v", id: "v-" + id, "data-x": x + 14 }, g);
    }
    labels.forEach(([attrs, label]) => (svg("text", attrs, el).textContent = label));
  }
  for (const id in values) {
    const t = $("v-" + id);
    if (!t) continue;
    const lines = (values[id] || "").split("\n");
    t.textContent = "";
    lines.forEach((l, i) => (svg("tspan", { x: t.dataset.x, dy: i ? 17 : -(lines.length - 1) * 17 }, t).textContent = l));
  }
}
function wrap(text, s, width, x) {
  const per = Math.floor(width / 6.6);
  let line = "", n = 0;
  const out = [];
  for (const w of s.split(" ")) {
    if ((line + " " + w).trim().length > per) { out.push(line); line = w; } else line = (line + " " + w).trim();
  }
  out.push(line);
  out.slice(0, 3).forEach((l, i) => svg("tspan", { x, dy: i ? 17 : 0 }, text).textContent = l);
}

// ---------- 04 what was tested ----------
function figures(s, armsLive) {
  const items = [
    ["tool_calls", "agent tool calls", "wide"], ["hypothesis_files", "hypotheses written down"], ["strategy_files", "strategies built"],
    ["sql_files", "SQL files run in RawTree"], ["arms", "arms live in the last 15 min"], ["subagents", "subagents started"], ["sessions", "agent sessions"],
    ["insights", "insights recorded in RawTree", "wide"], ["mcp", "RawTree MCP calls"], ["journal_entries", "journal entries"],
  ];
  const total = s.insight_rows_backfill != null ? (s.insight_rows_live || 0) + s.insight_rows_backfill : s.insight_rows_live;
  const v = { ...s, arms: armsLive, insights: total, mcp: s.mcp_calls_total };
  const box = $("figures");
  const want = items.filter(([k]) => v[k] != null && v[k] !== "");
  if (box.dataset.keys !== want.map((i) => i[0]).join()) {
    box.dataset.keys = want.map((i) => i[0]).join();
    box.innerHTML = want.map(([k, label, cls]) => `<div class="fig ${cls || ""}"><dd id="f-${k}">0</dd><dt>${label}</dt></div>`).join("");
    want.forEach(([k]) => delete shown["f-" + k]);
  }
  want.forEach(([k]) => count("f-" + k, Number(v[k])));
}

// ---------- 05 insights ----------
// Findings are written in markdown; show them as plain text: no emphasis marks, headings or table rules.
const plain = (s) => s.replace(/\*\*|`|^#+\s*/gm, "").replace(/\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{0,}:?/g, "").replace(/\s*\|\s*\|\s*/g, " | ").replace(/[ 	]{2,}/g, " ").trim();
const seenCards = new Set();
let firstCards = true;
function cards(rows) {
  const box = $("cards");
  if (!rows.length) { box.innerHTML = '<p class="empty">No insight rows yet. They appear here the moment an agent writes one into team_01.scratch.</p>'; return; }
  const open = new Set([...box.querySelectorAll(".card.open")].map((c) => c.dataset.key));
  box.innerHTML = rows.map((r) => {
    const key = r.ts + r.agent + r.question.slice(0, 40);
    const isNew = !firstCards && !seenCards.has(key);
    seenCards.add(key);
    const verdict = (r.verdict || "").trim();
    const vcls = "v-" + verdict.toLowerCase().split(/[^a-z]/)[0];
    const text = plain(r.finding), long = text.length > 340, isOpen = open.has(key);
    const finding = long && !isOpen ? text.slice(0, 320).trimEnd() + " …" : text;
    return `<article class="card panel${isNew ? " new" : ""}${isOpen ? " open" : ""}" data-key="${esc(key)}">
      <div class="meta"><span>${esc(r.ts)}</span><span>${esc(r.agent)}</span>${r.source ? `<span>${esc(r.source)}</span>` : ""}
      ${verdict ? `<span class="badge ${vcls}">${esc(verdict.length > 28 ? verdict.slice(0, 26) + "…" : verdict)}</span>` : ""}
      ${r.mcp_calls > 0 ? `<span class="badge mcp">via MCP · ${r.mcp_calls}</span>` : ""}</div>
      <h3>${esc(r.question.length > 240 ? r.question.slice(0, 236) + " …" : r.question)}</h3>
      <p>${esc(finding)}</p>${long ? `<button class="more" type="button" aria-expanded="${isOpen}">${isOpen ? "Show less" : "Read the finding"}</button>` : ""}
    </article>`;
  }).join("");
  firstCards = false;
}
$("cards").addEventListener("click", (e) => {
  if (!e.target.matches(".more")) return;
  e.target.closest(".card").classList.toggle("open");
  cards(last.insights);
});

// ---------- poll ----------
let last = null;
async function tick() {
  try {
    const r = await fetch("/api/live", { cache: "no-store" });
    const d = await r.json();
    last = d;
    const age = d.stream_age_s;
    $("dot").className = "dot " + (age != null && age < 20 ? "on" : "stale");
    $("status").innerHTML = age == null ? "starting" : `live · stream ${fmt(age, 1)} s old<span class="wide"> · ${d.now} UTC</span>`;
    const t = d.today || {}, l = d.last15 || {};
    count("k-n", t.n);
    $("k-ontime").textContent = t.n ? `${fmt(100 * t.on_time / t.n, 2)}% on time` : "";
    count("k-buys", t.buys);
    $("k-rev").textContent = t.revenue != null ? `€${fmt(t.revenue)} revenue` : "";
    count("k-conv", l.conversion, 2, "%");
    $("k-conv-n").textContent = l.n ? `${fmt(l.buys)} of ${fmt(l.n)} shoppers bought` : "";
    count("k-p50", l.p50, 0, " ms");
    stream(d.stream);
    conversion(d.minutes);
    slots(d.slots);
    const s = d.stats || {};
    const insights = s.insight_rows_backfill != null ? (s.insight_rows_live || 0) + s.insight_rows_backfill : (s.insight_rows_live ?? d.insights.length);
    diagram({
      dev: `${s.developers ?? 1} person`,
      main: s.sessions != null ? `${fmt(s.sessions)} sessions\n${fmt(s.journal_entries)} journal lines` : (s.journal_entries != null ? `${fmt(s.journal_entries)} journal lines` : ""),
      builders: s.subagents != null ? `${fmt(s.subagents)} subagents\n${s.strategy_files} strategies` : `${s.strategy_files} strategies`,
      analysts: `${s.hypothesis_files} hypotheses`,
      workers: `${fmt(insights)} insights${s.mcp_calls_total ? "\n" + fmt(s.mcp_calls_total) + " MCP calls" : ""}`,
      rawtree: `${fmt(t.n)} answers today\n${fmt(d.questions_open)} questions open`,
      router: `p50 ${fmt(l.p50)} ms\n${d.arms.length} arms live`,
      shop: `${fmt(t.buys)} purchases today`,
      operator: "runs while we sleep",
    });
    figures(s, d.arms.length);
    cards(d.insights);
    const bad = Object.entries(d.sources).filter(([, v]) => v.error);
    $("sources").textContent = bad.length ? "stale: " + bad.map(([k, v]) => `${k} ${fmt(v.age_s)} s`).join(", ") : `${Object.keys(d.sources).length} RawTree queries every 5 s, shared by every viewer`;
  } catch (e) {
    $("dot").className = "dot stale";
    $("status").textContent = "reconnecting";
  }
}
let resizeT;
addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => { layoutKey = ""; if (last) tick(); }, 200); });
tick();
setInterval(tick, 3000);
