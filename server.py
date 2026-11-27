"""Kalamela 2026 attendance tracker - local web server.

Run:  python server.py            (default port 8000)
      python server.py --port 9000
Then open http://localhost:8000 on this laptop, or http://<laptop-ip>:8000 on
phones/tablets connected to the same Wi-Fi.

Only Python's standard library + openpyxl (for the Excel export) are needed.
"""
import argparse, io, json, os, secrets, socket, sqlite3, threading, time
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
DB_PATH = os.environ.get("KALAMELA_DB", os.path.join(HERE, "kalamela.db"))
DATA_PATH = os.path.join(HERE, "data.json")

# The admin code is never stored in this repository. It comes from the
# KALAMELA_ADMIN_CODE environment variable, or a random one is created on first
# run and printed in the server window (change it later in Settings).
DEFAULT_CODES = {"V1": "CHURCH1", "V2": "BALCONY2", "V3": "SSHALL3", "V4": "FHALL4"}


def first_admin_code():
    env = os.environ.get("KALAMELA_ADMIN_CODE", "").strip().upper()
    if len(env) >= 4:
        return env
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "ADM-" + "".join(secrets.choice(alphabet) for _ in range(6))
STATUSES = {"present", "done", "absent"}
EVENT_STATES = {"upcoming", "live", "done"}

# ---------------------------------------------------------------- data
with open(DATA_PATH, encoding="utf-8") as f:
    SEED = json.load(f)
for e in SEED["events"]:
    e["venue"] = e["venue"].replace("Venue ", "V")
VENUES = [{"code": v["code"], "name": v["name"]} for v in SEED["venues"]]
VENUE_NAME = {v["code"]: v["name"] for v in VENUES}
PEOPLE = {p["chest"]: p for p in SEED["people"]}
EVENTS = {e["id"]: e for e in SEED["events"]}

LOCK = threading.Lock()
SESSIONS = {}  # token -> {"role": "admin"|"venue", "venue": "V1"|None, "at": ts}


def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


CON = db()


def init_db():
    with LOCK:
        CON.executescript("""
        CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS event_override(id TEXT PRIMARY KEY, venue TEXT, start INTEGER, "end" INTEGER);
        CREATE TABLE IF NOT EXISTS event_state(id TEXT PRIMARY KEY, state TEXT, at TEXT, by TEXT);
        CREATE TABLE IF NOT EXISTS attendance(eid TEXT, k TEXT, status TEXT, at TEXT, by TEXT, PRIMARY KEY(eid, k));
        CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, by TEXT, action TEXT, eid TEXT, k TEXT, detail TEXT);
        """)
        for k, v in DEFAULT_CODES.items():
            CON.execute("INSERT OR IGNORE INTO config(key,value) VALUES(?,?)", ("code_" + k, v))
        CON.execute("INSERT OR IGNORE INTO config(key,value) VALUES(?,?)", ("code_admin", first_admin_code()))
        CON.execute("INSERT OR IGNORE INTO config(key,value) VALUES('version','1')")
        CON.commit()


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def bump(cur):
    cur.execute("UPDATE config SET value = CAST(value AS INTEGER) + 1 WHERE key='version'")


def log(cur, by, action, eid="", k="", detail=""):
    cur.execute("INSERT INTO activity(at,by,action,eid,k,detail) VALUES(?,?,?,?,?,?)", (now_iso(), by, action, eid, k, detail))


def codes():
    rows = CON.execute("SELECT key,value FROM config WHERE key LIKE 'code_%'").fetchall()
    return {r["key"][5:]: r["value"] for r in rows}


def version():
    return int(CON.execute("SELECT value FROM config WHERE key='version'").fetchone()[0])


def overrides():
    return {r["id"]: {k: r[k] for k in ("venue", "start", "end") if r[k] is not None}
            for r in CON.execute('SELECT id,venue,start,"end" FROM event_override')}


_SNAP = {"v": None, "data": None}


def state_snapshot():
    """Full attendance state. Cached per version so 20+ devices polling cost one DB read per change."""
    with LOCK:
        v = version()
        if _SNAP["v"] == v:
            return _SNAP["data"]
        data = {
            "version": version(),
            "evo": overrides(),
            "est": {r["id"]: {"s": r["state"], "at": r["at"], "by": r["by"]} for r in CON.execute("SELECT * FROM event_state")},
            "att": {r["eid"] + "--" + r["k"]: {"s": r["status"], "at": r["at"], "by": r["by"]} for r in CON.execute("SELECT * FROM attendance")},
        }
        _SNAP["v"], _SNAP["data"] = v, data
        return data


def merged_events():
    with LOCK:
        evo = overrides()
    out = []
    for e in SEED["events"]:
        o = evo.get(e["id"], {})
        start, end = o.get("start", e["start"]), o.get("end", e["end"])
        d = start - e["start"]
        out.append({**e, "venue": o.get("venue", e["venue"]), "start": start, "end": end,
                    "entries": [{**x, "time": x["time"] + d} for x in e["entries"]]})
    out.sort(key=lambda e: (e["start"], e["venue"]))
    return out


def who(sess):
    return "Admin" if sess["role"] == "admin" else sess["venue"]


# ---------------------------------------------------------------- excel export
def fmt_min(m):
    h, mm = divmod(int(m), 60)
    ap = "PM" if h >= 12 else "AM"
    h = h % 12 or 12
    return f"{h}:{mm:02d} {ap}"


def build_workbook():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    snap = state_snapshot()
    evs = merged_events()
    est, att = snap["est"], snap["att"]
    label = {"present": "Present", "done": "Performed", "absent": "Absent", "waiting": "Not marked"}

    def status(ev, k):
        a = att.get(ev["id"] + "--" + k, {}).get("s")
        st = est.get(ev["id"], {}).get("s", "upcoming")
        if st == "done":
            return "done" if a in ("present", "done") else "absent"
        return a or "waiting"

    wb = Workbook()
    red = "C8102E"
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor=red)
    thin = Side(style="thin", color="D9DDE3")
    fills = {"Performed": "DCEBFF", "Present": "DDF3E4", "Absent": "FBE0E3", "Not marked": "F2F3F5"}

    def sheet(ws, headers, rows, widths, status_col=None):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = head_font, head_fill
            c.alignment = Alignment(vertical="center")
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.row_dimensions[1].height = 22
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.border = Border(bottom=thin)
            if status_col is not None:
                v = row[status_col].value
                if v in fills:
                    row[status_col].fill = PatternFill("solid", fgColor=fills[v])

    # Summary
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Ernakulam Yuvajana Sakhyam Kalamela 2026 - Attendance Report"
    ws["A1"].font = Font(bold=True, size=14, color=red)
    ws["A2"] = "Exported " + now_iso()
    per_person = {}
    att_rows = []
    for ev in evs:
        st = est.get(ev["id"], {}).get("s", "upcoming")
        for en in ev["entries"]:
            k = en.get("chest") or en.get("team")
            s = status(ev, k)
            a = att.get(ev["id"] + "--" + k, {})
            for c in (en.get("members") or [en["chest"]]):
                p = PEOPLE.get(c, {})
                per_person.setdefault(c, []).append(s)
                att_rows.append([ev["title"], "Group 1" if en.get("cat") == "G1" else "Group 2" if en.get("cat") == "G2" else "",
                                 f'{ev["venue"]} - {VENUE_NAME.get(ev["venue"], "")}', fmt_min(en["time"]),
                                 en.get("team", ""), c, p.get("name", ""), p.get("parish", ""), p.get("phone", ""),
                                 label[s], {"upcoming": "Upcoming", "live": "Live", "done": "Closed"}[st],
                                 a.get("by", ""), a.get("at", "")])
    total_entries = len(att_rows)
    cnt = lambda s: sum(1 for r in att_rows if r[9] == s)
    summary = [
        ("Participants", len(PEOPLE)),
        ("Participants reported at least once", sum(1 for v in per_person.values() if any(s in ("present", "done") for s in v))),
        ("Events", len(evs)),
        ("Events closed", sum(1 for e in evs if est.get(e["id"], {}).get("s") == "done")),
        ("Events live now", sum(1 for e in evs if est.get(e["id"], {}).get("s") == "live")),
        ("Participant entries", total_entries),
        ("Performed", cnt("Performed")),
        ("Present (not yet performed)", cnt("Present")),
        ("Absent", cnt("Absent")),
        ("Not marked yet", cnt("Not marked")),
    ]
    for i, (k, v) in enumerate(summary, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 14

    sheet(wb.create_sheet("Attendance"),
          ["Event", "Category", "Venue", "Call time", "Team", "Chest No", "Participant", "Parish", "Contact (parish secretary)",
           "Status", "Event status", "Marked by", "Marked at"],
          att_rows, [34, 10, 30, 10, 9, 10, 26, 38, 16, 12, 12, 10, 19], status_col=9)

    prow = []
    for c, p in sorted(PEOPLE.items()):
        v = per_person.get(c, [])
        prow.append([c, p["name"], p.get("gender", ""), p["parish"], p.get("secretary", ""), p.get("phone", ""), len(v),
                     v.count("done"), v.count("present"), v.count("absent"), v.count("waiting")])
    sheet(wb.create_sheet("Participants"),
          ["Chest No", "Participant", "Gender", "Parish", "Parish secretary", "Contact", "Entries", "Performed", "Present",
           "Absent", "Not marked"], prow, [10, 26, 9, 38, 22, 14, 9, 11, 9, 9, 11])

    erow = []
    for ev in evs:
        ss = [status(ev, en.get("chest") or en.get("team")) for en in ev["entries"]]
        st = est.get(ev["id"], {})
        erow.append([ev["title"], f'{ev["venue"]} - {VENUE_NAME.get(ev["venue"], "")}', fmt_min(ev["start"]), fmt_min(ev["end"]),
                     {"upcoming": "Upcoming", "live": "Live", "done": "Closed"}[st.get("s", "upcoming")], len(ss),
                     ss.count("done"), ss.count("present"), ss.count("absent"), ss.count("waiting")])
    sheet(wb.create_sheet("Events"),
          ["Event", "Venue", "Start", "End", "Status", "Entries", "Performed", "Present", "Absent", "Not marked"],
          erow, [40, 30, 10, 10, 11, 9, 11, 9, 9, 11], status_col=None)

    with LOCK:
        acts = [[r["at"], r["by"], r["action"], EVENTS.get(r["eid"], {}).get("title", r["eid"]), r["k"], r["detail"]]
                for r in CON.execute("SELECT * FROM activity ORDER BY id")]
    sheet(wb.create_sheet("Activity log"), ["Time", "By", "Action", "Event", "Chest / Team", "Detail"], acts,
          [19, 10, 16, 40, 12, 20])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- http
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    server_version = "Kalamela/1.0"

    def log_message(self, fmt, *args):
        pass

    # helpers
    def session(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        tok = c["kl_session"].value if "kl_session" in c else None
        return SESSIONS.get(tok) if tok else None

    def send_json(self, obj, code=200, headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 100_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def deny(self, msg="Please sign in again.", code=401):
        self.send_json({"error": msg}, code)

    # routes
    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p.startswith("/api/"):
            s = self.session()
            if p == "/api/me":
                return self.send_json({"user": s and {"role": s["role"], "venue": s["venue"]}})
            if not s:
                return self.deny()
            if p == "/api/bootstrap":
                return self.send_json({"venues": VENUES, "people": SEED["people"], "events": SEED["events"]})
            if p == "/api/state":
                since = int((parse_qs(u.query).get("v") or ["0"])[0] or 0)
                with LOCK:
                    v = version()
                if since == v:
                    return self.send_json({"version": v, "changed": False})
                return self.send_json({**state_snapshot(), "changed": True})
            if p == "/api/settings":
                if s["role"] != "admin":
                    return self.deny("Only the admin can do this.", 403)
                with LOCK:
                    return self.send_json({"codes": codes()})
            if p == "/api/export.xlsx":
                if s["role"] != "admin":
                    return self.deny("Only the admin can download attendance.", 403)
                data = build_workbook()
                name = "Kalamela2026_Attendance_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return self.send_json({"error": "Not found"}, 404)
        # static
        if p in ("/", ""):
            p = "/index.html"
        fp = os.path.normpath(os.path.join(STATIC, p.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            fp = os.path.join(STATIC, "index.html")
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(os.path.splitext(fp)[1], "application/octet-stream"))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        p = urlparse(self.path).path
        b = self.body()
        if p == "/api/login":
            code = str(b.get("code", "")).strip().upper()
            with LOCK:
                cs = codes()
            role = None
            if code and code == cs.get("admin", "").upper():
                role, venue = "admin", None
            else:
                venue = next((k for k, v in cs.items() if k != "admin" and v.upper() == code), None)
                role = "venue" if venue else None
            if not role:
                return self.send_json({"error": "That code does not match any venue. Check with the organiser."}, 400)
            tok = secrets.token_urlsafe(24)
            SESSIONS[tok] = {"role": role, "venue": venue, "at": time.time()}
            return self.send_json({"user": {"role": role, "venue": venue}},
                                  headers={"Set-Cookie": f"kl_session={tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age=172800"})
        s = self.session()
        if p == "/api/logout":
            c = SimpleCookie(self.headers.get("Cookie", ""))
            if "kl_session" in c:
                SESSIONS.pop(c["kl_session"].value, None)
            return self.send_json({"ok": True}, headers={"Set-Cookie": "kl_session=; Path=/; Max-Age=0"})
        if not s:
            return self.deny()
        evs = {e["id"]: e for e in merged_events()}

        if p == "/api/mark":
            eid, k, st = b.get("e"), str(b.get("k", "")), b.get("s")
            ev = evs.get(eid)
            if not ev or not any((x.get("chest") or x.get("team")) == k for x in ev["entries"]):
                return self.send_json({"error": "Unknown entry."}, 400)
            if s["role"] != "admin" and ev["venue"] != s["venue"]:
                return self.deny("This event is not at your venue.", 403)
            with LOCK:
                es = CON.execute("SELECT state FROM event_state WHERE id=?", (eid,)).fetchone()
                if es and es["state"] == "done" and s["role"] != "admin":
                    return self.send_json({"error": "This event is closed. Ask the admin to reopen it."}, 409)
                cur = CON.cursor()
                if st in STATUSES:
                    cur.execute("INSERT OR REPLACE INTO attendance(eid,k,status,at,by) VALUES(?,?,?,?,?)", (eid, k, st, now_iso(), who(s)))
                else:
                    cur.execute("DELETE FROM attendance WHERE eid=? AND k=?", (eid, k))
                log(cur, who(s), "Marked " + ({"present": "present", "done": "performed", "absent": "absent"}.get(st, "cleared")), eid, k)
                bump(cur)
                CON.commit()
            return self.send_json({"ok": True})

        if p == "/api/event-state":
            eid, st = b.get("e"), b.get("s")
            ev = evs.get(eid)
            if not ev or st not in EVENT_STATES:
                return self.send_json({"error": "Unknown event."}, 400)
            if s["role"] != "admin" and (ev["venue"] != s["venue"] or st == "upcoming"):
                return self.deny("Only the admin can do this.", 403)
            with LOCK:
                cur = CON.cursor()
                cur_state = cur.execute("SELECT state FROM event_state WHERE id=?", (eid,)).fetchone()
                if s["role"] != "admin" and cur_state and cur_state["state"] == "done":
                    return self.send_json({"error": "This event is closed. Ask the admin to reopen it."}, 409)
                if st == "upcoming":
                    cur.execute("DELETE FROM event_state WHERE id=?", (eid,))
                else:
                    cur.execute("INSERT OR REPLACE INTO event_state(id,state,at,by) VALUES(?,?,?,?)", (eid, st, now_iso(), who(s)))
                log(cur, who(s), {"live": "Started event", "done": "Closed event", "upcoming": "Reset event"}[st], eid)
                bump(cur)
                CON.commit()
            return self.send_json({"ok": True})

        if s["role"] != "admin":
            return self.deny("Only the admin can do this.", 403)

        if p == "/api/event-edit":
            eid = b.get("e")
            o = EVENTS.get(eid)
            if not o:
                return self.send_json({"error": "Unknown event."}, 400)
            venue = b.get("venue") if b.get("venue") in VENUE_NAME else None
            start, end = b.get("start"), b.get("end")
            vals = (venue if venue and venue != o["venue"] else None,
                    int(start) if isinstance(start, (int, float)) and int(start) != o["start"] else None,
                    int(end) if isinstance(end, (int, float)) and int(end) != o["end"] else None)
            with LOCK:
                cur = CON.cursor()
                if any(v is not None for v in vals):
                    cur.execute('INSERT OR REPLACE INTO event_override(id,venue,start,"end") VALUES(?,?,?,?)', (eid, *vals))
                else:
                    cur.execute("DELETE FROM event_override WHERE id=?", (eid,))
                log(cur, who(s), "Edited event", eid, "", json.dumps({"venue": venue, "start": start, "end": end}))
                bump(cur)
                CON.commit()
            return self.send_json({"ok": True})

        if p == "/api/settings":
            new = b.get("codes") or {}
            vals = {k: str(new.get(k, "")).strip().upper() for k in ("admin", *DEFAULT_CODES)}
            if any(len(v) < 4 for v in vals.values()):
                return self.send_json({"error": "Each code needs at least 4 characters."}, 400)
            if len(set(vals.values())) != len(vals):
                return self.send_json({"error": "Every code must be different."}, 400)
            with LOCK:
                cur = CON.cursor()
                for k, v in vals.items():
                    cur.execute("INSERT OR REPLACE INTO config(key,value) VALUES(?,?)", ("code_" + k, v))
                log(cur, who(s), "Changed sign-in codes")
                CON.commit()
            # sign out everyone else so old codes stop working
            mine = SimpleCookie(self.headers.get("Cookie", ""))["kl_session"].value
            for t in list(SESSIONS):
                if t != mine:
                    SESSIONS.pop(t, None)
            return self.send_json({"ok": True})

        if p == "/api/reset":
            with LOCK:
                cur = CON.cursor()
                cur.execute("DELETE FROM attendance")
                cur.execute("DELETE FROM event_state")
                log(cur, who(s), "Reset all attendance")
                bump(cur)
                CON.commit()
            return self.send_json({"ok": True})

        if p == "/api/sample":
            import random
            rnd = random.Random(11)
            now_m = int(b.get("now", 11 * 60 + 47))
            all_evs = merged_events()
            with LOCK:
                cur = CON.cursor()
                cur.execute("DELETE FROM attendance")
                cur.execute("DELETE FROM event_state")
                for ev in all_evs:
                    if ev["end"] <= now_m:
                        cur.execute("INSERT INTO event_state VALUES(?,?,?,?)", (ev["id"], "done", now_iso(), "sample"))
                        for en in ev["entries"]:
                            if rnd.random() < 0.9:
                                cur.execute("INSERT INTO attendance VALUES(?,?,?,?,?)", (ev["id"], en.get("chest") or en.get("team"), "done", now_iso(), "sample"))
                    elif ev["start"] <= now_m:
                        cur.execute("INSERT INTO event_state VALUES(?,?,?,?)", (ev["id"], "live", now_iso(), "sample"))
                        for en in ev["entries"]:
                            k = en.get("chest") or en.get("team")
                            if ev["type"] == "offstage":
                                st = "present" if rnd.random() < 0.85 else None
                            elif en["time"] < now_m - 6:
                                st = "done" if rnd.random() < 0.85 else None
                            elif en["time"] <= now_m + 4:
                                st = "present" if rnd.random() < 0.7 else None
                            else:
                                st = None
                            if st:
                                cur.execute("INSERT INTO attendance VALUES(?,?,?,?,?)", (ev["id"], k, st, now_iso(), "sample"))
                log(cur, who(s), "Loaded practice data")
                bump(cur)
                CON.commit()
            return self.send_json({"ok": True})

        return self.send_json({"error": "Not found"}, 404)


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    init_db()
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer.request_queue_size = 64
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("\n  Kalamela 2026 attendance tracker is running.\n")
    print(f"  On this laptop:      http://localhost:{a.port}")
    for ip in lan_ips():
        print(f"  Phones / tablets:    http://{ip}:{a.port}   (same Wi-Fi)")
    c = codes()
    print("\n  Sign-in codes:  admin " + c["admin"] + " | " + " | ".join(f"{k} {c[k]}" for k in ("V1", "V2", "V3", "V4")))
    print("  Keep this window open. Press Ctrl+C to stop.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
