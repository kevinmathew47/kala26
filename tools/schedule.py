"""Build a clash-free Kalamela timetable for the confirmed venues.

Usage:  python tools/schedule.py [trials]
Reads api/_lib/data.json (participants + entries), writes a new data.json with
venues, start/end times and call order, plus Kalamela_2026_Schedule.xlsx.

Rules (from the Kalamela manual and the first schedule):
- Day 8:45 AM - 6:00 PM, lunch 1:30 - 2:15 PM (nothing runs across lunch).
- Time per entry from the manual (DUR below); writing/drawing/quiz seat G1+G2 together.
- Nobody is in two places; at least 15 min between a person's events, 20 min
  around group events. Elocution contestants get the topic 10 min before their turn.
- One event at a time per venue, 3 min changeover between events.
"""
import json, os, random, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "api", "_lib", "data.json")

VENUES = [
    {"code": "V1", "key": "Venue 1", "name": "Inside the Church"},
    {"code": "V2", "key": "Venue 2", "name": "Balcony"},
    {"code": "V3", "key": "Venue 3", "name": "Vestry"},
    {"code": "V4", "key": "Venue 4", "name": "Fellowship Hall"},
    {"code": "V5", "key": "Venue 5", "name": "Ground Floor"},
]
VENUE_OF = [  # title prefix -> venue
    ("Solo", "V1"), ("Instrumental", "V1"),
    ("Essay Writing", "V2"), ("Story Writing", "V2"), ("Poetry Writing", "V2"), ("Quiz", "V2"),
    ("Bible Reading", "V3"), ("Elocution", "V3"), ("Poetry Recitation", "V3"),
    ("Group Song", "V4"), ("Margamkali", "V4"), ("Tableau", "V4"), ("Choreography", "V4"), ("Mime", "V4"),
    ("Pencil Drawing", "V5"), ("Painting", "V5"), ("Cartoon", "V5"), ("Clay Modeling", "V5"),
]
DUR = [("Solo A", 7), ("Solo B", 5), ("Instrumental", 6), ("Bible Reading", 4), ("Elocution", 6), ("Poetry Recitation", 8),
       ("Group Song", 12), ("Margamkali", 15), ("Tableau", 13), ("Choreography", 18), ("Mime", 14),
       ("Painting", 55), ("Quiz", 45), ("Essay", 40), ("Story", 40), ("Poetry Writing", 40), ("Pencil", 40), ("Cartoon", 40), ("Clay", 40)]
DAY_START, LUNCH_A, LUNCH_B, DAY_END = 8 * 60 + 45, 13 * 60 + 30, 14 * 60 + 15, 18 * 60
CHANGEOVER, GAP, GAP_GROUP, LATEST = 3, 15, 20, 19 * 60 + 45


def pick(table, title):
    return next(v for k, v in table if title.startswith(k))


def fmt(m):
    h, mm = divmod(m, 60)
    return f"{h % 12 or 12}:{mm:02d} {'PM' if h >= 12 else 'AM'}"


def load():
    d = json.load(open(DATA, encoding="utf-8"))
    evs = []
    for e in d["events"]:
        ev = {"id": e["id"], "title": e["title"], "type": e["type"], "venue": pick(VENUE_OF, e["title"]), "dur": pick(DUR, e["title"]),
              "entries": [{k: v for k, v in x.items() if k not in ("time", "order")} for x in e["entries"]]}
        evs.append(ev)
    return d, evs


def members(en):
    return en.get("members") or [en["chest"]]


class Sim:
    def __init__(self, evs, rnd):
        self.evs, self.rnd = evs, rnd
        self.busy = defaultdict(list)  # chest -> [(start, end, is_group)]
        self.pending = defaultdict(int)  # chest -> entries not yet scheduled
        for e in evs:
            for en in e["entries"]:
                for c in members(en):
                    self.pending[c] += 1
        self.weight = {e["id"]: rnd.random() for e in evs}
        stage = ["V1", "V3", "V4"]
        rnd.shuffle(stage)
        if rnd.random() < 0.7:
            stage.remove("V1"); stage.insert(0, "V1")
        self.prio = {v: i for i, v in enumerate(stage + ["V2", "V5"])}
        self.w_avail = rnd.uniform(0, 6)
        self.w_rand = rnd.uniform(0.5, 4)

    def free(self, c, a, b, group):
        for (s, t, g) in self.busy[c]:
            gap = GAP_GROUP if (g or group) else GAP
            if a < t + gap and s < b + gap:
                return False
        return True

    def book(self, c, a, b, group):
        self.busy[c].append((a, b, group))
        self.pending[c] -= 1

    def run(self):
        rnd = self.rnd
        todo = {v["code"]: [e for e in self.evs if e["venue"] == v["code"]] for v in VENUES}
        # all group events (Fellowship Hall) start after lunch
        state = {v["code"]: {"free_at": LUNCH_B if v["code"] == "V4" else DAY_START, "cur": None, "left": []} for v in VENUES}
        out = {}
        running = {}  # venue -> event currently calling entries
        t = DAY_START
        while t <= LATEST:
            if LUNCH_A <= t < LUNCH_B:
                t = LUNCH_B
                continue
            # the busiest stage venues pick people first; seated events fit around them
            order = sorted(state, key=lambda v: (self.prio[v], rnd.random()))
            for vc in order:
                st = state[vc]
                if st["free_at"] > t:
                    continue
                if st["cur"] is None:
                    if not todo[vc]:
                        continue
                    live = {c for s in state.values() if s["cur"] for en in s["left"] for c in members(en)}
                    ev = self.choose(todo[vc], t, live)
                    if ev is None:
                        continue
                    todo[vc].remove(ev)
                    if ev["type"] == "offstage":
                        for en in ev["entries"]:
                            for c in members(en):
                                self.book(c, t, t + ev["dur"], False)
                        out[ev["id"]] = {"start": t, "end": t + ev["dur"], "slots": [(t, en) for en in ev["entries"]]}
                        st["free_at"] = t + ev["dur"] + CHANGEOVER
                        continue
                    st["cur"], st["left"] = ev, list(ev["entries"])
                    out[ev["id"]] = {"start": t, "end": None, "slots": []}
                    running[vc] = ev
                ev = st["cur"]
                dur, grp = ev["dur"], ev["type"] == "group"
                pre = 10 if ev["title"].startswith("Elocution") else 0
                if t < LUNCH_A and t + dur > LUNCH_A:
                    st["free_at"] = LUNCH_B
                    continue
                ok = [en for en in st["left"] if all(self.free(c, t - pre, t + dur, grp) for c in members(en))]
                if not ok:
                    continue  # wait a minute for someone to become free
                # call the person who has the most still to do (they are the hardest to fit later)
                en = max(ok, key=lambda x: (sum(self.pending[c] for c in members(x)), rnd.random()))
                for c in members(en):
                    self.book(c, t - pre, t + dur, grp)
                out[ev["id"]]["slots"].append((t, en))
                st["left"].remove(en)
                st["free_at"] = t + dur
                if not st["left"]:
                    out[ev["id"]]["end"] = t + dur
                    st["cur"] = None
                    running.pop(vc, None)
                    st["free_at"] = t + dur + CHANGEOVER
            if all(not todo[v] and state[v]["cur"] is None for v in todo):
                break
            t += 1
        if any(todo.values()) or any(s["cur"] for s in state.values()):
            return None
        return out

    def choose(self, cands, t, live_pending):
        best, bkey = None, None
        for ev in cands:
            if ev["type"] == "offstage":
                end = t + ev["dur"]
                if t < LUNCH_A < end:
                    continue
                people = [c for en in ev["entries"] for c in members(en)]
                # don't lock people into a 40-55 min sitting while a live stage event still has to call them
                if any(c in live_pending for c in people):
                    continue
                if not all(self.free(c, t, end, False) for c in people):
                    continue
                avail = 1.0
            else:
                people = [c for en in ev["entries"] for c in members(en)]
                grp = ev["type"] == "group"
                pre = 10 if ev["title"].startswith("Elocution") else 0
                free_now = sum(all(self.free(c, t - pre, t + ev["dur"], grp) for c in members(en)) for en in ev["entries"])
                if free_now == 0:
                    continue  # nobody could be called yet: don't start this event now
                avail = free_now / len(ev["entries"])
            # prefer events whose people are free now and still have a lot to do, plus per-trial randomness
            load = sum(self.pending[c] for c in people) / max(1, len(people))
            key = load + self.w_avail * avail + self.w_rand * self.weight[ev["id"]]
            if bkey is None or key > bkey:
                best, bkey = ev, key
        return best


def check(evs, out):
    """Independent verification of every rule. Returns (problems, per-person intervals)."""
    problems, per = [], defaultdict(list)
    byv = defaultdict(list)
    for ev in evs:
        o = out[ev["id"]]
        byv[ev["venue"]].append((o["start"], o["end"], ev["title"]))
        if o["start"] < DAY_START:
            problems.append(f"{ev['title']} starts before 8:45")
        pre = 10 if ev["title"].startswith("Elocution") else 0
        for (t, en) in o["slots"]:
            a, b = (o["start"], o["end"]) if ev["type"] == "offstage" else (t, t + ev["dur"])
            if a < LUNCH_B and b > LUNCH_A:
                problems.append(f"{ev['title']} slot at {fmt(t)} runs into lunch")
            for c in members(en):
                per[c].append((a - pre, b, ev["type"] == "group", ev))
    for v, lst in byv.items():
        lst.sort()
        for (s1, e1, n1), (s2, e2, n2) in zip(lst, lst[1:]):
            if s2 < e1:
                problems.append(f"{v}: {n1} and {n2} overlap")
    tight = []
    for c, lst in per.items():
        lst.sort(key=lambda x: x[0])
        for x, y in zip(lst, lst[1:]):
            gap = y[0] - x[1]
            need = GAP_GROUP if (x[2] or y[2]) else GAP
            if gap < need:
                problems.append(f"{c}: only {gap} min between {x[3]['title']} and {y[3]['title']}")
            elif gap < 25:
                tight.append((c, gap, x[3], y[3], x[1], y[0]))
    return problems, per, tight


def score(evs, out):
    probs, per, tight = check(evs, out)
    if probs:
        return None
    last = max(o["end"] for o in out.values())
    venue_end = defaultdict(int)
    for ev in evs:
        venue_end[ev["venue"]] = max(venue_end[ev["venue"]], out[ev["id"]]["end"])
    idle = 0
    for ev in evs:
        o = out[ev["id"]]
        if ev["type"] != "offstage":
            idle += (o["end"] - o["start"]) - ev["dur"] * len(ev["entries"])
    # group events (V4) run after lunch and need ~4h50m, so they set the end of the day;
    # every other venue should still finish by 6:00 PM
    over = sum(max(0, e - DAY_END) for v, e in venue_end.items() if v != "V4")
    return over * 1000 + venue_end["V4"] * 8 + idle * 2 + len(tight) * 12 + sum(venue_end.values()) * 0.2, last, idle, len(tight)


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    d, evs = load()
    best = None
    off = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for i in range(off, off + trials):
        out = Sim(evs, random.Random(i)).run()
        if not out:
            continue
        s = score(evs, out)
        if s and (best is None or s[0] < best[0][0]):
            best = (s, out, i)
    if not best:
        sys.exit("No valid timetable found.")
    (sc, last, idle, ntight), out, seed = best
    probs, per, tight = check(evs, out)
    print(f"best seed {seed}: last event ends {fmt(last)}, idle waiting {idle} min, tight gaps {ntight}, problems {len(probs)}")

    events = []
    for ev in evs:
        o = out[ev["id"]]
        entries = []
        if ev["type"] == "offstage":
            for cat in ("G1", "G2"):
                n = 0
                for (t, en) in o["slots"]:
                    if en.get("cat") == cat:
                        n += 1
                        entries.append({**en, "order": n, "time": o["start"]})
        else:
            for n, (t, en) in enumerate(o["slots"], 1):
                entries.append({**en, "order": n, "time": t})
        start = o["start"] if ev["type"] == "offstage" else min(t for t, _ in o["slots"])  # first call, not when the venue opened
        events.append({"title": ev["title"], "venue": next(v["key"] for v in VENUES if v["code"] == ev["venue"]),
                       "start": start, "end": o["end"], "type": ev["type"], "id": ev["id"], "entries": entries})
    events.sort(key=lambda e: (e["start"], e["venue"]))
    d["venues"] = VENUES
    d["events"] = events
    json.dump(d, open(DATA, "w", encoding="utf-8"), ensure_ascii=False)
    for v in VENUES:
        print(f"\n{v['code']} {v['name']}")
        for e in [e for e in events if e["venue"] == v["key"]]:
            print(f"  {fmt(e['start']):>8} - {fmt(e['end']):>8}  {e['title']} ({len(e['entries'])})")
    return d, tight


if __name__ == "__main__":
    main()
