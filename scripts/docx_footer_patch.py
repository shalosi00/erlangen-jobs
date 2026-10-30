#!/usr/bin/env python3
"""Post-process report docx: footer PAGE field format switches + pgNumType cleanup.
Per docx skill references/toc.md (WPS compatibility)."""
import re
import shutil
import sys
import zipfile
from pathlib import Path

path = Path(sys.argv[1])
tmp = path.with_suffix(".tmp.docx")

with zipfile.ZipFile(path) as z:
    names = z.namelist()
    files = {n: z.read(n) for n in names}

doc = files["word/document.xml"].decode("utf-8")

# 0. strip docx-js TOC cached demo entry: inside the paragraph holding the TOC
#    begin+instrText+separate runs, drop every element AFTER the separate run
#    (docx-js emits a nested sample entry there; add_toc_placeholders inserts
#    the real entries after it -> duplicate first line without page number)
try:
    from lxml import etree
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    root = etree.fromstring(files["word/document.xml"])
    for para in root.iter(f"{{{W}}}p"):
        instrs = para.findall(f".//{{{W}}}instrText")
        if not any("TOC" in (i.text or "") for i in instrs):
            continue
        for run in para.findall(f"{{{W}}}r"):
            fc = run.find(f"{{{W}}}fldChar")
            if fc is not None and fc.get(f"{{{W}}}fldCharType") == "separate":
                seen_sep = False
                removed = 0
                for el in list(para):
                    if el is run:
                        seen_sep = True
                        continue
                    if seen_sep:
                        para.remove(el)
                        removed += 1
                print(f"TOC cached demo entry stripped ({removed} elements after separate)")
                break
        break
    files["word/document.xml"] = etree.tostring(root, xml_declaration=True,
                                                encoding="UTF-8", standalone=True)
except ImportError:
    print("lxml missing - skipped TOC demo-entry strip")
doc = files["word/document.xml"].decode("utf-8")

# 1. remove empty pgNumType (confuses WPS on cover section)
doc = doc.replace("<w:pgNumType/>", "")

# 2. map each sectPr's number format -> its footerReference rId
rels = files["word/_rels/document.xml.rels"].decode("utf-8")
rid_to_target = dict(re.findall(r'<Relationship Id="(rId\d+)"[^>]*Target="(footer\d+\.xml)"', rels))

sect_fmts = []  # list of (fmt, [footer files])
for sect in re.findall(r"<w:sectPr[^>]*>.*?</w:sectPr>|<w:sectPr[^>]*/>", doc, re.S):
    m = re.search(r'<w:pgNumType[^>]*w:fmt="([^"]+)"', sect)
    fmt = m.group(1) if m else None
    foots = rid_to_target.get(*(re.findall(r'<w:footerReference[^>]*r:id="(rId\d+)"', sect) or [""])),
    sect_fmts.append((fmt, [rid_to_target[r] for r in re.findall(r'<w:footerReference[^>]*r:id="(rId\d+)"', sect) if r in rid_to_target]))

patched = []
for fmt, foots in sect_fmts:
    if not fmt or not foots:
        continue
    switch = "ROMAN" if "oman" in fmt.lower() else "arabic"
    for f in set(foots):
        key = f"word/{f}"
        if key not in files:
            continue
        xml = files[key].decode("utf-8")
        new = re.sub(r"(<w:instrText[^>]*>)\s*PAGE\s*(</w:instrText>)",
                     rf"\1 PAGE \\* {switch} \\* MERGEFORMAT \2", xml)
        if new != xml:
            files[key] = new.encode("utf-8")
            patched.append((f, switch))

files["word/document.xml"] = doc.encode("utf-8")
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
    for n in names:
        z.writestr(n, files[n])
shutil.move(tmp, path)
print("patched footers:", patched or "none (check refs)")
print("pgNumType empty removed OK" if "<w:pgNumType/>" not in doc else "WARNING: empty pgNumType remains")
