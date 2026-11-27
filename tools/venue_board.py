"""A4 landscape notice-board guide: which events happen at which venue (no timings).

Usage: python tools/venue_board.py "<output.pdf>"
Reads venues and events from api/_lib/data.json.
"""
import json, os, re, sys
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = json.load(open(os.path.join(ROOT, "api", "_lib", "data.json"), encoding="utf-8"))
LOGO = os.path.join(ROOT, "public", "logo.png")

FONTS = "C:/Windows/Fonts"
pdfmetrics.registerFont(TTFont("UI", f"{FONTS}/segoeui.ttf"))
pdfmetrics.registerFont(TTFont("UI-B", f"{FONTS}/segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("UI-SB", f"{FONTS}/seguisb.ttf"))

RED, INK, MUTED, LINE, BG = HexColor("#c8102e"), HexColor("#14161c"), HexColor("#6b7080"), HexColor("#e7e8ee"), HexColor("#f6f6f9")
VC = {"V1": "#2563eb", "V2": "#0d9488", "V3": "#9333ea", "V4": "#d97706", "V5": "#65a30d"}
TINT = {"V1": "#eef3fe", "V2": "#e8f7f5", "V3": "#f6eefd", "V4": "#fdf4e7", "V5": "#f1f8e9"}


def venue_events(code):
    """Group 1 / Group 2 of the same item share one line: 'Essay Writing – English  [G1] [G2]'."""
    out = {}
    for e in DATA["events"]:
        if e["venue"] != code:
            continue
        base = re.sub(r" – Group [12]$", "", e["title"])
        out.setdefault(base, []).append(e.get("cat") or "")
    return [(b, sorted(c for c in cats if c)) for b, cats in out.items()]


def wrap(text, font, size, width):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def rounded(c, x, y, w, h, r, fill, stroke=None):
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1 if stroke else 0)


def main(out):
    W, H = landscape(A4)
    c = canvas.Canvas(out, pagesize=(W, H))
    c.setTitle("Kalamela 2026 – Venue Guide")
    c.setAuthor("Ernakulam Yuvajana Sakhyam")
    M = 26

    # background + header
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, H - 86, W, 86, fill=1, stroke=0)
    c.setFillColor(HexColor("#a50d26"))
    c.rect(0, H - 90, W, 4, fill=1, stroke=0)
    if os.path.exists(LOGO):
        rounded(c, M, H - 78, 58, 70, 10, white)
        c.drawImage(LOGO, M + 5, H - 74, width=48, height=62, preserveAspectRatio=True, mask="auto")
    c.setFillColor(white)
    c.setFont("UI-B", 26)
    c.drawString(M + 74, H - 44, "Kalamela 2026  ·  Venue Guide")
    c.setFont("UI", 12.5)
    c.drawString(M + 74, H - 64, "Ernakulam Yuvajana Sakhyam  ·  Find the venue for your event")
    c.setFont("UI-SB", 11)
    c.drawRightString(W - M, H - 44, "5 venues  ·  53 events")
    c.setFont("UI", 10)
    c.drawRightString(W - M, H - 62, "G1 = Group 1   ·   G2 = Group 2")

    # five venue columns
    venues = DATA["venues"]
    gap = 10
    top, bottom = H - 104, 46
    colw = (W - 2 * M - gap * (len(venues) - 1)) / len(venues)
    for i, v in enumerate(venues):
        code = v["code"]
        col, tint = HexColor(VC.get(code, "#c8102e")), HexColor(TINT.get(code, "#fdebee"))
        x = M + i * (colw + gap)
        rounded(c, x, bottom, colw, top - bottom, 12, white, LINE)
        # header block
        hh = 82
        c.setFillColor(col)
        c.roundRect(x, top - hh, colw, hh, 12, fill=1, stroke=0)
        c.rect(x, top - hh, colw, 12, fill=1, stroke=0)
        c.setFillColor(white)
        c.circle(x + 26, top - 30, 15, fill=1, stroke=0)
        c.setFillColor(col)
        c.setFont("UI-B", 15)
        c.drawCentredString(x + 26, top - 35.5, code[1:])
        c.setFillColor(white)
        c.setFont("UI-SB", 9)
        c.drawString(x + 48, top - 24, f"VENUE {code[1:]}")
        name = v["name"]
        lines = wrap(name, "UI-B", 13.5, colw - 56)
        c.setFont("UI-B", 13.5 if len(lines) <= 2 else 12)
        for li, ln in enumerate(lines[:3]):
            c.drawString(x + 48, top - 41 - li * 15, ln)
        # events, grouped by item: "Solo A Malayalam" -> Female [G1 G2], Male [G1 G2]
        evs = venue_events(code)
        fams = {}
        for base, cats in evs:
            fam, _, sub = base.partition(" – ")
            fams.setdefault(fam, []).append((sub, cats))
        y = top - hh - 18
        c.setFont("UI-SB", 8.5)
        c.setFillColor(MUTED)
        n_ev = sum(max(1, len(cats)) for _, cats in evs)
        c.drawString(x + 14, y, f"{n_ev} EVENT{'S' if n_ev != 1 else ''}")
        y -= 10

        def chips(cats, right):
            cx = right
            for cat in reversed(cats):
                w = pdfmetrics.stringWidth(cat, "UI-B", 8) + 10
                cx -= w
                rounded(c, cx, cy - 3, w, 12.5, 6, white, col)
                c.setFillColor(col)
                c.setFont("UI-B", 8)
                c.drawCentredString(cx + w / 2, cy + 0.6, cat)
                cx -= 4

        right = x + colw - 15
        for fam, subs in fams.items():
            single = len(subs) == 1 and not subs[0][0]
            nlines = len(wrap(fam, "UI-B", 12, colw - 30 - (40 if single else 0)))
            boxh = (14 + nlines * 14 + 6) if single else (14 + nlines * 14 + len(subs) * 19 + 4)
            rounded(c, x + 8, y - boxh, colw - 16, boxh, 8, tint)
            c.setFillColor(col)
            c.roundRect(x + 8, y - boxh, 3.5, boxh, 1.5, fill=1, stroke=0)
            c.setFillColor(INK)
            c.setFont("UI-B", 12)
            ty = y - 18
            for li, ln in enumerate(wrap(fam, "UI-B", 12, colw - 30 - (40 if single else 0))):
                c.drawString(x + 18, ty - li * 14, ln)
            if single:
                cy = y - 18
                cats = subs[0][1]
                if cats:
                    chips(cats, right)
                else:
                    c.setFillColor(MUTED)
                    c.setFont("UI", 8.5)
                    c.drawRightString(right, cy, "Team")
            else:
                cy = ty - (nlines - 1) * 14 - 19
                for sub, cats in subs:
                    c.setFillColor(HexColor("#3a3f4c"))
                    c.setFont("UI", 11)
                    c.drawString(x + 18, cy, sub)
                    chips(cats, right)
                    cy -= 19
            y -= boxh + 7

    # footer
    c.setFillColor(MUTED)
    c.setFont("UI", 9.5)
    c.drawString(M, 24, "Report to the volunteer desk at your venue before your event.  Volunteers will tell you where to go next.")
    c.setFillColor(RED)
    c.setFont("UI-SB", 9.5)
    c.drawRightString(W - M, 24, "Lighted to Lighten")
    c.showPage()
    c.save()
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1])
