#!/usr/bin/env python3
"""Crop reCAPTCHA 4x4 grid from screenshot into a labeled contact sheet (2x upscale)."""
import sys
from PIL import Image, ImageDraw

src, out = sys.argv[1], sys.argv[2]
# grid bounds in screenshot pixels (from visual inspection of 1280-wide screenshot)
GX0, GY0, GX1, GY1 = 455, 128, 823, 491
im = Image.open(src).convert("RGB")
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
rows = int(sys.argv[4]) if len(sys.argv) > 4 else 4
tw = (GX1 - GX0) / cols
th = (GY1 - GY0) / rows
tile = int(max(tw, th)) + 4
sheet = Image.new("RGB", (cols * tile, rows * tile + 30), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for r in range(rows):
    for c in range(cols):
        box = (int(GX0 + c * tw), int(GY0 + r * th), int(GX0 + (c + 1) * tw), int(GY0 + (r + 1) * th))
        t = im.crop(box).resize((tile - 8, tile - 8), Image.LANCZOS)
        x, y = c * tile + 4, r * tile + 4
        sheet.paste(t, (x, y))
        d.rectangle([x - 2, y - 2, x + tile - 6, y + tile - 6], outline=(255, 0, 0), width=2)
        d.text((x + 4, y + 4), f"r{r+1}c{c+1}", fill=(255, 255, 0))
d.text((8, rows * tile + 8), f"tiles {rows}x{cols} — src={src}", fill=(0, 0, 0))
sheet.save(out)
print(out, sheet.size)
