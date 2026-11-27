"""Excel export in the official Kalamela layout.

Sheets
  1. Summary            cover page: totals, Overall trophy, Kalaprathibha, Kalathilakam
  2. Results Report     every placed participant, for reporting to the higher level
  3. Church Points      championship table
  4. Individual Points  Kalaprathibha / Kalathilakam standings
  5. Attendance         every participant in every event
  6. Activity Log       who did what, when
  7+ one Judgment Sheet per event, in the same layout as the printed 2026 judgment
     sheets (criteria with maximum marks, one table per judge, consolidated result,
     judge / centre president signature lines). Ready to print, landscape, one page wide.
"""
import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

TITLE = "Ernakulam Yuvajana Sakhyam Kalamela 2026"
RED, INK, MUTED = "8F1D2C", "1C2333", "5B6475"
HEAD_FILL = PatternFill("solid", fgColor=RED)
SUB_FILL = PatternFill("solid", fgColor="F3E7E9")
ZEBRA = PatternFill("solid", fgColor="FAFAFB")
GOLD, SILVER, BRONZE = PatternFill("solid", fgColor="FDF1C7"), PatternFill("solid", fgColor="ECEEF2"), PatternFill("solid", fgColor="F8E3CF")
PLACE_FILL = {1: GOLD, 2: SILVER, 3: BRONZE}
STATUS_FILL = {"Completed": PatternFill("solid", fgColor="DCEBFF"), "Present": PatternFill("solid", fgColor="DDF3E4"),
               "Absent": PatternFill("solid", fgColor="FBE0E3"), "Not marked": PatternFill("solid", fgColor="F2F3F5")}
THIN = Side(style="thin", color="C9CED8")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WHITE_B = Font(bold=True, color="FFFFFF", size=10)
B = Font(bold=True, color=INK)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
PLACE_NAME = {1: "First", 2: "Second", 3: "Third"}

JUDGING_CAT = [("Solo", "I"), ("Instrumental", "I"), ("Group Song", "I"), ("Elocution", "II"), ("Bible Reading", "II"),
               ("Poetry Recitation", "II"), ("Essay Writing – English", "III"), ("Poetry Writing – English", "III"),
               ("Story Writing – English", "III"), ("Essay Writing – Malayalam", "IV"), ("Poetry Writing – Malayalam", "IV"),
               ("Story Writing – Malayalam", "IV"), ("Pencil Drawing", "V"), ("Painting", "V"), ("Cartoon", "V"),
               ("Margamkali", "VI"), ("Clay Modeling", "VI"), ("Tableau", "VII"), ("Mime", "VII"), ("Choreography", "VII"), ("Quiz", "VIII")]


def judging_cat(title):
    return next((c for p, c in JUDGING_CAT if title.startswith(p)), "")


def category(ev):
    return {"G1": "Group 1", "G2": "Group 2"}.get(ev.get("cat"), "Group (Team) Event")


def base_title(ev):
    return re.sub(r" – Group [12]$", "", ev["title"])


def sheet_name(ev, used):
    t = base_title(ev)
    for a, b in (("Solo A Malayalam", "Solo A"), ("Solo B English", "Solo B"), ("Instrumental", "Instr"), ("Poetry Recitation", "Recitation"),
                 ("Bible Reading", "Bible"), ("Essay Writing", "Essay"), ("Story Writing", "Story"), ("Poetry Writing", "Poetry Wr"),
                 ("Elocution", "Elocution"), ("Pencil Drawing", "Pencil"), ("Cartoon (Pencil)", "Cartoon"), ("Clay Modeling", "Clay"),
                 ("Malayalam", "Mal"), ("English", "Eng"), ("Female", "F"), ("Male", "M"), (" – ", " ")):
        t = t.replace(a, b)
    t = re.sub(r"[\[\]\*\?/\\:]", "", t).strip()
    if ev.get("cat"):
        t += " " + ev["cat"]
    t = t[:31]
    n, k = t, 2
    while n in used:
        n = f"{t[:28]} {k}"
        k += 1
    used.add(n)
    return n


def style_table(ws, r0, r1, c0, c1, zebra=True):
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BOX
            if cell.alignment is None or not cell.alignment.wrap_text:
                cell.alignment = Alignment(vertical="center", wrap_text=True, horizontal=cell.alignment.horizontal if cell.alignment else None)
            if zebra and (r - r0) % 2 == 1 and cell.fill.fgColor.rgb in (None, "00000000"):
                cell.fill = ZEBRA


def header_row(ws, r, values, c0=1, height=30):
    for i, v in enumerate(values):
        cell = ws.cell(row=r, column=c0 + i, value=v)
        cell.font, cell.fill, cell.alignment, cell.border = WHITE_B, HEAD_FILL, CENTER, BOX
    ws.row_dimensions[r].height = height


def banner(ws, title, sub, width):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    ws["A1"], ws["A2"] = TITLE, title
    ws["A1"].font = Font(bold=True, size=15, color=RED)
    ws["A2"].font = Font(bold=True, size=12, color=INK)
    ws["A1"].alignment = ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height, ws.row_dimensions[2].height = 24, 20
    if sub:
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=width)
        ws["A3"] = sub
        ws["A3"].font = Font(italic=True, size=9, color=MUTED)
        ws["A3"].alignment = Alignment(horizontal="center")


def page(ws, landscape=True, title_rows=None):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)
    ws.print_options.horizontalCentered = True
    ws.oddFooter.center.text = "&P of &N"
    ws.oddFooter.left.text = TITLE
    if title_rows:
        ws.print_title_rows = title_rows
    ws.sheet_view.showGridLines = False


def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build(ctx):
    """ctx: evs, people, status(ev,k), took(ev,k), results(ev) -> rows, champ (per_event, ind, church),
    points, venue_name, sheets, att, acts, exported_at, award_min"""
    evs, P, status, results = ctx["evs"], ctx["people"], ctx["status"], ctx["results"]
    per_event, ind, church = ctx["champ"]
    vn = lambda c: f"{c} – {ctx['venue_name'].get(c, '')}"
    label = {"present": "Present", "done": "Completed", "absent": "Absent", "waiting": "Not marked"}
    wb = Workbook()

    def ranked(items):
        items = sorted(items, key=lambda x: -x[1])
        out = []
        for i, (k, v) in enumerate(items):
            out.append((out[-1][0] if i and v == items[i - 1][1] else i + 1, k, v))
        return out

    churches = ranked(list(church.items()))
    male = ranked([(k, d["points"]) for k, d in ind.items() if P.get(k, {}).get("gender") == "Male"])
    female = ranked([(k, d["points"]) for k, d in ind.items() if P.get(k, {}).get("gender") == "Female"])

    # ---------- 1. Summary ----------
    ws = wb.active
    ws.title = "Summary"
    banner(ws, "Results & Attendance Summary", f"Exported {ctx['exported_at']} (IST) · points as per the Kalamela Manual 2026", 6)
    widths(ws, [30, 34, 14, 14, 14, 14])
    r = 5
    def award_line(name, lst):
        top = [x for x in lst if x[0] == 1 and x[2] >= ctx["award_min"]]
        if top:
            return ", ".join(f"{P[k]['name']} ({k}), {P[k]['parish']}" for _, k, _ in top), f"{top[0][2]:g} points"
        lead = f"leader {P[lst[0][1]]['name']} ({lst[0][2]:g} points)" if lst else "no results yet"
        return "Not awarded", f"needs {ctx['award_min']} points · {lead}"
    trophy = [x for x in churches if x[0] == 1]
    rows = [("Overall Trophy (champion church)", ", ".join(k for _, k, _ in trophy) or "Not decided", f"{trophy[0][2]:g} points" if trophy else ""),
            ("Runner-up church", ", ".join(k for rk, k, _ in churches if rk == 2) or "–", next((f"{v:g} points" for rk, _, v in churches if rk == 2), "")),
            ("Kalaprathibha", *award_line("Kalaprathibha", male)),
            ("Kalathilakam", *award_line("Kalathilakam", female))]
    header_row(ws, r, ["Award", "Winner", "Points"], height=22)
    for i, (a, w, p) in enumerate(rows, r + 1):
        ws.cell(row=i, column=1, value=a).font = B
        ws.cell(row=i, column=2, value=w)
        ws.cell(row=i, column=3, value=p)
        ws.row_dimensions[i].height = 30
    style_table(ws, r + 1, r + len(rows), 1, 3, zebra=False)
    for i in range(r + 1, r + 3):
        ws.cell(row=i, column=2).fill = GOLD if i == r + 1 else SILVER
    r += len(rows) + 2
    att_total = [label[status(ev, en.get("chest") or en.get("team"))] for ev in evs for en in ev["entries"] for _ in (en.get("members") or [en.get("chest")])]
    facts = [("Participants", len(P)), ("Events", len(evs)), ("Events finished", sum(1 for e in evs if ctx["est"].get(e["id"], {}).get("s") == "done")),
             ("Participant entries", len(att_total)), ("Completed", att_total.count("Completed")), ("Absent", att_total.count("Absent")),
             ("Not marked", att_total.count("Not marked") + att_total.count("Present")),
             ("Points per place (individual)", " / ".join(f"{x:g}" for x in ctx["points"]["ind"])),
             ("Points per place (group)", " / ".join(f"{x:g}" for x in ctx["points"]["grp"]))]
    header_row(ws, r, ["Figure", "Value"], height=22)
    for i, (a, v) in enumerate(facts, r + 1):
        ws.cell(row=i, column=1, value=a).font = B
        c = ws.cell(row=i, column=2, value=v)
        c.alignment = Alignment(horizontal="left")
    style_table(ws, r + 1, r + len(facts), 1, 2)
    r += len(facts) + 2
    ws.cell(row=r, column=1, value="Rules applied: 1st / 2nd / 3rd earn the points above; a participant below 50% of the maximum marks earns no place or points; "
            f"Kalaprathibha / Kalathilakam need at least {ctx['award_min']} points from individual events; tied participants share the place and its points.").font = Font(size=9, color=MUTED, italic=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    ws.cell(row=r, column=1).alignment = LEFT
    ws.row_dimensions[r].height = 30
    page(ws, landscape=False)

    # ---------- 2. Results Report ----------
    ws = wb.create_sheet("Results Report")
    cols = ["Sl. No", "Event", "Category", "Position", "Chest No", "Name of Participant / Team", "Gender", "Sakha (Parish)", "Total Marks", "Max Marks", "%", "Points", "Next level"]
    banner(ws, "Results Report — positions in every event", "For reporting to the higher level. First and second positions are eligible for the next level (Manual rule 10).", len(cols))
    header_row(ws, 5, cols)
    widths(ws, [6, 30, 14, 10, 10, 30, 9, 36, 10, 10, 8, 8, 11])
    r, n = 6, 0
    for ev, winners, scored in per_event:
        maxtot = sum(c["max"] for c in ev["criteria"]) * ev["judges"]
        for rank, k, total, pts in winners:
            n += 1
            en = next(x for x in ev["entries"] if (x.get("chest") or x.get("team")) == k)
            name = P.get(k, {}).get("name", "") if not en.get("team") else "Team " + k + " (" + ", ".join(en["members"]) + ")"
            parish = en.get("parish") or P.get(k, {}).get("parish", "")
            vals = [n, base_title(ev), category(ev), PLACE_NAME[rank], k, name, P.get(k, {}).get("gender", "") if not en.get("team") else "",
                    parish, total, maxtot or None, round(total / maxtot * 100, 1) if maxtot else None, pts, "Yes" if rank <= 2 else ""]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c, value=v)
                if c in (1, 4, 5, 7, 9, 10, 11, 12, 13):
                    cell.alignment = CENTER
            ws.cell(row=r, column=4).fill = PLACE_FILL[rank]
            r += 1
    if n:
        style_table(ws, 6, r - 1, 1, len(cols))
        ws.auto_filter.ref = f"A5:{get_column_letter(len(cols))}{r - 1}"
    else:
        ws.cell(row=6, column=1, value="No results yet. Results appear when events are finished and judges' marks are entered.")
    ws.freeze_panes = "C6"
    page(ws, title_rows="5:5")

    # ---------- 3. Church Points ----------
    ws = wb.create_sheet("Church Points")
    cols = ["Rank", "Sakha (Parish)", "Individual 1st", "Individual 2nd", "Individual 3rd", "Group 1st", "Group 2nd", "Group 3rd", "Total Points"]
    banner(ws, "Church Championship — Overall Trophy", "Points from every individual and group event", len(cols))
    header_row(ws, 5, cols)
    widths(ws, [8, 44, 12, 12, 12, 11, 11, 11, 12])
    tally = {}
    for ev, winners, _ in per_event:
        for rank, k, total, pts in winners:
            en = next(x for x in ev["entries"] if (x.get("chest") or x.get("team")) == k)
            parish = en.get("parish") or P.get(k, {}).get("parish", "")
            t = tally.setdefault(parish, [0] * 6)
            t[(3 if ev["type"] == "group" else 0) + rank - 1] += 1
    for i, (rank, k, v) in enumerate(churches, 6):
        vals = [rank, k] + tally.get(k, [0] * 6) + [v]
        for c, val in enumerate(vals, 1):
            cell = ws.cell(row=i, column=c, value=val if val != 0 or c in (1, 9) else None)
            if c != 2:
                cell.alignment = CENTER
        if rank <= 3:
            for c in range(1, len(cols) + 1):
                ws.cell(row=i, column=c).fill = PLACE_FILL[rank]
        ws.cell(row=i, column=9).font = B
    if churches:
        style_table(ws, 6, 5 + len(churches), 1, len(cols), zebra=False)
    ws.freeze_panes = "A6"
    page(ws, title_rows="5:5")

    # ---------- 4. Individual Points ----------
    ws = wb.create_sheet("Individual Points")
    cols = ["Rank", "Chest No", "Name", "Sakha (Parish)", "1st places", "2nd places", "3rd places", "Points", "Award"]
    banner(ws, "Individual Championship — Kalaprathibha & Kalathilakam", f"Points from individual events only · award needs at least {ctx['award_min']} points", len(cols))
    widths(ws, [8, 10, 28, 42, 10, 10, 10, 9, 16])
    r = 5
    for g, award, lst in (("Male", "Kalaprathibha", male), ("Female", "Kalathilakam", female)):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(cols))
        ws.cell(row=r, column=1, value=f"{g} participants — {award}").font = Font(bold=True, size=11, color=RED)
        ws.cell(row=r, column=1).fill = SUB_FILL
        r += 1
        header_row(ws, r, cols, height=22)
        r0 = r + 1
        for rank, k, v in lst:
            r += 1
            d = ind[k]
            vals = [rank, k, P[k]["name"], P[k]["parish"], d["first"] or None, d["second"] or None, d["third"] or None, v,
                    award if rank == 1 and v >= ctx["award_min"] else ""]
            for c, val in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c, value=val)
                if c not in (3, 4):
                    cell.alignment = CENTER
            if rank <= 3:
                ws.cell(row=r, column=1).fill = PLACE_FILL[rank]
        if lst:
            style_table(ws, r0, r, 1, len(cols))
        else:
            r += 1
            ws.cell(row=r, column=1, value="No results yet.")
        r += 2
    page(ws)

    # ---------- 5. Attendance ----------
    ws = wb.create_sheet("Attendance")
    cols = ["Event", "Category", "Venue", "Team", "Chest No", "Participant", "Gender", "Sakha (Parish)", "Contact (parish secretary)", "Status", "Time taken", "Over time", "Marked by", "Marked at"]
    banner(ws, "Attendance — every participant in every event", "", len(cols))
    header_row(ws, 5, cols)
    widths(ws, [30, 12, 26, 9, 10, 26, 9, 36, 16, 12, 10, 9, 10, 19])
    r = 6
    for ev in evs:
        for en in ev["entries"]:
            k = en.get("chest") or en.get("team")
            s = label[status(ev, k)]
            took, over = ctx["took"](ev, k)
            a = ctx["att"].get(ev["id"] + "--" + k, {})
            for c in (en.get("members") or [en["chest"]]):
                p = P.get(c, {})
                vals = [base_title(ev), category(ev), vn(ev["venue"]), en.get("team", ""), c, p.get("name", ""), p.get("gender", ""), p.get("parish", ""),
                        p.get("phone", ""), s, took, "Yes" if over else "", a.get("by", ""), a.get("at", "")]
                for ci, v in enumerate(vals, 1):
                    cell = ws.cell(row=r, column=ci, value=v)
                    if ci in (4, 5, 7, 10, 11, 12, 13):
                        cell.alignment = CENTER
                ws.cell(row=r, column=10).fill = STATUS_FILL[s]
                if over:
                    ws.cell(row=r, column=12).font = Font(bold=True, color="B91C1C")
                r += 1
    style_table(ws, 6, r - 1, 1, len(cols), zebra=False)
    ws.auto_filter.ref = f"A5:{get_column_letter(len(cols))}{r - 1}"
    ws.freeze_panes = "F6"
    page(ws, title_rows="5:5")

    # ---------- 6. Activity Log ----------
    ws = wb.create_sheet("Activity Log")
    cols = ["Time (IST)", "By", "Action", "Event", "Chest / Team", "Detail"]
    banner(ws, "Activity Log", "", len(cols))
    header_row(ws, 5, cols, height=22)
    widths(ws, [19, 10, 26, 38, 13, 30])
    ev_title = {e["id"]: e["title"] for e in evs}
    for i, a in enumerate(ctx["acts"], 6):
        for c, v in enumerate([a["ts"], a["actor"], a["action"], ev_title.get(a["eid"], a["eid"]), a["k"], a["detail"]], 1):
            ws.cell(row=i, column=c, value=v)
    if ctx["acts"]:
        style_table(ws, 6, 5 + len(ctx["acts"]), 1, len(cols))
    ws.freeze_panes = "A6"
    page(ws, title_rows="5:5")

    # ---------- 7+. Judgment sheets ----------
    used = set(wb.sheetnames)
    for ev in evs:
        ws = wb.create_sheet(sheet_name(ev, used))
        crit = ev["criteria"]
        J = ev["judges"]
        ncol = 4 + len(crit) + 2
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        ws["A1"], ws["A2"] = TITLE, "JUDGMENT SHEET"
        ws["A1"].font, ws["A2"].font = Font(bold=True, size=14, color=RED), Font(bold=True, size=12, color=INK)
        ws["A1"].alignment = ws["A2"].alignment = Alignment(horizontal="center")
        info = [("Event", base_title(ev)), ("Category", category(ev)), ("Judging Category", judging_cat(ev["title"])),
                ("Entries", len(ev["entries"])), ("Venue", vn(ev["venue"])), ("Judges", J)]
        for i, (a, v) in enumerate(info):
            rr, cc = 4 + i // 2, 1 + (i % 2) * 4
            ws.cell(row=rr, column=cc, value=a + ":").font = Font(bold=True, color=MUTED, size=10)
            ws.cell(row=rr, column=cc + 1, value=v).font = B
            ws.merge_cells(start_row=rr, start_column=cc + 1, end_row=rr, end_column=cc + 3)
        widths(ws, [6, 11, 26, 30] + [13] * len(crit) + [11, 9])
        sheet = ctx["sheets"].get(ev["id"]) or {}
        res = {r_["k"]: r_ for r_ in results(ev)}
        r = 8
        entries = ev["entries"]
        for j in range(J):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
            ws.cell(row=r, column=1, value=f"Judge {j + 1}").font = Font(bold=True, color=RED, size=11)
            ws.cell(row=r, column=1).fill = SUB_FILL
            r += 1
            header_row(ws, r, ["S.No", "Chest No", "Name / Team", "Sakha (Parish)"] + [f"{c['name']}\n(Max {c['max']})" if c["max"] else c["name"] for c in crit]
                       + [f"TOTAL\n(Max {sum(c['max'] for c in crit)})" if all(c["max"] for c in crit) else "TOTAL", "Rank"], height=48)
            r0 = r + 1
            jtot = []
            for i, en in enumerate(entries, 1):
                r += 1
                k = en.get("chest") or en.get("team")
                st = status(ev, k)
                marks = (sheet.get(k) or [])
                row = marks[j] if j < len(marks) and isinstance(marks[j], list) else []
                nums = [v if isinstance(v, (int, float)) else None for v in row] + [None] * (len(crit) - len(row))
                total = sum(v for v in nums if v is not None) if any(v is not None for v in nums) else None
                jtot.append((total, r))
                name = P.get(k, {}).get("name", "") if not en.get("team") else "Team " + k
                parish = en.get("parish") or P.get(k, {}).get("parish", "")
                vals = [i, k, name + (" (absent)" if st == "absent" else ""), parish] + nums[:len(crit)] + [total, None]
                for c, v in enumerate(vals, 1):
                    cell = ws.cell(row=r, column=c, value=v)
                    if c not in (3, 4):
                        cell.alignment = CENTER
                if st == "absent":
                    for c in range(1, ncol + 1):
                        ws.cell(row=r, column=c).font = Font(color="9AA1AD", italic=True)
                ws.cell(row=r, column=ncol - 1).font = B
            # rank within this judge's marks
            order = sorted([t for t in jtot if t[0] is not None], key=lambda x: -x[0])
            for idx, (tot, rr) in enumerate(order):
                rank = next(i + 1 for i, (t2, _) in enumerate(order) if t2 == tot)
                ws.cell(row=rr, column=ncol, value=rank)
            style_table(ws, r0, r, 1, ncol)
            r += 2
            ws.cell(row=r, column=1, value="Name of Judge: ____________________________________").font = Font(color=INK)
            ws.cell(row=r, column=ncol - 3, value="Signature of Judge: ________________").font = Font(color=INK)
            r += 3
        # consolidated
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
        ws.cell(row=r, column=1, value="Consolidated Result").font = Font(bold=True, color=RED, size=11)
        ws.cell(row=r, column=1).fill = SUB_FILL
        r += 1
        cons = ["S.No", "Chest No", "Name / Team", "Sakha (Parish)"] + [f"Judge {j + 1}" for j in range(J)] + ["Grand Total", "%", "Position", "Points"]
        header_row(ws, r, cons, height=30)
        r0 = r + 1
        maxtot = sum(c["max"] for c in crit) * J
        for i, en in enumerate(entries, 1):
            r += 1
            k = en.get("chest") or en.get("team")
            rr_ = res.get(k)
            st = status(ev, k)
            name = P.get(k, {}).get("name", "") if not en.get("team") else "Team " + k
            pos = PLACE_NAME.get(rr_["rank"]) if rr_ and rr_.get("rank") and rr_["rank"] <= 3 else ("Absent" if st == "absent" else ("Below 50%" if rr_ and not rr_.get("eligible", True) else ""))
            pts = ctx["points"]["grp" if ev["type"] == "group" else "ind"][rr_["rank"] - 1] if rr_ and rr_.get("rank") and rr_["rank"] <= 3 else None
            vals = [i, k, name, en.get("parish") or P.get(k, {}).get("parish", "")] + \
                   ([rr_["judgeTotals"][j] if rr_ and j < len(rr_["judgeTotals"]) else None for j in range(J)]) + \
                   [rr_["total"] if rr_ else None, round(rr_["total"] / maxtot * 100, 1) if rr_ and maxtot else None, pos, pts]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c, value=v)
                if c not in (3, 4):
                    cell.alignment = CENTER
            if rr_ and rr_.get("rank") and rr_["rank"] <= 3:
                for c in range(1, len(cons) + 1):
                    ws.cell(row=r, column=c).fill = PLACE_FILL[rr_["rank"]]
        style_table(ws, r0, r, 1, len(cons), zebra=False)
        r += 2
        ws.cell(row=r, column=1, value="Signature of Centre President: ______________________").font = Font(color=INK)
        ws.cell(row=r, column=ncol - 3, value="Date: ______________").font = Font(color=INK)
        r += 1
        ws.cell(row=r, column=1, value="Criteria and maximum marks as per the Mar Thoma Yuvajana Sakhyam Kalamela Manual (2026). "
                                       "Total = sum of the criteria. Grand Total = sum of all judges' totals.").font = Font(size=8, italic=True, color=MUTED)
        page(ws)
        ws.print_area = f"A1:{get_column_letter(max(ncol, len(cons)))}{r}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
