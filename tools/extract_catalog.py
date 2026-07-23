#!/usr/bin/env python3
"""
Extract an interactive catalog (data + drawing images) from the NTE200 Parts Book PDF.

The source PDF is stored in the repository as split zip parts
(``NTE200 PART номера Polyus.zip.001`` .. ``.004``). This script will
reconstruct the PDF from those parts if a plain PDF is not supplied.

Outputs:
  catalog/data/parts.js      -> ``window.CATALOG = {...}`` (works from file://)
  catalog/drawings/<code>-<n>.jpg  -> one rendered image per drawing page

Usage:
  python3 tools/extract_catalog.py [path/to/catalog.pdf]

Dependencies: PyMuPDF (``pip install pymupdf``).
"""
import os
import re
import io
import json
import glob
import sys
import zipfile

import fitz  # PyMuPDF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DATA = os.path.join(ROOT, "catalog", "data", "parts.js")
OUT_DRAW = os.path.join(ROOT, "catalog", "drawings")

RENDER_SCALE = 1.7      # ~120 DPI, good for line drawings
JPEG_QUALITY = 82

# Major chapter names (code prefix -> [zh, en]); from the Table of Contents.
CHAPTERS = {
    "020": ["结构件", "STRUCTURE"],
    "030": ["电气系统", "ELECTRICAL SYSTEM"],
    "040": ["动力系统", "POWER SYSTEM"],
    "050": ["液压系统", "HYDRAULIC SYSTEM"],
    "070": ["行走系统", "RUNNING SYSTEM"],
    "080": ["制动系统", "BRAKE SYSTEM"],
    "090": ["驾驶室", "CAB"],
    "100": ["附属系统", "SUBSIDIARY SYSTEM"],
    "150": ["轮胎和轮辋", "TIRES AND RIMS"],
    "210": ["选装", "OPTIONAL"],
    "220": ["选装", "OPTIONAL"],
}

SEC_RE = re.compile(r"^\s*(\d{3}-\d{4})\b(.*)")
CJK_RE = re.compile(r"[一-鿿]")


def reconstruct_pdf():
    """Rebuild the PDF from split zip parts in the repo root, return a path."""
    parts = sorted(glob.glob(os.path.join(ROOT, "*.zip.0*")))
    if not parts:
        raise SystemExit("No PDF given and no split zip parts (*.zip.0*) found.")
    tmp_zip = os.path.join(ROOT, "tools", "_catalog_combined.zip")
    with open(tmp_zip, "wb") as out:
        for p in parts:
            with open(p, "rb") as fh:
                out.write(fh.read())
    dest = os.path.join(ROOT, "tools", "_catalog_source.pdf")
    with zipfile.ZipFile(tmp_zip) as zf:
        name = [n for n in zf.namelist() if n.lower().endswith(".pdf")][0]
        with zf.open(name) as src, open(dest, "wb") as fh:
            fh.write(src.read())
    os.remove(tmp_zip)
    return dest


# ---- table parsing -------------------------------------------------------

# Fallback column x-anchors per side (used if a page's header row is missing).
_DEFAULT = {
    "L": [("nc", 52), ("ref", 80), ("qty", 108), ("pn", 140), ("zh", 205), ("en", 292)],
    "R": [("nc", 438), ("ref", 466), ("qty", 496), ("pn", 528), ("zh", 595), ("en", 672)],
}
_HDR = {"NC": "nc", "REF": "ref", "QTY": "qty", "PART": "pn", "ZH.": "zh", "EN.": "en"}


def _detect_anchors(page):
    """Column x-positions read from each page's own header row, per side.

    Tables are sometimes shifted horizontally, so fixed anchors are unreliable;
    the header labels track the shift and give per-page anchors."""
    sides = {"L": {}, "R": {}}
    for w in page.get_text("words"):
        if 95 < w[1] < 146 and w[4] in _HDR:
            side = "L" if w[0] < 431 else "R"
            sides[side].setdefault(_HDR[w[4]], w[0])
    out = {}
    for side in ("L", "R"):
        d = sides[side]
        if len(d) >= 5:
            out[side] = [(k, d[k]) for k in ("nc", "ref", "qty", "pn", "zh", "en") if k in d]
        else:
            out[side] = _DEFAULT[side]
    return out


def _col_of(x, anchors):
    return min(anchors, key=lambda a: abs(a[1] - x))[0]


_HDR_TOKENS = {"NC", "REF", "QTY", "PART", "NO.", "ZH.", "EN.", "DESC.",
               "注", "序号", "数量", "件号", "中文名称", "英文名称"}


def _parse_side(words, side, anchors):
    ws = [w for w in words if (w[0] < 431 if side == "L" else w[0] >= 431)]
    # keep rows below the column-label band; drop any stray header labels so the
    # first data row (which can sit close to the header) is not lost
    ws = [w for w in ws if w[1] > 137 and w[4] not in _HDR_TOKENS]
    clusters = []
    for w in sorted(ws, key=lambda w: (w[1], w[0])):
        for c in clusters:
            if abs(c["y"] - w[1]) < 7:
                c["ws"].append(w)
                c["y"] = (c["y"] * c["n"] + w[1]) / (c["n"] + 1)
                c["n"] += 1
                break
        else:
            clusters.append({"y": w[1], "n": 1, "ws": [w]})
    rows = []
    for c in sorted(clusters, key=lambda c: c["y"]):
        cols = {}
        for w in sorted(c["ws"], key=lambda w: w[0]):
            cn = _col_of(w[0], anchors)
            cols.setdefault(cn, []).append(w[4])
        rows.append({k: " ".join(v).strip() for k, v in cols.items()})
    return rows


def parse_parts(page):
    words = page.get_text("words")
    anchors = _detect_anchors(page)
    rows = _parse_side(words, "L", anchors["L"]) + _parse_side(words, "R", anchors["R"])
    parts = []
    for r in rows:
        ref = r.get("ref", "").strip()
        pn = r.get("pn", "").strip()
        zh = r.get("zh", "").strip()
        en = r.get("en", "").strip()

        # a part number column holding several tokens usually means the ref
        # digit and/or a wrapped name spilled into it
        tail = ""
        if " " in pn:
            toks = pn.split()
            if re.fullmatch(r"\d{1,3}", toks[0]) and not ref:
                ref, toks = toks[0], toks[1:]
            pn = toks[0] if toks else ""
            tail = " ".join(toks[1:])
        if tail:
            en = (en + " " + tail).strip()

        # The part number alone decides validity: indented sub-assembly items
        # (·-prefixed) are real orderable parts but often carry no REF number.
        valid_pn = bool(re.fullmatch(r"[0-9A-Z][0-9A-Z\-./]{3,}", pn) and re.search(r"\d", pn))
        if not valid_pn:
            # not a part row: treat as a wrapped-name continuation of the last part
            if parts and (en or zh):
                if zh:
                    parts[-1]["zh"] = (parts[-1]["zh"] + " " + zh).strip()
                if en:
                    parts[-1]["en"] = (parts[-1]["en"] + " " + en).strip()
            continue

        # indentation level = leading middle-dots marking sub-assembly depth
        lvl = len(re.match(r"[·•\s]*", (zh or en)).group(0).replace(" ", ""))
        parts.append({
            "nc": r.get("nc", "").strip(),
            "ref": ref if re.fullmatch(r"\d{1,3}", ref) else "",
            "qty": r.get("qty", "").strip(),
            "pn": pn,
            "zh": zh.lstrip("·• ").strip(),
            "en": en.lstrip("·• ").strip(),
            "lvl": lvl,
        })
    return parts


def parse_header(page):
    """Return (code, zh_title, en_title) from a section page header."""
    txt = page.get_text().strip()
    first = txt.splitlines()[0] if txt else ""
    m = SEC_RE.match(first)
    if not m:
        return None, "", ""
    code = m.group(1)
    rest = m.group(2)
    # strip trailing version/date/ECN tokens
    rest = re.split(r"\s{2,}[A-Z]?\s?\d{8}", rest)[0]
    zh = "".join(re.findall(r"[一-鿿（）()0-9．\.、/\-]+", rest)).strip()
    en_m = re.search(r"[A-Za-z].*", rest)
    en = en_m.group(0).strip() if en_m else ""
    en = re.sub(r"\s*[A-Z]?\d{6,}.*$", "", en).strip()
    return code, zh, en


# ---- main ----------------------------------------------------------------

def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else reconstruct_pdf()
    doc = fitz.open(pdf)
    os.makedirs(OUT_DRAW, exist_ok=True)

    # classify pages and group by section, keeping document order
    sections = []  # list of dicts
    current = None
    for i in range(doc.page_count):
        page = doc[i]
        txt = page.get_text()
        code, zh, en = parse_header(page)
        if code is None:
            continue  # front-matter / TOC page
        is_table = ("件号" in txt and "序号" in txt) or "PART NO" in txt

        if current is None or current["code"] != code:
            current = {"code": code, "zh": zh, "en": en,
                       "draw_pages": [], "table_pages": []}
            sections.append(current)
        else:
            # keep the richest title we have seen
            if not current["zh"] and zh:
                current["zh"] = zh
            if not current["en"] and en:
                current["en"] = en
        (current["table_pages"] if is_table else current["draw_pages"]).append(i)

    # render drawings + parse tables
    out_sections = []
    total_parts = 0
    for s in sections:
        code = s["code"]
        chapter = code[:3]
        images = []
        for n, pno in enumerate(s["draw_pages"], 1):
            pix = doc[pno].get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE))
            fname = "%s-%d.jpg" % (code, n)
            pix.save(os.path.join(OUT_DRAW, fname), jpg_quality=JPEG_QUALITY)
            images.append("drawings/" + fname)
        parts = []
        for pno in s["table_pages"]:
            parts.extend(parse_parts(doc[pno]))
        total_parts += len(parts)
        out_sections.append({
            "code": code,
            "chapter": chapter,
            "zh": s["zh"],
            "en": s["en"],
            "images": images,
            "parts": parts,
        })
        print("  %-9s %-34s draws=%d parts=%d" %
              (code, s["en"][:32], len(images), len(parts)))

    chapter_list = []
    seen = set()
    for s in out_sections:
        c = s["chapter"]
        if c not in seen:
            seen.add(c)
            names = CHAPTERS.get(c, [c, c])
            chapter_list.append({"code": c, "zh": names[0], "en": names[1]})

    data = {
        "title_zh": "NTE200 矿用自卸车 零部件手册",
        "title_en": "NTE200 Mining Truck — Parts Book",
        "maker": "Inner Mongolia North Hauler Joint Stock Co., Ltd (NHL)",
        "chapters": chapter_list,
        "sections": out_sections,
        "stats": {"sections": len(out_sections), "parts": total_parts},
    }

    os.makedirs(os.path.dirname(OUT_DATA), exist_ok=True)
    with open(OUT_DATA, "w", encoding="utf-8") as fh:
        fh.write("window.CATALOG = ")
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")

    print("\nSections: %d  Parts: %d  Drawings: %d" %
          (len(out_sections), total_parts,
           sum(len(s["images"]) for s in out_sections)))
    print("Wrote", OUT_DATA)


if __name__ == "__main__":
    main()
