"""Kalamela 2026 attendance tracker - shared backend.

Used by two entry points:
  * api/index.py  - Vercel serverless function (Postgres via DATABASE_URL)
  * server.py     - local laptop server (SQLite file, no internet needed)

Storage: Postgres when DATABASE_URL / POSTGRES_URL is set, otherwise SQLite.
Sessions: HMAC-signed cookies, so any serverless instance can verify them.
"""
import base64, hashlib, hmac, io, json, os, secrets, sqlite3, threading, time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

LIB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(LIB))
PUBLIC = os.path.join(ROOT, "public")
def _find_pg_url():
    """Neon/Vercel name the variable differently depending on how it was connected."""
    for name in ("DATABASE_URL", "POSTGRES_URL", "NEON_DATABASE_URL", "POSTGRES_PRISMA_URL", "DATABASE_URL_UNPOOLED", "POSTGRES_URL_NON_POOLING"):
        v = os.environ.get(name, "").strip()
        if v.startswith(("postgres://", "postgresql://")):
            return name, v
    for name, v in sorted(os.environ.items()):  # e.g. STORAGE_DATABASE_URL from a custom prefix
        v = v.strip()
        if (name.endswith("DATABASE_URL") or name.endswith("POSTGRES_URL")) and v.startswith(("postgres://", "postgresql://")):
            return name, v
    for name, v in sorted(os.environ.items()):  # last resort: any postgres link, preferring pooled ones
        v = v.strip()
        if v.startswith(("postgres://", "postgresql://")) and "UNPOOLED" not in name and "NON_POOLING" not in name:
            return name, v
    return "", ""


PG_ENV, PG_URL = _find_pg_url()
ON_VERCEL = bool(os.environ.get("VERCEL"))
SQLITE_PATH = os.environ.get("KALAMELA_DB", os.path.join(ROOT, "kalamela.db"))
IST = timezone(timedelta(hours=5, minutes=30))  # event times are India time

VENUE_DEFAULT_CODES = {"V1": "CHURCH1", "V2": "BALCONY2", "V3": "VESTRY3", "V4": "FHALL4", "V5": "GROUND5"}
STATUSES = {"present", "done", "absent"}
EVENT_STATES = {"upcoming", "live", "done"}
SESSION_HOURS = 48

# ------------------------------------------------------------------ seed data
with open(os.path.join(LIB, "data.json"), encoding="utf-8") as f:
    SEED = json.load(f)
for _e in SEED["events"]:
    _e["venue"] = _e["venue"].replace("Venue ", "V")
VENUES = [{"code": v["code"], "name": v["name"]} for v in SEED["venues"]]
VENUE_NAME = {v["code"]: v["name"] for v in VENUES}
PEOPLE = {p["chest"]: p for p in SEED["people"]}
EVENTS = {e["id"]: e for e in SEED["events"]}
BOOT_JSON = json.dumps({"venues": VENUES, "people": SEED["people"], "events": SEED["events"]}, ensure_ascii=False).encode("utf-8")


def now_iso():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def env_admin_code():
    c = os.environ.get("KALAMELA_ADMIN_CODE", "").strip().upper()
    return c if len(c) >= 4 else ""


# ------------------------------------------------------------------ database
class SetupError(Exception):
    pass


def explain(err):
    """A readable reason for a database failure, with anything secret removed."""
    import re
    if isinstance(err, SetupError):
        return str(err)
    msg = f"{type(err).__name__}: {err}"
    msg = re.sub(r"postgres(ql)?://\S+", "postgres://…", msg)
    if PG_URL:
        u = urlparse(PG_URL)
        for secret in (u.password, unquote(u.password or "")):
            if secret:
                msg = msg.replace(secret, "…")
    return msg[:400]


class Store:
    """Tiny wrapper so the same SQL runs on SQLite and Postgres ('?' params)."""

    def __init__(self):
        self.pg = bool(PG_URL)
        self.lock = threading.Lock()
        self.conn = None
        self.ready = False

    def _connect(self):
        if not self.pg and ON_VERCEL:
            raise SetupError("No database is connected. In Vercel open Storage, connect a Neon database to this project "
                             "(Production), then Redeploy.")
        if self.pg:
            import ssl
            import pg8000.dbapi
            u = urlparse(PG_URL)
            q = parse_qs(u.query)
            ctx = None
            if (q.get("sslmode") or ["require"])[0] != "disable":
                try:
                    import certifi
                    ctx = ssl.create_default_context(cafile=certifi.where())
                except ImportError:
                    ctx = ssl.create_default_context()
            return pg8000.dbapi.connect(user=unquote(u.username or ""), password=unquote(u.password or ""),
                                        host=u.hostname, port=u.port or 5432, database=(u.path or "/postgres")[1:],
                                        ssl_context=ctx, timeout=15)
        c = sqlite3.connect(SQLITE_PATH, check_same_thread=False, timeout=15)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    @contextmanager
    def tx(self):
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.conn is None:
                        self.conn = self._connect()
                    t = Tx(self.conn, self.pg)
                    if not self.ready:
                        t.init_schema()
                        self.conn.commit()
                        self.ready = True
                    break
                except Exception:
                    self.close()
                    if attempt == 2:
                        raise
            try:
                yield t
                self.conn.commit()
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    self.close()
                raise

    def close(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:
            pass
        self.conn = None


class Tx:
    def __init__(self, conn, pg):
        self.cur = conn.cursor()
        self.pg = pg

    def run(self, sql, params=()):
        if self.pg:
            sql = sql.replace("?", "%s")
        self.cur.execute(sql, tuple(params))
        return self

    def all(self, sql, params=()):
        self.run(sql, params)
        cols = [d[0] for d in self.cur.description]
        return [dict(zip(cols, r)) for r in self.cur.fetchall()]

    def one(self, sql, params=()):
        r = self.all(sql, params)
        return r[0] if r else None

    def init_schema(self):
        serial = "SERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for s in (
            "CREATE TABLE IF NOT EXISTS kl_config(name TEXT PRIMARY KEY, val TEXT)",
            "CREATE TABLE IF NOT EXISTS kl_event_override(id TEXT PRIMARY KEY, venue TEXT, start_m INTEGER, end_m INTEGER)",
            "CREATE TABLE IF NOT EXISTS kl_event_state(id TEXT PRIMARY KEY, state TEXT, ts TEXT, actor TEXT)",
            "CREATE TABLE IF NOT EXISTS kl_attendance(eid TEXT, k TEXT, status TEXT, ts TEXT, actor TEXT, PRIMARY KEY(eid, k))",
            f"CREATE TABLE IF NOT EXISTS kl_activity(id {serial}, ts TEXT, actor TEXT, action TEXT, eid TEXT, k TEXT, detail TEXT)",
            "CREATE TABLE IF NOT EXISTS kl_venue(code TEXT PRIMARY KEY, name TEXT, pos INTEGER)",
        ):
            self.run(s)
        for i, v in enumerate(VENUES):  # the confirmed venues; the admin can add more
            self.run("INSERT INTO kl_venue(code,name,pos) VALUES(?,?,?) ON CONFLICT(code) DO NOTHING", (v["code"], v["name"], i + 1))
        defaults = {"version": "1", "codes_version": "1", "secret": secrets.token_hex(32)}
        for k, v in VENUE_DEFAULT_CODES.items():
            defaults["code_" + k] = v
        if env_admin_code():
            defaults["code_admin"] = env_admin_code()
        elif not PG_URL:
            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            defaults["code_admin"] = "ADM-" + "".join(secrets.choice(alphabet) for _ in range(6))
        for k, v in defaults.items():
            self.run("INSERT INTO kl_config(name,val) VALUES(?,?) ON CONFLICT(name) DO NOTHING", (k, v))

    # helpers
    def config(self):
        return {r["name"]: r["val"] for r in self.all("SELECT name,val FROM kl_config")}

    def set_config(self, k, v):
        self.run("INSERT INTO kl_config(name,val) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET val=excluded.val", (k, str(v)))

    def bump(self):
        self.run("UPDATE kl_config SET val = CAST(CAST(val AS INTEGER) + 1 AS TEXT) WHERE name='version'")

    def log(self, actor, action, eid="", k="", detail=""):
        self.run("INSERT INTO kl_activity(ts,actor,action,eid,k,detail) VALUES(?,?,?,?,?,?)", (now_iso(), actor, action, eid, k, detail))

    def overrides(self):
        out = {}
        for r in self.all("SELECT id,venue,start_m,end_m FROM kl_event_override"):
            o = {}
            if r["venue"] is not None: o["venue"] = r["venue"]
            if r["start_m"] is not None: o["start"] = int(r["start_m"])
            if r["end_m"] is not None: o["end"] = int(r["end_m"])
            out[r["id"]] = o
        return out

    def venues(self):
        return [{"code": r["code"], "name": r["name"]} for r in self.all("SELECT code,name,pos FROM kl_venue ORDER BY pos, code")]

    def snapshot(self, version):
        return {
            "version": version,
            "venues": self.venues(),
            "evo": self.overrides(),
            "est": {r["id"]: {"s": r["state"], "at": r["ts"], "by": r["actor"]} for r in self.all("SELECT * FROM kl_event_state")},
            "att": {r["eid"] + "--" + r["k"]: {"s": r["status"], "at": r["ts"], "by": r["actor"]} for r in self.all("SELECT * FROM kl_attendance")},
        }


STORE = Store()
_SNAP = {"v": None, "data": None}


def codes_of(cfg):
    c = {k[5:]: v for k, v in cfg.items() if k.startswith("code_")}
    c.setdefault("admin", "")
    return c


def merged_events(evo):
    out = []
    for e in SEED["events"]:
        o = evo.get(e["id"], {})
        start, end = o.get("start", e["start"]), o.get("end", e["end"])
        d = start - e["start"]
        out.append({**e, "venue": o.get("venue", e["venue"]), "start": start, "end": end,
                    "entries": [{**x, "time": x["time"] + d} for x in e["entries"]]})
    out.sort(key=lambda e: (e["start"], e["venue"]))
    return out


def check_session(t, cfg, token):
    """Signed cookie plus: a venue volunteer is signed out if their venue was removed."""
    s = read_session(cfg, token)
    if s and s["role"] == "venue" and s["venue"] not in {v["code"] for v in t.venues()}:
        return None
    return s


def next_venue_code(venues):
    nums = [int(v["code"][1:]) for v in venues if v["code"][1:].isdigit()]
    return "V" + str(max(nums + [0]) + 1)


def validate_codes(passes, names):
    if any(not n for n in names.values()):
        return "Every venue needs a name."
    if any(len(v) < 4 for v in passes.values()):
        return "Each code needs at least 4 characters."
    if any(not all(ch.isalnum() or ch in "-_" for ch in v) for v in passes.values()):
        return "Codes can use only letters, numbers, - and _."
    if len(set(passes.values())) != len(passes):
        return "Every code must be different."
    if len({n.lower() for n in names.values()}) != len(names):
        return "Two venues have the same name."
    return ""


def actor(sess):
    return "Admin" if sess["role"] == "admin" else sess["venue"]


# ------------------------------------------------------------------ sessions
def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_session(cfg, role, venue):
    body = _b64(json.dumps({"r": role, "v": venue, "cv": cfg.get("codes_version", "1"), "exp": int(time.time()) + SESSION_HOURS * 3600}).encode())
    sig = _b64(hmac.new(cfg["secret"].encode(), body.encode(), hashlib.sha256).digest())
    return body + "." + sig


def read_session(cfg, token):
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(cfg["secret"].encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        d = json.loads(_unb64(body))
        if d["exp"] < time.time() or d.get("cv") != cfg.get("codes_version", "1"):
            return None
        return {"role": d["r"], "venue": d["v"]}
    except Exception:
        return None


# ------------------------------------------------------------------ excel
def fmt_min(m):
    h, mm = divmod(int(m), 60)
    ap = "PM" if h >= 12 else "AM"
    return f"{h % 12 or 12}:{mm:02d} {ap}"


def build_workbook(snap, acts, VENUE_NAME):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    evs = merged_events(snap["evo"])
    est, att = snap["est"], snap["att"]
    label = {"present": "Present", "done": "Performed", "absent": "Absent", "waiting": "Not marked"}
    st_label = {"upcoming": "Upcoming", "live": "Live", "done": "Closed"}

    def status(ev, k):
        a = att.get(ev["id"] + "--" + k, {}).get("s")
        if est.get(ev["id"], {}).get("s") == "done":
            return "done" if a in ("present", "done") else "absent"
        return a or "waiting"

    wb = Workbook()
    red = "C8102E"
    thin = Side(style="thin", color="D9DDE3")
    fills = {"Performed": "DCEBFF", "Present": "DDF3E4", "Absent": "FBE0E3", "Not marked": "F2F3F5"}

    def sheet(ws, headers, rows, widths, status_col=None):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=red)
            c.alignment = Alignment(vertical="center")
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.border = Border(bottom=thin)
            if status_col is not None and row[status_col].value in fills:
                row[status_col].fill = PatternFill("solid", fgColor=fills[row[status_col].value])

    per_person, att_rows = {}, []
    for ev in evs:
        st = est.get(ev["id"], {}).get("s", "upcoming")
        for en in ev["entries"]:
            k = en.get("chest") or en.get("team")
            s = status(ev, k)
            a = att.get(ev["id"] + "--" + k, {})
            for c in (en.get("members") or [en["chest"]]):
                p = PEOPLE.get(c, {})
                per_person.setdefault(c, []).append(s)
                att_rows.append([ev["title"], {"G1": "Group 1", "G2": "Group 2"}.get(en.get("cat"), ""),
                                 f'{ev["venue"]} - {VENUE_NAME.get(ev["venue"], "")}', fmt_min(en["time"]), en.get("team", ""), c,
                                 p.get("name", ""), p.get("parish", ""), p.get("phone", ""), label[s], st_label[st], a.get("by", ""), a.get("at", "")])

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Ernakulam Yuvajana Sakhyam Kalamela 2026 - Attendance Report"
    ws["A1"].font = Font(bold=True, size=14, color=red)
    ws["A2"] = "Exported " + now_iso() + " (IST)"
    cnt = lambda s: sum(1 for r in att_rows if r[9] == s)
    summary = [("Participants", len(PEOPLE)),
               ("Participants reported at least once", sum(1 for v in per_person.values() if any(s in ("present", "done") for s in v))),
               ("Events", len(evs)), ("Events closed", sum(1 for e in evs if est.get(e["id"], {}).get("s") == "done")),
               ("Events live now", sum(1 for e in evs if est.get(e["id"], {}).get("s") == "live")),
               ("Participant entries", len(att_rows)), ("Performed", cnt("Performed")), ("Present (not yet performed)", cnt("Present")),
               ("Absent", cnt("Absent")), ("Not marked yet", cnt("Not marked"))]
    for i, (k, v) in enumerate(summary, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 38, 14

    sheet(wb.create_sheet("Attendance"),
          ["Event", "Category", "Venue", "Call time", "Team", "Chest No", "Participant", "Parish", "Contact (parish secretary)",
           "Status", "Event status", "Marked by", "Marked at"], att_rows, [34, 10, 30, 10, 9, 10, 26, 38, 16, 12, 12, 10, 19], status_col=9)
    sheet(wb.create_sheet("Participants"),
          ["Chest No", "Participant", "Gender", "Parish", "Parish secretary", "Contact", "Entries", "Performed", "Present", "Absent", "Not marked"],
          [[c, p["name"], p.get("gender", ""), p["parish"], p.get("secretary", ""), p.get("phone", ""), len(v := per_person.get(c, [])),
            v.count("done"), v.count("present"), v.count("absent"), v.count("waiting")] for c, p in sorted(PEOPLE.items())],
          [10, 26, 9, 38, 22, 14, 9, 11, 9, 9, 11])
    erow = []
    for ev in evs:
        ss = [status(ev, en.get("chest") or en.get("team")) for en in ev["entries"]]
        erow.append([ev["title"], f'{ev["venue"]} - {VENUE_NAME.get(ev["venue"], "")}', fmt_min(ev["start"]), fmt_min(ev["end"]),
                     st_label[est.get(ev["id"], {}).get("s", "upcoming")], len(ss), ss.count("done"), ss.count("present"), ss.count("absent"), ss.count("waiting")])
    sheet(wb.create_sheet("Events"), ["Event", "Venue", "Start", "End", "Status", "Entries", "Performed", "Present", "Absent", "Not marked"],
          erow, [40, 30, 10, 10, 11, 9, 11, 9, 9, 11])
    sheet(wb.create_sheet("Activity log"), ["Time (IST)", "By", "Action", "Event", "Chest / Team", "Detail"],
          [[a["ts"], a["actor"], a["action"], EVENTS.get(a["eid"], {}).get("title", a["eid"]), a["k"], a["detail"]] for a in acts],
          [19, 10, 16, 40, 12, 20])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ HTTP handler
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    server_version = "Kalamela/2.0"
    serve_static = False  # local server turns this on; Vercel serves /public itself

    def log_message(self, fmt, *args):
        pass

    # ---- helpers
    def token(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return c["kl_session"].value if "kl_session" in c else ""

    def secure(self):
        return self.headers.get("X-Forwarded-Proto", "") == "https"

    def cookie(self, value, max_age):
        return f"kl_session={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}" + ("; Secure" if self.secure() else "")

    def send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code=200, headers=None):
        self.send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), headers=headers)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 100_000:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except Exception:
            return {}

    def route(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        if p == "/api/index":  # Vercel may pass the rewritten path; original is in the query
            p = "/api/" + (parse_qs(u.query).get("path") or [""])[0]
        return p, parse_qs(u.query)

    def fail(self, err):
        import sys, traceback
        traceback.print_exc(file=sys.stderr)  # shows in Vercel → Logs
        self.json({"error": "Database problem: " + explain(err)}, 503)

    def health(self):
        info = {"database": "postgres" if PG_URL else "sqlite", "database_env": PG_ENV or None, "on_vercel": ON_VERCEL,
                "admin_code_env_set": bool(env_admin_code())}
        if PG_URL:
            u = urlparse(PG_URL)
            info["database_host"] = u.hostname
        try:
            t0 = time.time()
            with STORE.tx() as t:
                cfg = t.config()
            info.update(ok=True, ms=int((time.time() - t0) * 1000), admin_code_set=bool(codes_of(cfg)["admin"] or env_admin_code()))
            return self.json(info)
        except Exception as e:
            import sys, traceback
            traceback.print_exc(file=sys.stderr)
            info.update(ok=False, error=explain(e))
            return self.json(info, 503)

    # ---- GET
    def do_GET(self):
        p, q = self.route()
        if not p.startswith("/api/"):
            return self.static(p)
        if p == "/api/health":
            return self.health()
        try:
            with STORE.tx() as t:
                cfg = t.config()
                s = check_session(t, cfg, self.token())
                if p == "/api/me":
                    return self.json({"user": s, "setup": bool(codes_of(cfg)["admin"] or env_admin_code())})
                if not s:
                    return self.json({"error": "Please sign in again."}, 401)
                if p == "/api/bootstrap":
                    return self.send(200, BOOT_JSON)
                if p == "/api/state":
                    v = int(cfg.get("version", "1"))
                    if int((q.get("v") or ["0"])[0] or 0) == v:
                        return self.json({"version": v, "changed": False})
                    if _SNAP["v"] != v:
                        _SNAP["v"], _SNAP["data"] = v, t.snapshot(v)
                    return self.json({**_SNAP["data"], "changed": True})
                if s["role"] != "admin":
                    return self.json({"error": "Only the admin can do this."}, 403)
                if p == "/api/settings":
                    c = codes_of(cfg)
                    used = {}
                    for e in merged_events(t.overrides()):
                        used[e["venue"]] = used.get(e["venue"], 0) + 1
                    return self.json({"admin": c["admin"] or env_admin_code(),
                                      "venues": [{**v, "pass": c.get(v["code"], ""), "events": used.get(v["code"], 0)} for v in t.venues()]})
                if p == "/api/export.xlsx":
                    snap = t.snapshot(int(cfg.get("version", "1")))
                    vnames = {v["code"]: v["name"] for v in snap["venues"]}
                    acts = t.all("SELECT ts,actor,action,eid,k,detail FROM kl_activity ORDER BY id")
                else:
                    return self.json({"error": "Not found"}, 404)
            data = build_workbook(snap, acts, vnames)
            name = "Kalamela2026_Attendance_" + datetime.now(IST).strftime("%Y%m%d_%H%M") + ".xlsx"
            return self.send(200, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             {"Content-Disposition": f'attachment; filename="{name}"'})
        except Exception as e:
            return self.fail(e)

    def static(self, p):
        if not self.serve_static:
            return self.json({"error": "Not found"}, 404)
        if p == "/":
            p = "/index.html"
        fp = os.path.normpath(os.path.join(PUBLIC, p.lstrip("/")))
        if not fp.startswith(PUBLIC) or not os.path.isfile(fp):
            fp = os.path.join(PUBLIC, "index.html")
        with open(fp, "rb") as f:
            data = f.read()
        self.send(200, data, MIME.get(os.path.splitext(fp)[1], "application/octet-stream"), {"Cache-Control": "no-cache"})

    # ---- POST
    def do_POST(self):
        p, _ = self.route()
        b = self.body()
        try:
            with STORE.tx() as t:
                cfg = t.config()
                if p == "/api/login":
                    return self.login(t, cfg, b)
                if p == "/api/logout":
                    return self.json({"ok": True}, headers={"Set-Cookie": self.cookie("", 0)})
                s = check_session(t, cfg, self.token())
                if not s:
                    return self.json({"error": "Please sign in again."}, 401)
                return self.action(t, cfg, s, p, b)
        except Exception as e:
            return self.fail(e)

    def login(self, t, cfg, b):
        code = str(b.get("code", "")).strip().upper()
        cs = codes_of(cfg)
        live_venues = {v["code"] for v in t.venues()}
        admin_codes = {c for c in (cs["admin"].upper(), env_admin_code()) if c}
        if not admin_codes and not code:
            return self.json({"error": "No admin code is set. Add KALAMELA_ADMIN_CODE in the hosting settings."}, 400)
        role = venue = None
        if code and code in admin_codes:
            role = "admin"
        else:
            venue = next((k for k, v in cs.items() if k in live_venues and v.upper() == code), None) if code else None
            role = "venue" if venue else None
        if not role:
            time.sleep(0.4)
            msg = "That code does not match any venue. Check with the organiser."
            if not admin_codes:
                msg += " (Admin: set KALAMELA_ADMIN_CODE in the hosting settings.)"
            return self.json({"error": msg}, 400)
        tok = sign_session(cfg, role, venue)
        return self.json({"user": {"role": role, "venue": venue}}, headers={"Set-Cookie": self.cookie(tok, SESSION_HOURS * 3600)})

    def action(self, t, cfg, s, p, b):
        evs = {e["id"]: e for e in merged_events(t.overrides())}
        who = actor(s)

        if p == "/api/mark":
            eid, k, st = b.get("e"), str(b.get("k", "")), b.get("s")
            ev = evs.get(eid)
            if not ev or not any((x.get("chest") or x.get("team")) == k for x in ev["entries"]):
                return self.json({"error": "Unknown entry."}, 400)
            if s["role"] != "admin" and ev["venue"] != s["venue"]:
                return self.json({"error": "This event is not at your venue."}, 403)
            es = t.one("SELECT state FROM kl_event_state WHERE id=?", (eid,))
            if es and es["state"] == "done" and s["role"] != "admin":
                return self.json({"error": "This event is closed. Ask the admin to reopen it."}, 409)
            if st in STATUSES:
                t.run("INSERT INTO kl_attendance(eid,k,status,ts,actor) VALUES(?,?,?,?,?) ON CONFLICT(eid,k) DO UPDATE SET "
                      "status=excluded.status, ts=excluded.ts, actor=excluded.actor", (eid, k, st, now_iso(), who))
            else:
                t.run("DELETE FROM kl_attendance WHERE eid=? AND k=?", (eid, k))
            t.log(who, "Marked " + {"present": "present", "done": "performed", "absent": "absent"}.get(st, "cleared"), eid, k)
            t.bump()
            return self.json({"ok": True})

        if p == "/api/event-state":
            eid, st = b.get("e"), b.get("s")
            ev = evs.get(eid)
            if not ev or st not in EVENT_STATES:
                return self.json({"error": "Unknown event."}, 400)
            if s["role"] != "admin" and (ev["venue"] != s["venue"] or st == "upcoming"):
                return self.json({"error": "Only the admin can do this."}, 403)
            cur = t.one("SELECT state FROM kl_event_state WHERE id=?", (eid,))
            if s["role"] != "admin" and cur and cur["state"] == "done":
                return self.json({"error": "This event is closed. Ask the admin to reopen it."}, 409)
            if st == "upcoming":
                t.run("DELETE FROM kl_event_state WHERE id=?", (eid,))
            else:
                t.run("INSERT INTO kl_event_state(id,state,ts,actor) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                      "state=excluded.state, ts=excluded.ts, actor=excluded.actor", (eid, st, now_iso(), who))
            t.log(who, {"live": "Started event", "done": "Closed event", "upcoming": "Reset event"}[st], eid)
            t.bump()
            return self.json({"ok": True})

        if s["role"] != "admin":
            return self.json({"error": "Only the admin can do this."}, 403)

        if p == "/api/event-edit":
            eid = b.get("e")
            o = EVENTS.get(eid)
            if not o:
                return self.json({"error": "Unknown event."}, 400)
            venue = b.get("venue") if b.get("venue") in {v["code"] for v in t.venues()} else None
            start, end = b.get("start"), b.get("end")
            vals = (venue if venue and venue != o["venue"] else None,
                    int(start) if isinstance(start, (int, float)) and int(start) != o["start"] else None,
                    int(end) if isinstance(end, (int, float)) and int(end) != o["end"] else None)
            if any(v is not None for v in vals):
                t.run("INSERT INTO kl_event_override(id,venue,start_m,end_m) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                      "venue=excluded.venue, start_m=excluded.start_m, end_m=excluded.end_m", (eid, *vals))
            else:
                t.run("DELETE FROM kl_event_override WHERE id=?", (eid,))
            t.log(who, "Edited event", eid, "", json.dumps({"venue": venue, "start": start, "end": end}))
            t.bump()
            return self.json({"ok": True})

        if p == "/api/settings":
            venues = t.venues()
            codes = codes_of(cfg)
            given = {str(v.get("code")): v for v in (b.get("venues") or []) if isinstance(v, dict)}
            admin = str(b.get("admin", codes["admin"])).strip().upper()
            names, passes = {}, {"admin": admin}
            for v in venues:
                g = given.get(v["code"], {})
                names[v["code"]] = str(g.get("name", v["name"])).strip()[:60]
                passes[v["code"]] = str(g.get("pass", codes.get(v["code"], ""))).strip().upper()
            err = validate_codes(passes, names)
            if err:
                return self.json({"error": err}, 400)
            changed = any(passes[k] != codes.get(k, "") for k in passes)
            for v in venues:
                if names[v["code"]] != v["name"]:
                    t.run("UPDATE kl_venue SET name=? WHERE code=?", (names[v["code"]], v["code"]))
            for k, v in passes.items():
                t.set_config("code_" + k, v)
            if changed:
                t.set_config("codes_version", int(cfg.get("codes_version", "1")) + 1)  # signs out every other device
            t.log(who, "Saved venues and codes" + (" (codes changed)" if changed else ""))
            t.bump()
            cfg = t.config()
            return self.json({"ok": True, "signedOut": changed},
                             headers={"Set-Cookie": self.cookie(sign_session(cfg, "admin", None), SESSION_HOURS * 3600)})

        if p == "/api/venue-add":
            venues = t.venues()
            codes = codes_of(cfg)
            name = str(b.get("name", "")).strip()[:60]
            pw = str(b.get("pass", "")).strip().upper()
            code = next_venue_code(venues)
            passes = {k: codes.get(k, "") for k in ["admin"] + [v["code"] for v in venues]}
            passes[code] = pw
            names = {v["code"]: v["name"] for v in venues}
            names[code] = name
            err = validate_codes(passes, names)
            if err:
                return self.json({"error": err}, 400)
            t.run("INSERT INTO kl_venue(code,name,pos) VALUES(?,?,?)", (code, name, len(venues) + 1))
            t.set_config("code_" + code, pw)
            t.log(who, "Added venue", "", code, name)
            t.bump()
            return self.json({"ok": True, "code": code})

        if p == "/api/venue-delete":
            code = str(b.get("code", ""))
            venues = t.venues()
            if code not in {v["code"] for v in venues}:
                return self.json({"error": "Unknown venue."}, 400)
            if len(venues) <= 1:
                return self.json({"error": "At least one venue is needed."}, 400)
            n = sum(1 for e in evs.values() if e["venue"] == code)
            if n:
                return self.json({"error": f"Move its {n} event(s) to another venue first, on the Events & schedule page."}, 409)
            t.run("DELETE FROM kl_venue WHERE code=?", (code,))
            t.run("DELETE FROM kl_config WHERE name=?", ("code_" + code,))
            t.log(who, "Removed venue", "", code)
            t.bump()
            return self.json({"ok": True})

        if p == "/api/reset":
            t.run("DELETE FROM kl_attendance")
            t.run("DELETE FROM kl_event_state")
            t.log(who, "Reset all attendance")
            t.bump()
            return self.json({"ok": True})

        if p == "/api/sample":
            import random
            rnd = random.Random(11)
            now_m = int(b.get("now", 11 * 60 + 47))
            ts = now_iso()
            t.run("DELETE FROM kl_attendance")
            t.run("DELETE FROM kl_event_state")
            att, est = [], []
            for ev in merged_events(t.overrides()):
                if ev["end"] <= now_m:
                    est.append((ev["id"], "done"))
                    att += [(ev["id"], en.get("chest") or en.get("team"), "done") for en in ev["entries"] if rnd.random() < 0.9]
                elif ev["start"] <= now_m:
                    est.append((ev["id"], "live"))
                    for en in ev["entries"]:
                        k = en.get("chest") or en.get("team")
                        if ev["type"] == "offstage":
                            stt = "present" if rnd.random() < 0.85 else None
                        elif en["time"] < now_m - 6:
                            stt = "done" if rnd.random() < 0.85 else None
                        elif en["time"] <= now_m + 4:
                            stt = "present" if rnd.random() < 0.7 else None
                        else:
                            stt = None
                        if stt:
                            att.append((ev["id"], k, stt))
            ph = "%s" if t.pg else "?"
            if est:
                t.cur.executemany(f"INSERT INTO kl_event_state(id,state,ts,actor) VALUES({ph},{ph},{ph},{ph})",
                                  [(i, s_, ts, "practice") for i, s_ in est])
            if att:
                t.cur.executemany(f"INSERT INTO kl_attendance(eid,k,status,ts,actor) VALUES({ph},{ph},{ph},{ph},{ph})",
                                  [(e, k, s_, ts, "practice") for e, k, s_ in att])
            t.log(who, "Loaded practice data")
            t.bump()
            return self.json({"ok": True})

        return self.json({"error": "Not found"}, 404)
