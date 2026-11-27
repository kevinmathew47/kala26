"""Build api/_lib/data.json from the master sheet (no timings).

Usage: python tools/build_events.py "<master sheet .xlsx>"

- One event per item and category: Group 1 and Group 2 are always separate events.
- Group (team) events: one team per parish, members = that parish's entries.
- Each event carries its judging criteria (from the 2026 judgment sheets), the
  default number of judges, and the default per-participant timer.
"""
import json, os, re, sys
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "api", "_lib", "data.json")

VENUES = [
    {"code": "V1", "name": "Inside the Church"},
    {"code": "V2", "name": "Balcony"},
    {"code": "V3", "name": "Vestry"},
    {"code": "V4", "name": "Fellowship Hall – Group Events"},
    {"code": "V5", "name": "Fellowship Hall – Art"},
]

# prefix -> venue, type, timer (limit min, minimum min), judges, criteria [(name, max)]
SOLO = [("Voice / Vocal texture", 20), ("Pitch & Tone", 20), ("Musical / Emotive Expression / Communication of meaning", 20), ("Rhythm", 20), ("Diction", 20)]
INSTR = [("Tone Quality", 20), ("Musical feel", 20), ("Rhythm", 20), ("Improvisation", 20), ("Technique (Efficiency in playing)", 20)]
ELOC = [("Use of Bible & Bible verses", 20), ("Poise", 15), ("Diction", 15), ("Eloquence", 15), ("Clarity of ideas", 15), ("Fluency", 10), ("Prosody", 10)]
BIBLE = [("Accuracy / Precision", 20), ("Voice control and modulation", 20), ("Pronunciation", 20), ("Style of presentation", 20), ("Speed in locating the assigned passage", 20)]
RECIT = [("Memorisation", 25), ("Diction", 25), ("Appropriate voice modulation and expression", 25), ("Clear communication of meaning and ideas", 25)]
ESSAY = [("Language proficiency", 20), ("Organization and presentation of facts", 20), ("Style of presentation", 20), ("Knowledge of the subject matter", 20), ("Use of Biblical references", 20)]
STORY = [("Language", 20), ("Creativity and originality", 20), ("Style / mode of expression", 20), ("Aesthetic quality", 20), ("Style of presentation", 20)]
PENCIL = [("Relevance", 20), ("Composition", 20), ("Skill in execution", 20), ("Character of lines / strokes and shadows", 20), ("Completeness / Overall finish", 20)]
PAINT = [("Relevance", 20), ("Composition", 20), ("Skill in the use of water colour", 20), ("Artistic Style", 20), ("Completeness / Overall finish", 20)]
CARTOON = [("Christian connection / relevance to the given subject", 20), ("Style of Presentation / Artistic Expression", 20), ("Satire and Social Criticism", 20), ("Composition", 20), ("Sense of Humour", 20)]
CLAY = [("Theme-based creation", 30), ("Completeness / Overall finish", 30), ("Combination", 20), ("Creativity and originality in modelling", 20)]
QUIZ = [("Round 1", 0), ("Round 2", 0), ("Round 3", 0), ("Round 4", 0), ("Round 5", 0)]
GSONG = [("Pitch", 30), ("Rhythm", 30), ("Coordination & harmony among choristers", 30), ("Clarity of notes", 10)]
MARGAM = [("Appropriateness of costume", 20), ("Devotional expression and team coordination", 20), ("Rhythm", 20), ("Footwork", 20), ("Music", 20)]
TABLEAU = [("Costume", 20), ("Creative presentation that effectively portrays the theme", 30), ("Use of Props / Materials", 25), ("Ability to maintain a still (static) display", 25)]
MIME = [("Theme & Message", 20), ("Acting & Facial expressions", 20), ("Coordination", 20), ("Creativity & Originality", 20), ("Overall Presentation", 20)]
CHOREO = [("Costume design and appropriateness of costumes", 20), ("Rhythm / Timing", 15), ("Expression (Facial and Emotional)", 15), ("Footwork / Steps", 15), ("Presentation", 20), ("Use of Props / Materials", 15)]

RULES = [  # (prefix, venue, type, limit, minimum, judges, criteria, team suffix)
    ("Solo A", "V1", "stage", 0, 0, 2, SOLO, None),
    ("Solo B", "V1", "stage", 0, 0, 2, SOLO, None),
    ("Instrumental", "V1", "stage", 5, 3, 2, INSTR, None),
    ("Essay Writing", "V2", "writing", 40, 0, 1, ESSAY, None),
    ("Poetry Writing", "V2", "writing", 40, 0, 1, ESSAY, None),
    ("Story Writing", "V2", "writing", 40, 0, 1, STORY, None),
    ("Quiz", "V2", "writing", 20, 0, 1, QUIZ, None),
    ("Bible Reading", "V3", "stage", 0, 0, 2, BIBLE, None),
    ("Elocution", "V3", "stage", 10, 0, 2, ELOC, None),
    ("Poetry Recitation", "V3", "stage", 10, 0, 2, RECIT, None),
    ("Group Song", "V4", "group", 0, 0, 2, GSONG, "GS"),
    ("Margamkali", "V4", "group", 0, 0, 2, MARGAM, "MG"),
    ("Tableau", "V4", "group", 0, 0, 2, TABLEAU, "TB"),
    ("Choreography", "V4", "group", 0, 0, 2, CHOREO, "CH"),
    ("Mime", "V4", "group", 0, 0, 2, MIME, "MI"),
    ("Pencil Drawing", "V5", "writing", 40, 0, 1, PENCIL, None),
    ("Painting", "V5", "writing", 45, 0, 1, PAINT, None),
    ("Cartoon", "V5", "writing", 40, 0, 1, CARTOON, None),
    ("Clay Modeling", "V5", "writing", 40, 0, 2, CLAY, None),
]
ORDER = [r[0] for r in RULES]


def rule(title):
    return next(r for r in RULES if title.startswith(r[0]))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("–", "-")).strip("-")


def main(xlsx):
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    rows = [r for r in wb["Participants"].iter_rows(min_row=2, values_only=True) if len(r) > 10 and r[6]]
    people = {}
    for r in rows:
        people.setdefault(r[6], {"chest": r[6], "name": str(r[7]).strip(), "gender": r[8], "parish": r[3],
                                 "secretary": r[4] or "", "phone": str(r[5] or "").replace(".0", "")})
    for r in wb["Chest Numbers"].iter_rows(min_row=2, values_only=True):
        if r and r[0] and r[0] not in people:
            people[r[0]] = {"chest": r[0], "name": r[2], "gender": r[3], "parish": r[1], "secretary": "", "phone": ""}
    groups = {}
    for r in rows:
        ev, cat = str(r[10]).strip(), r[9]
        g = "" if cat == "Group Event" else cat.replace("Group ", "G")
        groups.setdefault((ev, g), []).append(r)
    events = []
    for (ev, g), rs in groups.items():
        pre, venue, typ, limit, mn, judges, crit, suf = rule(ev)
        title = ev + (f" – Group {g[1]}" if g else "")
        if typ == "group":
            teams = {}
            for r in rs:
                teams.setdefault(r[6][:2], set()).add(r[6])
            entries = [{"team": f"{code}-{suf}", "members": sorted(m), "parish": people[sorted(m)[0]]["parish"]}
                       for code, m in sorted(teams.items())]
        else:
            entries = [{"chest": c} for c in sorted({r[6] for r in rs})]
        for i, en in enumerate(entries, 1):
            en["order"] = i
        events.append({"id": slug(title), "title": title, "cat": g, "venue": venue, "type": typ, "timer": limit, "timerMin": mn,
                       "judges": judges, "criteria": [{"name": n, "max": m} for n, m in crit], "entries": entries})
    events.sort(key=lambda e: (e["venue"], ORDER.index(rule(e["title"])[0]), e["title"]))
    data = {"venues": VENUES, "people": sorted(people.values(), key=lambda p: p["chest"]), "events": events}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    n_entries = sum(len(en.get("members") or [1]) for e in events for en in e["entries"])
    print(f"people {len(people)}, events {len(events)}, person-entries {n_entries}, sheet rows {len(rows)}")
    for e in events:
        print(f"  {e['venue']} {e['type']:8} timer {e['timer']:>2} judges {e['judges']}  {e['title']} ({len(e['entries'])})")


if __name__ == "__main__":
    main(sys.argv[1])
