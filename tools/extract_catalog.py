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


_HDR_TOKENS = {"NC", "REF", "QTY", "PART", "NO.", "ZH.", "EN.", "DESC.",
               "注", "序号", "数量", "件号", "中文名称", "英文名称"}
_CJK = re.compile(r"[一-鿿]")


def _is_pn(s):
    """A part number: alphanumeric, at least one digit, long enough that it
    cannot be confused with a REF/QTY count (which are 1-4 digit numbers)."""
    if not re.fullmatch(r"[0-9A-Z][0-9A-Z\-./]{4,}", s):
        return False
    if not re.search(r"\d", s):
        return False
    if re.fullmatch(r"\d{1,4}", s):   # a plain <=4-digit number is a count, not a PN
        return False
    return True


def _cluster_rows(ws):
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
    return [sorted(c["ws"], key=lambda w: w[0]) for c in sorted(clusters, key=lambda c: c["y"])]


def _parse_side(words, side, anchors):
    """Value-based row parsing: locate the part-number token, then read REF/QTY
    to its left and the ZH/EN names to its right. Robust to columns that are
    shifted relative to their header labels."""
    amap = dict(anchors)
    ref_a, qty_a, pn_a = amap.get("ref"), amap.get("qty"), amap.get("pn")
    ws = [w for w in words if (w[0] < 431 if side == "L" else w[0] >= 431)]
    ws = [w for w in ws if w[1] > 137 and w[4] not in _HDR_TOKENS]

    rows = []
    for toks in _cluster_rows(ws):
        # pick the part-number token: prefer one sitting in the PART-NO column
        cands = [w for w in toks if _is_pn(w[4])]
        if pn_a is not None and cands:
            pn_w = min(cands, key=lambda w: abs(w[0] - pn_a))
        else:
            pn_w = cands[0] if cands else None

        if pn_w is None:
            # No part number on this row. If it still starts with a position
            # number (REF) it is a real listed position without an orderable
            # catalog number (e.g. a kit sub-component) — keep it so the list
            # matches the drawing callouts. Otherwise it is a wrapped name.
            nums = [w for w in toks if re.fullmatch(r"\d{1,3}", w[4])]
            if nums and ref_a is not None and abs(nums[0][0] - ref_a) < 24:
                ref = nums[0][4]
                qty = ""
                if len(nums) >= 2 and qty_a is not None and abs(nums[1][0] - qty_a) < 24:
                    qty = nums[1][4]
                used = {id(w) for w in nums[:2]}
                nc = "".join(w[4] for w in toks if re.fullmatch(r"[A-Z]\d?\d?", w[4]) and w[0] < (ref_a - 8))
                name = [w for w in toks if id(w) not in used and not re.fullmatch(r"[A-Z]\d?\d?", w[4])]
                zh = " ".join(w[4] for w in name if _CJK.search(w[4]))
                en = " ".join(w[4] for w in name if re.search(r"[A-Za-z]", w[4]) and not _CJK.search(w[4]))
                if zh or en:
                    rows.append({"nc": nc, "ref": ref, "qty": qty, "pn": "", "zh": zh, "en": en})
                    continue
            rows.append({"cont": " ".join(w[4] for w in toks)})
            continue

        left = [w for w in toks if w[0] < pn_w[0]]
        right = [w for w in toks if w[0] > pn_w[0]]
        # REF is a 1-3 digit; QTY is a count or the marker "AR" (As Required)
        nums = [w for w in left if re.fullmatch(r"\d{1,4}", w[4])]
        ref = qty = ""
        if len(nums) >= 2:
            ref = min(nums, key=lambda w: abs(w[0] - (ref_a or nums[0][0])))[4]
            qty = nums[-1][4]
            if nums[-1][4] == ref and len(nums) >= 2:
                qty = nums[-2][4]
        elif len(nums) == 1:
            # single count: decide REF vs QTY by which column it sits under
            if ref_a is not None and qty_a is not None:
                if abs(nums[0][0] - qty_a) < abs(nums[0][0] - ref_a):
                    qty = nums[0][4]
                else:
                    ref = nums[0][4]
            else:
                ref = nums[0][4]
        if not qty:
            ar = [w for w in left if re.fullmatch(r"AR|A/R", w[4])]
            if ar:
                qty = ar[0][4]
        nc = "".join(w[4] for w in left if re.fullmatch(r"[A-Z]", w[4]))
        zh = " ".join(w[4] for w in right if _CJK.search(w[4]))
        en = " ".join(w[4] for w in right if re.search(r"[A-Za-z]", w[4]) and not _CJK.search(w[4]))
        rows.append({"nc": nc, "ref": ref, "qty": qty, "pn": pn_w[4], "zh": zh, "en": en})
    return rows


def parse_parts(page):
    words = page.get_text("words")
    anchors = _detect_anchors(page)
    rows = _parse_side(words, "L", anchors["L"]) + _parse_side(words, "R", anchors["R"])
    parts = []
    for r in rows:
        if "cont" in r:
            # wrapped name continuation of the previous part
            txt = r["cont"].strip()
            if parts and txt:
                if _CJK.search(txt):
                    parts[-1]["zh"] = (parts[-1]["zh"] + " " + "".join(
                        ch for ch in txt if _CJK.search(ch) or ch in "·• ")).strip()
                lat = " ".join(t for t in txt.split() if re.search(r"[A-Za-z]", t))
                if lat:
                    parts[-1]["en"] = (parts[-1]["en"] + " " + lat).strip()
            continue
        if not r["pn"] and not r["ref"]:
            continue  # nothing identifiable
        zh, en = r["zh"].strip(), r["en"].strip()
        lvl = len(re.match(r"[·•\s]*", (zh or en)).group(0).replace(" ", ""))
        parts.append({
            "nc": r["nc"],
            "ref": r["ref"] if re.fullmatch(r"\d{1,3}", r["ref"]) else "",
            "qty": r["qty"],
            "pn": r["pn"],
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
            current = {"code": code, "zh": zh, "en": en, "pages": []}
            sections.append(current)
        else:
            if not current["zh"] and zh:
                current["zh"] = zh
            if not current["en"] and en:
                current["en"] = en
        current["pages"].append(("T" if is_table else "D", i))

    # A "figure" is a run of drawing pages followed by its parts-table pages
    # (pattern D..T..). Interleaved sections (D T D T) thus split into several
    # figures, each pairing a drawing with exactly the positions listed for it.
    def group_figures(pages):
        figs, cur = [], None
        for kind, pno in pages:
            if kind == "D":
                if cur is None or cur["seen_tab"]:
                    cur = {"draw": [], "tab": [], "seen_tab": False}
                    figs.append(cur)
                cur["draw"].append(pno)
            else:
                if cur is None:
                    cur = {"draw": [], "tab": [], "seen_tab": False}
                    figs.append(cur)
                cur["tab"].append(pno)
                cur["seen_tab"] = True
        return figs

    out_sections = []
    total_parts = 0
    for s in sections:
        code = s["code"]
        chapter = code[:3]
        figures = []
        img_n = 0
        for fig in group_figures(s["pages"]):
            images = []
            for pno in fig["draw"]:
                img_n += 1
                pix = doc[pno].get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE))
                fname = "%s-%d.jpg" % (code, img_n)
                pix.save(os.path.join(OUT_DRAW, fname), jpg_quality=JPEG_QUALITY)
                images.append("drawings/" + fname)
            parts = []
            for pno in fig["tab"]:
                parts.extend(parse_parts(doc[pno]))
            total_parts += len(parts)
            figures.append({"images": images, "parts": parts})
        out_sections.append({
            "code": code, "chapter": chapter, "zh": s["zh"], "en": s["en"],
            "figures": figures,
        })
        np = sum(len(f["parts"]) for f in figures)
        print("  %-9s %-32s figures=%d draws=%d parts=%d" %
              (code, s["en"][:30], len(figures), img_n, np))

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

    ndraw = sum(len(f["images"]) for s in out_sections for f in s["figures"])
    print("\nSections: %d  Parts: %d  Drawings: %d" %
          (len(out_sections), total_parts, ndraw))
    print("Wrote", OUT_DATA)


if __name__ == "__main__":
    main()
