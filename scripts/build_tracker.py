#!/usr/bin/env python3
"""build_tracker.py — Task 21: application-tracker workbook implementing research/3-a.

Blueprint (per xlsx skill quality/pipeline.md):
  Sheet 1 "Tracker"   one row per posting; status funnel; followup_due = applied+7d
                      (research A4: follow up 5-7 business days after applying)
  Sheet 2 "Funnel"    live COUNTIF/SUMPRODUCT metrics for the Friday review (A5)
  Sheet 3 "Playbook"  self-documenting methodology (stage defs, cadence, base rates)
Seeded from download/jobs_latest.csv (2026-10-14 15:05 run, 46 postings), all status
"discovered" — the Friday review is where shortlisting happens.
CSV twin written alongside for portability (research B2: files must outlive tools).
"""
import csv
import hashlib
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, "/home/z/my-project/skills/xlsx")
sys.path.insert(0, "/home/z/my-project/skills/xlsx/templates")

import base  # skill design tokens / style factories
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

base.use_palette_explicit("professional")
from base import (  # noqa: E402  (import after palette switch)
    ACCENT_NEGATIVE, ACCENT_POSITIVE, ACCENT_WARNING, FONT_NAME, HEADER_BOLD,
    NEUTRAL_100, NEUTRAL_0, NEUTRAL_200, NEUTRAL_600, NEUTRAL_900, PRIMARY,
    SECONDARY, auto_fit_columns,
)

OUT_DIR = Path("/home/z/my-project/download/tracker")
STAMP = date.today().isoformat()
XLSX = OUT_DIR / f"application_tracker_{STAMP}.xlsx"
CSV_TWIN = OUT_DIR / f"application_tracker_{STAMP}.csv"
SEED = Path("/home/z/my-project/download/jobs_latest.csv")

STATUSES = ["discovered", "shortlisted", "applied", "interviewing", "offer", "closed", "rejected"]
HEADERS = ["id", "company", "role", "city", "source", "transit", "first_seen",
           "status", "applied_date", "followup_due", "fit", "url", "notes"]
N = len(HEADERS)                      # 13 data columns, B..N
FIRST_COL, DATA_START = 2, 5

# ---------------------------------------------------------------- seed rows
def load_seed():
    rows = []
    with open(SEED, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            fs = r.get("date_posted") or ""
            try:
                fs_date = datetime.strptime(fs, "%Y-%m-%d").date() if fs else None
            except ValueError:
                fs_date = None
            url = r.get("url", "")
            rows.append({
                "id": hashlib.sha1(url.encode()).hexdigest()[:10] if url else "",
                "company": (r.get("company") or "").strip()[:80],
                "role": (r.get("title") or "").strip()[:100],
                "city": (r.get("city") or "").strip()[:40],
                "source": (r.get("source") or "").strip()[:20],
                "transit": (r.get("transit") or "").strip()[:20],
                "first_seen": fs_date,
                "url": url[:160],
            })
    return rows


def style_title(ws, text, last_col, caption=None):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.row_dimensions[1].height = 15
    ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=last_col)
    c = ws.cell(row=2, column=2, value=text)
    c.font = Font(name=FONT_NAME, size=16, bold=HEADER_BOLD, color=PRIMARY)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 32
    if caption:
        ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=last_col)
        cc = ws.cell(row=3, column=2, value=caption)
        cc.font = Font(name=FONT_NAME, size=9, color=NEUTRAL_600)
        cc.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[3].height = 8


def style_header(ws, row, headers):
    fill = PatternFill("solid", fgColor=PRIMARY)
    for i, h in enumerate(headers, FIRST_COL):
        c = ws.cell(row=row, column=i, value=h)
        c.fill = fill
        c.font = Font(name=FONT_NAME, size=11, bold=HEADER_BOLD, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = base.Border(bottom=base.Side(style="thin", color=NEUTRAL_200))
    ws.row_dimensions[row].height = 28


# ---------------------------------------------------------------- sheet 1
def build_tracker(wb, rows):
    ws = wb.active
    ws.title = "Tracker"
    last_col = FIRST_COL + N - 1                       # 14 = N
    style_title(ws, "FISI Job Search Tracker — Application Funnel", last_col,
                f"seeded {STAMP} from download/jobs_latest.csv (2026-10-14 15:05 run) · "
                f"followup_due = applied_date + 7 d · statuses per research/3-a A1")
    style_header(ws, 4, HEADERS)

    date_fmt = "YYYY-MM-DD"
    for i, r in enumerate(rows):
        row = DATA_START + i
        fill = PatternFill("solid", fgColor=NEUTRAL_0 if i % 2 == 0 else NEUTRAL_100)
        vals = [r["id"], r["company"], r["role"], r["city"], r["source"], r["transit"],
                r["first_seen"], "discovered", None, None, None, r["url"], None]
        for j, v in enumerate(vals, FIRST_COL):
            c = ws.cell(row=row, column=j, value=v)
            c.fill = fill
            c.font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
            c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=(j in (3, 4, 13)))
        ws.cell(row=row, column=FIRST_COL + 6).number_format = date_fmt          # H first_seen
        ws.cell(row=row, column=FIRST_COL + 6).alignment = Alignment(horizontal="center", vertical="center")
        st = ws.cell(row=row, column=FIRST_COL + 7)                              # I status
        st.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row, column=FIRST_COL + 8).number_format = date_fmt          # J applied_date
        ws.cell(row=row, column=FIRST_COL + 8).alignment = Alignment(horizontal="center", vertical="center")
        kf = ws.cell(row=row, column=FIRST_COL + 9)                              # K followup_due
        kf.value = f'=IF(AND($J{row}<>"",$I{row}="applied"),$J{row}+7,"")'
        kf.number_format = date_fmt
        kf.alignment = Alignment(horizontal="center", vertical="center")
        fit = ws.cell(row=row, column=FIRST_COL + 10)                            # L fit
        fit.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row].height = 22

    last_row = DATA_START + len(rows) - 1
    rng = lambda col: f"{col}{DATA_START}:{col}{last_row}"                       # noqa: E731

    # status dropdown (spare rows included so the tracker grows cleanly)
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"',
                        allow_blank=True, showDropDown=False)
    dv.error = "Pick a status from the list"
    ws.add_data_validation(dv)
    dv.add(f"I{DATA_START}:I200")
    dv2 = DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True)
    dv2.error = "fit is 1 (low) .. 5 (top pick)"
    ws.add_data_validation(dv2)
    dv2.add(f"L{DATA_START}:L200")

    # conditional formatting — accent colors only (design.md §8.2)
    ws.conditional_formatting.add(
        rng("I"), FormulaRule(formula=[f'$I{DATA_START}="applied"'],
                              fill=PatternFill("solid", bgColor="FEF9E7"),
                              font=Font(color=ACCENT_WARNING)))
    ws.conditional_formatting.add(
        rng("I"), FormulaRule(formula=[f'OR($I{DATA_START}="interviewing",$I{DATA_START}="offer")'],
                              fill=PatternFill("solid", bgColor="E8F5E9"),
                              font=Font(color=ACCENT_POSITIVE)))
    # overdue follow-up: applied + followup_due in the past
    ws.conditional_formatting.add(
        rng("K"), FormulaRule(formula=[f'AND($I{DATA_START}="applied",$K{DATA_START}<>"",$K{DATA_START}<TODAY())'],
                              font=Font(color=ACCENT_NEGATIVE, bold=True)))

    ws.freeze_panes = "D5"
    ws.auto_filter.ref = f"B4:{get_column_letter(last_col)}{last_row}"
    auto_fit_columns(ws, min_width=8, max_width=34, header_row=4, data_start_row=DATA_START)
    ws.column_dimensions[get_column_letter(FIRST_COL + 11)].width = 34   # url
    ws.column_dimensions[get_column_letter(FIRST_COL + 12)].width = 28   # notes
    return last_row


# ---------------------------------------------------------------- sheet 2
def build_funnel(wb, rows, last_data_row):
    ws = wb.create_sheet("Funnel")
    last_col = 5
    style_title(ws, "Funnel Metrics — Friday Review", last_col,
                "live formulas over the Tracker sheet · research/3-a A5: review weekly, "
                "shift effort toward what produces interviews")
    TR = f"Tracker!$I${DATA_START}:$I${last_data_row}"
    TF = f"Tracker!$F${DATA_START}:$F${last_data_row}"
    TK = f"Tracker!$K${DATA_START}:$K${last_data_row}"

    style_header(ws, 4, ["metric", "value", "", "target / reading"])
    ws.merge_cells("E4:E4")
    metrics = [
        ("postings in tracker", f"=COUNTA(Tracker!$B${DATA_START}:$B${last_data_row})",
         "top of funnel = pipeline input"),
        ("discovered (unreviewed)", f'=COUNTIF({TR},"discovered")', "review these Friday → shortlist or close"),
        ("shortlisted", f'=COUNTIF({TR},"shortlisted")', "tailoring budget goes here (3–5 h/app in DE)"),
        ("applied", f'=COUNTIF({TR},"applied")', ""),
        ("interviewing", f'=COUNTIF({TR},"interviewing")', ""),
        ("offer", f'=COUNTIF({TR},"offer")', ""),
        ("closed / rejected", f'=COUNTIF({TR},"closed")+COUNTIF({TR},"rejected")', "keep for conversion math"),
        ("follow-ups OVERDUE", f'=SUMPRODUCT(({TR}="applied")*({TK}<>"")*({TK}<TODAY()))',
         "0 = on-cadence (5–7 d rule)"),
        ("conversion: applied→interview+", f'=IFERROR((COUNTIF({TR},"interviewing")+COUNTIF({TR},"offer"))/COUNTIF({TR},"applied"),0)',
         "benchmark ~12% (4 of 32); below → fix resume/top-of-funnel"),
        ("conversion: interview+→offer", f'=IFERROR(COUNTIF({TR},"offer")/(COUNTIF({TR},"interviewing")+COUNTIF({TR},"offer")),0)',
         "below ~20% → practice interviews, not more applications"),
    ]
    r = 5
    for i, (label, formula, note) in enumerate(metrics):
        fill = PatternFill("solid", fgColor=NEUTRAL_0 if i % 2 == 0 else NEUTRAL_100)
        ws.cell(row=r, column=2, value=label).font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
        v = ws.cell(row=r, column=3, value=formula)
        v.font = Font(name=FONT_NAME, size=11, bold=HEADER_BOLD, color=PRIMARY)
        v.alignment = Alignment(horizontal="right", vertical="center")
        v.number_format = "0.0%" if "conversion" in label else "0"
        ws.cell(row=r, column=5, value=note).font = Font(name=FONT_NAME, size=9, color=NEUTRAL_600)
        for col in (2, 3, 4, 5):
            ws.cell(row=r, column=col).fill = fill
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=last_col)
        ws.row_dimensions[r].height = 22
        r += 1

    # source yield block
    r += 1
    src_row = r
    ws.cell(row=r, column=2, value="source").fill = PatternFill("solid", fgColor=SECONDARY)
    ws.cell(row=r, column=3, value="rows").fill = PatternFill("solid", fgColor=SECONDARY)
    ws.cell(row=r, column=4, value="active").fill = PatternFill("solid", fgColor=SECONDARY)
    ws.cell(row=r, column=5, value="shortlisted").fill = PatternFill("solid", fgColor=SECONDARY)
    for col in range(2, 6):
        c = ws.cell(row=r, column=col)
        c.font = Font(name=FONT_NAME, size=11, bold=HEADER_BOLD, color=PRIMARY)
        c.border = base.Border(top=base.Side(style="medium", color=NEUTRAL_200))
    sources = sorted({row["source"] for row in rows if row["source"]})
    r += 1
    for i, s in enumerate(sources):
        fill = PatternFill("solid", fgColor=NEUTRAL_0 if i % 2 == 0 else NEUTRAL_100)
        ws.cell(row=r, column=2, value=s).font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
        ws.cell(row=r, column=3, value=f'=COUNTIF({TF},"{s}")').font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
        ws.cell(row=r, column=4, value=(
            f'=SUMPRODUCT(({TF}="{s}")*({TR}<>"discovered")*({TR}<>"closed")*({TR}<>"rejected"))'
        )).font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
        ws.cell(row=r, column=5, value=f'=SUMPRODUCT(({TF}="{s}")*({TR}="shortlisted"))'
                ).font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
        for col in range(2, 6):
            ws.cell(row=r, column=col).fill = fill
            ws.cell(row=r, column=col).alignment = Alignment(horizontal="right" if col > 2 else "left",
                                                             vertical="center")
        ws.row_dimensions[r].height = 20
        r += 1
    note = ws.cell(row=r + 1, column=2,
                   value="source yield: keep feeding sources with high active/rows ratio; "
                         "demote sources that never produce shortlisted rows (research/3-a B5)")
    note.font = Font(name=FONT_NAME, size=9, color=NEUTRAL_600)
    for col, w in (("B", 34), ("C", 12), ("D", 12), ("E", 46)):
        ws.column_dimensions[col].width = w
    ws.cell(row=src_row, column=2).font = Font(name=FONT_NAME, size=12, bold=HEADER_BOLD, color=PRIMARY)


# ---------------------------------------------------------------- sheet 3
def build_playbook(wb):
    ws = wb.create_sheet("Playbook")
    style_title(ws, "Playbook — How to Run This File", 8,
                "methodology from research/3-a (Cruit funnel, eztrackr columns, "
                "St. Louis Fed timing, Indeed/Muse follow-up cadence)")
    blocks = [
        ("Statuses (the MVP column — update it, everything else computes itself)",
         ["discovered — pulled by the pipeline, not reviewed yet",
          "shortlisted — worth tailoring a real application (the 3–5 h budget goes here)",
          "applied — sent; followup_due auto-fills +7 days (5–7 business-day rule)",
          "interviewing — any human contact; log notes + contact name",
          "offer — negotiate; everything before this was cost",
          "closed — you withdrew or the role died; rejected — they said no. Keep both for funnel math."]),
        ("The weekly loop (Friday, 10 minutes)",
         ["1. Funnel sheet: check follow-ups OVERDUE = 0, send any overdue follow-ups",
          "2. Review every 'discovered' row: shortlist or close — never leave them piling up",
          "3. Read the two conversion rates; act on the LEAKING stage, not the loudest one",
          "4. Source yield: demote sources with zero shortlisted rows after ~3 weeks",
          "5. Commit the file to git (same rule as the escrow — it must never be lost)"]),
        ("Base rates to calibrate against (research/3-a A2)",
         ["~32 applications → 4 interviews → 1 offer (2025 avg; The Interview Guys)",
          "median 68.5 days to first offer; 100–200 applications total is normal",
          "Germany junior IT: 3–6 months is NORMAL; one logged search: 12.5 apps/month for 11 months",
          "apply inside the first 48 h of a posting — 41% of all competition does (St. Louis Fed)",
          "Tue–Thu 8–11 AM sends get the best response; never Friday afternoon"]),
        ("File rules (research/3-a B1–B3)",
         ["one row per posting, keyed by the id hash of the URL — never apply twice",
          "statuses change in place; dates accumulate — the history IS the funnel data",
          "CSV twin ships alongside for tools that outlive Excel; both are committed to git",
          "daily pipeline CSVs in download/daily/ are INPUTS to this file, not a replacement"]),
    ]
    r = 4
    for title, lines in blocks:
        c = ws.cell(row=r, column=2, value=title)
        c.font = Font(name=FONT_NAME, size=12, bold=HEADER_BOLD, color=PRIMARY)
        ws.row_dimensions[r].height = 24
        r += 1
        for ln in lines:
            cc = ws.cell(row=r, column=2, value="• " + ln)
            cc.font = Font(name=FONT_NAME, size=11, color=NEUTRAL_900)
            cc.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
            ws.row_dimensions[r].height = 20
            r += 1
        r += 1
    ws.column_dimensions["B"].width = 20
    for col in "CDEFGH":
        ws.column_dimensions[col].width = 14


def write_csv(rows):
    with open(CSV_TWIN, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADERS)
        for r in rows:
            w.writerow([r["id"], r["company"], r["role"], r["city"], r["source"], r["transit"],
                        r["first_seen"].isoformat() if r["first_seen"] else "",
                        "discovered", "", "", "", r["url"], ""])


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_seed()
    print(f"seed rows: {len(rows)}")
    wb = Workbook()
    last = build_tracker(wb, rows)
    build_funnel(wb, rows, last)
    build_playbook(wb)
    wb.properties.creator = "Z.ai"
    wb.save(XLSX)
    write_csv(rows)
    print(f"wrote {XLSX}")
    print(f"wrote {CSV_TWIN}")


if __name__ == "__main__":
    main()
