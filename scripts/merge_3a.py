#!/usr/bin/env python3
"""merge_3a.py — insert cover as page 0 of body, normalize to A4, write metadata."""
import os
from pypdf import PdfReader, PdfWriter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

A4_W, A4_H = 595.28, 841.89
COVER = f"{BASE}/scripts/out/cover_3a.pdf"
BODY = f"{BASE}/scripts/out/body_3a.pdf"
OUT = f"{BASE}/download/reports/Job_Search_Methodology_and_Results_Organization_2026-10-15.pdf"
TITLE = "Job Search Methodology and Results Organization"


def normalize(page):
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    # tight tolerance: Playwright covers come out at 595.9x842.9 (96dpi rounding)
    # and must be scaled to the exact A4 mediabox of the body (595.28x841.89)
    if abs(w - A4_W) > 0.1 or abs(h - A4_H) > 0.1:
        page.scale_to(A4_W, A4_H)
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (A4_W, A4_H)
    return page


writer = PdfWriter()
writer.add_page(normalize(PdfReader(COVER).pages[0]))
for p in PdfReader(BODY).pages:
    writer.add_page(normalize(p))
writer.add_metadata({
    "/Title": TITLE,
    "/Author": "Z.ai",
    "/Creator": "Z.ai",
    "/Subject": "Internet research on job-search methodology and organizing results into durable files",
})
import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "wb") as f:
    writer.write(f)
n = len(PdfReader(OUT).pages)
print(f"merged: {OUT} ({n} pages)")
