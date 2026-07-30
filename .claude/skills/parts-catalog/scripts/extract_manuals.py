#!/usr/bin/env python3
"""
Integrate the NTE200 manuals into the catalog: copy the PDFs into the app and
build a link map so every catalog section can open its repair-manual page.

The repair manual's bookmarks are keyed by catalog section codes (e.g.
"…_020-0040 燃油箱…"), which lets us deep-link each section to its exact page
(browsers honour  file.pdf#page=N). Chapter-overview pages (XXX-0000) give a
fallback for sections without their own chapter.

Outputs:
  catalog/manuals/repair.pdf, operator.pdf, wiring-24v.pdf
  catalog/data/manuals.js  ->  window.MANUALS = {...}

Usage: python3 tools/extract_manuals.py
"""
import os, re, json, shutil
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN_DIR = os.path.join(ROOT, "catalog", "manuals")
OUT = os.path.join(ROOT, "catalog", "data", "manuals.js")

SRC = {
    "repair":   ("NTE200 MAINTAINCE BOOK.pdf", "repair.pdf",
                 "Инструкция по ремонту и ТО", "Руководство по ремонту и обслуживанию NTE200"),
    "operator": ("NTE200 DRIVER'S BOOK.pdf", "operator.pdf",
                 "Руководство оператора", "Инструкция оператора карьерного самосвала NTE200"),
    "wiring":   ("NTE200A 24V DRAWING.pdf", "wiring-24v.pdf",
                 "Электросхема 24В", "Принципиальная электрическая схема 24В (EPLAN)"),
}
GENERAL_RU = {"000-0000": "Введение", "000-0010": "Безопасность",
              "000-0020": "Проверки перед запуском", "000-0030": "Эксплуатация"}


def main():
    os.makedirs(MAN_DIR, exist_ok=True)
    cat = json.loads(open(os.path.join(ROOT, "catalog", "data", "parts.js"),
                          encoding="utf-8").read()[len("window.CATALOG = "):-2])
    # prefer the catalog's English section name for the repair TOC (its zh field
    # is Chinese; the general 000-* chapters get Russian names below)
    name_by_code = {s["code"]: (s["en"] or s["zh"]) for s in cat["sections"]}

    files = []
    for fid, (src, dst, title, desc) in SRC.items():
        shutil.copyfile(os.path.join(ROOT, src), os.path.join(MAN_DIR, dst))
        pages = fitz.open(os.path.join(MAN_DIR, dst)).page_count
        files.append({"id": fid, "title": title, "file": "manuals/" + dst,
                      "pages": pages, "desc": desc})

    # repair manual: map codes/chapters to pages, build a clean chapter list
    doc = fitz.open(os.path.join(ROOT, SRC["repair"][0]))
    by_code, by_chapter, toc, general = {}, {}, [], []
    for lvl, title, pg in doc.get_toc():
        m = re.search(r"(\d{3})-(\d{4})", title)
        if not m:
            continue
        code = "%s-%s" % (m.group(1), m.group(2))
        by_code.setdefault(code, pg)
        if code.endswith("-0000"):
            by_chapter.setdefault(m.group(1), pg)
        raw = re.sub(r".*\d{3}-\d{4}\s*", "", title)          # trailing name
        raw = re.sub(r"[-—]?\s*译文\s*$", "", raw).strip()      # drop "translation"
        name = GENERAL_RU.get(code) or name_by_code.get(code) or raw
        entry = {"code": code, "title": name, "page": pg}
        toc.append(entry)
        if code.startswith("000-"):
            general.append(entry)

    # 24V wiring: diagram-level page index (Chinese schematic names)
    wiring = []
    for lvl, title, pg in fitz.open(os.path.join(ROOT, SRC["wiring"][0])).get_toc():
        if lvl == 3 and re.match(r"\s*\d+\s", title):          # the "=图" children
            wiring.append({"title": title.strip(), "page": pg})

    data = {"files": files, "repairByCode": by_code, "repairByChapter": by_chapter,
            "repairToc": toc, "general": general, "wiring": wiring}
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("window.MANUALS = ")
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")

    print("Copied %d manuals; repair pages for %d section codes, %d chapters; "
          "%d wiring diagrams" % (len(files), len(by_code), len(by_chapter), len(wiring)))
    print("Wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
