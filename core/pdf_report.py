"""
core/pdf_report.py
Branded A4 PDF session report using reportlab.

Layout:
  Header    — Fluency Engine · Palencia Research · candidate · date · CEFR level
  Section 1 — Fluency Score + CEFR assessment + confidence
  Section 2 — Scenario (the task)
  Section 3 — Core metrics (WPM, pauses, fillers, discourse score)
  Section 4 — Sentence-level FS corrections (up to 8)
  Section 5 — Narrative coaching paragraph
  Section 6 — Next focus area
  Footer    — Research citations · GitHub
"""

import io
from datetime import datetime

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = (0.122, 0.220, 0.392)   # #1F3864
BLUE   = (0.180, 0.365, 0.627)   # #2E5DA0
GREY   = (0.333, 0.333, 0.333)
LGREY  = (0.600, 0.600, 0.600)
WHITE  = (1.000, 1.000, 1.000)
GREEN  = (0.102, 0.478, 0.235)
AMBER  = (0.690, 0.471, 0.000)


def _score_color(score: float):
    if score >= 75:
        return GREEN
    elif score >= 50:
        return BLUE
    elif score >= 30:
        return AMBER
    return (0.7, 0.1, 0.1)


def generate_pdf(
    username: str,
    session_n: int,
    level: str,
    scenario: dict,
    analysis: dict,
    score_data: dict,
    corrections: dict,
    cefr_assessment: dict,
    timestamp: str = None
) -> bytes:
    """
    Generate a one-page A4 branded PDF.
    Returns raw bytes (write to file or send as download).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color, HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    PAGE_W, PAGE_H = A4
    MARGIN = 18 * mm
    CW     = PAGE_W - 2 * MARGIN   # content width

    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    y = PAGE_H  # cursor starts at top

    def rgb(tup): return Color(tup[0], tup[1], tup[2])

    # ── Header bar ─────────────────────────────────────────────────────────
    bar_h = 22 * mm
    c.setFillColor(rgb(NAVY))
    c.rect(0, PAGE_H - bar_h, PAGE_W, bar_h, fill=1, stroke=0)

    # Brand left
    c.setFillColor(rgb(WHITE))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, PAGE_H - 10 * mm, "FLUENCY ENGINE")
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, PAGE_H - 15 * mm, "by Palencia Research  ·  Project 04  ·  Computational L2 Fluency Development")

    # Candidate info right
    ts = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 9 * mm, username)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 14 * mm, f"Session #{session_n}  ·  {ts}  ·  CEFR {level}")

    y = PAGE_H - bar_h - 7 * mm

    # ── Section 1 — Score ──────────────────────────────────────────────────
    fluency_score  = score_data.get("fluency_score", 0)
    assessed_level = cefr_assessment.get("assessed_level", level)
    confidence     = cefr_assessment.get("confidence", 0)
    grade          = score_data.get("grade", "")

    # Score circle (drawn manually)
    cx, cy, r = MARGIN + 18 * mm, y - 14 * mm, 13 * mm
    c.setFillColor(rgb(NAVY))
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFillColor(rgb(WHITE))
    c.setFont("Helvetica-Bold", 20)
    score_str = f"{fluency_score:.0f}"
    c.drawCentredString(cx, cy - 3.5 * mm, score_str)
    c.setFont("Helvetica", 7)
    c.drawCentredString(cx, cy - 8.5 * mm, "/100")

    # Grade and assessment text
    tx = MARGIN + 35 * mm
    c.setFillColor(rgb(_score_color(fluency_score)))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(tx, y - 8 * mm, grade)

    c.setFillColor(rgb(GREY))
    c.setFont("Helvetica", 9)
    c.drawString(tx, y - 14 * mm, f"CEFR Assessment: {assessed_level}  ·  Confidence: {confidence*100:.0f}%")
    c.drawString(tx, y - 19 * mm, score_data.get("interpretation", ""))

    # Component bars
    bx = MARGIN + 35 * mm
    bar_y = y - 25 * mm
    components = [
        ("WPM",    score_data.get("wpm_component", 0),    BLUE),
        ("Pauses", score_data.get("pause_component", 0),  (0.2, 0.6, 0.4)),
        ("Fillers",score_data.get("filler_component", 0),(0.7, 0.4, 0.0)),
    ]
    bar_max_w = 80 * mm
    for label, val, col in components:
        c.setFillColor(rgb(LGREY))
        c.rect(bx + 18 * mm, bar_y, bar_max_w, 3.5 * mm, fill=1, stroke=0)
        c.setFillColor(rgb(col))
        c.rect(bx + 18 * mm, bar_y, bar_max_w * val / 100, 3.5 * mm, fill=1, stroke=0)
        c.setFillColor(rgb(GREY))
        c.setFont("Helvetica", 8)
        c.drawString(bx, bar_y + 0.5 * mm, label)
        c.drawString(bx + 18 * mm + bar_max_w + 2 * mm, bar_y + 0.5 * mm, f"{val:.0f}")
        bar_y -= 6 * mm

    y = bar_y - 4 * mm
    _hline(c, MARGIN, y, CW, LGREY)
    y -= 5 * mm

    # ── Section 2 — Scenario ───────────────────────────────────────────────
    c.setFillColor(rgb(NAVY))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, y, f"SCENARIO  ·  {scenario.get('scenario_type_label','').upper()}  ·  {scenario.get('topic','')}")
    y -= 5 * mm

    c.setFillColor(rgb(GREY))
    c.setFont("Helvetica", 9)
    prompt_text = scenario.get("prompt", "")
    y = _wrapped_text(c, prompt_text, MARGIN, y, CW, 9, GREY, line_h=4.5*mm)
    y -= 2 * mm

    target = scenario.get("target_structure", "")
    if target:
        c.setFillColor(rgb(BLUE))
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(MARGIN, y, f"Target structure: {target}")
        y -= 5 * mm

    _hline(c, MARGIN, y, CW, LGREY)
    y -= 5 * mm

    # ── Section 3 — Metrics ────────────────────────────────────────────────
    c.setFillColor(rgb(NAVY))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, y, "CORE METRICS")
    y -= 5 * mm

    wpm         = analysis.get("wpm", 0)
    pause_count = analysis.get("pause_count", 0)
    pause_rate  = analysis.get("pause_rate", 0)
    filler_cnt  = analysis.get("filler_count", 0)
    filler_rate = analysis.get("filler_rate", 0)
    duration_s  = analysis.get("duration_s", 0)
    conn_data   = analysis.get("connector_data", {})
    disc_score  = conn_data.get("discourse_score", 0)
    types_used  = conn_data.get("types_used_count", 0)

    metrics = [
        ("Duration",        f"{duration_s:.0f}s"),
        ("WPM",             f"{wpm:.0f}"),
        ("Pauses",          f"{pause_count} ({pause_rate:.1f}/min)"),
        ("Fillers",         f"{filler_cnt} ({filler_rate:.1f}/min)"),
        ("Connectors used", f"{types_used} types  ·  Discourse score {disc_score:.0f}/100"),
    ]
    col_w = CW / len(metrics)
    mx    = MARGIN
    for label, val in metrics:
        c.setFillColor(rgb(LGREY))
        c.setFont("Helvetica", 7)
        c.drawCentredString(mx + col_w / 2, y - 1 * mm, label)
        c.setFillColor(rgb(NAVY))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(mx + col_w / 2, y - 6 * mm, val)
        mx += col_w

    y -= 12 * mm
    _hline(c, MARGIN, y, CW, LGREY)
    y -= 5 * mm

    # ── Section 4 — FS Corrections ─────────────────────────────────────────
    sentence_corrections = corrections.get("sentence_corrections", [])[:8]
    c.setFillColor(rgb(NAVY))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, y, f"CORRECTIONS  ({len(sentence_corrections)} identified)")
    y -= 5 * mm

    if sentence_corrections:
        for i, corr in enumerate(sentence_corrections):
            if y < 40 * mm:
                break
            orig     = corr.get("original", "")
            corrected = corr.get("corrected", "")
            rule     = corr.get("rule", "")
            repeat   = corr.get("repeat_prompt", "")

            c.setFillColor(rgb(GREY))
            c.setFont("Helvetica", 8)
            line = f"  {i+1}.  \"{orig}\"  →  \"{corrected}\""
            if rule:
                line += f"  [{rule}]"
            y = _wrapped_text(c, line, MARGIN, y, CW, 8, GREY, line_h=4*mm)
            if repeat:
                c.setFillColor(rgb(BLUE))
                c.setFont("Helvetica-Oblique", 8)
                c.drawString(MARGIN + 8 * mm, y, repeat)
                y -= 4.5 * mm
            y -= 1 * mm
    else:
        c.setFillColor(rgb(GREEN))
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN, y, "No significant grammar errors detected in this session.")
        y -= 5 * mm

    # Connector feedback
    conn_fb = corrections.get("connector_feedback", {})
    missing_type = conn_fb.get("strongest_missing", "")
    example_sent = conn_fb.get("example_sentence", "")
    if missing_type and y > 40 * mm:
        c.setFillColor(rgb(AMBER))
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN, y, f"  Connector gap: {missing_type}  |  Try: \"{example_sent}\"")
        y -= 5 * mm

    _hline(c, MARGIN, y, CW, LGREY)
    y -= 5 * mm

    # ── Section 5 — Narrative coaching ────────────────────────────────────
    if y > 35 * mm:
        narrative = corrections.get("narrative_coaching", "")
        c.setFillColor(rgb(NAVY))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, y, "COACHING SUMMARY")
        y -= 5 * mm
        if narrative:
            y = _wrapped_text(c, narrative, MARGIN, y, CW, 8.5, GREY, line_h=4.5*mm)
        y -= 3 * mm

    # ── Section 6 — Next focus ─────────────────────────────────────────────
    if y > 28 * mm:
        patterns = corrections.get("grammar_patterns_found", [])
        focus = patterns[0] if patterns else missing_type or "Continue at current level"
        c.setFillColor(rgb(BLUE))
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(MARGIN, y, f"NEXT SESSION FOCUS:  {focus}")
        y -= 5 * mm

    # ── Footer ─────────────────────────────────────────────────────────────
    footer_y = 10 * mm
    _hline(c, MARGIN, footer_y + 5 * mm, CW, LGREY)
    c.setFillColor(rgb(LGREY))
    c.setFont("Helvetica", 6.5)
    citations = (
        "Krashen (1982) Input Hypothesis  ·  Long (1996) Interaction Hypothesis  ·  "
        "Schmidt (1990) Noticing Hypothesis  ·  Skehan (1996) Fluency Framework  ·  "
        "CEFR: Council of Europe (2001)"
    )
    c.drawCentredString(PAGE_W / 2, footer_y + 2 * mm, citations)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(PAGE_W - MARGIN, footer_y + 2 * mm, "github.com/diegopalencia-research")

    c.save()
    return buf.getvalue()


# ── Drawing helpers ────────────────────────────────────────────────────────────
def _hline(c, x, y, w, color):
    from reportlab.lib.colors import Color
    c.setStrokeColor(Color(color[0], color[1], color[2]))
    c.setLineWidth(0.4)
    c.line(x, y, x + w, y)


def _wrapped_text(c, text, x, y, max_w, font_size, color, line_h=4.5):
    """Simple word-wrap for canvas. Returns new y position."""
    from reportlab.lib.colors import Color
    from reportlab.pdfbase.pdfmetrics import stringWidth

    c.setFillColor(Color(color[0], color[1], color[2]))
    c.setFont("Helvetica", font_size)

    words  = text.split()
    line   = ""
    lines  = []
    for word in words:
        test = (line + " " + word).strip()
        if stringWidth(test, "Helvetica", font_size) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)

    for ln in lines:
        c.drawString(x, y, ln)
        y -= line_h

    return y
