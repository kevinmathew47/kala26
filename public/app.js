(function () {
"use strict";

/* ================= utilities ================= */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clock = () => new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const short = t => t.replace(" – Group 1", " (G1)").replace(" – Group 2", " (G2)");
const mmss = ms => { const neg = ms < 0; ms = Math.abs(ms); const s = Math.floor(ms / 1000); return (neg ? "-" : "") + Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
const fmtMin = m => (m % 1 ? m.toFixed(1) : m) + " min";

const ICON = {
  dash: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  users: '<path d="M16 21v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V21"/><circle cx="9" cy="7.5" r="3.5"/><path d="M22 21v-1.5a4 4 0 0 0-3-3.8M16 4.2a3.5 3.5 0 0 1 0 6.6"/>',
  cal: '<rect x="3" y="4.5" width="18" height="16.5" rx="2"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  down: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  play: '<path d="M6 4l14 8-14 8z"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  chev: '<path d="m6 9 6 6 6-6"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0"/>'
};
const icon = k => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[k]}</svg>`;

let toastT;
function toast(msg, err) { const t = $("#toast"); t.textContent = msg; t.className = "toast show" + (err ? " err" : ""); clearTimeout(toastT); toastT = setTimeout(() => t.className = "toast", 3200); }

async function api(path, body) {
  const r = await fetch(path, body === undefined ? { credentials: "same-origin" } : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let j = {}; try { j = await r.json(); } catch (e) {}
  if (r.status === 401) { ME = null; render(); throw new Error(j.error || "Please sign in again."); }
  if (!r.ok) throw new Error(j.error || "Something went wrong.");
  return j;
}

/* bell for timers that run over (needs one tap on the page first, which every volunteer makes) */
let AC = null;
function bell() {
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.35, 0.7].forEach(d => { const o = AC.createOscillator(), g = AC.createGain(); o.type = "sine"; o.frequency.value = 880;
      g.gain.setValueAtTime(0.0001, AC.currentTime + d); g.gain.exponentialRampToValueAtTime(0.4, AC.currentTime + d + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, AC.currentTime + d + 0.3);
      o.connect(g); g.connect(AC.destination); o.start(AC.currentTime + d); o.stop(AC.currentTime + d + 0.32); });
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
  } catch (e) {}
}
document.addEventListener("pointerdown", () => { try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume(); } catch (e) {} }, { once: false, passive: true });

/* ================= state ================= */
let ME = null, BOOT = null, ONLINE = true, OFFSET = 0;
const S = { version: 0, venues: [], evo: {}, cfg: {}, est: {}, att: {}, tmr: {}, sheets: {}, points: { ind: [5, 3, 1], grp: [15, 10, 5] } };
const MIN_PCT = 50, AWARD_MIN = 13;  // Kalamela Manual 2026: rules 8 and 6
const ui = { venue: "V1", sel: null, q: "", filter: "all", person: null, confirm: null, navOpen: false, findQ: "", tab: {}, judge: {} };
let VMAP = {}, PEOPLE = {};
const DRAFT = {};          // eid -> unsaved marks
const RANG = new Set();    // timers that have already rung on this device
const serverNow = () => Date.now() + OFFSET;
const LBL = { in: "At an event", called: "Wanted at event", free: "Free", notyet: "Not reported", finished: "All done",
  waiting: "Not arrived", present: "Present", running: "In progress", done: "Completed", absent: "Absent", upcoming: "Not started", live: "In progress", closed: "Finished" };
const TONE = { in: "green", present: "green", running: "amber", live: "green", done: "blue", finished: "blue", closed: "blue", absent: "red", called: "amber", over: "red", waiting: "", upcoming: "", free: "", notyet: "" };
const badge = (k, txt) => `<span class="badge ${TONE[k] || ""} ${k === "live" ? "live" : ""}">${esc(txt || LBL[k] || k)}</span>`;
const PALETTE = ["#2563eb", "#0d9488", "#9333ea", "#d97706", "#65a30d", "#db2777", "#0891b2", "#4f46e5", "#ca8a04", "#dc2626"];
const vcolor = c => { const n = parseInt(String(c).slice(1), 10); return PALETTE[((isNaN(n) ? 1 : n) - 1) % PALETTE.length]; };
const vbadge = c => `<span class="vbadge" style="--vc:${vcolor(c)}">${esc(c)}</span>`;
const vName = c => VMAP[c] ? VMAP[c].name : c;
const isAdmin = () => ME && ME.role === "admin";

/* ================= derived ================= */
function events() {
  return BOOT.events.map(e => { const o = S.evo[e.id] || {}, c = S.cfg[e.id] || {};
    return { ...e, venue: o.venue || e.venue, timer: c.timer ?? e.timer, timerMin: c.timerMin ?? e.timerMin, judges: c.judges ?? e.judges }; });
}
const stateOf = id => (S.est[id] && S.est[id].s) || "upcoming";
const evLabel = id => ({ upcoming: "upcoming", live: "live", done: "closed" }[stateOf(id)]);
const keyOf = en => en.chest || en.team;
const tmrOf = (e, k) => S.tmr[e + "--" + k] || null;
function entryStatus(ev, k) {
  const a = S.att[ev.id + "--" + k], s = a ? a.s : null;
  if (stateOf(ev.id) === "done") return (s === "present" || s === "done") ? "done" : "absent";
  if (s === "present") { const t = tmrOf(ev.id, k); if (t && t.s && !t.e) return "running"; }
  return s || "waiting";
}
function overBy(ev, k) { const t = tmrOf(ev.id, k); if (!t || !t.s || !ev.timer) return null; return ((t.e || serverNow()) - t.s) - ev.timer * 60000; }
let IDX;
function index() {
  const evs = events(), pe = {};
  for (const ev of evs) for (const en of ev.entries) for (const c of (en.members || [en.chest])) (pe[c] ||= []).push({ ev, en, k: keyOf(en) });
  IDX = { evs, pe, info: {} };
}
function info(c) {
  if (IDX.info[c]) return IDX.info[c];
  const list = (IDX.pe[c] || []).map(x => ({ ...x, st: entryStatus(x.ev, x.k), es: stateOf(x.ev.id) }));
  const at = list.find(x => x.es === "live" && (x.st === "present" || x.st === "running")) || null;
  const due = list.filter(x => x.es === "live" && x.st === "waiting");
  const seen = list.some(x => ["present", "running", "done"].includes(x.st));
  let state;
  if (at) state = "in"; else if (due.length) state = "called";
  else if (list.length && list.every(x => x.st === "done" || x.st === "absent")) state = "finished";
  else if (!seen) state = "notyet"; else state = "free";
  const r = { list, at, due, seen, state, done: list.filter(x => x.st === "done").length, absent: list.filter(x => x.st === "absent").length,
    pending: list.filter(x => x.st === "waiting" && x.es !== "done"), clash: at ? due.filter(x => x.ev.id !== at.ev.id) : [], total: list.length };
  return IDX.info[c] = r;
}
const teamParish = en => en.parish || (PEOPLE[(en.members || [])[0]] || {}).parish || "";
const nameOf = (en) => en.team ? "Team " + en.team : (PEOPLE[en.chest] || {}).name || en.chest;
function counts(ev) { const c = { waiting: 0, present: 0, running: 0, done: 0, absent: 0 }; ev.entries.forEach(en => c[entryStatus(ev, keyOf(en))]++); return c; }
const timerText = ev => !ev.timer ? "" : ev.timerMin ? `${fmtMin(ev.timerMin)} – ${fmtMin(ev.timer)} per person` : `${fmtMin(ev.timer)} per person`;

/* results */
function sheetOf(ev) { return DRAFT[ev.id] || S.sheets[ev.id] || {}; }
function results(ev) {
  const sh = sheetOf(ev), rows = [];
  for (const en of ev.entries) {
    const k = keyOf(en); if (entryStatus(ev, k) === "absent") continue;
    const marks = sh[k] || [], totals = [];
    for (let j = 0; j < ev.judges; j++) { const v = (marks[j] || []).filter(x => typeof x === "number"); totals.push(v.length ? v.reduce((a, b) => a + b, 0) : null); }
    if (totals.every(x => x === null)) continue;
    rows.push({ k, en, totals, total: totals.reduce((a, b) => a + (b || 0), 0) });
  }
  const maxTot = ev.criteria.reduce((a, c) => a + (c.max || 0), 0) * ev.judges;
  rows.forEach(r => { r.pct = maxTot ? Math.round(r.total / maxTot * 1000) / 10 : null; r.eligible = r.pct === null || r.pct >= MIN_PCT; });
  rows.sort((a, b) => (a.eligible === b.eligible ? b.total - a.total : a.eligible ? -1 : 1));
  let prev = null;
  rows.forEach((r, i) => { if (!r.eligible) { r.rank = null; return; } r.rank = prev && r.total === prev.total ? prev.rank : i + 1; prev = r; });
  return rows;
}
function markedCount(ev) { const sh = sheetOf(ev); let n = 0; for (const en of ev.entries) { const k = keyOf(en); if (entryStatus(ev, k) === "absent") continue; const m = sh[k] || []; let full = true; for (let j = 0; j < ev.judges; j++) for (let c = 0; c < ev.criteria.length; c++) if (typeof (m[j] || [])[c] !== "number") full = false; if (full) n++; } return n; }
function championship() {
  const ind = {}, church = {}, per = [];
  for (const ev of IDX.evs) {
    const res = results(ev), pts = ev.type === "group" ? S.points.grp : S.points.ind, win = [];
    for (const r of res) { if (!r.rank || r.rank > 3) continue; const p = pts[r.rank - 1] || 0; const parish = r.en.team ? teamParish(r.en) : (PEOPLE[r.k] || {}).parish;
      church[parish] = (church[parish] || 0) + p;
      if (!r.en.team) { const d = ind[r.k] ||= { points: 0, r: [0, 0, 0] }; d.points += p; d.r[r.rank - 1]++; }
      win.push({ ...r, p }); }
    per.push({ ev, win, scored: res.length });
  }
  const rank = arr => { arr.sort((a, b) => b.v - a.v); arr.forEach((x, i) => x.rank = i && x.v === arr[i - 1].v ? arr[i - 1].rank : i + 1); return arr; };
  const male = rank(Object.entries(ind).filter(([k]) => (PEOPLE[k] || {}).gender === "Male").map(([k, d]) => ({ k, v: d.points, d })));
  const female = rank(Object.entries(ind).filter(([k]) => (PEOPLE[k] || {}).gender === "Female").map(([k, d]) => ({ k, v: d.points, d })));
  const churches = rank(Object.entries(church).map(([k, v]) => ({ k, v })));
  return { per, male, female, churches };
}

/* next event for a participant: open events first, then ones not started */
function nextStop(c, hereId) {
  const todo = info(c).list.filter(x => x.ev.id !== hereId && x.st === "waiting" && x.es !== "done");
  todo.sort((a, b) => (b.es === "live") - (a.es === "live"));
  return todo[0] || null;
}
function nextHTML(c, hereId) {
  const n = nextStop(c, hereId);
  if (!n) return `<div class="next none">${icon("flag")}No more events today</div>`;
  const live = n.es === "live";
  return `<div class="next ${live ? "go" : ""}">${icon("arrow")}<span>Next: <b>${esc(short(n.ev.title))}</b> at ${vbadge(n.ev.venue)} ${esc(vName(n.ev.venue))} ${live ? badge("live", "Open now") : badge("upcoming", "Not started yet")}</span></div>`;
}
function liveStrip() {
  const live = IDX.evs.filter(e => stateOf(e.id) === "live");
  const open = ui.lbOpen && live.find(e => e.id === ui.lbOpen);
  const items = live.map(e => { const c = counts(e);
    return `<button class="lb-item ${open && open.id === e.id ? "on" : ""}" style="--vc:${vcolor(e.venue)}" data-act="lb" data-e="${e.id}" aria-expanded="${open && open.id === e.id}">
      <span class="lb-v">${esc(e.venue)} · ${esc(vName(e.venue))}</span><b>${esc(short(e.title))}</b>
      <span class="lb-c"><span>${c.waiting} to come</span><span>${c.running + c.present} here</span><span>${c.done} done</span></span></button>`; }).join("");
  let detail = "";
  if (open) {
    const waiting = open.entries.filter(en => entryStatus(open, keyOf(en)) === "waiting");
    detail = `<div class="lb-detail"><b>Still to come at ${esc(vName(open.venue))} · ${esc(short(open.title))}</b>
      <div class="chips">${waiting.map(en => `<button class="chip" data-act="person" data-c="${esc(en.chest || en.members[0])}"><b>${esc(keyOf(en))}</b> ${esc(en.team ? teamParish(en) : (PEOPLE[en.chest] || {}).name)}</button>`).join("") || '<span class="muted">Everyone has arrived.</span>'}</div>
      ${isAdmin() ? `<button class="btn sm" data-act="open-ev" data-e="${open.id}">Open this event</button>` : ""}</div>`;
  }
  return `<section class="livebar"><div class="lb-h">${badge("live", "Live now")}<span class="muted">${live.length ? `${live.length} event${live.length > 1 ? "s" : ""} open across all venues — tap one to see who is still to come` : "No event is open right now"}</span></div>
    ${live.length ? `<div class="lb-items">${items}</div>` : ""}${detail}</section>`;
}
function hbars(rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${opts.empty || "No results yet."}</div>`;
  const max = Math.max(opts.threshold || 0, ...rows.map(r => r.v), 1);
  return `<div class="hb" role="list">${rows.map(r => `<div class="hb-row" role="listitem" data-tip="${esc(r.tip)}" ${r.act ? `data-act="${r.act}" data-c="${esc(r.c || "")}" tabindex="0"` : ""}>
      <span class="hb-rank">${r.rank <= 3 ? `<span class="medal m${r.rank}">${r.rank}</span>` : r.rank}</span>
      <span class="hb-name">${esc(r.label)}<small>${esc(r.sub || "")}</small></span>
      <span class="hb-track">${opts.threshold ? `<span class="hb-th" style="left:${opts.threshold / max * 100}%"></span>` : ""}<i class="${r.rank <= 3 ? "top" : ""}" style="width:${Math.max(1, r.v / max * 100)}%"></i></span>
      <span class="hb-v">${r.v}</span></div>`).join("")}</div>
    ${opts.threshold ? `<div class="hb-note"><span class="hb-th-key"></span>${opts.threshold} points needed for the award</div>` : ""}`;
}

function trophyCard(ch, compact) {
  const c = ch.churches, first = c.filter(x => x.rank === 1), second = c.filter(x => x.rank === 2), third = c.filter(x => x.rank === 3);
  const nm = x => esc(x.k.replace("Mar Thoma Church", "MTC"));
  return `<div class="card trophy ${first.length ? "won" : ""}">
    <div class="aw-t">${icon("trophy")}Overall trophy</div>
    <div class="aw-n">${first.length ? first.map(nm).join(" &amp; ") : "Not decided yet"}</div>
    <div class="aw-f">${first.length ? `${first[0].v} points · champion church` : "The church with the most points wins"}</div>
    ${!compact && (second.length || third.length) ? `<div class="podium">${second.length ? `<span><span class="medal m2">2</span>${second.map(nm).join(", ")} <b>${second[0].v}</b></span>` : ""}${third.length ? `<span><span class="medal m3">3</span>${third.map(nm).join(", ")} <b>${third[0].v}</b></span>` : ""}</div>` : ""}
  </div>`;
}

/* glass dropdown: groups = [[label, [{v, t, sub, tone}]]] */
function picker(id, label, cur, groups) {
  const open = ui.pk === id, all = groups.flatMap(g => g[1]), c = all.find(o => o.v === cur) || all[0] || {};
  return `<div class="picker ${open ? "open" : ""}" data-pk="${id}">
    <button class="pk-btn" data-act="pk-toggle" data-pk="${id}" aria-haspopup="listbox" aria-expanded="${open}">
      <span class="pk-main"><small>${esc(label)}</small><b>${esc(c.t || "")}</b>${c.sub ? `<em>${c.sub}</em>` : ""}</span>${icon("chev")}</button>
    ${open ? `<div class="pk-pop" role="listbox">${groups.filter(g => g[1].length).map(([gl, opts]) => `<div class="pk-group">${gl ? `<div class="pk-gl">${esc(gl)}<span>${opts.length}</span></div>` : ""}
      ${opts.map(o => `<button class="pk-opt ${o.v === cur ? "on" : ""}" role="option" aria-selected="${o.v === cur}" data-act="pk-pick" data-pk="${id}" data-v="${esc(o.v)}">
        <span class="pk-dot ${o.tone || ""}"></span><span class="pk-ot"><b>${esc(o.t)}</b>${o.sub ? `<em>${o.sub}</em>` : ""}</span>${o.v === cur ? icon("check") : ""}</button>`).join("")}</div>`).join("")}</div>` : ""}
  </div>`;
}

/* ================= actions ================= */
async function act(path, body, optimistic, okMsg) {
  const snap = JSON.stringify({ att: S.att, est: S.est, tmr: S.tmr });
  if (optimistic) { optimistic(); render(); }
  try { const j = await api(path, body); if (okMsg) toast(okMsg); poll(true); return j; }
  catch (err) { const o = JSON.parse(snap); S.att = o.att; S.est = o.est; S.tmr = o.tmr; render(); toast(err.message, true); }
}
const who = () => ME.role === "admin" ? "Admin" : ME.venue;
function mark(e, k, s) { const id = e + "--" + k; return act("/api/mark", { e, k, s }, () => { if (s) S.att[id] = { s, by: who() }; else { delete S.att[id]; delete S.tmr[id]; } }); }
function timer(e, k, action) {
  const id = e + "--" + k;
  return act("/api/timer", { e, k, action }, () => {
    if (action === "start") { S.tmr[id] = { s: serverNow(), e: null }; S.att[id] = { s: "present", by: who() }; if (!S.est[e]) S.est[e] = { s: "live" }; RANG.delete(id); }
    else if (action === "stop") { if (S.tmr[id]) S.tmr[id].e = serverNow(); S.att[id] = { s: "done", by: who() }; }
    else { delete S.tmr[id]; S.att[id] = { s: "present", by: who() }; RANG.delete(id); }
  });
}
function setEventState(e, s) { return act("/api/event-state", { e, s }, () => { if (s === "upcoming") delete S.est[e]; else S.est[e] = { s }; if (s === "done") ui.tab[e] = "marks"; },
  s === "live" ? "Event started" : s === "done" ? "Event finished. Enter the judges' marks below." : "Event reset"); }
async function eventCfg(e, patch) { try { await api("/api/event-cfg", { e, ...patch }); await poll(true); toast("Saved"); } catch (err) { toast(err.message, true); render(true); } }
let saveT = {};
function queueSave(eid) {
  clearTimeout(saveT[eid]); const st = $("#save-" + eid); if (st) st.textContent = "Saving…";
  saveT[eid] = setTimeout(async () => {
    try { await api("/api/sheet", { e: eid, data: DRAFT[eid] }); const s2 = $("#save-" + eid); if (s2) s2.textContent = "All marks saved"; await poll(true); delete DRAFT[eid]; }
    catch (err) { const s2 = $("#save-" + eid); if (s2) s2.textContent = "Not saved: " + err.message; toast(err.message, true); }
  }, 700);
}

/* ================= polling & ticking ================= */
async function poll(force) {
  if (!ME) return;
  try {
    const j = await api("/api/state?v=" + (force ? 0 : S.version));
    ONLINE = true; if (j.now) OFFSET = j.now - Date.now();
    if (j.changed) { Object.assign(S, { version: j.version, venues: j.venues, evo: j.evo, cfg: j.cfg, est: j.est, att: j.att, tmr: j.tmr, sheets: j.sheets, points: j.points });
      VMAP = Object.fromEntries(S.venues.map(v => [v.code, v])); render(); }
    else updateLive();
  } catch (e) { ONLINE = false; updateLive(); }
}
setInterval(poll, 2500);
function tick() {
  const c = $("#clock"); if (c) c.textContent = clock();
  if (!ME || !BOOT || !IDX) return;
  document.querySelectorAll("[data-tmr]").forEach(el => {
    const [eid, k] = el.dataset.tmr.split("|"); const ev = IDX.evs.find(x => x.id === eid); const t = tmrOf(eid, k); if (!ev || !t || !t.s) return;
    const el2 = (t.e || serverNow()) - t.s, lim = ev.timer * 60000, min = (ev.timerMin || 0) * 60000;
    el.querySelector(".tv").textContent = mmss(el2);
    const bar = el.querySelector(".tb i"); if (bar && lim) bar.style.width = Math.min(100, el2 / lim * 100) + "%";
    el.classList.toggle("over", !!lim && el2 > lim); el.classList.toggle("under", !!min && el2 < min);
    const note = el.querySelector(".tn");
    if (note) note.textContent = lim && el2 > lim ? `${mmss(el2 - lim)} over` : min && el2 < min ? `min ${fmtMin(ev.timerMin)}` : lim ? `${mmss(lim - el2)} left` : "";
  });
  // overtime bell: venue desks ring for their own venue, the admin for every venue
  for (const id in S.tmr) {
    const t = S.tmr[id]; if (!t.s || t.e || RANG.has(id)) continue;
    const [eid, k] = id.split("--"); const ev = IDX.evs.find(x => x.id === eid); if (!ev || !ev.timer) continue;
    if (serverNow() - t.s > ev.timer * 60000) { RANG.add(id);
      if (isAdmin() || ev.venue === ME.venue) { bell(); toast(`${k} has gone over ${fmtMin(ev.timer)} in ${short(ev.title)}`, true); } }
  }
  const ob = $("#overcount"); if (ob) { const n = overList().length; ob.textContent = n; ob.hidden = !n; }
}
setInterval(tick, 1000);
setInterval(() => { if (ME && BOOT && !isTyping()) render(); }, 30000);
function updateLive() { const l = $("#live"); if (l) { l.className = "live" + (ONLINE ? "" : " off"); l.lastElementChild.textContent = ONLINE ? "Live" : "Reconnecting…"; } }
function overList() {
  const out = [];
  for (const id in S.tmr) { const t = S.tmr[id]; if (!t.s || t.e) continue; const [eid, k] = id.split("--"); const ev = IDX.evs.find(x => x.id === eid);
    if (ev && ev.timer && serverNow() - t.s > ev.timer * 60000 && stateOf(eid) !== "done") out.push({ ev, k, over: serverNow() - t.s - ev.timer * 60000 }); }
  return out.sort((a, b) => b.over - a.over);
}

/* ================= routing ================= */
const ADMIN_ROUTES = [["dashboard", "Dashboard", "dash"], ["venues", "Venue desks", "pin"], ["participants", "Participants", "users"], ["results", "Results & rankings", "trophy"], ["events", "Events", "cal"], ["reports", "Export", "file"], ["settings", "Settings", "gear"]];
const VOL_ROUTES = [["desk", "My venue", "pin"], ["live", "Live now", "bell"], ["find", "Find", "search"]];
const ADMIN_TABS = ["dashboard", "venues", "participants", "results"];
const routes = () => isAdmin() ? ADMIN_ROUTES : VOL_ROUTES;
function currentRoute() { const h = location.hash.slice(1); return routes().some(x => x[0] === h) ? h : routes()[0][0]; }
window.addEventListener("hashchange", () => { ui.navOpen = false; ui.moreOpen = false; ui.confirm = null; render(true); window.scrollTo(0, 0); });

/* ================= render ================= */
function isTyping() { const a = document.activeElement; return a && ["INPUT", "SELECT", "TEXTAREA"].includes(a.tagName) && !["q", "findq"].includes(a.id); }
let pending = false, lastRoute = null, lastPerson = null, moreShown = false;
function render(force) {
  if (!ME) { renderLogin(); return; }
  if (!BOOT) return;
  if (isTyping() && !force) { pending = true; return; }
  pending = false;
  index();
  const route = currentRoute();
  const keep = document.activeElement && ["q", "findq"].includes(document.activeElement.id) ? { id: document.activeElement.id, pos: document.activeElement.selectionStart } : null;
  const sy = window.scrollY;
  const title = routes().find(r => r[0] === route)[1];
  $("#root").innerHTML = `
  <div class="app ${ui.navOpen ? "nav-open" : ""}">
    <aside class="sidebar" aria-label="Main navigation">
      <div class="side-brand"><img src="/logo.png" alt="Mar Thoma Church emblem"><div><b>Kalamela 2026</b><span>Ernakulam Yuvajana Sakhyam</span></div></div>
      <nav class="nav">
        <div class="nav-label">${isAdmin() ? "Admin" : esc(ME.venue + " · " + vName(ME.venue))}</div>
        ${routes().map(([k, l, ic]) => `<a href="#${k}" class="${k === route ? "on" : ""}">${icon(ic)}<span>${l}</span>${k === "dashboard" || k === "desk" ? `<span class="count" id="overcount" hidden></span>` : ""}</a>`).join("")}
      </nav>
      <div class="side-foot"><div class="avatar">${isAdmin() ? "AD" : esc(ME.venue)}</div>
        <div class="who"><b>${isAdmin() ? "Administrator" : esc(vName(ME.venue))}</b><span>${isAdmin() ? "All venues" : "Venue volunteer"}</span></div>
        <button class="btn ghost sm" data-act="logout" title="Sign out" aria-label="Sign out">${icon("out")}</button></div>
    </aside>
    <div class="scrim" data-act="nav-close"></div>
    <div class="main">
      <header class="topbar">
        <button class="btn ghost sm menu-btn" data-act="nav-open" aria-label="Open menu">${icon("menu")}</button>
        <h1>${esc(isAdmin() ? title : (route === "desk" ? vName(ME.venue) : title))}</h1><div class="grow"></div>
        <span class="live ${ONLINE ? "" : "off"}" id="live"><i></i><span>${ONLINE ? "Live" : "Reconnecting…"}</span></span>
        <span class="clock hide-sm" id="clock">${clock()}</span>
        ${isAdmin() ? `<a class="btn primary sm" href="/api/export.xlsx" download>${icon("down")}<span class="hide-sm">Export Excel</span></a>` : ""}
      </header>
      <main class="content ${route !== lastRoute ? "enter" : ""}" id="view">${view(route)}</main>
    </div>
    <nav class="tabbar" aria-label="Quick navigation">
      ${routes().filter(([k]) => !isAdmin() || ADMIN_TABS.includes(k)).map(([k, l, ic]) => `<a href="#${k}" class="${k === route ? "on" : ""}">${icon(ic)}<span>${l.replace("Venue desks", "Desks").replace("Results & rankings", "Results")}</span></a>`).join("")}
      <button data-act="more-open">${icon("menu")}<span>More</span></button>
    </nav>
  </div>`;
  if (keep) { const el = document.getElementById(keep.id); if (el) { el.focus(); try { el.setSelectionRange(keep.pos, keep.pos); } catch (e) {} } }
  if (route === lastRoute) window.scrollTo(0, sy);
  lastRoute = route;
  renderSheet(); renderMore(); tick();
}
function renderMore() {
  let root = document.getElementById("more-root");
  if (!root) { root = document.createElement("div"); root.id = "more-root"; document.body.appendChild(root); }
  if (!ui.moreOpen || !ME) { root.innerHTML = ""; moreShown = false; return; }
  const route = currentRoute();
  root.innerHTML = `<div class="more ${moreShown ? "" : "anim"}" data-act="more-close"><div class="more-card" role="dialog" aria-label="More">
    <div class="handle"></div>
    <div class="more-grid">${routes().map(([k, l, ic]) => `<a href="#${k}" class="${k === route ? "on" : ""}">${icon(ic)}<span>${l}</span></a>`).join("")}
      <button data-act="logout">${icon("out")}<span>Sign out</span></button></div>
    <div class="more-who"><div class="avatar">${isAdmin() ? "AD" : esc(ME.venue)}</div>${isAdmin() ? "Administrator · all venues" : esc(vName(ME.venue)) + " · venue volunteer"}</div>
  </div></div>`;
  moreShown = true;
}
function view(r) {
  switch (r) {
    case "dashboard": return vDashboard();
    case "venues": return `<div class="toolbar single venue-seg"><div class="seg" role="tablist">${S.venues.map(v => `<button class="${ui.venue === v.code ? "on" : ""}" data-act="venue" data-v="${v.code}">${v.code} · ${esc(v.name)}</button>`).join("")}</div></div>
      <div class="venue-pick">${picker("venue", "Venue", ui.venue, [["", S.venues.map(v => { const l = IDX.evs.filter(e => e.venue === v.code); return { v: v.code, t: `${v.code} · ${v.name}`, tone: l.some(e => stateOf(e.id) === "live") ? "green" : "", sub: `${l.filter(e => stateOf(e.id) === "live").length} open · ${l.filter(e => stateOf(e.id) === "done").length}/${l.length} finished` }; })]])}</div>${vDesk(ui.venue)}`;
    case "participants": return vParticipants();
    case "results": return vResults();
    case "events": return vEvents();
    case "reports": return vReports();
    case "settings": return vSettings();
    case "desk": return vDesk(ME.venue);
    case "find": return vFind();
    case "live": return vLive();
  }
  return "";
}

/* ---------- login ---------- */
function renderLogin() {
  $("#root").innerHTML = `
  <div class="login">
    <section class="login-brand">
      <img src="/logo.png" alt="Mar Thoma Church emblem — Lighted to Lighten">
      <h1>Kalamela 2026<br>Venue &amp; Results Desk</h1>
      <p>Ernakulam Yuvajana Sakhyam. Mark arrivals, run each participant's timer, enter the judges' marks and follow every participant through the day.</p>
      <div class="login-facts"><div><b>5</b><span>Venues</span></div><div><b>53</b><span>Events</span></div><div><b>128</b><span>Participants</span></div></div>
    </section>
    <section class="login-form">
      <form class="login-card" id="login-form" autocomplete="off">
        <h2>Sign in</h2>
        <p>Enter the code given to you by the organiser.</p>
        <div class="field"><label for="code">Venue or admin code</label><input class="input code" id="code" placeholder="e.g. BALCONY2" autofocus></div>
        <div class="form-err" id="login-err"></div>
        <button class="btn primary block" type="submit">Sign in</button>
        <div class="login-foot">Volunteers see only their own venue. The admin code opens the dashboard, results and Excel export.</div>
      </form>
    </section>
  </div>`;
}

/* ---------- dashboard ---------- */
function vDashboard() {
  const ppl = BOOT.people.map(p => ({ p, i: info(p.chest) }));
  const reported = ppl.filter(x => x.i.seen).length;
  const es = IDX.evs.map(e => stateOf(e.id)), doneN = es.filter(s => s === "done").length, liveN = es.filter(s => s === "live").length;
  let running = 0, waitingLive = 0, absentN = 0;
  IDX.evs.forEach(ev => { const c = counts(ev); running += c.running; absentN += c.absent; if (stateOf(ev.id) === "live") waitingLive += c.waiting; });
  const over = overList();
  const stat = (cls, lbl, val, foot, ratio) => `<div class="card stat ${cls}"><span class="lbl">${lbl}</span><span class="val">${val}</span>${ratio != null ? `<div class="meter"><i style="width:${Math.round(ratio * 100)}%"></i></div>` : `<span class="foot">${foot || "&nbsp;"}</span>`}</div>`;
  const stats = [
    stat("", "Reported today", `${reported}<small> / ${ppl.length}</small>`, "", reported / ppl.length),
    stat("amber", "Timers running", running, "Writing, drawing or on stage now"),
    stat("red", "Over time", over.length, "Past their time limit"),
    stat("amber", "Not arrived", waitingLive, "At events already in progress"),
    stat("red", "Absent", absentN, "Missed a finished event"),
    stat("blue", "Events finished", `${doneN}<small> / ${es.length}</small>`, "", doneN / es.length),
  ].join("");
  const venues = S.venues.map(v => {
    const evs = IDX.evs.filter(e => e.venue === v.code), live = evs.filter(e => stateOf(e.id) === "live"), d = evs.filter(e => stateOf(e.id) === "done").length;
    const marksDue = evs.filter(e => stateOf(e.id) === "done" && markedCount(e) < e.entries.length - counts(e).absent).length;
    return `<div class="vrow" style="--vc:${vcolor(v.code)}">
      <div class="vrow-h">${vbadge(v.code)}<b>${esc(v.name)}</b><span class="grow"></span><span class="sub">${d}/${evs.length} finished${marksDue ? ` · <span class="amber-t">${marksDue} need marks</span>` : ""}</span></div>
      <div class="vrow-b">${live.length ? live.map(e => { const c = counts(e); return `<button class="now-ev" data-act="open-ev" data-e="${e.id}"><span class="t">${esc(short(e.title))}</span>${progressBar(c, e.entries.length)}<span class="nums"><span>${c.waiting} to come</span><span>${c.running} timing</span><span>${c.done} done</span>${c.absent ? `<span class="r">${c.absent} absent</span>` : ""}</span></button>`; }).join("") : `<span class="muted idle">No event open</span>`}</div></div>`;
  }).join("");
  // participants wanted at a live event who haven't come
  const wanted = [];
  IDX.evs.filter(e => stateOf(e.id) === "live").forEach(e => e.entries.forEach(en => {
    if (entryStatus(e, keyOf(en)) !== "waiting") return;
    if (en.team) { const busy = en.members.filter(c => { const i = info(c); return i.at && i.at.ev.id !== e.id; });
      wanted.push({ c: en.members[0], t: `Team ${en.team} · ${teamParish(en)}`, d: `${short(e.title)} at ${e.venue}${busy.length ? ` · ${busy.length} member(s) busy at another event` : ""}`, red: !busy.length }); return; }
    const i = info(en.chest), p = PEOPLE[en.chest] || {};
    wanted.push({ c: en.chest, t: `${en.chest} · ${p.name || ""}`, red: !i.at,
      d: `Wanted at ${e.venue} · ${short(e.title)} — ${i.at ? "now busy at " + i.at.ev.venue + " · " + short(i.at.ev.title) : i.seen ? "not at any venue right now" : "not seen today"}${p.phone ? " · " + p.phone : ""}` });
  }));
  wanted.sort((a, b) => b.red - a.red);
  const overHTML = over.map(o => { const en = o.ev.entries.find(x => keyOf(x) === o.k);
    return `<div class="li red"><span class="sev"></span><div style="min-width:0"><div class="t">${esc(o.k)} · ${esc(nameOf(en))}</div><div class="d">${vbadge(o.ev.venue)} ${esc(short(o.ev.title))} · limit ${fmtMin(o.ev.timer)}</div></div><span class="badge red">+${mmss(o.over)}</span></div>`; }).join("");
  const ch = championship();
  return `
    <div class="stats six">${stats}</div>
    <div class="dash">
      <div class="dash-main">
        <div class="card"><div class="card-h"><h2>${icon("pin")} Venues</h2><span class="grow"></span><div class="status-key"><span><i style="background:var(--line-2)"></i>To come</span><span><i style="background:var(--green)"></i>Here</span><span><i style="background:var(--amber)"></i>Timing</span><span><i style="background:var(--blue)"></i>Done</span><span><i style="background:var(--red)"></i>Absent</span></div></div>
          <div class="vrows">${venues}</div></div>
        <div class="card"><div class="card-h"><h2>All events</h2><span class="sub">${liveN} open · ${doneN} finished · ${es.length - liveN - doneN} not started</span></div>
          <div class="table-wrap tall"><table class="t cards dense"><thead><tr><th>Event</th><th>Venue</th><th>Status</th><th>Arrived</th><th>Timing</th><th>Done</th><th>Absent</th><th>Marks</th></tr></thead><tbody>
          ${IDX.evs.map(e => { const c = counts(e), st = stateOf(e.id), mc = markedCount(e), need = e.entries.length - c.absent;
            return `<tr class="click" data-act="open-ev" data-e="${e.id}"><td class="lead" data-l="Event"><b>${esc(short(e.title))}</b></td><td data-l="Venue">${vbadge(e.venue)}</td><td data-l="Status">${badge(evLabel(e.id))}</td>
            <td data-l="Arrived" class="num">${c.present + c.running + c.done}/${e.entries.length}</td><td data-l="Timing" class="num">${c.running || ""}</td><td data-l="Done" class="num">${c.done || ""}</td><td data-l="Absent" class="num">${c.absent || ""}</td>
            <td data-l="Marks">${st === "done" ? (mc >= need ? badge("done", "Entered") : badge("called", `${mc}/${need}`)) : '<span class="muted">–</span>'}</td></tr>`; }).join("")}
          </tbody></table></div></div>
      </div>
      <aside class="dash-side">
        ${trophyCard(ch, true)}
        <div class="card"><div class="card-h"><h2>${icon("bell")} Over time</h2><span class="grow"></span>${over.length ? badge("over", over.length) : ""}</div>
          <div class="list scroll">${overHTML || `<div class="empty sm">Nobody is over time.</div>`}</div></div>
        <div class="card"><div class="card-h"><h2>Not arrived</h2><span class="grow"></span>${wanted.length ? badge("called", wanted.length) : ""}</div>
          <div class="list scroll">${wanted.slice(0, 80).map(a => `<div class="li ${a.red ? "red" : ""}" data-act="person" data-c="${a.c}" role="button" tabindex="0"><span class="sev"></span><div style="min-width:0"><div class="t">${esc(a.t)}</div><div class="d">${esc(a.d)}</div></div></div>`).join("") || `<div class="empty sm">Everyone needed at open events has arrived.</div>`}</div></div>
      </aside>
    </div>`;
}
function progress(c, total) {
  const p = x => total ? x / total * 100 : 0, arr = c.present + c.running;
  return `<div class="bar" role="img" aria-label="${c.done} completed, ${arr} present, ${c.absent} absent of ${total}"><i style="width:${p(c.done)}%;background:var(--blue)"></i><i style="width:${p(c.running)}%;background:var(--amber)"></i><i style="width:${p(c.present)}%;background:var(--green)"></i><i style="width:${p(c.absent)}%;background:var(--red)"></i></div>
    <div class="legend"><span><span class="d" style="background:var(--green)"></span><b>${c.present}</b> present</span><span><span class="d" style="background:var(--amber)"></span><b>${c.running}</b> in progress</span><span><span class="d" style="background:var(--blue)"></span><b>${c.done}</b> completed</span><span><span class="d" style="background:var(--red)"></span><b>${c.absent}</b> absent</span><span><span class="d" style="background:var(--line-2)"></span><b>${c.waiting}</b> not arrived</span></div>`;
}

/* ---------- venue desk ---------- */
function vDesk(venue) {
  const evs = IDX.evs.filter(e => e.venue === venue);
  if (!evs.length) return liveStrip() + `<div class="card empty">No events are assigned to ${esc(vName(venue))}.</div>`;
  let sel = evs.find(e => e.id === ui.sel);
  if (!sel) sel = evs.find(e => stateOf(e.id) === "live") || evs.find(e => stateOf(e.id) === "upcoming") || evs[0];
  const item = e => { const c = counts(e), here = c.present + c.running + c.done;
    return `<button class="ev-item ${e.id === sel.id ? "sel" : ""} st-${stateOf(e.id)}" data-act="sel" data-e="${e.id}"><span class="nm">${esc(short(e.title))}</span>
      <span class="mt">${stateOf(e.id) === "upcoming" ? `${e.entries.length} ${e.type === "group" ? "teams" : "participants"}` : `${here}/${e.entries.length} arrived`}${c.running ? ` · <b class="amber-t">${c.running} timing</b>` : ""}</span></button>`; };
  const groups = [["live", "Open now"], ["upcoming", "Not started"], ["done", "Finished"]].map(([st, label]) => {
    const list = evs.filter(e => stateOf(e.id) === st); return list.length ? `<div class="ev-group"><div class="ev-gh">${label}<span>${list.length}</span></div>${list.map(item).join("")}</div>` : ""; }).join("");
  const opt = e => { const c = counts(e), st = stateOf(e.id);
    return { v: e.id, t: short(e.title), tone: st === "live" ? "green" : st === "done" ? "blue" : "", sub: st === "upcoming" ? `${e.entries.length} ${e.type === "group" ? "teams" : "participants"}` : `${c.present + c.running + c.done}/${e.entries.length} arrived${c.running ? ` · ${c.running} timing` : ""}` }; };
  const select = `<div class="ev-select">${picker("ev", "Event", sel.id, [["Open now", evs.filter(e => stateOf(e.id) === "live").map(opt)], ["Not started", evs.filter(e => stateOf(e.id) === "upcoming").map(opt)], ["Finished", evs.filter(e => stateOf(e.id) === "done").map(opt)]])}</div>`;
  return `${liveStrip()}${select}<div class="desk"><div class="ev-list">${groups}</div><div style="min-width:0;display:grid;gap:16px">${callSheet(sel)}</div></div>`;
}
function callSheet(ev) {
  const st = stateOf(ev.id), c = counts(ev), admin = isAdmin();
  const tab = ui.tab[ev.id] || (st === "done" ? "marks" : "people");
  let ctl = "";
  if (st === "upcoming") ctl = `<button class="btn success big" data-act="start" data-e="${ev.id}">${icon("play")}Start event</button>`;
  else if (st === "live") ctl = `<button class="btn dark big" data-act="ask-close" data-e="${ev.id}">${icon("flag")}Finish event</button>`;
  else if (admin) ctl = `<div class="fix-acts"><button class="btn" data-act="reopen" data-e="${ev.id}" title="The venue volunteer can mark attendance again, then press Finish event">Reopen for corrections</button><button class="btn ghost" data-act="ask-restart" data-e="${ev.id}">Restart attendance</button></div>`;
  const restart = ui.confirm && ui.confirm.restart === ev.id ? `<div class="confirm"><span>Clear all attendance and timers for <b>${esc(short(ev.title))}</b> and set it back to Not started? Judges' marks already entered are kept.</span><button class="btn sm" data-act="cancel">Cancel</button><button class="btn sm danger" data-act="restart" data-e="${ev.id}">Clear and restart</button></div>` : "";
  const conf = ui.confirm && ui.confirm.e === ev.id ? `<div class="confirm"><span>Finish <b>${esc(short(ev.title))}</b>? ${c.waiting ? `<b>${c.waiting}</b> not arrived will be recorded as absent. ` : ""}${c.running ? `<b>${c.running}</b> running timer(s) will stop. ` : ""}Then enter the judges' marks.</span><button class="btn sm" data-act="cancel">Not yet</button><button class="btn sm dark" data-act="close" data-e="${ev.id}">Yes, finish event</button></div>` : "";
  const f = (ui.af || {})[ev.id] || "all";
  const FILT = [["all", "All", ev.entries.length, ""], ["waiting", "To come", c.waiting, "var(--line-2)"], ["here", "Here", c.present, "var(--green)"], ["running", "Timing", c.running, "var(--amber)"], ["done", "Done", c.done, "var(--blue)"], ["absent", "Absent", c.absent, "var(--red)"]];
  const shown = ev.entries.filter(en => { const s = entryStatus(ev, keyOf(en)); return f === "all" || (f === "here" ? s === "present" : s === f); });
  return `<div class="card sheet" style="--vc:${vcolor(ev.venue)}">
    <div class="sheet-head"><div class="grow"><div class="eyebrow">${vbadge(ev.venue)} ${esc(vName(ev.venue))} ${badge(evLabel(ev.id))}</div><h2>${esc(short(ev.title))}</h2>
      <div class="meta">${ev.entries.length} ${ev.type === "group" ? "teams" : "participants"}${ev.timer ? ` · ${icon("timer")} ${timerText(ev)}` : ""} · ${ev.judges} judge${ev.judges > 1 ? "s" : ""}</div></div>${ctl}</div>
    ${conf}${restart}
    ${st === "done" && admin && tab !== "marks" ? `<div class="fixnote">${icon("gear")}<span>Admin correction: use <b>Completed / Absent</b> on any row to fix a mistake. The results update straight away.</span></div>` : ""}
    <div class="sheet-prog">${progressBar(c, ev.entries.length)}</div>
    <div class="tabs-in"><button class="${tab === "people" ? "on" : ""}" data-act="tab" data-e="${ev.id}" data-t="people">Attendance</button><button class="${tab === "marks" ? "on" : ""}" data-act="tab" data-e="${ev.id}" data-t="marks">Judges' marks${st === "done" ? ` <span class="c">${markedCount(ev)}/${ev.entries.length - c.absent}</span>` : ""}</button></div>
    ${tab === "marks" ? marksPanel(ev) : `<div class="afilter" role="tablist">${FILT.filter(x => x[0] === "all" || x[2] || f === x[0]).map(([k, l, n, col]) => `<button class="${f === k ? "on" : ""}" data-act="af" data-e="${ev.id}" data-f="${k}" role="tab" aria-selected="${f === k}">${col ? `<i style="background:${col}"></i>` : ""}${l}<span>${n}</span></button>`).join("")}</div>
      <div class="entries">${shown.map(en => entryRow(ev, en)).join("") || `<div class="empty">Nobody here.</div>`}</div>`}
  </div>`;
}
function progressBar(c, total) {
  const p = x => total ? x / total * 100 : 0;
  return `<div class="bar" role="img" aria-label="${c.done} done, ${c.running} timing, ${c.present} here, ${c.absent} absent, ${c.waiting} to come"><i style="width:${p(c.done)}%;background:var(--blue)"></i><i style="width:${p(c.running)}%;background:var(--amber)"></i><i style="width:${p(c.present)}%;background:var(--green)"></i><i style="width:${p(c.absent)}%;background:var(--red)"></i></div>`;
}
function whereHTML(c, hereId) {
  const i = info(c);
  if (i.at && i.at.ev.id !== hereId) return `${badge("called", "Busy at " + i.at.ev.venue)} <span class="muted">${esc(short(i.at.ev.title))}</span>`;
  if (i.at) return "";
  const other = i.due.filter(x => x.ev.id !== hereId);
  if (other.length) return `${badge("called", "Also wanted at " + other[0].ev.venue)} <span class="muted">${esc(short(other[0].ev.title))}</span>`;
  return `<span class="muted">${i.seen ? "Free right now" : "Not seen at any venue yet"}</span>`;
}
function entryRow(ev, en) {
  const k = keyOf(en), s = entryStatus(ev, k), st = stateOf(ev.id), closed = st === "done", locked = closed && !isAdmin();
  const t = tmrOf(ev.id, k);
  let who, where = "";
  if (en.team) {
    const busy = en.members.filter(c => { const i = info(c); return i.at && i.at.ev.id !== ev.id; });
    who = `<div class="nm">${esc(teamParish(en))}</div><div class="sub">${en.members.length} members</div><div class="members">${en.members.map(c => { const i = info(c); const cl = i.at ? (i.at.ev.id === ev.id ? "in" : "busy") : ""; return `<button class="mem ${cl}" data-act="person" data-c="${c}" title="${esc((PEOPLE[c] || {}).name || c)}">${c}</button>`; }).join("")}</div>`;
    if (busy.length && s === "waiting") where = `<div class="where">${badge("called", busy.length + " member" + (busy.length > 1 ? "s" : "") + " busy at another event")}</div>`;
  } else {
    const p = PEOPLE[en.chest] || { name: en.chest, parish: "" };
    who = `<div class="nm"><a href="#" data-act="person" data-c="${en.chest}">${esc(p.name)}</a></div><div class="sub">${esc(p.parish)}</div>`;
    if (s === "waiting" && !closed) where = `<div class="where">${whereHTML(en.chest, ev.id)}</div>`;
    if (s === "done") where = nextHTML(en.chest, ev.id);
  }
  const tw = t && t.s ? `<div class="timer ${t.e ? "stopped" : ""}" data-tmr="${ev.id}|${esc(k)}"><span class="tv">0:00</span>${ev.timer ? `<span class="tb"><i></i></span>` : ""}<span class="tn"></span></div>` : "";
  const b = (cls, lab, a, extra = "") => `<button class="btn sm ${cls}" data-act="${a}" data-e="${ev.id}" data-k="${esc(k)}" ${extra}>${lab}</button>`;
  let acts = "";
  if (closed && isAdmin()) {
    acts = `<div class="toggle" role="group" aria-label="Correct attendance"><button class="${s === "done" ? "on ok" : ""}" data-act="mark" data-e="${ev.id}" data-k="${esc(k)}" data-s="done">Completed</button><button class="${s === "absent" ? "on bad" : ""}" data-act="mark" data-e="${ev.id}" data-k="${esc(k)}" data-s="absent">Absent</button></div>`;
  } else if (!locked) {
    if (s === "waiting") acts = b("success", "Present", "mark", 'data-s="present"') + b("", "Absent", "mark", 'data-s="absent"');
    else if (s === "present") acts = (ev.timer ? b("primary", icon("timer") + "Start timer", "tstart") : b("primary", ev.type === "writing" ? "Submitted" : "Performed", "mark", 'data-s="done"')) + b("ghost", "Undo", "mark", 'data-s=""');
    else if (s === "running") acts = b("primary", ev.type === "writing" ? "Submitted" : "Finished", "tstop") + b("ghost", "Restart", "treset");
    else acts = b("ghost", "Undo", "mark", 'data-s="' + (s === "done" ? "present" : "") + '"');
  }
  const ob = overBy(ev, k);
  const doneNote = s === "done" && t && t.s && t.e ? (ob > 0 ? badge("over", `Took ${mmss(t.e - t.s)} · ${mmss(ob)} over`) : ev.timerMin && (t.e - t.s) < ev.timerMin * 60000 ? badge("called", `Took ${mmss(t.e - t.s)} · under ${fmtMin(ev.timerMin)}`) : badge("done", `Took ${mmss(t.e - t.s)}`)) : "";
  return `<div class="entry ${s === "done" || s === "absent" ? "dim" : ""} ${s === "running" ? "running" : ""}"><span class="ord">${en.order}</span>
    <span class="chest">${esc(k)}</span>
    <div class="info" style="min-width:0">${who}${where}</div>
    <div class="acts">${s === "running" ? tw : closed && isAdmin() ? doneNote : doneNote || badge(s)}${acts}</div></div>`;
}

/* ---------- judges' marks ---------- */
function marksPanel(ev) {
  const st = stateOf(ev.id), canEdit = isAdmin() || (ev.venue === ME.venue);
  if (st !== "done" && !isAdmin()) return `<div class="empty">Marks open when the event is finished. Press <b>Finish event</b> once every participant is done.</div>`;
  const J = ev.judges, j = Math.min(ui.judge[ev.id] ?? 0, J), sh = sheetOf(ev);
  const ents = ev.entries.filter(en => entryStatus(ev, keyOf(en)) !== "absent");
  const res = results(ev), rk = Object.fromEntries(res.map(r => [r.k, r]));
  const jtabs = Array.from({ length: J }, (_, i) => `<button class="${j === i ? "on" : ""}" data-act="judge" data-e="${ev.id}" data-j="${i}">Judge ${i + 1}</button>`).join("") + `<button class="${j === J ? "on" : ""}" data-act="judge" data-e="${ev.id}" data-j="${J}">Total &amp; ranks</button>`;
  const head = `<div class="marks-head"><div class="seg">${jtabs}</div><span class="grow"></span>
    <span class="judges">Judges <button class="btn sm" data-act="judges" data-e="${ev.id}" data-d="-1" ${J <= 1 || !canEdit ? "disabled" : ""} aria-label="One judge fewer">−</button><b>${J}</b><button class="btn sm" data-act="judges" data-e="${ev.id}" data-d="1" ${J >= 10 || !canEdit ? "disabled" : ""} aria-label="One judge more">+</button></span>
    <span class="muted save-state" id="save-${ev.id}">${DRAFT[ev.id] ? "Saving…" : "All marks saved"}</span></div>`;
  if (!ents.length) return head + `<div class="empty">Nobody took part, so there is nothing to mark.</div>`;
  if (j === J) {
    return head + `<div class="table-wrap"><table class="t marks"><thead><tr><th>Rank</th><th>Chest / Team</th><th>Name</th>${Array.from({ length: J }, (_, i) => `<th class="num">Judge ${i + 1}</th>`).join("")}<th class="num">Total</th><th class="num">%</th></tr></thead><tbody>
      ${res.map(r => `<tr class="${r.rank && r.rank <= 3 ? "win r" + r.rank : ""}"><td>${!r.rank ? badge("absent", "Below 50%") : r.rank <= 3 ? `<span class="medal m${r.rank}">${r.rank}</span>` : r.rank}</td><td><b>${esc(r.k)}</b></td><td>${esc(nameOf(r.en))}<div class="sub">${esc(r.en.team ? teamParish(r.en) : (PEOPLE[r.k] || {}).parish)}</div></td>${r.totals.map(x => `<td class="num">${x ?? "–"}</td>`).join("")}<td class="num"><b>${r.total}</b></td><td class="num">${r.pct ?? "–"}</td></tr>`).join("") || `<tr><td colspan="${J + 5}" class="empty">No marks entered yet.</td></tr>`}
      </tbody></table></div><div class="card-b muted" style="font-size:12.5px">As per the Kalamela Manual, a participant needs at least ${MIN_PCT}% of the maximum marks to be placed and earn points. Points: ${S.points.ind.join(" / ")} for individual events, ${S.points.grp.join(" / ")} for group events.</div>`;
  }
  const crit = ev.criteria;
  return head + `<div class="table-wrap"><table class="t marks"><thead><tr><th>Chest / Team</th>${crit.map(c => `<th class="num" title="${esc(c.name)}">${esc(c.name)}${c.max ? `<span class="mx">max ${c.max}</span>` : ""}</th>`).join("")}<th class="num">Total</th></tr></thead><tbody>
    ${ents.map(en => { const k = keyOf(en), row = ((sh[k] || [])[j]) || [];
      const tot = row.filter(x => typeof x === "number").reduce((a, b) => a + b, 0);
      return `<tr><td><b>${esc(k)}</b><div class="sub">${esc(en.team ? teamParish(en) : (PEOPLE[k] || {}).name || "")}</div></td>${crit.map((c, ci) => `<td class="num"><input class="input mark" type="number" inputmode="decimal" min="0" ${c.max ? `max="${c.max}"` : ""} step="0.5" value="${row[ci] ?? ""}" data-act="mark-in" data-e="${ev.id}" data-k="${esc(k)}" data-j="${j}" data-c="${ci}" ${canEdit ? "" : "disabled"} aria-label="${esc(k)} ${esc(c.name)} judge ${j + 1}"></td>`).join("")}<td class="num"><b id="tot-${ev.id}-${esc(k)}-${j}">${tot || ""}</b>${rk[k] && rk[k].rank && rk[k].rank <= 3 ? ` <span class="medal m${rk[k].rank}">${rk[k].rank}</span>` : ""}</td></tr>`; }).join("")}
    </tbody></table></div><div class="card-b muted" style="font-size:12.5px">Marks save automatically. Absent participants are left out. ${crit.some(c => !c.max) ? "Quiz: enter each round's score as the quiz master directs." : "Each criterion's maximum is shown under its name."}</div>`;
}

/* ---------- participants ---------- */
const PF = [["all", "All"], ["in", "At an event"], ["called", "Wanted, not arrived"], ["absent", "Missed an event"], ["notyet", "Not reported"], ["free", "Free"], ["finished", "All done"]];
function pMatch(p, i, f) { if (f === "all") return true; if (f === "absent") return i.absent > 0; return i.state === f; }
function vParticipants() {
  const all = BOOT.people.map(p => ({ p, i: info(p.chest) }));
  return `<div class="toolbar"><div class="search">${icon("search")}<input class="input" id="q" placeholder="Search by chest number, name or parish" value="${esc(ui.q)}" aria-label="Search participants"></div>
    <div class="seg">${PF.map(([k, l]) => `<button class="${ui.filter === k ? "on" : ""}" data-act="filter" data-f="${k}">${l}<span class="c">${all.filter(x => pMatch(x.p, x.i, k)).length}</span></button>`).join("")}</div></div>
    <div class="card"><div class="table-wrap" id="ptable">${pTable()}</div></div>`;
}
function pTable() {
  const q = ui.q.trim().toLowerCase();
  const rows = BOOT.people.map(p => ({ p, i: info(p.chest) })).filter(({ p, i }) => (!q || (p.chest + " " + p.name + " " + p.parish).toLowerCase().includes(q)) && pMatch(p, i, ui.filter));
  if (!rows.length) return `<div class="empty">No participants match.</div>`;
  return `<table class="t cards"><thead><tr><th>Chest no.</th><th>Participant</th><th>Parish</th><th>Contact</th><th>Status</th><th>Now at</th><th>Progress</th><th>Still to do</th></tr></thead><tbody>
  ${rows.map(({ p, i }) => `<tr class="click" data-act="person" data-c="${p.chest}">
    <td class="lead" data-l="Chest"><b>${p.chest}</b></td><td data-l="Name"><b>${esc(p.name)}</b><div class="sub">${esc(p.gender || "")}</div></td>
    <td data-l="Parish"><span class="sub">${esc(p.parish)}</span></td><td data-l="Contact" class="num">${esc(p.phone || "–")}</td>
    <td data-l="Status">${badge(i.state)}${i.clash.length ? " " + badge("called", "Clash") : ""}</td>
    <td data-l="Now at">${i.at ? `${vbadge(i.at.ev.venue)} ${esc(short(i.at.ev.title))}` : `<span class="muted">–</span>`}</td>
    <td data-l="Progress" class="num">${i.done}/${i.total} done${i.absent ? ` · <span style="color:var(--red)">${i.absent} absent</span>` : ""}</td>
    <td data-l="Still to do">${i.pending.length ? i.pending.slice(0, 3).map(x => `${vbadge(x.ev.venue)} <span class="sub">${esc(short(x.ev.title))}</span>`).join("<br>") + (i.pending.length > 3 ? `<br><span class="sub">+${i.pending.length - 3} more</span>` : "") : `<span class="muted">–</span>`}</td></tr>`).join("")}
  </tbody></table>`;
}

/* ---------- live now (volunteer) ---------- */
function vLive() {
  const live = IDX.evs.filter(e => stateOf(e.id) === "live");
  if (!live.length) return `<div class="card empty">${icon("bell")}<br>No event is open right now. Events appear here the moment a venue presses <b>Start event</b>.</div>`;
  return `<p class="muted lead-in">Events open now at every venue. Send waiting participants to these.</p>
  <div class="live-cards">${live.map(e => { const c = counts(e), waiting = e.entries.filter(en => entryStatus(e, keyOf(en)) === "waiting");
    return `<div class="card live-card" style="--vc:${vcolor(e.venue)}"><div class="lc-h">${vbadge(e.venue)}<span>${esc(vName(e.venue))}</span>${badge("live", "Open")}</div>
      <b class="lc-t">${esc(short(e.title))}</b>${progressBar(c, e.entries.length)}
      <div class="lc-n"><span><b>${c.waiting}</b> to come</span><span><b>${c.present + c.running}</b> here</span><span><b>${c.done}</b> done</span></div>
      ${waiting.length ? `<div class="chips">${waiting.map(en => `<button class="chip" data-act="person" data-c="${esc(en.chest || en.members[0])}"><b>${esc(keyOf(en))}</b> ${esc(en.team ? teamParish(en) : (PEOPLE[en.chest] || {}).name)}</button>`).join("")}</div>` : `<div class="muted">Everyone has arrived.</div>`}
    </div>`; }).join("")}</div>`;
}

/* ---------- find (volunteer) ---------- */
function vFind() {
  return `${liveStrip()}<div class="toolbar"><div class="search">${icon("search")}<input class="input" id="findq" placeholder="Type a chest number or name" value="${esc(ui.findQ)}" aria-label="Find a participant"></div></div>
  <div class="card"><div class="list" id="findres">${findRows()}</div></div>`;
}
function findRows() {
  const q = ui.findQ.trim().toLowerCase();
  if (!q) return `<div class="empty">Search any participant to see where they are and what they still have to do today.</div>`;
  const hits = BOOT.people.filter(p => (p.chest + " " + p.name).toLowerCase().includes(q)).slice(0, 30);
  if (!hits.length) return `<div class="empty">No match.</div>`;
  return hits.map(p => { const i = info(p.chest); return `<div class="li"><span class="sev" style="background:var(--line)"></span><div style="min-width:0"><div class="t">${p.chest} · ${esc(p.name)}</div><div class="d">${esc(p.parish)} · ${i.at ? "At " + i.at.ev.venue + " · " + esc(short(i.at.ev.title)) : LBL[i.state]} · ${i.pending.length} still to do</div></div><button class="btn sm" data-act="person" data-c="${p.chest}">View</button></div>`; }).join("");
}

/* ---------- results & rankings (admin) ---------- */
function vResults() {
  const ch = championship();
  const done = ch.per.filter(x => stateOf(x.ev.id) === "done");
  const complete = done.filter(x => markedCount(x.ev) >= x.ev.entries.length - counts(x.ev).absent && x.scored).length;
  const award = (list, title) => { const top = list.filter(x => x.rank === 1 && x.v >= AWARD_MIN);
    return `<div class="card award ${top.length ? "won" : ""}"><div class="aw-t">${icon("trophy")}${title}</div>
      <div class="aw-n">${top.length ? top.map(x => `${esc((PEOPLE[x.k] || {}).name)} <small>${esc(x.k)}</small>`).join("<br>") : "Not decided yet"}</div>
      <div class="aw-f">${top.length ? `${top[0].v} points · ${esc((PEOPLE[top[0].k] || {}).parish)}` : `Needs at least ${AWARD_MIN} points from individual events${list[0] ? ` · leader ${esc(list[0].k)} has ${list[0].v}` : ""}`}</div></div>`; };
  const people = list => list.slice(0, 8).map(x => { const p = PEOPLE[x.k] || {};
    return { rank: x.rank, label: `${x.k} ${p.name || ""}`, sub: (p.parish || "").replace("Mar Thoma Church", "MTC"), v: x.v, act: "person", c: x.k,
      tip: `${p.name}: ${x.v} points — ${x.d.r[0]} first, ${x.d.r[1]} second, ${x.d.r[2]} third` }; });
  const churches = ch.churches.map(x => ({ rank: x.rank, label: x.k.replace("Mar Thoma Church", "MTC"), v: x.v, tip: `${x.k}: ${x.v} points` }));
  const stat = (cls, lbl, val, foot) => `<div class="card stat ${cls}"><span class="lbl">${lbl}</span><span class="val">${val}</span><span class="foot">${foot}</span></div>`;
  return `
  <div class="grid-3 awards">${trophyCard(ch)}${award(ch.male, "Kalaprathibha")}${award(ch.female, "Kalathilakam")}</div>
  <div class="stats four">
    ${stat("blue", "Events finished", `${done.length}<small> / ${ch.per.length}</small>`, "Finish event pressed")}
    ${stat("green", "Results complete", `${complete}<small> / ${done.length || 0}</small>`, "All judges' marks entered")}
    ${stat("", "Churches with points", ch.churches.length, "Out of " + new Set(BOOT.people.map(p => p.parish)).size + " churches")}
    ${stat("amber", "Prize winners", new Set(ch.per.flatMap(x => x.win.map(w => w.k))).size, "Placed 1st, 2nd or 3rd")}
  </div>
  <div class="card"><div class="card-h"><h2>${icon("chart")} Church championship</h2><span class="sub">Points from every individual and group event</span></div>
    <div class="card-b">${hbars(churches, { empty: "Church points appear here as soon as results are entered." })}</div></div>
  <div class="grid-2">
    <div class="card"><div class="card-h"><h2>${icon("chart")} Kalaprathibha race</h2><span class="sub">Top male participants</span></div><div class="card-b">${hbars(people(ch.male), { threshold: AWARD_MIN })}</div></div>
    <div class="card"><div class="card-h"><h2>${icon("chart")} Kalathilakam race</h2><span class="sub">Top female participants</span></div><div class="card-b">${hbars(people(ch.female), { threshold: AWARD_MIN })}</div></div>
  </div>
  <div class="card"><div class="card-h"><h2>Event results</h2><span class="sub">${done.length} of ${ch.per.length} events finished</span></div>
    <div class="table-wrap"><table class="t cards"><thead><tr><th>Event</th><th>Status</th><th>1st</th><th>2nd</th><th>3rd</th><th>Marks</th></tr></thead><tbody>
    ${ch.per.map(({ ev, win }) => { const place = r => win.filter(w => w.rank === r).map(w => `<b>${esc(w.k)}</b> ${esc(w.en.team ? teamParish(w.en) : (PEOPLE[w.k] || {}).name)} <span class="sub">${w.total}</span>`).join("<br>") || '<span class="muted">–</span>';
      const need = ev.entries.length - counts(ev).absent, mc = markedCount(ev);
      return `<tr class="click" data-act="open-ev" data-e="${ev.id}"><td class="lead" data-l="Event"><b>${esc(short(ev.title))}</b> ${vbadge(ev.venue)}</td><td data-l="Status">${badge(evLabel(ev.id))}</td><td data-l="1st">${place(1)}</td><td data-l="2nd">${place(2)}</td><td data-l="3rd">${place(3)}</td><td data-l="Marks">${stateOf(ev.id) === "done" ? (mc >= need ? badge("done", "Complete") : badge("called", `${mc}/${need}`)) : '<span class="muted">–</span>'}</td></tr>`; }).join("")}
    </tbody></table></div></div>
  <div class="card"><div class="card-b toolbar" style="justify-content:space-between">
    <div><b>Points per place</b><div class="muted" style="font-size:12.5px">As per the Kalamela Manual: individual 5 / 3 / 1, group 15 / 10 / 5. Below 50% marks earns no place or points. Ties share the place and its points.</div></div>
    <form id="points-form" class="toolbar">
      <span class="muted">Individual</span>${[0, 1, 2].map(i => `<input class="input pts" id="pi${i}" type="number" min="0" step="0.5" value="${S.points.ind[i]}" aria-label="Individual ${i + 1} place points">`).join("")}
      <span class="muted">Group</span>${[0, 1, 2].map(i => `<input class="input pts" id="pg${i}" type="number" min="0" step="0.5" value="${S.points.grp[i]}" aria-label="Group ${i + 1} place points">`).join("")}
      <button class="btn primary sm" type="submit">Save points</button></form></div></div>`;
}

/* ---------- events (admin) ---------- */
function vEvents() {
  const opts = v => S.venues.map(x => `<option value="${x.code}" ${x.code === v ? "selected" : ""}>${x.code} · ${esc(x.name)}</option>`).join("");
  return `<div class="banner" style="background:var(--blue-bg);color:#1e3a8a">Assign each event to a venue, set the time allowed per participant (0 = no timer), a minimum time if needed (instrumentals: 3–5 min), and the number of judges. Changes reach every device in a few seconds.</div>
  <div class="card"><div class="table-wrap"><table class="t cards"><thead><tr><th>Event</th><th>Venue</th><th>Timer (min)</th><th>Minimum (min)</th><th>Judges</th><th>Status</th><th></th></tr></thead><tbody>
  ${IDX.evs.map(e => `<tr class="ev-edit"><td class="lead" data-l="Event"><b>${esc(short(e.title))}</b><div class="sub">${e.entries.length} ${e.type === "group" ? "teams" : "participants"}</div></td>
    <td data-l="Venue"><select class="input" data-act="ev-venue" data-e="${e.id}" aria-label="Venue">${opts(e.venue)}</select></td>
    <td data-l="Timer (min)"><input class="input num-in" type="number" min="0" max="300" step="0.5" value="${e.timer || 0}" data-act="ev-timer" data-e="${e.id}" aria-label="Timer minutes"></td>
    <td data-l="Minimum (min)"><input class="input num-in" type="number" min="0" max="300" step="0.5" value="${e.timerMin || 0}" data-act="ev-tmin" data-e="${e.id}" aria-label="Minimum minutes"></td>
    <td data-l="Judges"><input class="input num-in" type="number" min="1" max="10" step="1" value="${e.judges}" data-act="ev-judges" data-e="${e.id}" aria-label="Judges"></td>
    <td data-l="Status">${badge(evLabel(e.id))}</td>
    <td data-l=""><button class="btn sm" data-act="open-ev" data-e="${e.id}">Open</button></td></tr>`).join("")}
  </tbody></table></div></div>`;
}

/* ---------- export ---------- */
function vReports() {
  return `<div class="card"><div class="card-b export-hero"><div><h2 style="margin:0 0 4px;font-size:17px">Download everything as Excel</h2><div class="muted">Attendance, timings, judges' marks, results and championship standings, up to the minute. Admin only.</div></div>
    <a class="btn primary" href="/api/export.xlsx" download>${icon("down")}Download .xlsx</a></div>
    <div class="card-b" style="padding-top:0"><div class="sheets-list">
      <div><b>Summary</b>Totals for the day</div><div><b>Attendance</b>Every participant in every event, with status, time taken and over-time</div>
      <div><b>Results</b>1st, 2nd and 3rd in every event with marks and points</div><div><b>Championship</b>Top male, top female and church standings</div>
      <div><b>Marks</b>Every judge's marks per criterion</div><div><b>Events</b>Status, counts, judges and timer for every event</div><div><b>Activity log</b>Every action with time and venue</div></div></div></div>`;
}

/* ---------- settings ---------- */
let SET = null;
function loadSettings() { return api("/api/settings").then(j => { SET = j; render(true); }).catch(e => toast(e.message, true)); }
function vSettings() {
  if (!SET) { loadSettings(); return `<div class="card empty">Loading…</div>`; }
  const rows = SET.venues.map(v => `<tr>
      <td data-l="Venue" class="lead"><span class="vbadge" style="--vc:${vcolor(v.code)}">${esc(v.code)}</span></td>
      <td data-l="Name"><input class="input" id="vn-${v.code}" value="${esc(v.name)}" maxlength="60" aria-label="Name of ${esc(v.code)}"></td>
      <td data-l="Sign-in code"><input class="input code" id="vp-${v.code}" value="${esc(v.pass)}" maxlength="24" aria-label="Sign-in code for ${esc(v.code)}"></td>
      <td data-l="Events" class="num">${v.events}</td>
      <td data-l="">${ui.confirm && ui.confirm.delVenue === v.code
        ? `<span class="muted" style="font-size:12.5px">Remove?</span> <button type="button" class="btn sm" data-act="cancel">No</button> <button type="button" class="btn sm danger" data-act="venue-del-do" data-v="${v.code}">Remove</button>`
        : `<button type="button" class="btn sm ghost" data-act="venue-del-ask" data-v="${v.code}" ${v.events ? `disabled title="Move its ${v.events} event(s) to another venue first"` : ""}>Remove</button>`}</td></tr>`).join("");
  return `
  <div class="card"><div class="card-h"><h2>Venues &amp; sign-in codes</h2><span class="grow"></span><span class="sub">${SET.venues.length} venues</span></div>
    <form id="venues-form" autocomplete="off">
      <div class="table-wrap"><table class="t cards"><thead><tr><th>Code</th><th>Venue name</th><th>Sign-in code (password)</th><th>Events</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="card-b" style="display:grid;gap:14px;border-top:1px solid var(--line)">
        <div class="field" style="max-width:320px;margin:0"><label for="c-admin">Admin code</label><input class="input code" id="c-admin" value="${esc(SET.admin)}" maxlength="24"></div>
        <div class="toolbar"><button class="btn primary" type="submit">Save venues &amp; codes</button><span class="muted" style="font-size:12.5px">Changing any code signs out every other device.</span></div>
      </div>
    </form>
  </div>
  <div class="grid-2">
  <div class="card"><div class="card-h"><h2>Add a venue</h2></div><div class="card-b">
    <form class="settings-form" id="venue-add-form" autocomplete="off">
      <div class="row2">
        <div class="field"><label for="nv-name">Venue name</label><input class="input" id="nv-name" placeholder="e.g. Parish Hall" maxlength="60"></div>
        <div class="field"><label for="nv-pass">Sign-in code (password)</label><input class="input code" id="nv-pass" placeholder="e.g. PHALL6" maxlength="24"></div>
      </div>
      <div><button class="btn primary" type="submit">Add venue</button></div>
      <div class="muted" style="font-size:12.5px">Then open <a href="#events">Events</a> to move events into it.</div>
    </form></div></div>
  <div class="card"><div class="card-h"><h2>Practice &amp; reset</h2></div><div class="card-b" style="display:grid;gap:16px">
    <div><b>Load practice data</b><div class="muted" style="margin:2px 0 10px">Fills in sample arrivals, timers and marks so volunteers can rehearse. Replaces everything entered so far.</div>
      ${ui.confirm && ui.confirm.sample ? `<div class="confirm" style="margin:0"><span>Replace all attendance, timers and marks with practice data?</span><button class="btn sm" data-act="cancel">Cancel</button><button class="btn sm primary" data-act="sample-do">Load practice data</button></div>` : `<button class="btn" data-act="sample-ask">Load practice data</button>`}</div>
    <div><b>Reset the day</b><div class="muted" style="margin:2px 0 10px">Clears every arrival, timer, event status and mark. Venues, codes, timers and judges are kept. Download the Excel first if you need a copy.</div>
      ${ui.confirm && ui.confirm.reset ? `<div class="confirm" style="margin:0"><span>Delete all attendance, timers and judges' marks? This cannot be undone.</span><button class="btn sm" data-act="cancel">Cancel</button><button class="btn sm danger" data-act="reset-do">Reset everything</button></div>` : `<button class="btn danger" data-act="reset-ask">Reset the day</button>`}</div>
  </div></div></div>`;
}

/* ---------- person sheet ---------- */
function renderSheet() {
  const root = $("#sheet-root"), p = ui.person && PEOPLE[ui.person];
  if (!p) { root.innerHTML = ""; lastPerson = null; return; }
  const i = info(p.chest), anim = lastPerson !== p.chest; lastPerson = p.chest;
  root.innerHTML = `<div class="overlay ${anim ? "anim" : ""}" data-act="sheet-close"><aside class="panel" role="dialog" aria-modal="true" aria-label="${esc(p.name)}"><div class="handle"></div>
    <div class="panel-h"><div style="flex:1;min-width:0"><div class="muted" style="font-size:12.5px;font-weight:600">${p.chest}</div><h2>${esc(p.name)}</h2><div style="margin-top:6px">${badge(i.state)}${i.at ? ` <span class="muted">at</span> ${vbadge(i.at.ev.venue)} ${esc(short(i.at.ev.title))}` : ""}</div></div>
      <button class="btn ghost sm" data-act="sheet-close" aria-label="Close">${icon("x")}</button></div>
    <div class="panel-b">
      <dl class="dl"><dt>Parish</dt><dd>${esc(p.parish)}</dd><dt>Gender</dt><dd>${esc(p.gender || "–")}</dd><dt>Contact</dt><dd class="num">${esc(p.phone || "–")}<div class="muted" style="font-size:12.5px">${esc(p.secretary || "")}, parish secretary</div></dd><dt>Events</dt><dd>${i.done} completed · ${i.absent} absent · ${i.pending.length} still to do</dd></dl>
      <div><div style="font-weight:600;margin-bottom:10px">Events today</div><div class="steps">
      ${i.list.map(x => { const t = tmrOf(x.ev.id, x.k); const took = t && t.s && t.e ? ` · took ${mmss(t.e - t.s)}` : "";
        return `<div class="step ${x.st === "running" ? "present" : x.st}"><div class="tt">${esc(short(x.ev.title))}${x.en.team ? ` <span class="muted">· team ${esc(x.en.team)}</span>` : ""}</div><div class="mt">${vbadge(x.ev.venue)}<span>${esc(vName(x.ev.venue))}</span>${badge(x.st)}${x.es === "live" ? badge("live", "Event in progress") : x.es === "done" ? badge("closed") : ""}<span>${took}</span></div></div>`; }).join("")}</div></div>
    </div></aside></div>`;
}

/* ================= events ================= */
document.addEventListener("click", e => {
  if (ui.pk && !e.target.closest(".picker")) { ui.pk = null; render(true); }
  const t = e.target.closest("[data-act]"); if (!t) return;
  const a = t.dataset.act;
  if (a === "sheet-close") { if (t.classList.contains("overlay") && e.target !== t) return; ui.person = null; renderSheet(); return; }
  if (t.tagName === "A" || a === "open-ev") e.preventDefault();
  const E = t.dataset.e, K = t.dataset.k;
  switch (a) {
    case "logout": api("/api/logout", {}).finally(() => { ME = null; SET = null; location.hash = ""; renderLogin(); }); break;
    case "nav-open": ui.navOpen = true; render(true); break;
    case "more-open": ui.moreOpen = true; renderMore(); break;
    case "pk-toggle": ui.pk = ui.pk === t.dataset.pk ? null : t.dataset.pk; render(true); break;
    case "pk-pick": { const id = t.dataset.pk, v = t.dataset.v; ui.pk = null;
      if (id === "ev") { ui.sel = v; ui.confirm = null; } else if (id === "venue") { ui.venue = v; ui.sel = null; }
      render(true); break; }
    case "more-close": if (e.target !== t) return; ui.moreOpen = false; renderMore(); break;
    case "nav-close": ui.navOpen = false; render(true); break;
    case "venue": ui.venue = t.dataset.v; ui.sel = null; render(true); break;
    case "sel": ui.sel = E; ui.confirm = null; render(true); break;
    case "tab": ui.tab[E] = t.dataset.t; render(true); break;
    case "judge": ui.judge[E] = +t.dataset.j; render(true); break;
    case "judges": { const ev = IDX.evs.find(x => x.id === E); eventCfg(E, { judges: ev.judges + +t.dataset.d }); break; }
    case "open-ev": { const ev = IDX.evs.find(x => x.id === E); if (!ev) break; ui.sel = ev.id; ui.person = null;
      if (isAdmin()) { ui.venue = ev.venue; if (location.hash !== "#venues") { location.hash = "venues"; return; } } render(true); window.scrollTo(0, 0); break; }
    case "filter": ui.filter = t.dataset.f; render(true); break;
    case "person": ui.person = t.dataset.c; renderSheet(); break;
    case "mark": mark(E, K, t.dataset.s || null).then(() => { if (t.dataset.s === "done") tellNext(E, K); }); break;
    case "lb": ui.lbOpen = ui.lbOpen === E ? null : E; render(true); break;
    case "af": (ui.af ||= {})[E] = t.dataset.f; render(true); break;
    case "tstart": timer(E, K, "start"); break;
    case "tstop": timer(E, K, "stop").then(() => tellNext(E, K)); break;
    case "treset": timer(E, K, "reset"); break;
    case "start": setEventState(E, "live"); break;
    case "ask-close": ui.confirm = { e: E }; render(true); break;
    case "cancel": ui.confirm = null; render(true); break;
    case "close": ui.confirm = null; setEventState(E, "done"); break;
    case "reopen": setEventState(E, "live"); break;
    case "reset-ask": ui.confirm = { reset: true }; render(true); break;
    case "ask-restart": ui.confirm = { restart: E }; render(true); break;
    case "restart": ui.confirm = null; api("/api/event-reset", { e: E }).then(() => { toast("Attendance cleared. The event is back to Not started."); ui.tab[E] = "people"; return poll(true); }).catch(er => toast(er.message, true)); break;
    case "sample-ask": ui.confirm = { sample: true }; render(true); break;
    case "venue-del-ask": ui.confirm = { delVenue: t.dataset.v }; render(true); break;
    case "venue-del-do": ui.confirm = null; api("/api/venue-delete", { code: t.dataset.v }).then(() => { toast("Venue removed"); SET = null; return poll(true); }).then(() => render(true)).catch(er => { toast(er.message, true); render(true); }); break;
    case "reset-do": ui.confirm = null; api("/api/reset", {}).then(() => { toast("The day has been reset"); return poll(true); }).catch(er => toast(er.message, true)); break;
    case "sample-do": ui.confirm = null; api("/api/sample", {}).then(() => { toast("Practice data loaded"); return poll(true); }).catch(er => toast(er.message, true)); break;
  }
});
function tellNext(eid, k) {
  if (!PEOPLE[k]) return;
  index(); const n = nextStop(k, eid);
  toast(n ? `${k} is done. Next: ${short(n.ev.title)} at ${vName(n.ev.venue)}${n.es === "live" ? " (open now)" : " (not started yet)"}` : `${k} is done. No more events today.`);
}
/* hover tooltip for chart bars */
document.addEventListener("mouseover", e => { const r = e.target.closest("[data-tip]"); const tip = $("#tip"); if (!tip) return;
  if (!r || !r.dataset.tip) { tip.hidden = true; return; } tip.textContent = r.dataset.tip; tip.hidden = false;
  const b = r.getBoundingClientRect(); tip.style.left = Math.min(window.innerWidth - tip.offsetWidth - 8, b.left + 24) + "px"; tip.style.top = (b.top - tip.offsetHeight - 6) + "px"; });
document.addEventListener("keydown", e => { if (e.key === "Escape") { if (ui.pk) { ui.pk = null; render(true); return; } if (ui.moreOpen) { ui.moreOpen = false; renderMore(); return; } if (ui.person) { ui.person = null; renderSheet(); } else if (ui.navOpen) { ui.navOpen = false; render(true); } } });
document.addEventListener("input", e => {
  const t = e.target;
  if (t.id === "q") { ui.q = t.value; const el = $("#ptable"); if (el) el.innerHTML = pTable(); }
  if (t.id === "findq") { ui.findQ = t.value; $("#findres").innerHTML = findRows(); }
  if (t.dataset && t.dataset.act === "mark-in") {
    const ev = IDX.evs.find(x => x.id === t.dataset.e), k = t.dataset.k, j = +t.dataset.j, c = +t.dataset.c, max = ev.criteria[c].max;
    let v = t.value === "" ? null : Number(t.value);
    t.classList.toggle("bad", v !== null && (isNaN(v) || v < 0 || (max && v > max)));
    if (v !== null && (isNaN(v) || v < 0 || (max && v > max))) return;
    const d = DRAFT[ev.id] ||= JSON.parse(JSON.stringify(S.sheets[ev.id] || {}));
    const rows = d[k] ||= []; while (rows.length <= j) rows.push([]); const row = rows[j]; while (row.length < ev.criteria.length) row.push(null); row[c] = v;
    const tot = row.filter(x => typeof x === "number").reduce((a, b) => a + b, 0); const te = document.getElementById(`tot-${ev.id}-${k}-${j}`); if (te) te.textContent = tot || "";
    queueSave(ev.id);
  }
});
document.addEventListener("change", e => {
  const t = e.target, a = t.dataset && t.dataset.act; if (!a) return;
  if (a === "sel-select") { ui.sel = t.value; ui.confirm = null; t.blur(); render(true); return; }
  const id = t.dataset.e;
  if (a === "ev-venue") api("/api/event-edit", { e: id, venue: t.value }).then(() => { toast("Event moved"); return poll(true); }).catch(er => toast(er.message, true));
  if (a === "ev-timer") eventCfg(id, { timer: +t.value || 0 });
  if (a === "ev-tmin") eventCfg(id, { timerMin: +t.value || 0 });
  if (a === "ev-judges") eventCfg(id, { judges: +t.value || 1 });
});
document.addEventListener("focusout", () => setTimeout(() => { if (pending && !isTyping()) render(); }, 0));
document.addEventListener("submit", async e => {
  e.preventDefault();
  const id = e.target.id;
  if (id === "login-form") {
    const err = $("#login-err"); err.textContent = "";
    try { const j = await api("/api/login", { code: $("#code").value }); ME = j.user; location.hash = ""; await start(); }
    catch (x) { err.textContent = x.message; }
  }
  if (id === "venues-form") {
    const venues = SET.venues.map(v => ({ code: v.code, name: $("#vn-" + v.code).value, pass: $("#vp-" + v.code).value }));
    try { const j = await api("/api/settings", { admin: $("#c-admin").value, venues }); SET = null; await poll(true); toast(j.signedOut ? "Saved. Other devices were signed out because codes changed." : "Saved."); render(true); }
    catch (x) { toast(x.message, true); }
  }
  if (id === "venue-add-form") {
    try { const j = await api("/api/venue-add", { name: $("#nv-name").value, pass: $("#nv-pass").value }); SET = null; await poll(true); toast("Venue " + j.code + " added. Move events into it under Events."); render(true); }
    catch (x) { toast(x.message, true); }
  }
  if (id === "points-form") {
    try { await api("/api/points", { ind: [0, 1, 2].map(i => +$("#pi" + i).value), grp: [0, 1, 2].map(i => +$("#pg" + i).value) }); await poll(true); toast("Points saved"); render(true); }
    catch (x) { toast(x.message, true); }
  }
});

/* ================= boot ================= */
async function start() {
  if (!BOOT) { BOOT = await api("/api/bootstrap"); PEOPLE = Object.fromEntries(BOOT.people.map(p => [p.chest, p])); }
  await poll(true);
  // timers that were already over before this device opened don't ring again
  for (const id in S.tmr) { const t = S.tmr[id]; const ev = BOOT.events.find(x => x.id === id.split("--")[0]); const lim = ((S.cfg[ev && ev.id] || {}).timer ?? (ev && ev.timer)) * 60000;
    if (t.s && !t.e && lim && serverNow() - t.s > lim) RANG.add(id); }
  render(true);
}
(async function init() {
  try { const j = await api("/api/me"); ME = j.user; } catch (e) { ME = null; }
  if (ME) await start(); else renderLogin();
})();
})();
