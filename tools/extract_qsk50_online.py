#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_qsk50_online.py — add the *Cummins online* QSK50 catalog into the NTE200 book.

Source: the QuickServe/online catalog exported for engine serial 33239899
        (model «QSK50 CM2150 MCRS»), stored as window.CATALOGS["33239899"]
        in the sibling Cummins_Parts_Book repository. Unlike the QSK50 book we
        built from the PDF (chapters Q01–Q12, which stay untouched), the online
        catalog carries, for almost every part, the **weight, overall
        dimensions, a photo and the full spec sheet** — exactly the extra data
        the customer asked to bring across.

What this produces, appended to catalog/data/parts.js:
  * 14 new chapters QO01…QO14 — one per Cummins engine system, in catalog order.
  * one section per (system, option); an option shared by several systems is
    listed under each, the same way the PDF book repeats WP6704-14 under
    cooling and pumps. Section code = "<chapter>-<option>", e.g. QO06-WP6704-14.
  * every part keeps a compact `d` block { img, wt, dim, at } with the photo
    file name (served from the Cummins CDN, like the standalone Cummins app),
    the metric weight/size and the cleaned attribute sheet.

Drawings:
  * the 60 sheet PNGs shipped with the online catalog are copied into
    catalog/drawings/ under a QO- prefix and wired to their options.
  * the 40 options the online export ships without a sheet are back-filled from
    the PDF QSK50 book where a matching drawing exists — 29 of them do (exact
    option number first, then the same base number with a different revision).
    The remaining 11 have no drawing in either source and stay drawing-less.

Re-runnable: it strips any existing QO* chapters/sections before re-adding, so
running it twice yields the same file. Prices are NOT touched here — they live
in prices.js and are matched by part number at render time.
"""

import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NHL = os.path.dirname(HERE)
CUM = os.path.join(os.path.dirname(NHL), "Cummins_Parts_Book")
ESN = "33239899"

PARTS_JS = os.path.join(NHL, "catalog", "data", "parts.js")
DRAW_DIR = os.path.join(NHL, "catalog", "drawings")

# Source of the online catalog. Prefer a copy vendored under sources/ (so this
# branch rebuilds without the sibling Cummins repo); fall back to that repo.
SRC_LOCAL = os.path.join(NHL, "sources", "qsk50-online")
if os.path.exists(os.path.join(SRC_LOCAL, ESN + ".js")):
    CUM_DATA = os.path.join(SRC_LOCAL, ESN + ".js")
    CUM_DRAW = os.path.join(SRC_LOCAL, "drawings")
else:
    CUM_DATA = os.path.join(CUM, "data", ESN + ".js")
    CUM_DRAW = os.path.join(CUM, "drawings", ESN)

DRAW_PREFIX = "QO-"                 # prefix for copied online sheets
ATTR_SKIP = {"Length", "Width", "Height", "Weight"}   # imperial dupes of wt/dim


def load_js_object(path, needle):
    """Pull the JSON object assigned right after `needle` out of a *.js data file."""
    raw = open(path, encoding="utf-8").read()
    i = raw.index(needle)
    eq = raw.index("=", i)
    js = raw[eq + 1:].strip()
    if js.endswith(";"):
        js = js[:-1].strip()
    return json.loads(js)


def clean_remarks(s):
    # the online export packs the marketing blurb as "A|B|C"; keep it readable
    return " ".join(part.strip() for part in str(s or "").split("|") if part.strip())


def clean_attrs(attrs):
    out = {}
    for k, v in (attrs or {}).items():
        if k in ATTR_SKIP:
            continue
        if v is None or v == "":
            continue
        if k == "Sellable":
            v = "да" if v == "Y" else "нет"
        out[k] = v
    return out


def pdf_drawing_index():
    """Map option number -> [drawing files] from the PDF QSK50 book already in the repo."""
    by_opt = {}
    for f in os.listdir(DRAW_DIR):
        m = re.match(r"^QSK50-Q\d+-(.+?)-\d+\.jpg$", f, re.I)
        if m:
            by_opt.setdefault(m.group(1), []).append(f)
    for k in by_opt:
        by_opt[k].sort()
    by_base = {}
    for opt, files in by_opt.items():
        by_base.setdefault(re.sub(r"-\d+$", "", opt), []).append(opt)
    return by_opt, by_base


def build():
    cum = load_js_object(CUM_DATA, 'CATALOGS["%s"]' % ESN)
    systems = cum["systems"]
    options = {o["no"]: o for o in cum["options"]}
    cards = cum.get("cards", {}) or {}
    pdf_by_opt, pdf_by_base = pdf_drawing_index()

    if not os.path.isdir(CUM_DRAW):
        sys.exit("Cummins drawings folder not found: " + CUM_DRAW)

    chapters = []
    sys_code = {}
    for i, s in enumerate(systems, 1):
        code = "QO%02d" % i
        sys_code[s["code"]] = code
        chapters.append({"code": code, "zh": s.get("name") or s["code"].title(),
                         "en": s["code"].title()})

    copied = set()
    backfilled = 0
    no_drawing = []

    def images_for(o):
        nonlocal backfilled
        sheets = o.get("sheets") or []
        if sheets:
            imgs = []
            for sh in sheets:
                src = os.path.join(CUM_DRAW, sh)
                dst_name = DRAW_PREFIX + sh
                if sh not in copied:
                    if os.path.exists(src):
                        shutil.copyfile(src, os.path.join(DRAW_DIR, dst_name))
                        copied.add(sh)
                    else:
                        continue
                imgs.append("drawings/" + dst_name)
            return imgs
        # no online sheet — back-fill from the PDF book
        no = o["no"]
        files = pdf_by_opt.get(no)
        if not files:
            base = re.sub(r"-\d+$", "", no)
            alt = pdf_by_base.get(base)
            if alt:
                files = pdf_by_opt.get(sorted(alt)[0])
        if files:
            backfilled += 1
            return ["drawings/" + f for f in files]
        no_drawing.append(no)
        return []

    def build_part(p):
        r = {"nc": "", "lvl": p.get("lvl", 0), "pn": p.get("no", ""),
             "ref": p.get("pos", ""), "qty": p.get("qty", ""),
             "zh": "", "en": p.get("name", "")}
        c = cards.get(p.get("no")) or {}
        d = {}
        img = p.get("img") or c.get("img") or ""
        if img:
            d["img"] = img
        if c.get("wt"):
            d["wt"] = c["wt"]
        if c.get("dim"):
            d["dim"] = c["dim"]
        elif p.get("dim"):
            d["dim"] = p["dim"]
        at = clean_attrs(c.get("attrs"))
        if at:
            d["at"] = at
        if d:
            r["d"] = d
        return r

    sections = []
    for i, s in enumerate(systems, 1):
        ch = "QO%02d" % i
        for no in s["options"]:
            o = options.get(no)
            if not o:
                continue
            rem = clean_remarks(o.get("remarks", ""))
            sections.append({
                "code": ch + "-" + no,
                "chapter": ch,
                "zh": o.get("name") or no,
                "en": no,
                "remarks": rem,
                "figures": [{"images": images_for(o),
                             "parts": [build_part(p) for p in o["parts"]]}],
            })

    return chapters, sections, {
        "copied_sheets": len(copied),
        "backfilled": backfilled,
        "no_drawing": no_drawing,
    }


def merge(chapters, sections):
    D = load_js_object(PARTS_JS, "window.CATALOG")
    D["chapters"] = [c for c in D["chapters"] if not str(c["code"]).startswith("QO")]
    D["sections"] = [s for s in D["sections"] if not str(s["chapter"]).startswith("QO")]
    D["chapters"] += chapters
    D["sections"] += sections
    parts = sum(len(f["parts"]) for s in D["sections"] for f in s["figures"])
    D.setdefault("stats", {})
    D["stats"]["sections"] = len(D["sections"])
    D["stats"]["parts"] = parts
    out = "window.CATALOG = " + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(PARTS_JS, "w", encoding="utf-8").write(out)
    return len(D["chapters"]), len(D["sections"]), parts


def main():
    chapters, sections, info = build()
    nch, nsec, nparts = merge(chapters, sections)
    print("online QSK50 added: %d chapters, %d sections" % (len(chapters), len(sections)))
    print("  sheets copied:      %d" % info["copied_sheets"])
    print("  PDF back-filled:    %d options" % info["backfilled"])
    print("  no drawing at all:  %d -> %s" % (len(info["no_drawing"]), " ".join(info["no_drawing"])))
    print("catalog totals now:   %d chapters, %d sections, %d part rows" % (nch, nsec, nparts))


if __name__ == "__main__":
    main()
