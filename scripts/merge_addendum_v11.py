#!/usr/bin/env python3
"""Merge cover + body with cover rescaled to exact body A4 dims."""
from pypdf import PdfReader, PdfWriter, Transformation

BODY = "/tmp/addendum_v11_body.pdf"
COVER = "/tmp/cover_v11.pdf"
OUT = "/home/z/my-project/download/FISI_Toolkit_Report_v1.1_Addendum_20261014.pdf"

body = PdfReader(BODY)
cover = PdfReader(COVER)
bw = float(body.pages[0].mediabox.width)
bh = float(body.pages[0].mediabox.height)
cw = float(cover.pages[0].mediabox.width)
ch = float(cover.pages[0].mediabox.height)
p = cover.pages[0]
sx, sy = bw / cw, bh / ch
p.add_transformation(Transformation().scale(sx, sy))
p.mediabox.lower_left = (0, 0)
p.mediabox.upper_right = (bw, bh)

w = PdfWriter()
w.add_page(p)
for pg in body.pages:
    w.add_page(pg)
w.add_metadata({"/Title": "Asha FISI Job-Toolkit - Report v1.1 Addendum",
                "/Author": "Z.ai", "/Creator": "Z.ai",
                "/Subject": "Addendum to the baseline report: sources, transit whitelist, fix campaign, production evidence",
                "/Producer": "http://z.ai"})
with open(OUT, "wb") as f:
    w.write(f)
print("merged:", OUT, f"cover scale sx={sx:.5f} sy={sy:.5f}")
