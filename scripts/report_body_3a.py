#!/usr/bin/env python3
"""report_body_3a.py — Task 21 body PDF (Report route, ReportLab).

Chapter numbering plan (report.md Step 3.5 mapping):
  | Outline | Type    | Chapter | Title                                    |
  | 1       | cover   | -       | Cover (separate HTML/Playwright PDF)     |
  | 2       | toc     | -       | Table of Contents                        |
  | 3       | content | 1       | Executive Summary                        |
  | 4       | content | 2       | The Funnel Model                         |
  | 5       | content | 3       | Timing: The 48-Hour Window               |
  | 6       | content | 4       | The Follow-Up Cadence                    |
  | 7       | content | 5       | Organizing Results: File Architecture    |
  | 8       | content | 6       | The Application Tracker                  |
  | 9       | content | 7       | The Friday Review Loop                   |
  | 10      | content | 8       | Germany Junior-IT Reality Check          |
  | 11      | content | 9       | Gap Analysis: What the Toolkit Covers    |

Front matter (TOC) = roman i footer; body = arabic restarting at 1
(implemented as doc.page - 1 with the TOC occupying exactly page 1).
"""
import hashlib
import os
import sys

PDF_SKILL_DIR = "/home/z/my-project/skills/pdf"
sys.path.insert(0, os.path.join(PDF_SKILL_DIR, "scripts"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, HRFlowable, Image, KeepTogether,
                                PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

# ------------------------------------------------------------------ fonts
FONT_DIR = "/usr/share/fonts"
pdfmetrics.registerFont(TTFont("NotoSerifSC", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NotoSerifSC-Bold", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif", f"{FONT_DIR}/truetype/freefont/FreeSerif.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-Bold", f"{FONT_DIR}/truetype/freefont/FreeSerifBold.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-Italic", f"{FONT_DIR}/truetype/freefont/FreeSerifItalic.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-BoldItalic", f"{FONT_DIR}/truetype/freefont/FreeSerifBoldItalic.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans", f"{FONT_DIR}/truetype/dejavu/DejaVuSansMono.ttf"))
registerFontFamily("NotoSerifSC", normal="NotoSerifSC", bold="NotoSerifSC-Bold")
registerFontFamily("FreeSerif", normal="FreeSerif", bold="FreeSerif-Bold",
                   italic="FreeSerif-Italic", boldItalic="FreeSerif-BoldItalic")
registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans")

from pdf import install_font_fallback  # noqa: E402
install_font_fallback()

# ------------------------------------------------ cascade palette (seed 21)
PAGE_BG = colors.HexColor("#f2f1f0")
SECTION_BG = colors.HexColor("#f1f0ef")
CARD_BG = colors.HexColor("#ecebe8")
TABLE_STRIPE = colors.HexColor("#ebebe9")
HEADER_FILL = colors.HexColor("#675e45")
COVER_BLOCK = colors.HexColor("#78715d")
BORDER = colors.HexColor("#c2beb0")
ICON = colors.HexColor("#a08f5e")
ACCENT = colors.HexColor("#96771c")
ACCENT_2 = colors.HexColor("#5537b0")
TEXT_PRIMARY = colors.HexColor("#22211f")
TEXT_MUTED = colors.HexColor("#87857d")

# ------------------------------------------------------------------ layout
MARGIN = 1.0 * inch
PAGE_W, PAGE_H = A4
AVAIL_W = PAGE_W - 2 * MARGIN
AVAIL_H = PAGE_H - 2 * MARGIN
H1_COND = AVAIL_H * 0.25
OUT = "/home/z/my-project/scripts/out/body_3a.pdf"
TITLE = "Job Search Methodology and Results Organization"

# ------------------------------------------------------------------ styles
S = {}
S["body"] = ParagraphStyle("Body", fontName="FreeSerif", fontSize=10.5, leading=17,
                           alignment=TA_JUSTIFY, textColor=TEXT_PRIMARY,
                           spaceBefore=0, spaceAfter=10)
S["h1"] = ParagraphStyle("H1", fontName="FreeSerif", fontSize=22, leading=27,
                         textColor=TEXT_PRIMARY, spaceBefore=18, spaceAfter=4)
S["h2"] = ParagraphStyle("H2", fontName="FreeSerif", fontSize=15, leading=20,
                         textColor=HEADER_FILL, spaceBefore=14, spaceAfter=8)
S["kicker"] = ParagraphStyle("Kicker", fontName="FreeSerif", fontSize=10, leading=14,
                             textColor=TEXT_MUTED, spaceAfter=2)
S["bullet"] = ParagraphStyle("Bullet", fontName="FreeSerif", fontSize=10.5, leading=17,
                             alignment=TA_LEFT, textColor=TEXT_PRIMARY,
                             leftIndent=14, bulletIndent=2, spaceAfter=5)
S["caption"] = ParagraphStyle("Caption", fontName="FreeSerif", fontSize=8.5, leading=12,
                              alignment=TA_CENTER, textColor=TEXT_MUTED,
                              spaceBefore=3, spaceAfter=6)
S["quote"] = ParagraphStyle("Quote", fontName="FreeSerif-Italic", fontSize=10.5, leading=17,
                            leftIndent=24, textColor=TEXT_PRIMARY, spaceBefore=6, spaceAfter=10)
S["th"] = ParagraphStyle("TH", fontName="FreeSerif", fontSize=9.5, leading=13,
                         textColor=colors.white, alignment=TA_LEFT)
S["td"] = ParagraphStyle("TD", fontName="FreeSerif", fontSize=9.5, leading=13.5,
                         textColor=TEXT_PRIMARY, alignment=TA_LEFT)
S["stat"] = ParagraphStyle("Stat", fontName="FreeSerif", fontSize=20, leading=24,
                           textColor=ACCENT, alignment=TA_CENTER)
S["statlabel"] = ParagraphStyle("StatLabel", fontName="FreeSerif", fontSize=8, leading=11,
                                textColor=TEXT_MUTED, alignment=TA_CENTER)
S["toc_title"] = ParagraphStyle("TocTitle", fontName="FreeSerif", fontSize=20, leading=25,
                                textColor=TEXT_PRIMARY, spaceAfter=14)
toc_l0 = ParagraphStyle("TOC0", fontName="FreeSerif", fontSize=11.5, leading=20,
                        leftIndent=6, textColor=TEXT_PRIMARY)
toc_l1 = ParagraphStyle("TOC1", fontName="FreeSerif", fontSize=10, leading=16,
                        leftIndent=26, textColor=TEXT_MUTED)


# ------------------------------------------------------------------ helpers
def P(text, style="body"):
    return Paragraph(text, S[style])


def add_heading(text, level=0):
    key = "h_" + hashlib.md5(text.encode()).hexdigest()[:8]
    style = S["h1"] if level == 0 else S["h2"]
    p = Paragraph(f'<a name="{key}"/><b>{text}</b>', style)
    p.bookmark_name = key
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = key
    return p


def h1_block(num, title, kicker_text):
    """H1 with accent underline rule + kicker, orphan-guarded (NOT a forced break)."""
    label = f"{num}. {title}" if num else title
    return [
        CondPageBreak(H1_COND),
        KeepTogether([
            Paragraph(kicker_text.upper(), S["kicker"]),
            add_heading(label, level=0),
            HRFlowable(width="100%", thickness=1.6, color=ACCENT,
                       spaceBefore=2, spaceAfter=12),
        ]),
    ]


def make_table(headers, rows, ratios, font_size=9.5):
    assert abs(sum(ratios) - 1.0) < 0.01, "ratios must sum to 1"
    widths = [r * AVAIL_W * 0.98 for r in ratios]
    assert sum(widths) <= AVAIL_W + 0.5
    th = ParagraphStyle("th_x", parent=S["th"], fontSize=font_size)
    td = ParagraphStyle("td_x", parent=S["td"], fontSize=font_size)
    data = [[Paragraph(f"<b>{h}</b>", th) for h in headers]]
    for row in rows:
        data.append([Paragraph(c, td) for c in row])
    t = Table(data, colWidths=widths, hAlign="CENTER", repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
    ]
    for i in range(1, len(data)):
        style.append(("BACKGROUND", (0, i), (-1, i),
                      colors.white if i % 2 == 1 else TABLE_STRIPE))
    t.setStyle(TableStyle(style))
    return t


def stat_row(stats):
    """4-up callout row: [(value, label), ...] — data-to-ink CalloutBox pattern."""
    vals = [Paragraph(f"<b>{v}</b>", S["stat"]) for v, _ in stats]
    labs = [Paragraph(l, S["statlabel"]) for _, l in stats]
    n = len(stats)
    t = Table([vals, labs], colWidths=[AVAIL_W * 0.98 / n] * n, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def fit_image(path, max_w, max_h):
    img = Image(path)
    ow, oh = img.drawWidth, img.drawHeight
    ratio = min(max_w / ow if ow > max_w else 1.0, max_h / oh if oh > max_h else 1.0)
    img.drawWidth, img.drawHeight = ow * ratio, oh * ratio
    return img


# ------------------------------------------------------------------ doc
class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, "bookmark_name"):
            level = getattr(flowable, "bookmark_level", 0)
            text = getattr(flowable, "bookmark_text", "")
            key = getattr(flowable, "bookmark_key", "")
            # TOC occupies exactly one page; body numbering = doc.page - 1
            self.notify("TOCEntry", (level, text, self.page - 1, key))


ROMAN = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v"}


def on_page(canvas, doc):
    # set page-default font BEFORE saveState so restoreState restores FreeSerif
    # (otherwise ReportLab re-selects Helvetica on restore -> forbidden font in stream)
    canvas.setFont("FreeSerif", 9)
    canvas.saveState()
    # header: title left + accent rule (skip on TOC page for a cleaner front matter)
    if doc.page > 1:
        canvas.setFont("FreeSerif", 7.5)
        canvas.setFillColor(TEXT_MUTED)
        canvas.drawString(MARGIN, PAGE_H - 0.62 * inch, TITLE)
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN, PAGE_H - 0.70 * inch, PAGE_W - MARGIN, PAGE_H - 0.70 * inch)
    # footer: roman on TOC page, arabic (page-1) on body pages
    canvas.setFont("FreeSerif", 9)
    canvas.setFillColor(TEXT_MUTED)
    num = ROMAN.get(doc.page, str(doc.page)) if doc.page == 1 else str(doc.page - 1)
    canvas.drawCentredString(PAGE_W / 2, 0.5 * inch, num)
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 0.68 * inch, PAGE_W - MARGIN, 0.68 * inch)
    canvas.restoreState()


# ------------------------------------------------------------------ story
story = []

toc = TableOfContents()
toc.levelStyles = [toc_l0, toc_l1]
story.append(Paragraph("<b>Table of Contents</b>", S["toc_title"]))
story.append(HRFlowable(width="100%", thickness=1.6, color=ACCENT, spaceBefore=0, spaceAfter=14))
story.append(toc)
story.append(PageBreak())

# ── 1. Executive Summary ─────────────────────────────────────────────
story += h1_block(1, "Executive Summary", "research brief · october 2026")
story.append(P(
    "This report condenses an internet research sweep on two questions asked together: how should a job "
    "search actually be run, and how should its results be organized so that the saved files become a "
    "durable asset rather than a pile of exports. The evidence base is ten targeted web searches and three "
    "full-page source reads, captured under <i>research/3-a/</i> in the project repository on 15 October "
    "2026. Every quantitative claim in the pages that follow traces back to a named source in that folder."))
story.append(P(
    "The research converges on one framing: a job search is a funnel, and the funnel should be operated "
    "like a measurable pipeline rather than an act of patience. Candidate-side trackers, recruiter-side "
    "hiring funnels, and data-driven search guides all describe the same stages - discover, shortlist, "
    "apply, interview, offer - and all recommend computing conversion rates per stage so that effort goes "
    "to the stage that is actually leaking. The base rates are unforgiving: roughly 32 applications and "
    "four interviews stand behind every offer, which is precisely why untracked searching feels like noise."))
story.append(Spacer(1, 8))
story.append(stat_row([
    ("41%", "of applications arrive within 48 h of posting (St. Louis Fed)"),
    ("68.5 d", "median time to first offer, 2025 (Interview Guys)"),
    ("250", "resumes per posting on average"),
    ("97.4%", "of Fortune 500 screen via an ATS first"),
]))
story.append(Spacer(1, 14))
story.append(P(
    "On the organization half, the authoritative file-management literature (CESSDA and the UK Data "
    "Service, plus university records-management practice) gives rules that map cleanly onto this "
    "project: dates in YYYY-MM-DD, hyphen-separated elements, folders over name-only conventions, stable "
    "pointers for current files, and README documentation as part of the structure. Task 21 implements "
    "both halves in the repository: the <i>download/</i> tree is reorganized into a documented layout "
    "maintained by an idempotent archiver, and a pre-seeded application tracker with live funnel "
    "formulas ships in <i>download/tracker/</i>."))

# ── 2. The Funnel Model ──────────────────────────────────────────────
story += h1_block(2, "The Funnel Model", "methodology · stages and base rates")
story.append(P(
    "A job search funnel is defined by Cruit as a structured system that tracks every stage of the "
    "search, from first discovering a company to signing an offer, modeled like a sales pipeline: many "
    "opportunities enter at the top, the best ones convert at the bottom. The model breaks the search "
    "into three macro-stages - visibility (getting in front of hiring managers), engagement (turning "
    "interest into conversations), and closing (converting interviews into offers). The practical value "
    "of the framing is diagnostic: knowing which stage is leaking tells you which problem to fix, instead "
    "of guessing whether the resume, the market, or the interview performance is at fault."))
story.append(P(
    "The recruiter side runs a mirror funnel - sourced, contacted, responded, screened, submitted, "
    "interviewed, offered - and practitioner advice on r/recruiting is to keep it simple but always "
    "track conversion by stage. That advice transfers directly to the candidate side. Select Software "
    "Reviews' 2025 analysis found that 97.4 percent of Fortune 500 companies run an applicant tracking "
    "system, meaning most applications are machine-filtered before a human reads anything; visibility "
    "is a numbers problem before it is a charm problem."))
story.append(Spacer(1, 24))
_img = fit_image("/home/z/my-project/scripts/out/funnel_base_rates.png",
                 AVAIL_W * 0.92, A4[1] * 0.28)
story.append(KeepTogether([
    _img,
    Spacer(1, 8),
    Paragraph("Figure 1 - Funnel base rates per one offer, 2025 averages "
              "(The Interview Guys, via askcruit.com).", S["caption"]),
]))
story.append(Spacer(1, 18))
story.append(P(
    "The stage vocabulary below is the one implemented in the project's application tracker. It merges "
    "the candidate-side conventions of Teal and Huntr with the recruiting-funnel stages, and it is kept "
    "deliberately short: every extra stage is one more field a tired human will not update."))
story.append(Spacer(1, 18))
story.append(make_table(
    ["Stage", "Meaning", "Owner action"],
    [
        ["discovered", "Pulled by the pipeline, not yet reviewed", "Friday review: shortlist or close"],
        ["shortlisted", "Worth a tailored application", "Spend the 3-5 h tailoring budget here"],
        ["applied", "Application sent", "followup_due auto-fills at +7 days"],
        ["interviewing", "Any human contact scheduled or held", "Log notes and contact person"],
        ["offer", "Offer in hand", "Negotiate; everything before was cost"],
        ["closed / rejected", "Withdrawn, role died, or declined", "Keep for conversion arithmetic"],
    ],
    [0.16, 0.42, 0.42]))
story.append(Spacer(1, 6))
story.append(Paragraph("Table 1 - Status vocabulary of the application funnel.", S["caption"]))
story.append(Spacer(1, 12))

# ── 3. Timing ────────────────────────────────────────────────────────
story += h1_block(3, "Timing: The 48-Hour Window", "methodology · freshness")
story.append(P(
    "The cleanest timing evidence comes from the St. Louis Fed's analysis of application arrival times: "
    "41 percent of all applications for a posting arrive within the first 48 hours, and 56 percent "
    "within 96 hours. Everyone competes in the same fresh window. Sources disagree on the size of the "
    "edge inside it - one claims applicants in the first 48 hours are four to five times more likely to "
    "get an interview request, others cite a 30 percent higher response rate, a third a 32 percent "
    "callback boost within 24 hours - but the direction is consistent across five independent sources, "
    "and even the most conservative reading puts early applicants ahead."))
story.append(P(
    "Day and time matter secondarily: applications sent Tuesday through Thursday mornings (8-11 AM) "
    "show roughly 30 percent higher response rates than other slots in metaintro's 2026 guide, with "
    "multiple sources agreeing mid-week beats Friday afternoon. For this project the implication is "
    "structural rather than behavioral: the daily pull cadence is already correct, and the pipeline's "
    "digest already flags rows that are new since yesterday. The tracker's <i>first_seen</i> column "
    "carries the freshness signal forward, so a shortlisting decision made on day three is visibly "
    "different from one made on day thirteen."))
story.append(Spacer(1, 18))
story.append(make_table(
    ["Window", "Evidence", "Action"],
    [
        ["First 24-48 h", "41% of competition applies here (St. Louis Fed); response-rate edge of 30-32% "
         "reported by three sources", "Review pipeline output daily; shortlist fast"],
        ["Day 3-14", "56% of applications in by 96 h; odds decay after", "Second-chance review before "
         "rows age out of the 14-day window"],
        ["Tue-Thu, 8-11 AM", "~30% higher response (metaintro 2026)", "Send tailored applications and "
         "follow-ups mid-week mornings"],
        ["Friday afternoon", "Weakest slot per multiple sources", "Use for the review itself, not sends"],
    ],
    [0.18, 0.48, 0.34]))
story.append(Spacer(1, 6))
story.append(Paragraph("Table 2 - Application-timing windows and the corresponding actions.", S["caption"]))
story.append(Spacer(1, 12))

# ── 4. Follow-Up Cadence ─────────────────────────────────────────────
story += h1_block(4, "The Follow-Up Cadence", "methodology · after the send")
story.append(P(
    "Follow-up is the cheapest lever in the whole funnel and the first one people forget. The consensus "
    "across Indeed, Handshake, LinkedIn career-advice posts, and Frontline Source Group is to wait "
    "one week - five to seven business days - after applying, then send one polite follow-up; ten to "
    "fourteen days remains acceptable for slower processes. The purpose is dual: it reminds the hiring "
    "manager the application exists, and it restates interest while the requisition is still open. "
    "Multiple sources recommend sending mid-week, consistent with the timing table above."))
story.append(P(
    "After an interview the rhythm compresses: a thank-you note within 24 hours, a checking-in note "
    "after about a week, and only then a second follow-up a few days later (The Muse). None of this "
    "happens reliably by memory once more than a handful of applications are live - which is exactly "
    "the argument the tracker research makes. In the shipped tracker the <i>followup_due</i> column is "
    "a live formula: the moment a row's status becomes <i>applied</i> and an applied date exists, the "
    "due date auto-fills at plus seven days, and the Funnel sheet counts overdue follow-ups against "
    "today's date, turning the etiquette rule into a zero-memory checklist."))
story.append(Spacer(1, 18))
story.append(make_table(
    ["Situation", "Wait", "Move"],
    [
        ["After applying", "5-7 business days", "One polite follow-up email, mid-week"],
        ["Still silent at 10-14 days", "10-14 days total", "Second contact acceptable; then close it"],
        ["After interview", "Within 24 h", "Thank-you note to every interviewer"],
        ["Post-interview silence", "~1 week", "Checking-in note; second follow-up a few days later"],
    ],
    [0.30, 0.22, 0.48]))
story.append(Spacer(1, 6))
story.append(Paragraph("Table 3 - Follow-up cadence, aggregated from Indeed, The Muse, Handshake, "
                       "and Frontline Source Group.", S["caption"]))
story.append(Spacer(1, 12))

# ── 5. Organizing Results ────────────────────────────────────────────
story += h1_block(5, "Organizing Results: File Architecture", "perfect files · conventions")
story.append(P(
    "The file-management literature is unusually concrete. The CESSDA Data Management Expert Guide, "
    "transmitting UK Data Service best practice, treats the file name as the principal identifier: it "
    "should describe content, carry status and version, and sort correctly. Its rules - dates in "
    "YYYY-MM-DD, elements separated by hyphens or underscores, no spaces or special characters, "
    "meaningful but brief names, extensions reserved for the format - are exactly the convention this "
    "project's generated files already follow. University records-management guidance (University of "
    "Washington) adds the structural point: folder hierarchies are the stronger, more foolproof "
    "organization method, while name-only conventions demand ongoing discipline that humans rarely "
    "sustain."))
story.append(P(
    "Applied to the project, the redesign separates three kinds of files. Stable pointers "
    "(<i>jobs_latest.csv/json</i>) keep fixed names and are overwritten by every pipeline run, so "
    "humans and scripts always have one canonical current address. Immutable history lives in dated "
    "folders (<i>daily/YYYY-MM-DD/</i>) that are never edited in place - corrected re-runs land as new "
    "timestamped files beside the originals. Partition-by-kind containers (<i>reports/, tracker/, "
    "archive/</i>) keep the root minimal. The layout is maintained by <i>scripts/organize_downloads.py</i>, "
    "an idempotent archiver that classifies every root file, never overwrites, and is wired into the "
    "daily pipeline as step 5 of 6 - automating the maintenance that name-only conventions expect "
    "people to remember. Thirty-five previously flat files were organized on adoption day."))
story.append(Spacer(1, 18))
story.append(make_table(
    ["Path", "Role", "Rules"],
    [
        ["download/jobs_latest.*", "Stable pointers", "Fixed names, overwritten each run, never moved"],
        ["download/daily/YYYY-MM-DD/", "Immutable run history", "Timestamped CSV/JSON/rejected files; "
         "never edited in place"],
        ["download/reports/", "Generated documents", "PDF reports, XLSX workbooks, cover sources"],
        ["download/tracker/", "The funnel file", "Application tracker XLSX + CSV twin, committed to git"],
        ["download/archive/", "Legacy one-offs", "Kept for history, excluded from the daily flow"],
        ["download/README.md", "The runbook", "Documents the layout and the Friday protocol"],
    ],
    [0.30, 0.24, 0.46]))
story.append(Spacer(1, 6))
story.append(Paragraph("Table 4 - The reorganized download/ layout.", S["caption"]))
story.append(Spacer(1, 12))

# ── 6. The Application Tracker ───────────────────────────────────────
story += h1_block(6, "The Application Tracker", "perfect files · the funnel file")
story.append(P(
    "Tracker design advice is remarkably consistent across eztrackr, BeamJobs, Indeed, and the Reddit "
    "template threads. The spreadsheet is the external brain: it answers \"did I already apply here?\", "
    "it holds follow-up promises, and after a few weeks it starts producing strategic insights - which "
    "resume version gets callbacks, which boards send quality leads, where effort actually pays. The "
    "status column is called out as the MVP: a one-glance command center that only means something if "
    "it is updated, which is why the stage list is short and the Friday review exists. One row per "
    "posting, keyed by a hash of the posting URL, prevents the classic double-application mistake."))
story.append(P(
    "The tracker shipped with this task implements the researched column set and seeds it from the "
    "2026-10-14 pipeline run: 46 postings, each with company, role, city, source, transit class, "
    "first-seen date, and a stable URL hash. Status is a validated dropdown; the applied-date field "
    "drives the follow-up formula; a one-to-five fit score marks the shortlist. Two design choices "
    "follow the portability argument in the tool-comparison literature: the file is a plain XLSX with "
    "a CSV twin - no subscription, no lock-in, formats that outlive any vendor - and the workbook is "
    "committed to git on every change, the same durability rule the mail-channel escrow follows."))
story.append(Spacer(1, 18))
story.append(make_table(
    ["Column group", "Columns", "Purpose"],
    [
        ["Identity", "id, company, role, city, url", "Dedupe by URL hash; one row per posting"],
        ["Provenance", "source, transit, first_seen", "Source-yield analytics; freshness tracking"],
        ["Status (MVP)", "status", "Funnel stage; validated dropdown, conditional colors"],
        ["Dates", "applied_date, followup_due", "Cadence made executable (+7 d formula)"],
        ["Priority", "fit", "1-5; the tailoring budget goes to the top rows"],
        ["Materials", "notes", "Contact person, resume version, outcome notes"],
    ],
    [0.22, 0.36, 0.42]))
story.append(Spacer(1, 6))
story.append(Paragraph("Table 5 - Tracker columns and their rationale (research/3-a B2).", S["caption"]))
story.append(Spacer(1, 12))

# ── 7. The Friday Review Loop ────────────────────────────────────────
story += h1_block(7, "The Friday Review Loop", "methodology · closing the system")
story.append(P(
    "The data-driven search guides agree on the operating cadence: review the tracker weekly, read "
    "conversion by stage and by source, and shift effort toward what produces interviews. Resumly's "
    "analytics guide recommends exporting the tracker every Friday and adjusting keywords or target "
    "companies from what the numbers say; LinkedIn's tracking guide says the same in plainer words - "
    "spot trends, understand what works, move effort. Without this loop the tracker is a diary; with "
    "it, the funnel becomes a feedback system."))
story.append(P(
    "The Funnel sheet in the shipped workbook computes the review automatically: stage counts, the "
    "two conversion benchmarks (applied-to-interview at roughly 12 percent per the base rates, "
    "interview-to-offer around one in four), overdue follow-ups against today's date, and per-source "
    "yield as rows, active rows, and shortlisted rows. The ten-minute Friday protocol, documented in "
    "both the workbook's Playbook sheet and the download README: clear overdue follow-ups first; "
    "review every discovered row and either shortlist or close it, never let them pile; read the two "
    "conversion rates and act on the leaking stage, not the loudest problem; demote any source with "
    "zero shortlisted rows after three weeks; then commit the tracker to git. The commit step matters "
    "more than it looks - the tracker is the only file in the system whose history cannot be "
    "regenerated from the pipeline database."))

# ── 8. Germany Junior-IT Reality Check ───────────────────────────────
story += h1_block(8, "Germany Junior-IT Reality Check", "calibration · the local market")
story.append(P(
    "One r/Germany_Jobs post documents a complete junior IT search with unusual honesty: eleven "
    "months, 12.5 applications per month at 40-60 minutes each, five interviews (7.1 percent of "
    "applications), three of the five killed at the HR screen, and finally an offer. The arithmetic "
    "matches the international base rates almost exactly, which is reassuring: the funnel math is not "
    "American folklore, it holds in the German market. The same thread's comment section and the "
    "Germany-specific guides converge on 3-6 months as a normal search duration, and on 3-5 hours per "
    "tailored application when the Anschreiben is written properly."))
story.append(Spacer(1, 8))
story.append(stat_row([
    ("11 mo", "logged duration of a real junior IT search"),
    ("12.5", "applications per month sustained"),
    ("7.1%", "application-to-interview rate achieved"),
    ("3-6 mo", "considered normal in Germany (niv-now)"),
]))
story.append(Spacer(1, 14))
story.append(P(
    "The strategic implication for this project is the division of labor the architecture already "
    "encodes. The pipeline does the volume work - seventeen sources, hard filters for full-time roles "
    "without Ausbildung requirements, a 50-kilometer transit-feasibility ring, a fourteen-day window - "
    "so the human tailoring budget of 3-5 hours per application is spent only on shortlisted rows "
    "rather than sprayed across a hundred portals. The tracker then measures whether that budget "
    "converts. Quality-over-quantity advice (Forbes 2025) and the German volume reality are not in "
    "conflict: the correct synthesis is qualified volume, a hard-filtered feed feeding a deliberately "
    "small shortlist."))

# ── 9. Gap Analysis ──────────────────────────────────────────────────
story += h1_block(9, "Gap Analysis: What the Toolkit Covers", "implementation map · task 21")
story.append(P(
    "The research lands on a project that already implements roughly half of it. The naming convention, "
    "source attribution, daily cadence, hard filters, and backup regime predate this task; the funnel "
    "tracker, the follow-up automation, the documented file layout, and the weekly-review instrumentation "
    "are new. The table below records the mapping, including what changed in Task 21 and what remains "
    "deliberately open."))
story.append(Spacer(1, 18))
story.append(make_table(
    ["Research recommendation", "Status before", "Task 21 action"],
    [
        ["Track stages, compute conversion (A1-A2)", "Job memory tracked postings seen, not a funnel",
         "Tracker XLSX+CSV with status funnel, pre-seeded (46 rows)"],
        ["Apply inside 48 h (A3)", "Daily cadence existed; freshness not surfaced",
         "first_seen column + digest new-flags carried into tracker"],
        ["Follow up at 5-7 business days (A4)", "Nothing", "followup_due formula + overdue counter on "
         "Funnel sheet"],
        ["Weekly Friday review (A5)", "Nothing scheduled", "Funnel metrics sheet + protocol in Playbook "
         "and README"],
        ["YYYY-MM-DD names, no special chars (B1)", "Already compliant", "Convention documented in "
         "download README"],
        ["Folders by date/kind + pointers (B3)", "Gap: 35 files flat at root, 1-line README",
         "daily/, reports/, tracker/, archive/ + idempotent organizer wired into the pipeline"],
        ["Source attribution (B5)", "Already: source column everywhere", "Feeds Funnel sheet yield table"],
        ["Long-horizon durability (B4)", "Git bundles v1-v8", "Tracker committed to git on every change"],
    ],
    [0.34, 0.30, 0.36], font_size=9))
story.append(Spacer(1, 6))
story.append(Paragraph("Table 6 - Research recommendations mapped to toolkit status (A/B references "
                       "point to research/3-a/findings.md).", S["caption"]))
story.append(Spacer(1, 12))
story.append(P(
    "Two gaps remain open on purpose. The durable x0.at mirror for large backup bundles is still "
    "blocked by a datacenter IP ban and needs a residential-IP retry, unchanged from the Task 20 note. "
    "And the tracker itself is a discipline, not a daemon: the pipeline can fill it every morning, but "
    "only the Friday review turns rows into decisions. The evidence says that review is where the "
    "search is actually won - everything else in this report is scaffolding for it."))
story.append(Spacer(1, 10))
story.append(Paragraph(
    "Sources: St. Louis Fed On the Economy (2017); The Interview Guys 2025 via askcruit.com; Select "
    "Software Reviews 2025; eztrackr.app (2025); CESSDA DMEG / UK Data Service; University of Washington "
    "Records Management; metaintro (2026); Indeed, The Muse, Handshake, Frontline Source Group; "
    "r/Germany_Jobs; niv-now.com; germanycareercoach.com; Forbes (2025). Full evidence trail with URLs "
    "in research/3-a/findings.md and raw captures in research/3-a/raw/.", S["caption"]))

# ------------------------------------------------------------------ build
doc = TocDocTemplate(
    OUT, pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
    title=TITLE, author="Z.ai", creator="Z.ai",
    subject="Internet research on job-search methodology and organizing results into durable files",
)
doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)

from pypdf import PdfReader
n = len(PdfReader(OUT).pages)
print(f"body built: {OUT} ({n} pages)")

