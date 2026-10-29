#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge cover + body into the final deliverable PDF."""
from pypdf import PdfReader, PdfWriter

A4_W, A4_H = 595.28, 841.89

def normalize(page):
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    if abs(w - A4_W) > 0.1 or abs(h - A4_H) > 0.1:
        page.scale_to(A4_W, A4_H)
    return page

writer = PdfWriter()
cover = PdfReader("/home/z/my-project/scripts/out/cover.pdf").pages[0]
writer.add_page(normalize(cover))
for p in PdfReader("/home/z/my-project/scripts/out/body.pdf").pages:
    writer.add_page(normalize(p))
writer.add_metadata({
    "/Title": "Programmatic Job Hunting in Germany",
    "/Author": "Z.ai",
    "/Creator": "Z.ai",
    "/Subject": "Verified APIs, feeds and automation recipes for a fast first job in Systemintegration",
})
out = "/home/z/my-project/download/Programmatic_Job_Hunting_Germany_Systemintegration.pdf"
with open(out, "wb") as f:
    writer.write(f)
print("merged ->", out, "pages:", len(writer.pages))
