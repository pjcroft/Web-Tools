"""Dedicated vector Gantt layout. No browser screenshots; all dates are inclusive."""

from datetime import date, timedelta
from math import ceil
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, A4, TABLOID, legal, landscape, portrait
from reportlab.lib.colors import HexColor, Color, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
if FONT_PATH.exists():
    pdfmetrics.registerFont(TTFont("Plan", str(FONT_PATH)))
    pdfmetrics.registerFont(TTFont("PlanBold", str(FONT_PATH.with_name("DejaVuSans-Bold.ttf"))))
    REG, BOLD = "Plan", "PlanBold"
else:
    REG, BOLD = "Helvetica", "Helvetica-Bold"
INK, MUTED, RULE = HexColor("#233e38"), HexColor("#70857b"), HexColor("#d8e2dc")


def fit(text, width, size=7, bold=False):
    text = str(text or "").replace("\n", " ")
    font = BOLD if bold else REG
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…" if text else ""


def export_pdf(project, settings, output):
    start, end = date.fromisoformat(settings["start"]), date.fromisoformat(settings["end"])
    if end < start or (end - start).days > 3660:
        raise ValueError("Choose a PDF date range of at most 10 years.")
    scale = settings.get("scale", "week")
    if scale not in ("day", "week", "month"):
        raise ValueError("Invalid timeline scale.")
    paper = {"tabloid": TABLOID, "legal": legal, "a3": A3, "a4": A4}.get(
        settings.get("paper"), TABLOID
    )
    width, height = (portrait if settings.get("orientation") == "portrait" else landscape)(paper)
    margin = 26
    usable = width - 2 * margin
    cols = [("id", "ID", 24), ("name", "Task name", max(130, usable * 0.20))]
    for key, title, w in [
        ("duration", "Days", 37),
        ("start", "Start", 56),
        ("finish", "Finish", 56),
        ("owner", "Owner", 62),
    ]:
        if key in settings.get("columns", ["duration", "start", "finish"]):
            cols.append((key, title, w))
    # Narrow paper scales the grid so at least half the width remains for the chart.
    factor = min(1, usable * 0.48 / sum(w for _, _, w in cols))
    cols = [(k, t, w * factor) for k, t, w in cols]
    grid_width = sum(w for _, _, w in cols)
    chart_left = margin + grid_width
    chart_width = usable - grid_width
    label_reserve = 62
    plot_width = chart_width - label_reserve
    days = (end - start).days + 1
    min_day = {"day": 8, "week": 3, "month": 1.05}[scale]
    per_slice = max(1, int(plot_width / min_day))
    slice_count = ceil(days / per_slice)
    row_height = 12 if settings.get("density", "compact") == "compact" else 18
    top = height - 100
    capacity = max(1, int((top - 48) / row_height))
    tasks = project["tasks"]
    row_pages = max(1, ceil(len(tasks) / capacity))
    total = row_pages * slice_count
    if total > settings.get("maxPages", 150):
        raise ValueError("Too many PDF pages. Shorten the date range or reduce rows.")
    c = canvas.Canvas(str(output), pagesize=(width, height))
    c.setTitle(project["name"])
    c.setAuthor("PC Plan")

    def text(x, y, s, size=7, bold=False, color=INK):
        c.setFillColor(color)
        c.setFont(BOLD if bold else REG, size)
        c.drawString(x, y, str(s))

    def line(x1, y1, x2, y2, color=RULE, w=0.4):
        c.setStrokeColor(color)
        c.setLineWidth(w)
        c.line(x1, y1, x2, y2)

    page = 0
    for section in range(slice_count):
        a = start + timedelta(days=section * per_slice)
        b = min(end, a + timedelta(days=per_slice - 1))
        n = (b - a).days + 1
        unit = plot_width / n

        def xpos(s, after=False):
            return chart_left + ((date.fromisoformat(s) - a).days + (1 if after else 0)) * unit

        for chunk in range(row_pages):
            page += 1
            rows = tasks[chunk * capacity : (chunk + 1) * capacity]
            bottom = top - len(rows) * row_height
            text(margin, height - 34, fit(project["name"], usable, 19, True), 19, True)
            text(
                margin,
                height - 53,
                f"{a:%d %b %Y} - {b:%d %b %Y}  /  Project schedule",
                8,
                color=MUTED,
            )
            text(width - margin - 112, height - 52, "PC PLAN  /  SCHEDULE", 7, color=MUTED)
            c.setFillColor(HexColor("#f0f5f1"))
            c.rect(margin, top, usable, 36, fill=1, stroke=0)
            x = margin
            for key, title, w in cols:
                text(x + 4, top + 14, title, 7, True)
                line(x, top + 36, x, bottom)
                x += w
            line(chart_left, top + 36, chart_left, bottom)
            # Three-tier quarter/month/day or week headers match the reference's hierarchy.
            last_month = None
            last_quarter = None
            for d in range(n):
                day = a + timedelta(days=d)
                xx = chart_left + d * unit
                if day.weekday() > 4:
                    c.setFillColor(HexColor("#f7f9f6"))
                    c.rect(xx, bottom, unit, top - bottom, fill=1, stroke=0)
                quarter = (day.year, (day.month - 1) // 3 + 1)
                if quarter != last_quarter:
                    remaining = (
                        date(day.year + int(day.month > 9), (quarter[1] * 3) % 12 + 1, 1) - day
                    ).days
                    label = fit(
                        f"Q{quarter[1]} {day.year}",
                        min(plot_width - d * unit, remaining * unit) - 3,
                        6,
                    )
                    text(xx + 3, top + 27, label, 6, color=MUTED)
                    last_quarter = quarter
                if day.month != last_month:
                    next_month = date(day.year + int(day.month == 12), day.month % 12 + 1, 1)
                    label = fit(
                        day.strftime("%B %Y"),
                        min(plot_width - d * unit, (next_month - day).days * unit) - 3,
                        6,
                    )
                    text(xx + 3, top + 16, label, 6, True)
                    line(xx, top + 24, xx, bottom)
                    last_month = day.month
                tick = (
                    scale == "day"
                    or (scale == "week" and day.weekday() == 0)
                    or (scale == "month" and day.day == 1)
                )
                if tick:
                    text(
                        xx + 2,
                        top + 4,
                        str(day.day) if scale != "month" else day.strftime("%b"),
                        5.5,
                        color=MUTED,
                    )
                    if scale != "day":
                        line(xx, top, xx, bottom)
            positions = {t["id"]: i for i, t in enumerate(rows)}
            byid = {t["id"]: t for t in tasks}
            # Draw dependencies behind the bars and clip to the timeline rectangle.
            c.saveState()
            clip = c.beginPath()
            clip.rect(chart_left, bottom, plot_width, top - bottom)
            c.clipPath(clip, stroke=0)
            for t in rows:
                ty = top - positions[t["id"]] * row_height - row_height / 2
                for dep in t.get("deps", []):
                    pred = byid.get(dep)
                    if not pred:
                        continue
                    sx = xpos(pred["finish"], True)
                    ex = xpos(t["start"])
                    mid = max(sx + 4, ex - 5)
                    if dep in positions:
                        sy = top - positions[dep] * row_height - row_height / 2
                        path = c.beginPath()
                        path.moveTo(sx, sy)
                        path.lineTo(mid, sy)
                        path.lineTo(mid, ty)
                        path.lineTo(ex, ty)
                        c.setStrokeColor(HexColor("#8ba096"))
                        c.setLineWidth(0.6)
                        c.drawPath(path)
                        arrow = c.beginPath()
                        arrow.moveTo(ex, ty)
                        arrow.lineTo(ex - 3, ty + 2)
                        arrow.lineTo(ex - 3, ty - 2)
                        arrow.close()
                        c.setFillColor(HexColor("#8ba096"))
                        c.drawPath(arrow, fill=1, stroke=0)
            c.restoreState()
            for i, t in enumerate(rows):
                y = top - (i + 1) * row_height
                center = y + row_height / 2
                summary = t["kind"] == "phase"
                if summary:
                    c.setFillColor(HexColor("#edf2ee"))
                    c.rect(margin, y, grid_width, row_height, fill=1, stroke=0)
                x = margin
                for key, title, w in cols:
                    value = t.get(key, "")
                    if key == "duration":
                        value = f"{value:g}" if isinstance(value, (int, float)) else value
                    if key in ("start", "finish"):
                        value = date.fromisoformat(value).strftime("%d %b %y")
                    indent = t["level"] * 8 if key == "name" else 0
                    text(
                        x + 4 + indent,
                        center - 2.5,
                        fit(value, w - 8 - indent, 6.4, summary),
                        6.4,
                        summary,
                    )
                    x += w
                line(margin, y, width - margin, y)
                ta, tb = date.fromisoformat(t["start"]), date.fromisoformat(t["finish"])
                if tb < a or ta > b:
                    continue
                xx = max(chart_left, xpos(t["start"]))
                right = min(chart_left + plot_width, xpos(t["finish"], True))
                barw = max(1, right - xx)
                color = HexColor(t["color"])
                if settings.get("mono"):
                    gray = 0.299 * color.red + 0.587 * color.green + 0.114 * color.blue
                    color = Color(gray, gray, gray)
                c.setFillColor(INK if summary else color)
                if summary:
                    c.rect(xx, center, barw, 4, fill=1, stroke=0)
                    for corner in [xx, xx + barw - 4]:
                        path = c.beginPath()
                        path.moveTo(corner, center + 4)
                        path.lineTo(corner + 4, center + 4)
                        path.lineTo(corner + 2, center - 3)
                        path.close()
                        c.drawPath(path, stroke=0, fill=1)
                elif t["kind"] == "milestone":
                    cx = max(
                        chart_left + 4,
                        min(chart_left + plot_width - 4, xpos(t["start"]) + unit / 2),
                    )
                    path = c.beginPath()
                    path.moveTo(cx, center + 3.5)
                    path.lineTo(cx + 3.5, center)
                    path.lineTo(cx, center - 3.5)
                    path.lineTo(cx - 3.5, center)
                    path.close()
                    c.drawPath(path, stroke=0, fill=1)
                    if settings.get("milestoneDates", True):
                        text(cx + 6, center - 2, ta.strftime("%m/%d"), 6, True)
                else:
                    c.rect(xx, center - 3, barw, 6, fill=1, stroke=0)
                    label = t.get("owner") or t["name"]
                    label_x = right + 4
                    text(label_x, center - 2, fit(label, width - margin - label_x - 3, 6), 6, True)
                off_page = [d for d in t.get("deps", []) if d not in positions]
                if off_page:
                    text(
                        chart_left + 3,
                        y + 1,
                        "From ID " + ",".join(map(str, off_page)),
                        4.8,
                        color=MUTED,
                    )
            for xx in [margin, chart_left, width - margin]:
                line(xx, top + 36, xx, bottom)
            line(margin, top + 36, width - margin, top + 36)
            line(margin, top, width - margin, top)
            line(margin, 36, width - margin, 36)
            text(margin, 23, "Working plan  |  Task dates shown as scheduled", 6.5, color=MUTED)
            text(width - margin - 100, 23, f"Page {page} of {total}", 7, color=MUTED)
            c.showPage()
    c.save()
    return total
