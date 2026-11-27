"""Build data.json for the Kalamela tracker from the schedule PDF + master sheet."""
import json, re, sys
import fitz, openpyxl

ROOT = sys.argv[1]
pdf = fitz.open(f"{ROOT}/Kalamela_2026_Final_Time_Schedule.pdf")
text = "\n".join(p.get_text() for p in pdf)
lines = [l.strip() for l in text.splitlines() if l.strip()]
lines = [l for l in lines if not l.startswith("Ernakulam Yuvajana Sakhyam Kalamela 2026 – Final")
         and not re.fullmatch(r"Page \d+", l)]

VENUES = {
    "Venue 1": "Inside the Church",
    "Venue 2": "Balcony",
    "Venue 3": "Sunday School Hall / Vestry",
    "Venue 4": "Fellowship Hall",
}
TIME = r"\d{1,2}:\d{2} [AP]M"
hdr = re.compile(rf"^(.+?) · (Venue \d) – .+? · ({TIME}) – ({TIME})$")

def to_min(t):
    h, m = map(int, t[:-3].split(":"))
    ap = t[-2:]
    if ap == "PM" and h != 12: h += 12
    if ap == "AM" and h == 12: h = 0
    return h * 60 + m

# Find header lines (they may wrap? check they are single lines)
start = next(i for i, l in enumerate(lines) if l.startswith("Call sheets"))
end = next(i for i, l in enumerate(lines) if l.startswith("Participant timeline"))
body = lines[start:end]

events = []
cur = None
for i, l in enumerate(body):
    m = hdr.match(l)
    if m:
        name, venue, s, e = m.groups()
        # continuation of the same event onto a new page -> reuse
        if cur and cur["title"] == name and cur["venue"] == venue:
            continue
        cur = {"title": name, "venue": venue, "start": to_min(s), "end": to_min(e), "_lines": []}
        events.append(cur)
        continue
    if cur is not None:
        cur["_lines"].append(l)

CHEST = re.compile(r"^[A-Z]{2}\d{3}$")
TEAM = re.compile(r"^[A-Z]{2}-[A-Z]{2}$")
for ev in events:
    L = ev.pop("_lines")
    entries = []
    is_group = any(x == "Team Chest No" for x in L)
    combined = any(x == "Seat #" for x in L)
    ev["type"] = "group" if is_group else ("offstage" if combined else "stage")
    if is_group:
        for k, x in enumerate(L):
            if TEAM.match(x):
                t = L[k - 1]
                members = L[k + 2]
                j = k + 3
                while j < len(L) and re.match(r"^[A-Z]{2}\d{3}", L[j]) and not CHEST.match(L[j]) is None and "," in L[j]:
                    members += ", " + L[j]; j += 1
                entries.append({"order": int(L[k - 2]), "time": to_min(t), "team": x,
                                "members": [m.strip() for m in members.split(",") if m.strip()]})
    else:
        for k, x in enumerate(L):
            if CHEST.match(x):
                prev = L[k - 1]
                if re.fullmatch(TIME, prev):
                    entries.append({"order": int(L[k - 2]), "time": to_min(prev), "chest": x})
                elif prev in ("G1", "G2"):
                    entries.append({"order": int(L[k - 2]), "cat": prev, "time": ev["start"], "chest": x})
    ev["entries"] = entries

# Participants from master sheet
wb = openpyxl.load_workbook(f"{ROOT}/Ernakulam Yuvajana Sakhyam Kalamela 2026 – Master Sheet (2).xlsx", data_only=True)
people = {}
for r in wb["Participants"].iter_rows(min_row=2, values_only=True):
    if not r[6]: continue
    people.setdefault(r[6], {"chest": r[6], "name": r[7], "gender": r[8], "parish": r[3],
                             "secretary": r[4], "phone": str(r[5] or "").replace(".0", "")})
for r in wb["Chest Numbers"].iter_rows(min_row=2, values_only=True):
    if r[0] and r[0] not in people:
        people[r[0]] = {"chest": r[0], "name": r[2], "gender": r[3], "parish": r[1], "secretary": "", "phone": ""}

# Secretary phone per parish as fallback contact
sec = {}
for p in people.values():
    if p["phone"]: sec.setdefault(p["parish"], (p["secretary"], p["phone"]))
for p in people.values():
    if not p["phone"] and p["parish"] in sec:
        p["secretary"], p["phone"] = sec[p["parish"]]

for i, ev in enumerate(events):
    ev["id"] = f"E{i+1:02d}"
events.sort(key=lambda e: (e["start"], e["venue"]))

missing = set()
for ev in events:
    for en in ev["entries"]:
        for c in en.get("members", [en.get("chest")]):
            if c not in people: missing.add(c)
print("events", len(events), "entries", sum(len(e["entries"]) for e in events),
      "people", len(people), "missing", sorted(missing))
for ev in events:
    print(ev["id"], ev["venue"], ev["title"], ev["type"], len(ev["entries"]))

json.dump({"venues": [{"code": k.replace("Venue ", "V"), "key": k, "name": v} for k, v in VENUES.items()],
           "events": events, "people": sorted(people.values(), key=lambda p: p["chest"])},
          open(f"{ROOT}/build/data.json", "w", encoding="utf-8"), ensure_ascii=False)
