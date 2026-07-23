#!/usr/bin/env python3
"""
Extract the GE driving-system spare-parts book (a binary Word .doc) and merge
it into the interactive catalog as chapter 600.

The .doc is an OLE2 (Composite Document) file. LibreOffice is not required:
text is read straight from the WordDocument piece table, and the drawings are
pulled as PNG blobs from the Data stream. Drawings are mapped to sections by
counting inline-picture anchors (0x01) per section — pictures and anchors are
both stored in document order, so the per-section counts slice the ordered
picture list exactly.

Outputs:
  - appends chapter 600 + its sections to catalog/data/parts.js
  - writes catalog/drawings/600-*.png
  - writes catalog/data/all_part_numbers.csv (all unique catalog numbers)

Usage:
  pip install olefile
  python3 tools/extract_ge.py ["NTE200 GE备件手册20230805.doc"]
"""
import os, re, sys, json, struct, glob, csv
import olefile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS = os.path.join(ROOT, "catalog", "data", "parts.js")
DRAW_DIR = os.path.join(ROOT, "catalog", "drawings")
CSV_OUT = os.path.join(ROOT, "catalog", "data", "all_part_numbers.csv")

CJK = re.compile(r"[一-鿿]")
HDR = re.compile(r"^(\d{3}-\d{4}-\d{3})\s+(.*)")
PN = re.compile(r"^[0-9A-Z][0-9A-Z\-./]{4,}$")


# ---- read WordDocument text via the piece table ----
def doc_text(ole):
    wd = ole.openstream("WordDocument").read()
    flags = struct.unpack_from("<H", wd, 0x0A)[0]
    tname = "1Table" if (flags & 0x0200) else "0Table"
    if not ole.exists(tname):
        tname = "0Table" if tname == "1Table" else "1Table"
    tbl = ole.openstream(tname).read()
    fcClx = struct.unpack_from("<I", wd, 0x01A2)[0]
    lcbClx = struct.unpack_from("<I", wd, 0x01A6)[0]
    clx = tbl[fcClx:fcClx + lcbClx]
    i, plc = 0, None
    while i < len(clx):
        if clx[i] == 0x01:
            cb = struct.unpack_from("<H", clx, i + 1)[0]
            i += 3 + cb
        elif clx[i] == 0x02:
            lcb = struct.unpack_from("<I", clx, i + 1)[0]
            plc = clx[i + 5:i + 5 + lcb]
            break
        else:
            i += 1
    if plc is None:
        raise SystemExit("piece table not found")
    n = (len(plc) - 4) // 12
    cps = [struct.unpack_from("<I", plc, k * 4)[0] for k in range(n + 1)]
    out = []
    for k in range(n):
        pcd = plc[4 * (n + 1) + k * 8: 4 * (n + 1) + k * 8 + 8]
        fc = struct.unpack_from("<I", pcd, 2)[0]
        comp = bool(fc & 0x40000000)
        fc &= 0x3FFFFFFF
        cch = cps[k + 1] - cps[k]
        if comp:
            out.append(wd[fc // 2: fc // 2 + cch].decode("cp1252", "replace"))
        else:
            out.append(wd[fc: fc + cch * 2].decode("utf-16-le", "replace"))
    return "".join(out)


def clean_title(rest):
    rest = rest.strip().rstrip(".").strip()
    zh = "".join(re.findall(r"[一-鿿（）()0-9．\.、/\-]+", rest)).strip()
    m = re.search(r"[A-Za-z].*", rest)
    en = m.group(0).strip().rstrip(".").strip() if m else ""
    return zh, en


def is_pn(s):
    return bool(PN.match(s) and re.search(r"\d", s) and not re.fullmatch(r"\d{1,3}", s))


def parse_sections(text):
    paras = [re.sub(r"\s+", " ", p).strip()
             for p in text.replace("\x0b", "\n").replace("\x07", "\n").split("\r")]
    sections, order, cur, intable = {}, [], None, False
    for p in paras:
        if not p:
            continue
        m = HDR.match(p)
        if m:
            code = m.group(1)
            if code not in sections:
                zh, en = clean_title(m.group(2))
                sections[code] = {"code": code, "zh": zh, "en": en, "tok": []}
                order.append(code)
            cur, intable = code, False
            continue
        if cur is None:
            continue
        if ("PART NO" in p) or ("件号" in p and "序号" in p):
            intable = True
            continue
        if intable:
            sections[cur]["tok"].append(p)

    result = []
    for code in order:
        toks = sections[code]["tok"]
        parts, i = [], 0
        while i < len(toks):
            if is_pn(toks[i]):
                pn = toks[i]
                # A row is [NC] REF [QTY] PART-NO ZH EN, one field per token.
                # Collect the short leading tokens before the part number; the
                # QTY may be a count OR "AR" (As Required) and may be absent,
                # and the REF may carry a letter suffix (e.g. "4A"). Handling all
                # of these keeps every listed position (no gaps in the numbers).
                lead = []
                k = i - 1
                while k >= 0 and re.fullmatch(r"\d{1,4}|AR|A/R|\d{1,3}[A-Z]|[A-Z]{1,3}\d{1,3}[A-Z]?", toks[k]):
                    lead.insert(0, toks[k]); k -= 1
                    if len(lead) >= 3:
                        break
                nc = ref = qty = ""
                while lead and re.match(r"[A-Z]", lead[0]) and not re.fullmatch(r"AR|A/R", lead[0]):
                    nc += lead.pop(0)                       # kit/note code (K01, AA…)
                if lead and re.fullmatch(r"\d{1,3}[A-Z]?", lead[0]):
                    ref = lead.pop(0)                        # position, maybe "4A"
                if lead and re.fullmatch(r"\d{1,4}|AR|A/R", lead[0]):
                    qty = lead.pop(0)
                zh = en = ""
                j = i + 1
                if j < len(toks) and CJK.search(toks[j]):
                    zh = toks[j]; j += 1
                if j < len(toks) and re.search(r"[A-Za-z]", toks[j]) and not CJK.search(toks[j]) and not is_pn(toks[j]):
                    en = toks[j]; j += 1
                lvl = 1 if re.match(r"[·•]", (zh or en)) else 0
                parts.append({"nc": nc, "ref": ref, "qty": qty, "pn": pn,
                              "zh": zh.lstrip("·• ").strip(), "en": en.lstrip("·• ").strip(), "lvl": lvl})
                i = j
            else:
                i += 1
        result.append({"code": code, "zh": sections[code]["zh"],
                       "en": sections[code]["en"], "parts": parts})
    return result


def anchors_per_section(text, codes):
    """Count inline-picture anchors (0x01) inside each section, in order."""
    pos = [text.find(c) for c in codes] + [len(text)]
    return [text[pos[i]:pos[i + 1]].count("\x01") for i in range(len(codes))]


def extract_pngs(ole):
    d = ole.openstream("Data").read()
    sig = b"\x89PNG\r\n\x1a\n"
    offs, i = [], 0
    while True:
        j = d.find(sig, i)
        if j < 0:
            break
        offs.append(j); i = j + 1
    blobs = []
    for o in offs:
        e = d.find(b"IEND", o)
        blobs.append(d[o: e + 8] if e > 0 else d[o:])
    return blobs


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        cand = glob.glob(os.path.join(ROOT, "*GE*.doc")) + glob.glob(os.path.join(ROOT, "*.doc"))
        if not cand:
            raise SystemExit("GE .doc not found; pass its path as an argument")
        src = cand[0]
    ole = olefile.OleFileIO(src)
    text = doc_text(ole)
    secs = parse_sections(text)
    codes = [s["code"] for s in secs]

    counts = anchors_per_section(text, codes)
    pngs = extract_pngs(ole)
    ole.close()

    # map ordered pictures to sections by anchor counts (exact when they sum to len)
    if sum(counts) != len(pngs):
        print("WARN: anchor count %d != picture count %d; mapping proportionally"
              % (sum(counts), len(pngs)))
    os.makedirs(DRAW_DIR, exist_ok=True)
    idx = 0
    for s, cnt in zip(secs, counts):
        s["images"] = []
        take = min(cnt, len(pngs) - idx)
        for n in range(take):
            fname = "%s-%d.png" % (s["code"], n + 1)
            with open(os.path.join(DRAW_DIR, fname), "wb") as fh:
                fh.write(pngs[idx])
            s["images"].append("drawings/" + fname)
            idx += 1
        print("  %-14s %-18s pics=%d parts=%d" % (s["code"], s["en"][:16], take, len(s["parts"])))

    # ---- merge into parts.js ----
    raw = open(DATA_JS, encoding="utf-8").read()
    data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    # drop any previous chapter 600 (idempotent re-runs)
    data["sections"] = [s for s in data["sections"] if s.get("chapter") != "600"]
    data["chapters"] = [c for c in data["chapters"] if c["code"] != "600"]
    data["chapters"].append({"code": "600", "zh": "驱动系统 (GE)", "en": "DRIVING SYSTEM (GE)"})
    for s in secs:
        # the GE book has one combined parts list per section (its several
        # drawings share it), so each section is a single figure
        data["sections"].append({
            "code": s["code"], "chapter": "600", "zh": s["zh"], "en": s["en"],
            "figures": [{"images": s["images"], "parts": s["parts"]}],
        })
    data["stats"] = {"sections": len(data["sections"]),
                     "parts": sum(len(f["parts"]) for s in data["sections"] for f in s["figures"])}
    with open(DATA_JS, "w", encoding="utf-8") as fh:
        fh.write("window.CATALOG = ")
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")

    # ---- unique catalog numbers export ----
    uniq = {}
    for s in data["sections"]:
        for f in s["figures"]:
            for p in f["parts"]:
                if not p["pn"]:
                    continue  # listed position without an orderable catalog number
                u = uniq.setdefault(p["pn"], {"pn": p["pn"], "zh": p["zh"], "en": p["en"],
                                              "secs": set(), "src": set()})
                u["secs"].add(s["code"])
                u["src"].add("GE" if s["chapter"] == "600" else "NTE200")
                if not u["en"] and p["en"]:
                    u["en"] = p["en"]
                if not u["zh"] and p["zh"]:
                    u["zh"] = p["zh"]
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Part No.", "Description (EN)", "Description (ZH)", "Source", "Sections"])
        for pn in sorted(uniq):
            u = uniq[pn]
            w.writerow([u["pn"], u["en"], u["zh"], "/".join(sorted(u["src"])),
                        " ".join(sorted(u["secs"]))])

    print("\nGE sections: %d  GE parts: %d  GE drawings: %d"
          % (len(secs), sum(len(s["parts"]) for s in secs), idx))
    print("Catalog totals -> sections: %d  parts: %d"
          % (data["stats"]["sections"], data["stats"]["parts"]))
    print("Unique catalog numbers: %d -> %s" % (len(uniq), os.path.relpath(CSV_OUT, ROOT)))


if __name__ == "__main__":
    main()
