#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Programmatic Job Search Germany report (body PDF, ReportLab)."""
import os, sys, hashlib, html

PDF_SKILL_DIR = "/home/z/my-project/skills/pdf"
sys.path.insert(0, os.path.join(PDF_SKILL_DIR, "scripts"))
sys.path.insert(0, "/home/z/my-project/scripts")

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Table, TableStyle, KeepTogether, CondPageBreak,
                                XPreformatted, Flowable, HRFlowable)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ---------------- Fonts ----------------
FONT_DIR = "/usr/share/fonts"
pdfmetrics.registerFont(TTFont("NotoSerifSC", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NotoSerifSC-Bold", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Noto Sans SC", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Noto Sans SC Bold", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif", f"{FONT_DIR}/truetype/freefont/FreeSerif.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-Bold", f"{FONT_DIR}/truetype/freefont/FreeSerifBold.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-Italic", f"{FONT_DIR}/truetype/freefont/FreeSerifItalic.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-BoldItalic", f"{FONT_DIR}/truetype/freefont/FreeSerifBoldItalic.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans", f"{FONT_DIR}/truetype/dejavu/DejaVuSansMono.ttf"))
registerFontFamily("NotoSerifSC", normal="NotoSerifSC", bold="NotoSerifSC-Bold")
registerFontFamily("Noto Sans SC", normal="Noto Sans SC", bold="Noto Sans SC Bold")
registerFontFamily("FreeSerif", normal="FreeSerif", bold="FreeSerif-Bold",
                   italic="FreeSerif-Italic", boldItalic="FreeSerif-BoldItalic")
registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans")

from pdf import install_font_fallback
install_font_fallback()

# ---------------- Palette: Template 07 Crystal Blue (fixed body subset) ----------------
PAGE_BG      = colors.HexColor("#f5f8fc")
SECTION_BG   = colors.HexColor("#edf2f9")
CARD_BG      = colors.HexColor("#e4ecf5")
TABLE_STRIPE = colors.HexColor("#eef3fa")
HEADER_FILL  = colors.HexColor("#1a4a7a")
BORDER       = colors.HexColor("#c0d0e2")
ACCENT       = colors.HexColor("#2d7ab3")
TEXT_PRIMARY = colors.HexColor("#142840")
TEXT_MUTED   = colors.HexColor("#5a7a96")

# ---------------- Layout constants ----------------
MARGIN = 1.0 * inch
PAGE_W, PAGE_H = A4
AVAIL_W = PAGE_W - 2 * MARGIN
AVAIL_H = PAGE_H - 2 * MARGIN
H1_THRESHOLD = AVAIL_H * 0.25
MAX_KEEP = PAGE_H * 0.4

DOC_TITLE = "Programmatic Job Hunting in Germany"
DOC_AUTHOR = "Z.ai"

# ---------------- Styles ----------------
S = {}
S["body"] = ParagraphStyle("Body", fontName="FreeSerif", fontSize=10.5, leading=17,
                           alignment=TA_JUSTIFY, textColor=TEXT_PRIMARY, spaceAfter=8)
S["body_left"] = ParagraphStyle("BodyLeft", parent=S["body"], alignment=TA_LEFT)
S["h1"] = ParagraphStyle("H1", fontName="FreeSerif", fontSize=22, leading=27,
                         textColor=HEADER_FILL, spaceBefore=18, spaceAfter=4)
S["h2"] = ParagraphStyle("H2", fontName="FreeSerif", fontSize=15, leading=20,
                         textColor=TEXT_PRIMARY, spaceBefore=16, spaceAfter=7)
S["h3"] = ParagraphStyle("H3", fontName="FreeSerif", fontSize=11.5, leading=16,
                         textColor=TEXT_PRIMARY, spaceBefore=12, spaceAfter=6)
S["bullet"] = ParagraphStyle("Bullet", fontName="FreeSerif", fontSize=10.5, leading=16,
                             alignment=TA_LEFT, textColor=TEXT_PRIMARY,
                             leftIndent=14, spaceAfter=5)
S["caption"] = ParagraphStyle("Caption", fontName="FreeSerif", fontSize=8.5, leading=12,
                              alignment=TA_CENTER, textColor=TEXT_MUTED,
                              spaceBefore=3, spaceAfter=6)
S["code"] = ParagraphStyle("Code", fontName="DejaVuSans", fontSize=7.8, leading=11,
                           alignment=TA_LEFT, textColor=TEXT_PRIMARY)
S["codelabel"] = ParagraphStyle("CodeLabel", fontName="FreeSerif", fontSize=8.5, leading=12,
                                alignment=TA_LEFT, textColor=TEXT_MUTED, spaceAfter=2)
S["th"] = ParagraphStyle("TH", fontName="FreeSerif", fontSize=9, leading=12,
                         alignment=TA_LEFT, textColor=colors.white)
S["td"] = ParagraphStyle("TD", fontName="FreeSerif", fontSize=8.8, leading=12,
                         alignment=TA_LEFT, textColor=TEXT_PRIMARY, wordWrap="CJK")
S["stat"] = ParagraphStyle("Stat", fontName="FreeSerif", fontSize=19, leading=23,
                           alignment=TA_CENTER, textColor=ACCENT)
S["statlabel"] = ParagraphStyle("StatLabel", fontName="FreeSerif", fontSize=8.2, leading=11,
                                alignment=TA_CENTER, textColor=TEXT_MUTED)
S["quote"] = ParagraphStyle("Quote", fontName="FreeSerif", fontSize=10.5, leading=16.5,
                            alignment=TA_LEFT, textColor=TEXT_PRIMARY, leftIndent=6)
S["toc_title"] = ParagraphStyle("TocTitle", fontName="FreeSerif", fontSize=20, leading=26,
                                textColor=HEADER_FILL, spaceAfter=14)
S["toc0"] = ParagraphStyle("TOC0", fontName="FreeSerif", fontSize=11, leading=17,
                           leftIndent=4, textColor=TEXT_PRIMARY)
S["toc1"] = ParagraphStyle("TOC1", fontName="FreeSerif", fontSize=9.5, leading=14.5,
                           leftIndent=22, textColor=TEXT_MUTED)

# ---------------- Doc template with TOC + page zones ----------------
REGISTRY = {"body_start": None}

class BodyStartMarker(Flowable):
    def __init__(self):
        Flowable.__init__(self)
        self.width = 0
        self.height = 0
    def draw(self):
        REGISTRY["body_start"] = self.canv.getPageNumber()

class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, "bookmark_name"):
            level = getattr(flowable, "bookmark_level", 0)
            text = getattr(flowable, "bookmark_text", "")
            key = getattr(flowable, "bookmark_key", "")
            self.notify("TOCEntry", (level, text, self.page, key))

ROMAN = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii"}

def on_page(canvas, doc):
    canvas.saveState()
    # full-page background tint (Crystal Blue body)
    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # header
    canvas.setFont("FreeSerif", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN, PAGE_H - 0.62 * inch, DOC_TITLE.upper())
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1.2)
    canvas.line(MARGIN, PAGE_H - 0.70 * inch, PAGE_W - MARGIN, PAGE_H - 0.70 * inch)
    # footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 0.62 * inch, PAGE_W - MARGIN, 0.62 * inch)
    canvas.setFont("FreeSerif", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN, 0.44 * inch, "Job Search Automation Playbook - October 2026")
    page = canvas.getPageNumber()
    bs = REGISTRY.get("body_start")
    if bs is not None and page >= bs:
        label = str(page - bs + 1)
    else:
        label = ROMAN.get(page, str(page))
    canvas.drawRightString(PAGE_W - MARGIN, 0.44 * inch, label)
    canvas.restoreState()

# ---------------- Helpers ----------------
def esc(t):
    return html.escape(str(t), quote=False)

def add_heading(text, style, level=0):
    key = "h_" + hashlib.md5(text.encode()).hexdigest()[:8]
    p = Paragraph('<a name="%s"/><b>%s</b>' % (key, text), style)
    p.bookmark_name = key
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = key
    return p

def safe_keep(elements):
    total = 0
    for el in elements:
        w, h = el.wrap(AVAIL_W, PAGE_H)
        total += h
    if total <= MAX_KEEP:
        return [KeepTogether(elements)]
    elif len(elements) >= 2:
        return [KeepTogether(elements[:2])] + list(elements[2:])
    return list(elements)

def make_table(headers, rows, ratios, bold_first=False, font_size=8.8):
    n = len(headers)
    width_share = 0.99
    col_w = [r * AVAIL_W * width_share for r in ratios]
    th = ParagraphStyle("THx", parent=S["th"], fontSize=font_size + 0.2)
    td = ParagraphStyle("TDx", parent=S["td"], fontSize=font_size)
    data = [[Paragraph("<b>%s</b>" % esc(h), th) for h in headers]]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            txt = esc(cell)
            if bold_first and i == 0:
                txt = "<b>%s</b>" % txt
            cells.append(Paragraph(txt, td))
        data.append(cells)
    t = Table(data, colWidths=col_w, hAlign="CENTER", repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for r in range(1, len(data)):
        style.append(("BACKGROUND", (0, r), (-1, r),
                      colors.white if r % 2 == 1 else TABLE_STRIPE))
    t.setStyle(TableStyle(style))
    return t

def make_code(label, code_text):
    inner = XPreformatted(esc(code_text), S["code"])
    t = Table([[inner]], colWidths=[AVAIL_W * 0.985], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SECTION_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    out = [Paragraph(esc(label), S["codelabel"]), t]
    return safe_keep(out)

def make_callout(stats):
    n = len(stats)
    cells = []
    for big, label in stats:
        cells.append([Paragraph("<b>%s</b>" % esc(big), S["stat"]),
                      Spacer(1, 3),
                      Paragraph(esc(label), S["statlabel"])])
    t = Table([cells], colWidths=[AVAIL_W * 0.96 / n] * n, hAlign="CENTER")
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, n):
        style.append(("LINEBEFORE", (i, 0), (i, -1), 0.5, BORDER))
    t.setStyle(TableStyle(style))
    return [Spacer(1, 8), KeepTogether(t), Spacer(1, 10)]

def make_quote(text):
    p = Paragraph("<i>%s</i>" % text, S["quote"])
    t = Table([[p]], colWidths=[AVAIL_W * 0.96], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 2, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [Spacer(1, 6), t, Spacer(1, 8)]

def render_blocks(blocks, story):
    for blk in blocks:
        kind = blk[0]
        if kind == "h2":
            story.extend(safe_keep([add_heading(blk[1], S["h2"], level=1),
                                    Spacer(1, 2)]))
        elif kind == "h3":
            story.append(add_heading(blk[1], S["h3"], level=2))
        elif kind == "body":
            story.append(Paragraph(blk[1], S["body"]))
        elif kind == "bullets":
            for item in blk[1]:
                story.append(Paragraph("\u2022  " + item, S["bullet"]))
            story.append(Spacer(1, 4))
        elif kind == "table":
            d = blk[1]
            story.append(Spacer(1, 10))
            t = make_table(d["headers"], d["rows"], d["ratios"],
                           bold_first=d.get("bold_first", False),
                           font_size=d.get("font", 8.8))
            if len(d["rows"]) <= 14:
                cap = d.get("caption")
                if cap:
                    story.extend(safe_keep([t, Paragraph(esc(cap), S["caption"])]))
                else:
                    story.append(KeepTogether(t))
            else:
                story.append(t)
                if d.get("caption"):
                    story.append(Paragraph(esc(d["caption"]), S["caption"]))
            story.append(Spacer(1, 10))
        elif kind == "code":
            story.extend(make_code(blk[1], blk[2]))
            story.append(Spacer(1, 6))
        elif kind == "callout":
            story.extend(make_callout(blk[1]))
        elif kind == "quote":
            story.extend(make_quote(blk[1]))
        elif kind == "spacer":
            story.append(Spacer(1, blk[1]))

def build():
    from report_content_a import CHAPTERS_A
    from report_content_b import CHAPTERS_B
    from report_content_c import CHAPTERS_C
    chapters = CHAPTERS_A + CHAPTERS_B + CHAPTERS_C

    out_path = "/home/z/my-project/scripts/out/body.pdf"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = TocDocTemplate(out_path, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=1.0 * inch, bottomMargin=0.85 * inch,
                         title=DOC_TITLE, author=DOC_AUTHOR, creator=DOC_AUTHOR,
                         subject="Verified APIs, feeds and automation recipes for fast junior IT job search in Germany")
    story = []

    # ---- TOC (front matter, roman numbering) ----
    story.append(Paragraph("<b>Table of Contents</b>", S["toc_title"]))
    toc = TableOfContents()
    toc.dotsMinLevel = 0
    toc.levelStyles = [S["toc0"], S["toc1"]]
    story.append(toc)
    story.append(PageBreak())
    story.append(BodyStartMarker())

    # ---- Chapters ----
    first_chapter = True
    for ch in chapters:
        if not first_chapter:
            story.append(CondPageBreak(H1_THRESHOLD))
        first_chapter = False
        h1 = add_heading(ch["title"], S["h1"], level=0)
        rule = HRFlowable(width="100%", color=ACCENT, thickness=1.4,
                          spaceBefore=0, spaceAfter=10)
        blocks = list(ch["blocks"])
        head = [h1, rule]
        # pull first body paragraph next to the heading to avoid orphan heading
        story.extend(safe_keep(head + ([Paragraph(blocks[0][1], S["body"])]
                                       if blocks and blocks[0][0] == "body" else [])))
        consumed = 1 if (blocks and blocks[0][0] == "body") else 0
        render_blocks(blocks[consumed:], story)
        story.append(Spacer(1, 14))

    doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)
    print("body pages built:", doc.page)

if __name__ == "__main__":
    build()
