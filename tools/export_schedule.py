"""Write the timetable in api/_lib/data.json to an Excel workbook.
Usage: python tools/export_schedule.py <output.xlsx>
"""
import json, os, sys
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "api", "_lib", "data.json"), encoding="utf-8"))
P = {p["chest"]: p for p in d["people"]}
VN = {v["key"]: (v["code"], v["name"]) for v in d["venues"]}
RED, thin = "C8102E", Side(style="thin", color="D9DDE3")
VCOL = {"V1": "DBE7FF", "V2": "D7F3EF", "V3": "F0E1FB", "V4": "FDEBD3", "V5": "E6F4D7"}


def fmt(m):
    h, mm = divmod(int(m), 60)
    return f"{h % 12 or 12}:{mm:02d} {'PM' if h >= 12 else 'AM'}"


def head(ws, row, values, widths=None):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=RED)
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def vlabel(key):
    c, n = VN[key]
    return f"{c} – {n}"


wb = Workbook()
evs = sorted(d["events"], key=lambda e: (e["start"], e["venue"]))

# 1. Venue-wise timetable
ws = wb.active
ws.title = "Timetable"
ws["A1"] = "Ernakulam Yuvajana Sakhyam Kalamela 2026 – Timetable (5 venues)"
ws["A1"].font = Font(bold=True, size=14, color=RED)
ws["A2"] = "Day 8:45 AM – 7:15 PM · Lunch 1:30 – 2:15 PM · All group events in the Fellowship Hall after lunch · Times are estimates; call participants in the order on the call sheets."
r = 4
for v in d["venues"]:
    ws.cell(row=r, column=1, value=f'{v["code"]} – {v["name"]}').font = Font(bold=True, size=12)
    r += 1
    head(ws, r, ["Start", "End", "Event", "Entries"], [11, 11, 52, 12])
    r += 1
    lunch = False
    for e in [e for e in evs if e["venue"] == v["key"]]:
        if not lunch and e["start"] >= 13 * 60 + 15 and e["end"] > 13 * 60 + 30:
            lunch = True
            if e["start"] >= 14 * 60 + 15:
                ws.append([]) if False else None
                for i, val in enumerate(["1:30 PM", "2:15 PM", "LUNCH BREAK", ""], 1):
                    ws.cell(row=r, column=i, value=val).fill = PatternFill("solid", fgColor="EEEEEE")
                r += 1
        n = len(e["entries"])
        vals = [fmt(e["start"]), fmt(e["end"]), e["title"] + (" (runs across lunch)" if e["start"] < 810 < e["end"] else ""),
                f"{n} {'teams' if e['type'] == 'group' else 'entries'}"]
        for i, val in enumerate(vals, 1):
            c = ws.cell(row=r, column=i, value=val)
            c.fill = PatternFill("solid", fgColor=VCOL[v["code"]])
            c.border = Border(bottom=thin)
        r += 1
    r += 1

# 2. Grid by time
gs = wb.create_sheet("At a glance")
head(gs, 1, ["Time"] + [f'{v["code"]} – {v["name"]}' for v in d["venues"]], [11] + [34] * len(d["venues"]))
for slot in range(8 * 60 + 45, 19 * 60 + 15, 15):
    row = [fmt(slot)]
    for v in d["venues"]:
        cell = [e["title"] for e in evs if e["venue"] == v["key"] and e["start"] < slot + 15 and e["end"] > slot]
        row.append("LUNCH" if 13 * 60 + 30 <= slot < 14 * 60 + 15 else " / ".join(cell))
    gs.append(row)
for row in gs.iter_rows(min_row=2):
    for i, c in enumerate(row[1:]):
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if c.value:
            c.fill = PatternFill("solid", fgColor="EEEEEE" if c.value == "LUNCH" else VCOL[d["venues"][i]["code"]])
gs.freeze_panes = "B2"

# participant schedules (used by the next sheets)
per = defaultdict(list)
for e in evs:
    for en in e["entries"]:
        for c in (en.get("members") or [en["chest"]]):
            per[c].append((en["time"], e, en))
for c in per:
    per[c].sort(key=lambda x: x[0])


def others(c, e):
    return "; ".join(f"{fmt(t)} {ev['title']}{' [' + x['team'] + ']' if x.get('team') else ''} @ {VN[ev['venue']][1]}"
                     for t, ev, x in per[c] if ev is not e)


# 3. Call sheets
cs = wb.create_sheet("Call sheets")
head(cs, 1, ["Event", "Venue", "Call #", "Cat.", "Time", "Chest / Team", "Participant / Church", "Members", "Contact", "Their other events today"],
     [40, 26, 7, 6, 10, 12, 30, 40, 13, 90])
for e in evs:
    for en in e["entries"]:
        if en.get("team"):
            mem = en["members"]
            p0 = P.get(mem[0], {})
            cs.append([e["title"], vlabel(e["venue"]), en["order"], "", fmt(en["time"]), en["team"], p0.get("parish", ""), ", ".join(mem), p0.get("phone", ""), ""])
        else:
            p = P[en["chest"]]
            cs.append([e["title"], vlabel(e["venue"]), en["order"], en.get("cat", ""), fmt(en["time"]), en["chest"], p["name"] + " – " + p["parish"], "",
                       p.get("phone", ""), others(en["chest"], e)])
cs.freeze_panes = "A2"
cs.auto_filter.ref = cs.dimensions

# 4. Participant timeline + 5. attention list
pt = wb.create_sheet("Participant timeline")
head(pt, 1, ["Chest No", "Participant", "Parish", "Contact", "Events", "Shortest gap (min)", "Schedule for the day"], [10, 26, 38, 13, 8, 12, 140])
at_rows = []
DUR = {"Solo A": 7, "Solo B": 5, "Instrumental": 6, "Bible": 4, "Elocution": 6, "Poetry Recitation": 8, "Group Song": 12, "Margamkali": 15,
       "Tableau": 13, "Choreography": 18, "Mime": 14}


def span(e, t):
    if e["type"] == "offstage":
        return e["start"], e["end"]
    du = next(v for k, v in DUR.items() if e["title"].startswith(k))
    pre = 10 if e["title"].startswith("Elocution") else 0
    return t - pre, t + du


for c in sorted(per):
    p = P[c]
    lst = per[c]
    gaps = []
    for (t1, e1, _), (t2, e2, _) in zip(lst, lst[1:]):
        g = span(e2, t2)[0] - span(e1, t1)[1]
        gaps.append(g)
        if g < 25:
            at_rows.append([c, p["name"], p["parish"], g, f"{e1['title']} @ {VN[e1['venue']][1]} ends {fmt(span(e1, t1)[1])}",
                            f"{e2['title']} @ {VN[e2['venue']][1]} starts {fmt(t2)}"])
    pt.append([c, p["name"], p["parish"], p.get("phone", ""), len(lst), min(gaps) if gaps else "",
               " | ".join(f"{fmt(t)} {e['title']} @ {VN[e['venue']][1]}" for t, e, _ in lst)])
pt.freeze_panes = "A2"
pt.auto_filter.ref = pt.dimensions

an = wb.create_sheet("Needs attention")
head(an, 1, ["Chest No", "Participant", "Parish", "Gap (min)", "Finishes", "Next starts"], [10, 26, 38, 10, 60, 60])
for row in sorted(at_rows, key=lambda x: x[3]):
    an.append(row)
an.freeze_panes = "A2"

out = sys.argv[1]
wb.save(out)
print("saved", out, "| tight gaps:", len(at_rows), "| people with a tight gap:", len({r[0] for r in at_rows}))
