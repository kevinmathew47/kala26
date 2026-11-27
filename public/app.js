(function () {
"use strict";

/* ================= utilities ================= */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = m => { if (m == null || isNaN(m)) return "–"; let h = Math.floor(m / 60); const mm = m % 60, ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12; return h + ":" + String(mm).padStart(2, "0") + " " + ap; };
const toHHMM = m => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
const fromHHMM = s => { const [h, m] = s.split(":").map(Number); return h * 60 + m; };
const nowMin = () => { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); };
const short = t => t.replace(" – Group 1", " (G1)").replace(" – Group 2", " (G2)").replace(" (G1 + G2 together)", " (G1 + G2)");

const ICON = {
  dash: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  users: '<path d="M16 21v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V21"/><circle cx="9" cy="7.5" r="3.5"/><path d="M22 21v-1.5a4 4 0 0 0-3-3.8M16 4.2a3.5 3.5 0 0 1 0 6.6"/>',
  cal: '<rect x="3" y="4.5" width="18" height="16.5" rx="2"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  down: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  play: '<path d="M6 4l14 8-14 8z"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>'
};
const icon = k => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[k]}</svg>`;

let toastT;
function toast(msg, err) { const t = $("#toast"); t.textContent = msg; t.className = "toast show" + (err ? " err" : ""); clearTimeout(toastT); toastT = setTimeout(() => t.className = "toast", 2600); }

async function api(path, body) {
  const r = await fetch(path, body === undefined ? { credentials: "same-origin" } : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let j = {}; try { j = await r.json(); } catch (e) {}
  if (r.status === 401) { ME = null; render(); throw new Error(j.error || "Please sign in again."); }
  if (!r.ok) throw new Error(j.error || "Something went wrong.");
  return j;
}

/* ================= state ================= */
let ME = null, BOOT = null, ONLINE = true;
const S = { version: 0, evo: {}, est: {}, att: {} };
const ui = { route: "", venue: "V1", sel: null, q: "", filter: "all", person: null, confirm: null, navOpen: false, findQ: "" };
let VMAP = {}, PEOPLE = {}, ORIG = {};
const LBL = { in: "In competition", called: "Called", late: "Late", free: "Free", notyet: "Not reported", finished: "Finished",
  waiting: "Waiting", present: "Present", done: "Performed", absent: "Absent", upcoming: "Upcoming", live: "Live" };
const TONE = { in: "green", present: "green", live: "green", done: "blue", finished: "blue", late: "red", absent: "red", called: "amber", clash: "amber", waiting: "", upcoming: "", free: "", notyet: "" };
const badge = (k, txt) => `<span class="badge ${TONE[k] || ""} ${k === "live" ? "live" : ""}">${esc(txt || LBL[k] || k)}</span>`;
const vbadge = c => `<span class="vbadge" style="--vc:var(--${c.toLowerCase()})">${esc(c)}</span>`;
const vName = c => VMAP[c] ? VMAP[c].name : c;

/* ================= derived ================= */
function events() {
  return BOOT.events.map(e => {
    const o = S.evo[e.id] || {};
    const start = o.start ?? e.start, end = o.end ?? e.end, d = start - e.start;
    return { ...e, venue: o.venue || e.venue, start, end, entries: d ? e.entries.map(x => ({ ...x, time: x.time + d })) : e.entries };
  }).sort((a, b) => a.start - b.start || a.venue.localeCompare(b.venue));
}
const stateOf = id => (S.est[id] && S.est[id].s) || "upcoming";
const attOf = (e, k) => { const a = S.att[e + "--" + k]; return a ? a.s : null; };
const keyOf = en => en.chest || en.team;
function entryStatus(ev, k) { const a = attOf(ev.id, k); if (stateOf(ev.id) === "done") return (a === "present" || a === "done") ? "done" : "absent"; return a || "waiting"; }
let IDX;
function index() {
  const evs = events(), pe = {};
  for (const ev of evs) for (const en of ev.entries) for (const c of (en.members || [en.chest])) (pe[c] ||= []).push({ ev, en, k: keyOf(en), time: en.time });
  for (const c in pe) pe[c].sort((a, b) => a.time - b.time);
  IDX = { evs, pe, info: {} };
}
function info(c) {
  if (IDX.info[c]) return IDX.info[c];
  const list = (IDX.pe[c] || []).map(x => ({ ...x, st: entryStatus(x.ev, x.k), es: stateOf(x.ev.id) }));
  const at = list.find(x => x.es === "live" && x.st === "present") || null;
  const due = list.filter(x => x.es === "live" && x.st === "waiting");
  const seen = list.some(x => x.st === "present" || x.st === "done");
  const n = nowMin();
  let state;
  if (at) state = "in";
  else if (due.length) state = due.some(x => n > x.time + 5) ? "late" : "called";
  else if (list.length && list.every(x => x.st === "done" || x.st === "absent")) state = "finished";
  else if (!seen) state = "notyet";
  else state = "free";
  const r = { list, at, due, seen, state, done: list.filter(x => x.st === "done").length, absent: list.filter(x => x.st === "absent").length,
    next: list.find(x => x.st === "waiting" && x.es !== "done") || null, clash: at ? due.filter(x => x.ev.id !== at.ev.id) : [], total: list.length };
  return IDX.info[c] = r;
}
const teamParish = en => { const p = PEOPLE[(en.members || [])[0]]; return p ? p.parish : ""; };
function counts(ev) { const c = { waiting: 0, present: 0, done: 0, absent: 0 }; ev.entries.forEach(en => c[entryStatus(ev, keyOf(en))]++); return c; }

/* ================= actions ================= */
async function mark(e, k, s) {
  const id = e + "--" + k, prev = S.att[id];
  if (s) S.att[id] = { s, by: ME.role === "admin" ? "Admin" : ME.venue }; else delete S.att[id];
  render();
  try { await api("/api/mark", { e, k, s }); } catch (err) { if (prev) S.att[id] = prev; else delete S.att[id]; render(); toast(err.message, true); }
}
async function setEventState(e, s) {
  const prev = S.est[e];
  if (s === "upcoming") delete S.est[e]; else S.est[e] = { s };
  render();
  try { await api("/api/event-state", { e, s }); toast(s === "live" ? "Event started" : s === "done" ? "Event closed" : "Event reset"); }
  catch (err) { if (prev) S.est[e] = prev; else delete S.est[e]; render(); toast(err.message, true); }
}
async function editEvent(e, patch) {
  const ev = IDX.evs.find(x => x.id === e);
  const body = { e, venue: patch.venue ?? ev.venue, start: patch.start ?? ev.start, end: patch.end ?? ev.end };
  try { await api("/api/event-edit", body); await poll(true); toast("Event updated"); } catch (err) { toast(err.message, true); render(); }
}

/* ================= polling ================= */
async function poll(force) {
  if (!ME) return;
  try {
    const j = await api("/api/state?v=" + (force ? 0 : S.version));
    ONLINE = true;
    if (j.changed) { S.version = j.version; S.evo = j.evo; S.est = j.est; S.att = j.att; render(); }
    else updateLive();
  } catch (e) { ONLINE = false; updateLive(); }
}
setInterval(poll, 2500);
setInterval(() => { const c = $("#clock"); if (c) c.textContent = fmt(nowMin()); }, 10000);
setInterval(() => { if (ME && !isTyping()) render(); }, 60000);
function updateLive() { const l = $("#live"); if (l) { l.className = "live" + (ONLINE ? "" : " off"); l.lastElementChild.textContent = ONLINE ? "Live" : "Reconnecting…"; } }

/* ================= routing ================= */
const ADMIN_ROUTES = [["dashboard", "Dashboard", "dash"], ["venues", "Venue desks", "pin"], ["participants", "Participants", "users"], ["events", "Events & schedule", "cal"], ["reports", "Reports & export", "file"], ["settings", "Settings", "gear"]];
const VOL_ROUTES = [["desk", "My venue", "pin"], ["find", "Find participant", "search"]];
function routes() { return ME && ME.role === "admin" ? ADMIN_ROUTES : VOL_ROUTES; }
function currentRoute() { const h = location.hash.slice(1); const r = routes(); return r.some(x => x[0] === h) ? h : r[0][0]; }
window.addEventListener("hashchange", () => { ui.navOpen = false; ui.confirm = null; render(true); window.scrollTo(0, 0); });

/* ================= render ================= */
function isTyping() { const a = document.activeElement; return a && ["INPUT", "SELECT", "TEXTAREA"].includes(a.tagName) && !["q", "findq"].includes(a.id); }
let pending = false;
function render(force) {
  if (!ME) { renderLogin(); return; }
  if (!BOOT) return;
  if (isTyping() && !force) { pending = true; return; }
  pending = false;
  index();
  const route = currentRoute();
  const keep = document.activeElement && ["q", "findq"].includes(document.activeElement.id) ? { id: document.activeElement.id, pos: document.activeElement.selectionStart } : null;
  const title = routes().find(r => r[0] === route)[1];
  const lateN = SEEDPEOPLE().filter(p => { const i = info(p.chest); return i.state === "late"; }).length;
  $("#root").innerHTML = `
  <div class="app ${ui.navOpen ? "nav-open" : ""}">
    <aside class="sidebar" aria-label="Main navigation">
      <div class="side-brand"><img src="/logo.png" alt="Mar Thoma Church emblem"><div><b>Kalamela 2026</b><span>Ernakulam Yuvajana Sakhyam</span></div></div>
      <nav class="nav">
        <div class="nav-label">${ME.role === "admin" ? "Admin" : esc(ME.venue + " · " + vName(ME.venue))}</div>
        ${routes().map(([k, l, ic]) => `<a href="#${k}" class="${k === route ? "on" : ""}">${icon(ic)}<span>${l}</span>${k === "dashboard" && lateN ? `<span class="count">${lateN}</span>` : ""}</a>`).join("")}
      </nav>
      <div class="side-foot"><div class="avatar">${ME.role === "admin" ? "AD" : esc(ME.venue)}</div>
        <div class="who"><b>${ME.role === "admin" ? "Administrator" : esc(vName(ME.venue))}</b><span>${ME.role === "admin" ? "All venues" : "Venue volunteer"}</span></div>
        <button class="btn ghost sm" data-act="logout" title="Sign out" aria-label="Sign out">${icon("out")}</button></div>
    </aside>
    <div class="scrim" data-act="nav-close"></div>
    <div class="main">
      <header class="topbar">
        <button class="btn ghost sm menu-btn" data-act="nav-open" aria-label="Open menu">${icon("menu")}</button>
        <h1>${esc(title)}</h1><div class="grow"></div>
        <span class="live ${ONLINE ? "" : "off"}" id="live"><i></i><span>${ONLINE ? "Live" : "Reconnecting…"}</span></span>
        <span class="clock hide-sm" id="clock">${fmt(nowMin())}</span>
        ${ME.role === "admin" ? `<a class="btn primary sm" href="/api/export.xlsx" download>${icon("down")}<span class="hide-sm">Export Excel</span></a>` : ""}
      </header>
      <main class="content" id="view">${view(route)}</main>
    </div>
  </div>`;
  if (keep) { const el = document.getElementById(keep.id); if (el) { el.focus(); try { el.setSelectionRange(keep.pos, keep.pos); } catch (e) {} } }
  renderSheet();
}
function SEEDPEOPLE() { return BOOT.people; }
function view(r) {
  switch (r) {
    case "dashboard": return vDashboard();
    case "venues": return `<div class="toolbar"><div class="seg" role="tablist">${BOOT.venues.map(v => `<button class="${ui.venue === v.code ? "on" : ""}" data-act="venue" data-v="${v.code}">${v.code} · ${esc(v.name)}</button>`).join("")}</div></div>${vDesk(ui.venue)}`;
    case "participants": return vParticipants();
    case "events": return vEvents();
    case "reports": return vReports();
    case "settings": return vSettings();
    case "desk": return vDesk(ME.venue);
    case "find": return vFind();
  }
  return "";
}

/* ---------- login ---------- */
function renderLogin() {
  const multi = BOOT ? Object.keys(BOOT.people).length : 127;
  $("#root").innerHTML = `
  <div class="login">
    <section class="login-brand">
      <img src="/logo.png" alt="Mar Thoma Church emblem — Lighted to Lighten">
      <h1>Kalamela 2026<br>Attendance &amp; Venue Tracker</h1>
      <p>Ernakulam Yuvajana Sakhyam. Mark participants at each venue and follow every participant through the day.</p>
      <div class="login-facts"><div><b>5</b><span>Venues</span></div><div><b>42</b><span>Events</span></div><div><b>127</b><span>Participants</span></div></div>
    </section>
    <section class="login-form">
      <form class="login-card" id="login-form" autocomplete="off">
        <h2>Sign in</h2>
        <p>Enter the code given to you by the organiser.</p>
        <div class="field"><label for="code">Venue or admin code</label><input class="input code" id="code" placeholder="e.g. BALCONY2" autofocus></div>
        <div class="form-err" id="login-err"></div>
        <button class="btn primary block" type="submit">Sign in</button>
        <div class="login-foot">Volunteers see only their own venue. The admin code opens the full dashboard and Excel export.</div>
      </form>
    </section>
  </div>`;
}

/* ---------- dashboard ---------- */
function vDashboard() {
  const ppl = BOOT.people.map(p => ({ p, i: info(p.chest) }));
  const cnt = s => ppl.filter(x => x.i.state === s).length;
  const reported = ppl.filter(x => x.i.seen).length;
  const es = IDX.evs.map(e => stateOf(e.id));
  const doneN = es.filter(s => s === "done").length, liveN = es.filter(s => s === "live").length;
  const absentN = ppl.reduce((a, x) => a + x.i.absent, 0);
  const stat = (cls, lbl, val, foot, ratio) => `<div class="card stat ${cls}"><span class="lbl">${lbl}</span><span class="val">${val}</span>${ratio != null ? `<div class="meter"><i style="width:${Math.round(ratio * 100)}%"></i></div>` : `<span class="foot">${foot || "&nbsp;"}</span>`}</div>`;
  const stats = [
    stat("", "Reported today", `${reported}<small> / ${ppl.length}</small>`, "", reported / ppl.length),
    stat("green", "In competition now", cnt("in"), "Marked present at a live event"),
    stat("red", "Late", cnt("late"), "Past call time, not reported"),
    stat("amber", "Called / clashing", cnt("called") + ppl.filter(x => x.i.clash.length).length, "Wanted at another venue"),
    stat("red", "Absent entries", absentN, "Missed a closed event"),
    stat("blue", "Events completed", `${doneN}<small> / ${es.length}</small>`, "", doneN / es.length),
  ].join("");

  const venues = BOOT.venues.map(v => {
    const evs = IDX.evs.filter(e => e.venue === v.code);
    const live = evs.filter(e => stateOf(e.id) === "live");
    const next = evs.find(e => stateOf(e.id) === "upcoming");
    const d = evs.filter(e => stateOf(e.id) === "done").length;
    return `<div class="card venue" style="--vc:var(--${v.code.toLowerCase()})">
      <div class="card-h">${vbadge(v.code)}<h2>${esc(v.name)}</h2><span class="grow"></span><span class="sub">${d}/${evs.length} done</span></div>
      <div class="card-b">
        ${live.length ? live.map(e => { const c = counts(e); return `<div class="now-ev"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">${badge("live", "Live")}<a href="#venues" data-act="open-ev" data-e="${e.id}">${esc(short(e.title))}</a></div>${progress(c, e.entries.length)}</div>`; }).join("") : `<div class="muted">No event running.</div>`}
        <div class="kv-row"><span class="muted">Next</span><span>${next ? `${fmt(next.start)} · ${esc(short(next.title))}` : "None"}</span></div>
      </div></div>`;
  }).join("");

  const n = nowMin(), alerts = [];
  IDX.evs.filter(e => stateOf(e.id) === "live").forEach(e => e.entries.forEach(en => {
    if (entryStatus(e, keyOf(en)) !== "waiting") return;
    const late = n > en.time + 5;
    if (en.team) {
      const busy = en.members.filter(c => { const i = info(c); return i.at && i.at.ev.id !== e.id; });
      if (busy.length || late) alerts.push({ red: late, t: en.time, c: en.members[0], title: `Team ${en.team} · ${teamParish(en)}`, d: `${short(e.title)} at ${e.venue} · call ${fmt(en.time)}${busy.length ? ` · ${busy.length} member(s) still in another event` : ""}` });
      return;
    }
    const i = info(en.chest), p = PEOPLE[en.chest] || {};
    if (!late && !i.at) return;
    alerts.push({ red: late && !i.at, t: en.time, c: en.chest, title: `${en.chest} · ${p.name || ""}`,
      d: `Due at ${e.venue} · ${short(e.title)} (${fmt(en.time)}) · ${i.at ? "now at " + i.at.ev.venue + " · " + short(i.at.ev.title) : i.seen ? "not at any venue" : "not seen today"}${p.phone ? " · " + p.phone : ""}` });
  }));
  alerts.sort((a, b) => (b.red - a.red) || a.t - b.t);
  const soon = IDX.evs.filter(e => stateOf(e.id) === "upcoming" && e.start <= n + 30 && e.start > n - 240).map(e => ({ e, late: e.start < n - 10 }));
  return `
    <div class="stats">${stats}</div>
    <div class="venue-grid">${venues}</div>
    <div class="card">
      <div class="card-h"><h2>Schedule by venue</h2><span class="sub">${liveN} live · click an event to open its call sheet</span></div>
      <div class="tl-scroll">${timeline()}</div>
      <div class="tl-key"><span><i style="background:color-mix(in srgb,var(--v1) 10%,white);border:1px solid color-mix(in srgb,var(--v1) 45%,white)"></i>Upcoming</span><span><i style="background:var(--v1)"></i>Live</span><span><i style="background:var(--gray-bg);border:1px solid var(--line)"></i>Closed</span><span><i style="border:1.5px dashed var(--red)"></i>Not started on time</span><span><i style="background:var(--primary)"></i>Current time</span></div>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-h"><h2>Needs attention</h2><span class="grow"></span>${alerts.length ? badge("late", alerts.length + " open") : ""}</div>
        <div class="list">${alerts.slice(0, 40).map(a => `<div class="li ${a.red ? "red" : ""}"><span class="sev"></span><div style="min-width:0"><div class="t">${esc(a.title)}</div><div class="d">${esc(a.d)}</div></div><button class="btn sm" data-act="person" data-c="${a.c}">View</button></div>`).join("") || `<div class="empty">Nobody is late or held up at another venue.</div>`}</div></div>
      <div class="card"><div class="card-h"><h2>Starting soon</h2></div>
        <div class="list">${soon.map(({ e, late }) => `<div class="li ${late ? "red" : "blue"}"><span class="sev"></span><div style="min-width:0"><div class="t">${vbadge(e.venue)} ${esc(short(e.title))}</div><div class="d">${late ? "Scheduled " + fmt(e.start) + ", not started yet" : "Starts " + fmt(e.start)} · ${e.entries.length} ${e.type === "group" ? "teams" : "entries"}</div></div><button class="btn sm" data-act="open-ev" data-e="${e.id}">Open</button></div>`).join("") || `<div class="empty">No event due in the next 30 minutes.</div>`}</div></div>
    </div>`;
}
function progress(c, total) {
  const p = x => total ? x / total * 100 : 0;
  return `<div class="bar" role="img" aria-label="${c.done} performed, ${c.present} present, ${c.absent} absent of ${total}"><i style="width:${p(c.done)}%;background:var(--blue)"></i><i style="width:${p(c.present)}%;background:var(--green)"></i><i style="width:${p(c.absent)}%;background:var(--red)"></i></div>
    <div class="legend"><span><span class="d" style="background:var(--green)"></span><b>${c.present}</b> present</span><span><span class="d" style="background:var(--blue)"></span><b>${c.done}</b> performed</span><span><span class="d" style="background:var(--red)"></span><b>${c.absent}</b> absent</span><span><span class="d" style="background:var(--line-2)"></span><b>${c.waiting}</b> waiting</span></div>`;
}
function timeline() {
  const T0 = 8 * 60 + 30, T1 = 19 * 60 + 30, span = T1 - T0, n = nowMin();
  const x = m => (Math.min(Math.max(m, T0), T1) - T0) / span * 100;
  const ticks = []; for (let h = 9; h <= 19; h++) ticks.push(`<span class="tl-tick" style="left:${x(h * 60)}%">${h > 12 ? h - 12 : h} ${h >= 12 ? "PM" : "AM"}</span>`);
  const grid = `background-image:linear-gradient(to right,var(--line) 0 1px,transparent 1px);background-size:${100 / (span / 60)}% 100%;background-position:${x(9 * 60)}% 0`;
  const now = lbl => n >= T0 && n <= T1 ? `<div class="tl-now" style="left:${x(n)}%">${lbl ? `<span>${fmt(n)}</span>` : ""}</div>` : "";
  const rows = BOOT.venues.map(v => {
    const evs = IDX.evs.filter(e => e.venue === v.code), lanes = [];
    const placed = evs.map(e => { let l = lanes.findIndex(end => end <= e.start); if (l < 0) { l = lanes.length; lanes.push(0); } lanes[l] = e.end; return { e, l }; });
    const h = Math.max(1, lanes.length) * 30 + 8;
    return `<div class="tl-row" style="--vc:var(--${v.code.toLowerCase()})"><div class="tl-lab">${vbadge(v.code)}<span>${esc(v.name)}</span></div>
      <div class="tl-track" style="height:${h}px;${grid}"><div class="tl-lunch" style="left:${x(810)}%;width:${x(855) - x(810)}%"></div>
      ${placed.map(({ e, l }) => { const st = stateOf(e.id), late = st === "upcoming" && n > e.start + 10 && n < e.start + 240;
        return `<button class="tl-blk ${st} ${late ? "late" : ""}" style="left:${x(e.start)}%;width:calc(${x(e.end) - x(e.start)}% - 2px);top:${4 + l * 30}px" data-act="open-ev" data-e="${e.id}" title="${esc(short(e.title))} · ${fmt(e.start)}–${fmt(e.end)} · ${LBL[st]}">${esc(short(e.title))}</button>`; }).join("")}
      ${now(false)}</div></div>`;
  }).join("");
  return `<div class="tl"><div class="tl-row axis"><div></div><div class="tl-track" style="height:26px">${ticks.join("")}${now(true)}</div></div>${rows}</div>`;
}

/* ---------- venue desk ---------- */
function vDesk(venue) {
  const evs = IDX.evs.filter(e => e.venue === venue);
  if (!evs.length) return `<div class="card empty">No events are assigned to ${esc(vName(venue))}.</div>`;
  let sel = evs.find(e => e.id === ui.sel);
  if (!sel) sel = evs.find(e => stateOf(e.id) === "live") || evs.find(e => stateOf(e.id) === "upcoming") || evs[evs.length - 1];
  let lunch = false;
  const items = evs.map(e => {
    const st = stateOf(e.id), c = counts(e), rep = c.present + c.done;
    let pre = ""; if (!lunch && e.start >= 810) { lunch = true; pre = `<div class="lunch">Lunch · 1:30 – 2:15 PM</div>`; }
    return pre + `<button class="ev-item ${e.id === sel.id ? "sel" : ""}" data-act="sel" data-e="${e.id}"><span class="tm">${fmt(e.start)}<br>${fmt(e.end)}</span><span style="min-width:0"><span class="nm">${esc(short(e.title))}</span><span class="mt">${badge(st)}<span>${rep}/${e.entries.length} reported</span></span></span></button>`;
  }).join("");
  const select = `<div class="ev-select"><label class="sr" for="evsel">Event</label><select class="input" id="evsel" data-act="sel-select">${evs.map(e => `<option value="${e.id}" ${e.id === sel.id ? "selected" : ""}>${fmt(e.start)} · ${esc(short(e.title))} · ${LBL[stateOf(e.id)]}</option>`).join("")}</select></div>`;
  return `${select}<div class="desk"><div class="ev-list">${items}</div><div style="min-width:0;display:grid;gap:16px">${callSheet(sel)}${nextHere(evs, sel)}</div></div>`;
}
function nextHere(evs, sel) {
  const nx = evs.find(e => stateOf(e.id) === "upcoming" && e.id !== sel.id);
  if (!nx) return "";
  const busy = [];
  nx.entries.forEach(en => (en.members || [en.chest]).forEach(c => { const i = info(c); if (i.at) busy.push({ c, i }); }));
  return `<div class="card"><div class="card-h"><h2>Next here: ${esc(short(nx.title))}</h2><span class="sub">${fmt(nx.start)}</span></div>
    <div class="list">${busy.length ? busy.slice(0, 15).map(b => `<div class="li"><span class="sev"></span><div><div class="t">${b.c} · ${esc((PEOPLE[b.c] || {}).name || "")}</div><div class="d">Currently at ${b.i.at.ev.venue} · ${esc(short(b.i.at.ev.title))}</div></div><span></span></div>`).join("") : `<div class="empty">Nobody in the next event is busy at another venue.</div>`}</div></div>`;
}
function callSheet(ev) {
  const st = stateOf(ev.id), c = counts(ev), admin = ME.role === "admin", locked = st === "done" && !admin;
  let ctl = "";
  if (st === "upcoming") ctl = `<button class="btn success" data-act="start" data-e="${ev.id}">${icon("play")}Start event</button>`;
  else if (st === "live") ctl = `<button class="btn danger" data-act="ask-close" data-e="${ev.id}">${icon("stop")}Close event</button>`;
  else if (admin) ctl = `<button class="btn" data-act="reopen" data-e="${ev.id}">Reopen</button>`;
  const conf = ui.confirm && ui.confirm.e === ev.id ? `<div class="confirm"><span>Close <b>${esc(short(ev.title))}</b>? ${c.waiting ? `<b>${c.waiting}</b> not marked will be recorded as absent.` : "Everyone is marked."}</span><button class="btn sm" data-act="cancel">Keep open</button><button class="btn sm danger" data-act="close" data-e="${ev.id}">Close event</button></div>` : "";
  return `<div class="card">
    <div class="sheet-head">${vbadge(ev.venue)}<div class="grow"><h2>${esc(short(ev.title))}</h2><div class="meta">${esc(vName(ev.venue))} · ${fmt(ev.start)} – ${fmt(ev.end)} · ${ev.entries.length} ${ev.type === "group" ? "teams" : "entries"}${ev.type === "offstage" ? " · seated together" : ""}</div></div>${badge(st)}${ctl}</div>
    ${conf}
    <div class="sheet-prog">${progress(c, ev.entries.length)}</div>
    <div>${ev.entries.map(en => entryRow(ev, en, locked || (st === "done"))).join("")}</div>
  </div>`;
}
function whereHTML(c, hereId) {
  const i = info(c);
  if (i.at && i.at.ev.id !== hereId) return `${badge("clash", "Busy at " + i.at.ev.venue)} <span class="muted">${esc(short(i.at.ev.title))}, until ~${fmt(i.at.ev.end)}</span>`;
  if (i.at) return "";
  const other = i.due.filter(x => x.ev.id !== hereId);
  if (other.length) return `${badge("called", "Also called at " + other[0].ev.venue)} <span class="muted">${esc(short(other[0].ev.title))}</span>`;
  return `<span class="muted">${i.seen ? "Free right now" : "Not seen at any venue yet"}</span>`;
}
function entryRow(ev, en, locked) {
  const k = keyOf(en), s = entryStatus(ev, k), st = stateOf(ev.id);
  let who, where = "";
  if (en.team) {
    const busy = en.members.filter(c => { const i = info(c); return i.at && i.at.ev.id !== ev.id; });
    who = `<div class="nm">${esc(teamParish(en))}</div><div class="sub">${en.members.length} members</div><div class="members">${en.members.map(c => { const i = info(c); const cl = i.at ? (i.at.ev.id === ev.id ? "in" : "busy") : ""; return `<button class="mem ${cl}" data-act="person" data-c="${c}" title="${esc((PEOPLE[c] || {}).name || c)}">${c}</button>`; }).join("")}</div>`;
    if (busy.length && s === "waiting") where = `<div class="where">${badge("clash", busy.length + " member" + (busy.length > 1 ? "s" : "") + " in another event")}</div>`;
  } else {
    const p = PEOPLE[en.chest] || { name: en.chest, parish: "" };
    who = `<div class="nm"><a href="#" data-act="person" data-c="${en.chest}">${esc(p.name)}</a></div><div class="sub">${esc(p.parish)}${p.phone ? " · " + esc(p.phone) : ""}</div>`;
    if (s === "waiting" && st !== "done") where = `<div class="where">${whereHTML(en.chest, ev.id)}</div>`;
  }
  const late = s === "waiting" && st === "live" && nowMin() > en.time + 5;
  let acts = badge(late ? "late" : s, late ? "Late" : LBL[s]);
  if (!locked) {
    const b = (cls, lab, val) => `<button class="btn sm ${cls}" data-act="mark" data-e="${ev.id}" data-k="${esc(k)}" data-s="${val}">${lab}</button>`;
    if (s === "waiting") acts += b("success", "Present", "present") + b("", "Absent", "absent");
    else if (s === "present") acts += b("primary", "Performed", "done") + b("ghost", "Undo", "");
    else acts += b("ghost", "Undo", "");
  }
  return `<div class="entry ${s === "done" || s === "absent" ? "dim" : ""}"><span class="ord">${en.order}${en.cat ? `<br>${en.cat}` : ""}</span>
    <span class="chest">${esc(k)}<small>${fmt(en.time)}</small></span>
    <div class="info" style="min-width:0">${who}${where}</div><div class="acts">${acts}</div></div>`;
}

/* ---------- participants ---------- */
const PF = [["all", "All"], ["in", "In competition"], ["late", "Late / called"], ["absent", "Missed an event"], ["notyet", "Not reported"], ["free", "Free"], ["finished", "Finished"]];
function pMatch(p, i, f) { if (f === "all") return true; if (f === "late") return i.state === "late" || i.state === "called" || i.clash.length > 0; if (f === "absent") return i.absent > 0; return i.state === f; }
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
  return `<table class="t cards"><thead><tr><th>Chest no.</th><th>Participant</th><th>Parish</th><th>Contact</th><th>Status</th><th>Current location</th><th>Progress</th><th>Next event</th></tr></thead><tbody>
  ${rows.map(({ p, i }) => `<tr class="click" data-act="person" data-c="${p.chest}">
    <td class="lead" data-l="Chest"><b>${p.chest}</b><span class="muted" style="display:none"></span></td>
    <td data-l="Name"><b>${esc(p.name)}</b></td>
    <td data-l="Parish"><span class="sub">${esc(p.parish)}</span></td>
    <td data-l="Contact" class="num">${esc(p.phone || "–")}</td>
    <td data-l="Status">${badge(i.state)}${i.clash.length ? " " + badge("clash", "Clash") : ""}</td>
    <td data-l="Location">${i.at ? `${vbadge(i.at.ev.venue)} ${esc(short(i.at.ev.title))}` : `<span class="muted">–</span>`}</td>
    <td data-l="Progress" class="num">${i.done}/${i.total} done${i.absent ? ` · <span style="color:var(--red)">${i.absent} absent</span>` : ""}</td>
    <td data-l="Next">${i.next ? `${fmt(i.next.time)} · ${i.next.ev.venue} <span class="sub">${esc(short(i.next.ev.title))}</span>` : `<span class="muted">–</span>`}</td></tr>`).join("")}
  </tbody></table>`;
}

/* ---------- find (volunteer) ---------- */
function vFind() {
  const q = ui.findQ.trim().toLowerCase();
  const hits = q ? BOOT.people.filter(p => (p.chest + " " + p.name).toLowerCase().includes(q)).slice(0, 30) : [];
  return `<div class="toolbar"><div class="search">${icon("search")}<input class="input" id="findq" placeholder="Type a chest number or name" value="${esc(ui.findQ)}" aria-label="Find a participant"></div></div>
  <div class="card"><div class="list" id="findres">${findRows(hits, q)}</div></div>`;
}
function findRows(hits, q) {
  if (!q) return `<div class="empty">Search any participant to see where they are and their events today.</div>`;
  if (!hits.length) return `<div class="empty">No match.</div>`;
  return hits.map(p => { const i = info(p.chest); return `<div class="li"><span class="sev" style="background:var(--line)"></span><div style="min-width:0"><div class="t">${p.chest} · ${esc(p.name)}</div><div class="d">${esc(p.parish)} · ${i.at ? "At " + i.at.ev.venue + " · " + esc(short(i.at.ev.title)) : LBL[i.state]}</div></div><button class="btn sm" data-act="person" data-c="${p.chest}">View</button></div>`; }).join("");
}

/* ---------- events editor ---------- */
function vEvents() {
  const opts = v => BOOT.venues.map(x => `<option value="${x.code}" ${x.code === v ? "selected" : ""}>${x.code} · ${esc(x.name)}</option>`).join("");
  return `<div class="banner" style="background:var(--blue-bg);color:#1e3a8a">Assign each event to a venue and adjust its time. Volunteers only see the events at their own venue. Call times move with the start time.</div>
  <div class="card"><div class="table-wrap"><table class="t cards"><thead><tr><th>Event</th><th>Venue</th><th>Start</th><th>End</th><th>Status</th><th>Attendance</th><th></th></tr></thead><tbody>
  ${IDX.evs.map(e => { const st = stateOf(e.id), c = counts(e), ch = S.evo[e.id] && Object.keys(S.evo[e.id]).length;
    return `<tr class="ev-edit"><td class="lead" data-l="Event"><b>${esc(short(e.title))}</b><div class="sub">${e.entries.length} ${e.type === "group" ? "teams" : "entries"}${ch ? " · changed from printed schedule" : ""}</div></td>
    <td data-l="Venue"><select class="input" data-act="ev-venue" data-e="${e.id}" aria-label="Venue">${opts(e.venue)}</select></td>
    <td data-l="Start"><input class="input" type="time" value="${toHHMM(e.start)}" data-act="ev-start" data-e="${e.id}" aria-label="Start time"></td>
    <td data-l="End"><input class="input" type="time" value="${toHHMM(e.end)}" data-act="ev-end" data-e="${e.id}" aria-label="End time"></td>
    <td data-l="Status">${badge(st)}</td>
    <td data-l="Attendance" class="num">${c.present + c.done}/${e.entries.length}${c.absent ? ` · <span style="color:var(--red)">${c.absent} absent</span>` : ""}</td>
    <td data-l=""><button class="btn sm" data-act="open-ev" data-e="${e.id}">Open</button>${ch ? ` <button class="btn sm ghost" data-act="ev-reset" data-e="${e.id}">Undo changes</button>` : ""}</td></tr>`; }).join("")}
  </tbody></table></div></div>`;
}

/* ---------- reports ---------- */
function vReports() {
  const rows = IDX.evs.map(e => ({ e, c: counts(e) }));
  const tot = rows.reduce((a, { c }) => { for (const k in c) a[k] += c[k]; return a; }, { waiting: 0, present: 0, done: 0, absent: 0 });
  return `<div class="card"><div class="card-b export-hero"><div><h2 style="margin:0 0 4px;font-size:17px">Download attendance as Excel</h2><div class="muted">Up-to-the-minute workbook of every event, participant and mark. Admin only.</div></div>
    <a class="btn primary" href="/api/export.xlsx" download>${icon("down")}Download .xlsx</a></div>
    <div class="card-b" style="padding-top:0"><div class="sheets-list">
      <div><b>Summary</b>Totals for the day</div><div><b>Attendance</b>One row per participant per event, with status and who marked it</div>
      <div><b>Participants</b>Each person's performed, absent and pending counts</div><div><b>Events</b>Status and counts for every event</div><div><b>Activity log</b>Every action with time and venue</div></div></div></div>
  <div class="card"><div class="card-h"><h2>Attendance by event</h2><span class="grow"></span><span class="sub">${tot.done} performed · ${tot.present} present · ${tot.absent} absent · ${tot.waiting} not marked</span></div>
    <div class="table-wrap"><table class="t cards"><thead><tr><th>Event</th><th>Venue</th><th>Time</th><th>Status</th><th>Performed</th><th>Present</th><th>Absent</th><th>Not marked</th></tr></thead><tbody>
    ${rows.map(({ e, c }) => `<tr class="click" data-act="open-ev" data-e="${e.id}"><td class="lead" data-l="Event"><b>${esc(short(e.title))}</b></td><td data-l="Venue">${vbadge(e.venue)} ${esc(vName(e.venue))}</td><td data-l="Time" class="num">${fmt(e.start)}</td><td data-l="Status">${badge(stateOf(e.id))}</td><td data-l="Performed" class="num">${c.done}</td><td data-l="Present" class="num">${c.present}</td><td data-l="Absent" class="num" style="color:${c.absent ? "var(--red)" : "inherit"}">${c.absent}</td><td data-l="Not marked" class="num">${c.waiting}</td></tr>`).join("")}
    </tbody></table></div></div>`;
}

/* ---------- settings ---------- */
let CODES = null;
function vSettings() {
  if (!CODES) { api("/api/settings").then(j => { CODES = j.codes; render(true); }).catch(e => toast(e.message, true)); return `<div class="card empty">Loading…</div>`; }
  return `<div class="grid-2">
  <div class="card"><div class="card-h"><h2>Sign-in codes</h2></div><div class="card-b">
    <form class="settings-form" id="codes-form">
      <div class="row2">${BOOT.venues.map(v => `<div class="field"><label for="c-${v.code}">${v.code} · ${esc(v.name)}</label><input class="input code" id="c-${v.code}" value="${esc(CODES[v.code])}"></div>`).join("")}</div>
      <div class="field"><label for="c-admin">Admin code</label><input class="input code" id="c-admin" value="${esc(CODES.admin)}"></div>
      <div><button class="btn primary" type="submit">Save codes</button></div>
      <div class="muted" style="font-size:12.5px">Saving new codes signs out every other device. Share the new venue codes with volunteers.</div>
    </form></div></div>
  <div class="card"><div class="card-h"><h2>Practice &amp; reset</h2></div><div class="card-b" style="display:grid;gap:16px">
    <div><b>Load practice data</b><div class="muted" style="margin:2px 0 10px">Fills in sample attendance up to the current time so volunteers can rehearse. Replaces all current marks.</div>
      ${ui.confirm && ui.confirm.sample ? `<div class="confirm" style="margin:0"><span>Replace all attendance with practice data?</span><button class="btn sm" data-act="cancel">Cancel</button><button class="btn sm primary" data-act="sample-do">Load practice data</button></div>` : `<button class="btn" data-act="sample-ask">Load practice data</button>`}</div>
    <div><b>Reset attendance</b><div class="muted" style="margin:2px 0 10px">Clears every mark and event status before the real day. Schedule changes are kept. Download the Excel first if you need a copy.</div>
      ${ui.confirm && ui.confirm.reset ? `<div class="confirm" style="margin:0"><span>Delete all ${Object.keys(S.att).length} marks and ${Object.keys(S.est).length} event statuses? This cannot be undone.</span><button class="btn sm" data-act="cancel">Cancel</button><button class="btn sm danger" data-act="reset-do">Reset everything</button></div>` : `<button class="btn danger" data-act="reset-ask">Reset attendance</button>`}</div>
  </div></div></div>`;
}

/* ---------- person sheet ---------- */
function renderSheet() {
  const root = $("#sheet-root");
  const p = ui.person && PEOPLE[ui.person];
  if (!p) { root.innerHTML = ""; return; }
  const i = info(p.chest);
  root.innerHTML = `<div class="overlay" data-act="sheet-close"><aside class="panel" role="dialog" aria-modal="true" aria-label="${esc(p.name)}">
    <div class="panel-h"><div style="flex:1;min-width:0"><div class="muted" style="font-size:12.5px;font-weight:600">${p.chest}</div><h2>${esc(p.name)}</h2><div style="margin-top:6px">${badge(i.state)}${i.at ? ` <span class="muted">at</span> ${vbadge(i.at.ev.venue)} ${esc(short(i.at.ev.title))}` : ""}</div></div>
      <button class="btn ghost sm" data-act="sheet-close" aria-label="Close">${icon("x")}</button></div>
    <div class="panel-b">
      <dl class="dl"><dt>Parish</dt><dd>${esc(p.parish)}</dd><dt>Gender</dt><dd>${esc(p.gender || "–")}</dd><dt>Contact</dt><dd class="num">${esc(p.phone || "–")}<div class="muted" style="font-size:12.5px">${esc(p.secretary || "")}, parish secretary</div></dd><dt>Events</dt><dd>${i.done} performed · ${i.absent} absent · ${i.total} total</dd></dl>
      <div><div style="font-weight:600;margin-bottom:10px">Schedule today</div><div class="steps">
      ${i.list.map(x => `<div class="step ${x.st}"><div class="tt">${esc(short(x.ev.title))}${x.en.team ? ` <span class="muted">· team ${esc(x.en.team)}</span>` : ""}</div><div class="mt"><span class="num">${fmt(x.time)}</span>${vbadge(x.ev.venue)}<span>${esc(vName(x.ev.venue))}</span>${badge(x.st)}${x.es === "live" ? badge("live", "Event live") : ""}</div></div>`).join("")}</div></div>
    </div></aside></div>`;
}

/* ================= events ================= */
document.addEventListener("click", e => {
  const t = e.target.closest("[data-act]"); if (!t) return;
  const a = t.dataset.act;
  if (a === "sheet-close") { if (t.classList.contains("overlay") && e.target !== t) return; ui.person = null; renderSheet(); return; }
  if (t.tagName === "A" && a !== "open-ev") e.preventDefault();
  if (a === "open-ev") e.preventDefault();
  switch (a) {
    case "logout": api("/api/logout", {}).finally(() => { ME = null; CODES = null; location.hash = ""; renderLogin(); }); break;
    case "nav-open": ui.navOpen = true; render(true); break;
    case "nav-close": ui.navOpen = false; render(true); break;
    case "venue": ui.venue = t.dataset.v; ui.sel = null; render(true); break;
    case "sel": ui.sel = t.dataset.e; ui.confirm = null; render(true); break;
    case "open-ev": { const ev = IDX.evs.find(x => x.id === t.dataset.e); if (!ev) break; ui.sel = ev.id; ui.person = null;
      if (ME.role === "admin") { ui.venue = ev.venue; if (location.hash !== "#venues") { location.hash = "venues"; return; } } render(true); window.scrollTo(0, 0); break; }
    case "filter": ui.filter = t.dataset.f; render(true); break;
    case "person": ui.person = t.dataset.c; renderSheet(); break;
    case "mark": mark(t.dataset.e, t.dataset.k, t.dataset.s || null); break;
    case "start": setEventState(t.dataset.e, "live"); break;
    case "ask-close": ui.confirm = { e: t.dataset.e }; render(true); break;
    case "cancel": ui.confirm = null; render(true); break;
    case "close": ui.confirm = null; setEventState(t.dataset.e, "done"); break;
    case "reopen": setEventState(t.dataset.e, "live"); break;
    case "ev-reset": { const o = ORIG[t.dataset.e]; editEvent(o.id, { venue: o.venue, start: o.start, end: o.end }); break; }
    case "reset-ask": ui.confirm = { reset: true }; render(true); break;
    case "sample-ask": ui.confirm = { sample: true }; render(true); break;
    case "reset-do": ui.confirm = null; api("/api/reset", {}).then(() => { toast("All attendance cleared"); return poll(true); }).catch(er => toast(er.message, true)); break;
    case "sample-do": { ui.confirm = null; const n = Math.min(Math.max(nowMin(), 9 * 60 + 30), 17 * 60 + 30);
      api("/api/sample", { now: n }).then(() => { toast("Practice data loaded"); return poll(true); }).catch(er => toast(er.message, true)); break; }
  }
});
document.addEventListener("keydown", e => { if (e.key === "Escape") { if (ui.person) { ui.person = null; renderSheet(); } else if (ui.navOpen) { ui.navOpen = false; render(true); } } });
document.addEventListener("input", e => {
  if (e.target.id === "q") { ui.q = e.target.value; const el = $("#ptable"); if (el) el.innerHTML = pTable(); }
  if (e.target.id === "findq") { ui.findQ = e.target.value; const q = ui.findQ.trim().toLowerCase(); $("#findres").innerHTML = findRows(q ? BOOT.people.filter(p => (p.chest + " " + p.name).toLowerCase().includes(q)).slice(0, 30) : [], q); }
});
document.addEventListener("change", e => {
  const t = e.target, a = t.dataset && t.dataset.act; if (!a) return;
  if (a === "sel-select") { ui.sel = t.value; ui.confirm = null; t.blur(); render(true); return; }
  const id = t.dataset.e, ev = IDX.evs.find(x => x.id === id);
  if (a === "ev-venue") editEvent(id, { venue: t.value });
  if (a === "ev-start" && t.value) { const ns = fromHHMM(t.value); editEvent(id, { start: ns, end: ev.end + (ns - ev.start) }); }
  if (a === "ev-end" && t.value) editEvent(id, { end: fromHHMM(t.value) });
});
document.addEventListener("focusout", () => setTimeout(() => { if (pending && !isTyping()) render(); }, 0));
document.addEventListener("submit", async e => {
  e.preventDefault();
  if (e.target.id === "login-form") {
    const err = $("#login-err"); err.textContent = "";
    try { const j = await api("/api/login", { code: $("#code").value }); ME = j.user; location.hash = ""; await start(); }
    catch (x) { err.textContent = x.message; }
  }
  if (e.target.id === "codes-form") {
    const codes = { admin: $("#c-admin").value }; BOOT.venues.forEach(v => codes[v.code] = $("#c-" + v.code).value);
    try { await api("/api/settings", { codes }); CODES = null; toast("Codes saved. Other devices have been signed out."); render(true); } catch (x) { toast(x.message, true); }
  }
});

/* ================= boot ================= */
async function start() {
  if (!BOOT) {
    BOOT = await api("/api/bootstrap");
    VMAP = Object.fromEntries(BOOT.venues.map(v => [v.code, v]));
    PEOPLE = Object.fromEntries(BOOT.people.map(p => [p.chest, p]));
    ORIG = Object.fromEntries(BOOT.events.map(e => [e.id, e]));
  }
  await poll(true);
  render(true);
}
(async function init() {
  try { const j = await api("/api/me"); ME = j.user; } catch (e) { ME = null; }
  if (ME) await start(); else renderLogin();
})();
})();
