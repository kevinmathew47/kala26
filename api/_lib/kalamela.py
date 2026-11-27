"""Kalamela 2026 attendance & results - shared backend.

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
    for name, v in sorted(os.environ.items()):
        v = v.strip()
        if (name.endswith("DATABASE_URL") or name.endswith("POSTGRES_URL")) and v.startswith(("postgres://", "postgresql://")):
            return name, v
    for name, v in sorted(os.environ.items()):
        v = v.strip()
        if v.startswith(("postgres://", "postgresql://")) and "UNPOOLED" not in name and "NON_POOLING" not in name:
            return name, v
    return "", ""


PG_ENV, PG_URL = _find_pg_url()
ON_VERCEL = bool(os.environ.get("VERCEL"))
SQLITE_PATH = os.environ.get("KALAMELA_DB", os.path.join(ROOT, "kalamela.db"))
IST = timezone(timedelta(hours=5, minutes=30))

VENUE_DEFAULT_CODES = {"V1": "CHURCH1", "V2": "BALCONY2", "V3": "VESTRY3", "V4": "FHALL4", "V5": "ART5"}
STATUSES = {"present", "done", "absent"}
EVENT_STATES = {"upcoming", "live", "done"}
SESSION_HOURS = 48
DEFAULT_POINTS = {"ind": [5, 3, 1], "grp": [15, 10, 5]}  # Kalamela Manual 2026, General Instructions 7
MIN_PERCENT = 50     # Manual 8: below 50% marks earns no points or prize
AWARD_MIN_POINTS = 13  # Manual 6: Kalaprathibha / Kalathilakam need at least 13 points

# ------------------------------------------------------------------ seed data
with open(os.path.join(LIB, "data.json"), encoding="utf-8") as f:
    SEED = json.load(f)
VENUES = [{"code": v["code"], "name": v["name"]} for v in SEED["venues"]]
PEOPLE = {p["chest"]: p for p in SEED["people"]}
EVENTS = {e["id"]: e for e in SEED["events"]}
BOOT_JSON = json.dumps({"people": SEED["people"], "events": SEED["events"]}, ensure_ascii=False).encode("utf-8")


def now_iso():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def now_ms():
    return int(time.time() * 1000)


def env_admin_code():
    c = os.environ.get("KALAMELA_ADMIN_CODE", "").strip().upper()
    return c if len(c) >= 4 else ""


def key_of(en):
    return en.get("chest") or en.get("team")


def members(en):
    return en.get("members") or [en["chest"]]


# ------------------------------------------------------------------ database
class SetupError(Exception):
    pass


def explain(err):
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
            "CREATE TABLE IF NOT EXISTS kl_timer(eid TEXT, k TEXT, started BIGINT, ended BIGINT, PRIMARY KEY(eid, k))",
            "CREATE TABLE IF NOT EXISTS kl_event_cfg(id TEXT PRIMARY KEY, timer REAL, timer_min REAL, judges INTEGER)",
            "CREATE TABLE IF NOT EXISTS kl_sheet(eid TEXT PRIMARY KEY, data TEXT, ts TEXT, actor TEXT)",
        ):
            self.run(s)
        for i, v in enumerate(VENUES):
            self.run("INSERT INTO kl_venue(code,name,pos) VALUES(?,?,?) ON CONFLICT(code) DO NOTHING", (v["code"], v["name"], i + 1))
        # earlier default names -> confirmed names (only if the admin hasn't renamed them)
        self.run("UPDATE kl_venue SET name=? WHERE code='V4' AND name='Fellowship Hall'", ("Fellowship Hall – Group Events",))
        self.run("UPDATE kl_venue SET name=? WHERE code='V5' AND name='Ground Floor'", ("Fellowship Hall – Art",))
        defaults = {"version": "1", "codes_version": "1", "secret": secrets.token_hex(32), "points": json.dumps(DEFAULT_POINTS)}
        for k, v in VENUE_DEFAULT_CODES.items():
            defaults["code_" + k] = v
        if env_admin_code():
            defaults["code_admin"] = env_admin_code()
        elif not PG_URL:
            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            defaults["code_admin"] = "ADM-" + "".join(secrets.choice(alphabet) for _ in range(6))
        for k, v in defaults.items():
            self.run("INSERT INTO kl_config(name,val) VALUES(?,?) ON CONFLICT(name) DO NOTHING", (k, v))
        # the old timed schedule used different event ids; drop its leftovers once
        if not self.one("SELECT val FROM kl_config WHERE name='schema'"):
            known = tuple(EVENTS)
            for tbl, col in (("kl_attendance", "eid"), ("kl_event_state", "id"), ("kl_event_override", "id")):
                for r in self.all(f"SELECT DISTINCT {col} AS x FROM {tbl}"):
                    if r["x"] not in known:
                        self.run(f"DELETE FROM {tbl} WHERE {col}=?", (r["x"],))
            self.run("INSERT INTO kl_config(name,val) VALUES('schema','2') ON CONFLICT(name) DO NOTHING")
            self.bump()
        # points follow the manual; replace the earlier 10/6/2 group default if nobody changed it
        if (self.one("SELECT val FROM kl_config WHERE name='schema'") or {}).get("val") == "2":
            cur = self.one("SELECT val FROM kl_config WHERE name='points'")
            try:
                if cur and json.loads(cur["val"]).get("grp") in ([10, 6, 2], [10.0, 6.0, 2.0]):
                    self.set_config("points", json.dumps(DEFAULT_POINTS))
            except Exception:
                pass
            self.set_config("schema", "3")
            self.bump()

    # helpers
    def config(self):
        return {r["name"]: r["val"] for r in self.all("SELECT name,val FROM kl_config")}

    def set_config(self, k, v):
        self.run("INSERT INTO kl_config(name,val) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET val=excluded.val", (k, str(v)))

    def bump(self):
        self.run("UPDATE kl_config SET val = CAST(CAST(val AS INTEGER) + 1 AS TEXT) WHERE name='version'")

    def log(self, actor, action, eid="", k="", detail=""):
        self.run("INSERT INTO kl_activity(ts,actor,action,eid,k,detail) VALUES(?,?,?,?,?,?)", (now_iso(), actor, action, eid, k, detail))

    def venues(self):
        return [{"code": r["code"], "name": r["name"]} for r in self.all("SELECT code,name,pos FROM kl_venue ORDER BY pos, code")]

    def overrides(self):
        return {r["id"]: {"venue": r["venue"]} for r in self.all("SELECT id,venue FROM kl_event_override") if r["venue"]}

    def event_cfg(self):
        out = {}
        for r in self.all("SELECT * FROM kl_event_cfg"):
            o = {}
            if r["timer"] is not None: o["timer"] = float(r["timer"])
            if r["timer_min"] is not None: o["timerMin"] = float(r["timer_min"])
            if r["judges"] is not None: o["judges"] = int(r["judges"])
            out[r["id"]] = o
        return out

    def sheets(self):
        out = {}
        for r in self.all("SELECT eid,data FROM kl_sheet"):
            try:
                out[r["eid"]] = json.loads(r["data"] or "{}")
            except Exception:
                out[r["eid"]] = {}
        return out

    def points(self, cfg=None):
        try:
            p = json.loads((cfg or self.config()).get("points") or "{}")
            return {"ind": [float(x) for x in p.get("ind", DEFAULT_POINTS["ind"])][:3], "grp": [float(x) for x in p.get("grp", DEFAULT_POINTS["grp"])][:3]}
        except Exception:
            return DEFAULT_POINTS

    def snapshot(self, version):
        return {
            "version": version,
            "venues": self.venues(),
            "evo": self.overrides(),
            "cfg": self.event_cfg(),
            "est": {r["id"]: {"s": r["state"], "at": r["ts"], "by": r["actor"]} for r in self.all("SELECT * FROM kl_event_state")},
            "att": {r["eid"] + "--" + r["k"]: {"s": r["status"], "at": r["ts"], "by": r["actor"]} for r in self.all("SELECT * FROM kl_attendance")},
            "tmr": {r["eid"] + "--" + r["k"]: {"s": int(r["started"]) if r["started"] is not None else None,
                                               "e": int(r["ended"]) if r["ended"] is not None else None} for r in self.all("SELECT * FROM kl_timer")},
            "sheets": self.sheets(),
            "points": self.points(),
        }


STORE = Store()
_SNAP = {"v": None, "data": None}


def codes_of(cfg):
    c = {k[5:]: v for k, v in cfg.items() if k.startswith("code_")}
    c.setdefault("admin", "")
    return c


def merged_events(evo, cfg=None):
    cfg = cfg or {}
    out = []
    for e in SEED["events"]:
        o, c = evo.get(e["id"], {}), cfg.get(e["id"], {})
        out.append({**e, "venue": o.get("venue", e["venue"]), "timer": c.get("timer", e["timer"]),
                    "timerMin": c.get("timerMin", e["timerMin"]), "judges": c.get("judges", e["judges"])})
    return out


# ------------------------------------------------------------------ results
def event_results(ev, sheet, judges, status_of):
    """Rows sorted by total; rank shared on ties (1,1,3). Only entries with marks are listed.
    Manual rule 8: an entry below 50% of the maximum marks gets no rank (no points, no prize)."""
    rows = []
    for en in ev["entries"]:
        k = key_of(en)
        if status_of(k) == "absent":
            continue
        marks = (sheet or {}).get(k) or []
        totals = []
        for j in range(judges):
            vals = marks[j] if j < len(marks) and isinstance(marks[j], list) else []
            nums = [float(v) for v in vals if isinstance(v, (int, float))]
            totals.append(sum(nums) if nums else None)
        if all(x is None for x in totals):
            continue
        rows.append({"k": k, "judgeTotals": totals, "total": sum(x for x in totals if x is not None)})
    maxtot = sum(c["max"] for c in ev["criteria"]) * judges
    for r in rows:
        r["pct"] = round(r["total"] / maxtot * 100, 1) if maxtot else None
        r["eligible"] = r["pct"] is None or r["pct"] >= MIN_PERCENT
    rows.sort(key=lambda r: (not r["eligible"], -r["total"]))
    prev = None
    for i, r in enumerate(rows):
        if not r["eligible"]:
            r["rank"] = None
            continue
        r["rank"] = prev["rank"] if prev and r["total"] == prev["total"] else i + 1
        prev = r
    return rows


def championship(evs, sheets, status_fn, points, venue_name):
    ind, church = {}, {}
    per_event = []
    for ev in evs:
        res = event_results(ev, sheets.get(ev["id"]), ev["judges"], lambda k, ev=ev: status_fn(ev, k))
        pts = points["grp"] if ev["type"] == "group" else points["ind"]
        winners = []
        for r in res:
            if r["rank"] is None or r["rank"] > 3:
                continue
            p = pts[r["rank"] - 1] if r["rank"] - 1 < len(pts) else 0
            en = next(x for x in ev["entries"] if key_of(x) == r["k"])
            parish = en.get("parish") or PEOPLE.get(r["k"], {}).get("parish", "")
            church[parish] = church.get(parish, 0) + p
            if ev["type"] != "group":
                d = ind.setdefault(r["k"], {"points": 0, "first": 0, "second": 0, "third": 0})
                d["points"] += p
                d[["first", "second", "third"][r["rank"] - 1]] += 1
            winners.append((r["rank"], r["k"], r["total"], p))
        per_event.append((ev, winners, len(res)))
    return per_event, ind, church


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


def check_session(t, cfg, token):
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


# ------------------------------------------------------------------ excel
def fmt_dur(ms):
    if ms is None:
        return ""
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def build_workbook(snap, acts, venue_name):
    import export
    evs = merged_events(snap["evo"], snap["cfg"])
    est, att, tmr = snap["est"], snap["att"], snap["tmr"]

    def status(ev, k):
        a = att.get(ev["id"] + "--" + k, {}).get("s")
        if est.get(ev["id"], {}).get("s") == "done":
            return "done" if a in ("present", "done") else "absent"
        return a or "waiting"

    def took(ev, k):
        tm = tmr.get(ev["id"] + "--" + k, {})
        d = (tm["e"] - tm["s"]) if tm.get("s") and tm.get("e") else None
        return fmt_dur(d), bool(d and ev["timer"] and d > ev["timer"] * 60000)

    champ = championship(evs, snap["sheets"], status, snap["points"], venue_name)
    return export.build({
        "evs": evs, "people": PEOPLE, "status": status, "took": took, "att": att, "est": est, "acts": acts,
        "results": lambda ev: event_results(ev, snap["sheets"].get(ev["id"]), ev["judges"], lambda k: status(ev, k)),
        "champ": champ, "points": snap["points"], "venue_name": venue_name, "sheets": snap["sheets"],
        "exported_at": now_iso(), "award_min": AWARD_MIN_POINTS})


# ------------------------------------------------------------------ HTTP handler
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    server_version = "Kalamela/3.0"
    serve_static = False

    def log_message(self, fmt, *args):
        pass

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
        if n <= 0 or n > 400_000:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except Exception:
            return {}

    def route(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        if p == "/api/index":
            p = "/api/" + (parse_qs(u.query).get("path") or [""])[0]
        return p, parse_qs(u.query)

    def fail(self, err):
        import sys, traceback
        traceback.print_exc(file=sys.stderr)
        self.json({"error": "Database problem: " + explain(err)}, 503)

    def health(self):
        info = {"database": "postgres" if PG_URL else "sqlite", "database_env": PG_ENV or None, "on_vercel": ON_VERCEL,
                "admin_code_env_set": bool(env_admin_code())}
        if PG_URL:
            info["database_host"] = urlparse(PG_URL).hostname
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
                    return self.json({"user": s})
                if not s:
                    return self.json({"error": "Please sign in again."}, 401)
                if p == "/api/bootstrap":
                    return self.send(200, BOOT_JSON)
                if p == "/api/state":
                    v = int(cfg.get("version", "1"))
                    if int((q.get("v") or ["0"])[0] or 0) == v:
                        return self.json({"version": v, "changed": False, "now": now_ms()})
                    if _SNAP["v"] != v:
                        _SNAP["v"], _SNAP["data"] = v, t.snapshot(v)
                    return self.json({**_SNAP["data"], "changed": True, "now": now_ms()})
                if s["role"] != "admin":
                    return self.json({"error": "Only the admin can do this."}, 403)
                if p == "/api/settings":
                    c = codes_of(cfg)
                    used = {}
                    for e in merged_events(t.overrides()):
                        used[e["venue"]] = used.get(e["venue"], 0) + 1
                    return self.json({"admin": c["admin"] or env_admin_code(), "points": t.points(cfg),
                                      "venues": [{**v, "pass": c.get(v["code"], ""), "events": used.get(v["code"], 0)} for v in t.venues()]})
                if p == "/api/export.xlsx":
                    snap = t.snapshot(int(cfg.get("version", "1")))
                    vnames = {v["code"]: v["name"] for v in snap["venues"]}
                    acts = t.all("SELECT ts,actor,action,eid,k,detail FROM kl_activity ORDER BY id")
                else:
                    return self.json({"error": "Not found"}, 404)
            data = build_workbook(snap, acts, vnames)
            name = "Kalamela2026_" + datetime.now(IST).strftime("%Y%m%d_%H%M") + ".xlsx"
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
        evs = {e["id"]: e for e in merged_events(t.overrides(), t.event_cfg())}
        who = actor(s)
        admin = s["role"] == "admin"

        def event_for_write(eid, allow_closed=False):
            ev = evs.get(eid)
            if not ev:
                return None, self.json({"error": "Unknown event."}, 400)
            if not admin and ev["venue"] != s["venue"]:
                return None, self.json({"error": "This event is not at your venue."}, 403)
            if not admin and not allow_closed:
                es = t.one("SELECT state FROM kl_event_state WHERE id=?", (eid,))
                if es and es["state"] == "done":
                    return None, self.json({"error": "This event is finished. Ask the admin to reopen it."}, 409)
            return ev, None

        def entry_ok(ev, k):
            return any(key_of(x) == k for x in ev["entries"])

        def set_status(eid, k, st):
            if st in STATUSES:
                t.run("INSERT INTO kl_attendance(eid,k,status,ts,actor) VALUES(?,?,?,?,?) ON CONFLICT(eid,k) DO UPDATE SET "
                      "status=excluded.status, ts=excluded.ts, actor=excluded.actor", (eid, k, st, now_iso(), who))
            else:
                t.run("DELETE FROM kl_attendance WHERE eid=? AND k=?", (eid, k))

        if p == "/api/mark":
            eid, k, st = b.get("e"), str(b.get("k", "")), b.get("s")
            ev, err = event_for_write(eid)
            if err:
                return err
            if not entry_ok(ev, k):
                return self.json({"error": "Unknown entry."}, 400)
            set_status(eid, k, st)
            if st not in ("present", "done"):
                t.run("DELETE FROM kl_timer WHERE eid=? AND k=?", (eid, k))
            t.log(who, "Marked " + {"present": "present", "done": "completed", "absent": "absent"}.get(st, "cleared"), eid, k)
            t.bump()
            return self.json({"ok": True})

        if p == "/api/timer":
            eid, k, act = b.get("e"), str(b.get("k", "")), b.get("action")
            ev, err = event_for_write(eid)
            if err:
                return err
            if not entry_ok(ev, k) or act not in ("start", "stop", "reset"):
                return self.json({"error": "Unknown entry."}, 400)
            now = now_ms()
            if act == "start":
                t.run("INSERT INTO kl_timer(eid,k,started,ended) VALUES(?,?,?,NULL) ON CONFLICT(eid,k) DO UPDATE SET started=excluded.started, ended=NULL",
                      (eid, k, now))
                set_status(eid, k, "present")
                st = t.one("SELECT state FROM kl_event_state WHERE id=?", (eid,))
                if not st:  # starting someone's timer means the event has started
                    t.run("INSERT INTO kl_event_state(id,state,ts,actor) VALUES(?,?,?,?) ON CONFLICT(id) DO NOTHING", (eid, "live", now_iso(), who))
                t.log(who, "Started timer", eid, k)
            elif act == "stop":
                row = t.one("SELECT started FROM kl_timer WHERE eid=? AND k=?", (eid, k))
                if not row or row["started"] is None:
                    return self.json({"error": "The timer was not started."}, 400)
                t.run("UPDATE kl_timer SET ended=? WHERE eid=? AND k=?", (now, eid, k))
                set_status(eid, k, "done")
                t.log(who, "Submitted / finished", eid, k, fmt_dur(now - int(row["started"])))
            else:
                t.run("DELETE FROM kl_timer WHERE eid=? AND k=?", (eid, k))
                set_status(eid, k, "present")
                t.log(who, "Reset timer", eid, k)
            t.bump()
            return self.json({"ok": True, "now": now})

        if p == "/api/event-state":
            eid, st = b.get("e"), b.get("s")
            ev = evs.get(eid)
            if not ev or st not in EVENT_STATES:
                return self.json({"error": "Unknown event."}, 400)
            if not admin and (ev["venue"] != s["venue"] or st == "upcoming"):
                return self.json({"error": "Only the admin can do this."}, 403)
            cur = t.one("SELECT state FROM kl_event_state WHERE id=?", (eid,))
            if not admin and cur and cur["state"] == "done":
                return self.json({"error": "This event is finished. Ask the admin to reopen it."}, 409)
            if st == "upcoming":
                t.run("DELETE FROM kl_event_state WHERE id=?", (eid,))
            else:
                t.run("INSERT INTO kl_event_state(id,state,ts,actor) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                      "state=excluded.state, ts=excluded.ts, actor=excluded.actor", (eid, st, now_iso(), who))
                if st == "done":  # stop any timers still running
                    t.run("UPDATE kl_timer SET ended=? WHERE eid=? AND ended IS NULL", (now_ms(), eid))
            t.log(who, {"live": "Started event", "done": "Event finished", "upcoming": "Reset event"}[st], eid)
            t.bump()
            return self.json({"ok": True})

        if p == "/api/event-cfg":
            eid = b.get("e")
            ev = evs.get(eid)
            if not ev:
                return self.json({"error": "Unknown event."}, 400)
            if not admin and ev["venue"] != s["venue"]:
                return self.json({"error": "This event is not at your venue."}, 403)
            cur = t.event_cfg().get(eid, {})
            new = dict(cur)
            if "judges" in b:
                j = int(b.get("judges") or 0)
                if not 1 <= j <= 10:
                    return self.json({"error": "Judges must be between 1 and 10."}, 400)
                new["judges"] = j
            if admin:
                for key, lo, hi in (("timer", 0, 300), ("timerMin", 0, 300)):
                    if key in b:
                        v = float(b.get(key) or 0)
                        if not lo <= v <= hi:
                            return self.json({"error": "Timer must be between 0 and 300 minutes."}, 400)
                        new[key] = v
            elif "timer" in b or "timerMin" in b:
                return self.json({"error": "Only the admin can change timers."}, 403)
            t.run("INSERT INTO kl_event_cfg(id,timer,timer_min,judges) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                  "timer=excluded.timer, timer_min=excluded.timer_min, judges=excluded.judges",
                  (eid, new.get("timer"), new.get("timerMin"), new.get("judges")))
            t.log(who, "Event settings", eid, "", json.dumps({k: v for k, v in new.items()}))
            t.bump()
            return self.json({"ok": True})

        if p == "/api/sheet":
            eid, data = b.get("e"), b.get("data")
            ev, err = event_for_write(eid, allow_closed=True)
            if err:
                return err
            if not isinstance(data, dict):
                return self.json({"error": "Nothing to save."}, 400)
            maxes = [c["max"] for c in ev["criteria"]]
            clean = {}
            for k, judges in data.items():
                if not entry_ok(ev, k) or not isinstance(judges, list):
                    continue
                rows = []
                for vals in judges[:10]:
                    row = []
                    for i, v in enumerate((vals or [])[:len(maxes)]):
                        if v in (None, ""):
                            row.append(None)
                            continue
                        try:
                            v = float(v)
                        except (TypeError, ValueError):
                            return self.json({"error": f"{k}: marks must be numbers."}, 400)
                        if v < 0 or (maxes[i] and v > maxes[i]):
                            return self.json({"error": f"{k}: {ev['criteria'][i]['name']} must be between 0 and {maxes[i]}."}, 400)
                        row.append(int(v) if v == int(v) else v)
                    rows.append(row)
                clean[k] = rows
            t.run("INSERT INTO kl_sheet(eid,data,ts,actor) VALUES(?,?,?,?) ON CONFLICT(eid) DO UPDATE SET data=excluded.data, ts=excluded.ts, actor=excluded.actor",
                  (eid, json.dumps(clean), now_iso(), who))
            t.log(who, "Saved marks", eid)
            t.bump()
            return self.json({"ok": True})

        if not admin:
            return self.json({"error": "Only the admin can do this."}, 403)

        if p == "/api/points":
            try:
                pts = {"ind": [float(x) for x in b["ind"]][:3], "grp": [float(x) for x in b["grp"]][:3]}
                assert len(pts["ind"]) == 3 and len(pts["grp"]) == 3 and all(0 <= x <= 1000 for x in pts["ind"] + pts["grp"])
            except Exception:
                return self.json({"error": "Enter points for 1st, 2nd and 3rd as numbers."}, 400)
            t.set_config("points", json.dumps(pts))
            t.log(who, "Changed points", "", "", json.dumps(pts))
            t.bump()
            return self.json({"ok": True})

        if p == "/api/event-edit":
            eid = b.get("e")
            o = EVENTS.get(eid)
            if not o:
                return self.json({"error": "Unknown event."}, 400)
            venue = b.get("venue") if b.get("venue") in {v["code"] for v in t.venues()} else None
            if venue and venue != o["venue"]:
                t.run("INSERT INTO kl_event_override(id,venue) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET venue=excluded.venue", (eid, venue))
            else:
                t.run("DELETE FROM kl_event_override WHERE id=?", (eid,))
            t.log(who, "Moved event", eid, "", venue or o["venue"])
            t.bump()
            return self.json({"ok": True})

        if p == "/api/settings":
            venues = t.venues()
            codes = codes_of(cfg)
            given = {str(v.get("code")): v for v in (b.get("venues") or []) if isinstance(v, dict)}
            admin_code = str(b.get("admin", codes["admin"])).strip().upper()
            names, passes = {}, {"admin": admin_code}
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
                t.set_config("codes_version", int(cfg.get("codes_version", "1")) + 1)
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
                return self.json({"error": f"Move its {n} event(s) to another venue first, on the Events page."}, 409)
            t.run("DELETE FROM kl_venue WHERE code=?", (code,))
            t.run("DELETE FROM kl_config WHERE name=?", ("code_" + code,))
            t.log(who, "Removed venue", "", code)
            t.bump()
            return self.json({"ok": True})

        if p == "/api/event-reset":  # admin: clear one event's attendance and timers, back to Not started
            eid = b.get("e")
            if eid not in evs:
                return self.json({"error": "Unknown event."}, 400)
            for tbl, col in (("kl_attendance", "eid"), ("kl_timer", "eid"), ("kl_event_state", "id")):
                t.run(f"DELETE FROM {tbl} WHERE {col}=?", (eid,))
            t.log(who, "Restarted attendance", eid)
            t.bump()
            return self.json({"ok": True})

        if p == "/api/reset":
            for tbl in ("kl_attendance", "kl_event_state", "kl_timer", "kl_sheet"):
                t.run(f"DELETE FROM {tbl}")
            t.log(who, "Reset attendance, timers and marks")
            t.bump()
            return self.json({"ok": True})

        if p == "/api/sample":
            import random
            rnd = random.Random(7)
            now, ts = now_ms(), now_iso()
            for tbl in ("kl_attendance", "kl_event_state", "kl_timer", "kl_sheet"):
                t.run(f"DELETE FROM {tbl}")
            ph = "%s" if t.pg else "?"
            att, est, tmr, sheets = [], [], [], []
            for ev in evs.values():
                r = rnd.random()
                state = "done" if r < 0.4 else "live" if r < 0.75 else None
                if not state:
                    continue
                est.append((ev["id"], state))
                marks = {}
                for i, en in enumerate(ev["entries"]):
                    k = key_of(en)
                    if state == "done":
                        if rnd.random() < 0.1:
                            continue  # absent
                        att.append((ev["id"], k, "done"))
                        if ev["timer"]:
                            dur = int(ev["timer"] * 60000 * rnd.uniform(0.6, 1.1))
                            tmr.append((ev["id"], k, now - 3600000 - dur, now - 3600000))
                        marks[k] = [[round(c["max"] * rnd.uniform(0.55, 0.95)) if c["max"] else rnd.randint(2, 10) for c in ev["criteria"]]
                                    for _ in range(ev["judges"])]
                    else:
                        x = rnd.random()
                        if x < 0.25:
                            continue  # not here yet
                        if x < 0.45:
                            att.append((ev["id"], k, "done"))
                            if ev["timer"]:
                                tmr.append((ev["id"], k, now - int(ev["timer"] * 60000), now - 60000))
                        else:
                            att.append((ev["id"], k, "present"))
                            if ev["timer"] and rnd.random() < 0.8:
                                tmr.append((ev["id"], k, now - int(ev["timer"] * 60000 * rnd.uniform(0.2, 1.25)), None))
                if marks:
                    sheets.append((ev["id"], json.dumps(marks)))
            if est:
                t.cur.executemany(f"INSERT INTO kl_event_state(id,state,ts,actor) VALUES({ph},{ph},{ph},{ph})", [(i, s_, ts, "practice") for i, s_ in est])
            if att:
                t.cur.executemany(f"INSERT INTO kl_attendance(eid,k,status,ts,actor) VALUES({ph},{ph},{ph},{ph},{ph})", [(e, k, s_, ts, "practice") for e, k, s_ in att])
            if tmr:
                t.cur.executemany(f"INSERT INTO kl_timer(eid,k,started,ended) VALUES({ph},{ph},{ph},{ph})", tmr)
            if sheets:
                t.cur.executemany(f"INSERT INTO kl_sheet(eid,data,ts,actor) VALUES({ph},{ph},{ph},{ph})", [(e, d, ts, "practice") for e, d in sheets])
            t.log(who, "Loaded practice data")
            t.bump()
            return self.json({"ok": True})

        return self.json({"error": "Not found"}, 404)
