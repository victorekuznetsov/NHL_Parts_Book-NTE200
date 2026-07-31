#!/usr/bin/env python3
"""
Extract the Cummins QSK50 engine catalog (a folder tree of QuickServe "Option
Detail" PDFs) and merge it into the NTE200 catalog as its own chapters.

Structure of the source: <system>/<subsystem>/<CODE>.pdf, where each PDF is one
assembly — page 0 is the option spec sheet, and the following pages hold an
exploded diagram plus a Russian parts table (№ · Номер по каталогу · Название ·
Кол-во · Dimensions). This differs from the NHL parts books, so it has its own
parser; see .claude/skills/parts-catalog for the shared approach.

Outputs (merged, idempotent — replaces any previous chapter Q*):
  catalog/data/parts.js       -> QSK50 chapters + sections appended
  catalog/drawings/QSK50-*.jpg

Usage:
  pip install pymupdf
  python3 tools/extract_qsk50.py [path/to/extracted/tree | path/to/*.zip]
"""
import os, re, sys, json, glob, zipfile, subprocess, tempfile
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS = os.path.join(ROOT, "catalog", "data", "parts.js")
DRAW_DIR = os.path.join(ROOT, "catalog", "drawings")
RENDER_SCALE = 1.7
JPEG_QUALITY = 82

PN = re.compile(r"[0-9A-Z][0-9A-Z\-]{3,}$")
HDR = {"Каталог", "деталей", "№", "Номер", "по", "каталогу", "Название",
       "Кол-во", "Dimensions", "Genuine", "Cummins", "Parts"}

# Russian names for the English subsystem folders (shown in section subtitles)
SUBSYS_RU = {
    "ACCESSORY DRIVE": "Привод вспомогательных агрегатов",
    "ACCESSORY DRIVE PULLEY": "Шкив привода вспомогательных агрегатов",
    "AFTERCOOLER": "Охладитель наддувочного воздуха",
    "ALTERNATOR": "Генератор",
    "ALTERNATOR DRIVE": "Привод генератора",
    "ALTERNATOR MOUNTING": "Крепление генератора",
    "AUXILIARY COOLING INLET CONNECTION": "Впускной патрубок вспомогательного охлаждения",
    "AUXILIARY COOLING SYSTEM": "Вспомогательная система охлаждения",
    "BARRING DRIVE": "Валоповоротное устройство",
    "BASE COMPONENTS": "Базовые компоненты",
    "CABIN HEATER PLUMBING": "Трубопроводы отопителя кабины",
    "CAM FOLLOWER COVER": "Крышка толкателей",
    "CAMSHAFT GEAR": "Шестерня распредвала",
    "COOLANT LEVEL SWITCH": "Датчик уровня охлаждающей жидкости",
    "CORROSION RESISTOR": "Антикоррозионный фильтр",
    "CORROSION RESISTOR MOUNTING": "Крепление антикоррозионного фильтра",
    "CRANKCASE BREATHER": "Сапун картера",
    "CRANKCASE BREATHER PLUMBING ARRANGEMENT": "Трубопроводы сапуна картера",
    "CYLINDER BLOCK": "Блок цилиндров",
    "CYLINDER BLOCK COOLANT PLUMBING": "Трубопроводы охлаждения блока цилиндров",
    "CYLINDER BLOCK PLUMBING": "Трубопроводы блока цилиндров",
    "DRAIN LOCATION": "Точки слива",
    "ELECTRICAL STARTING ACCESSORIES": "Электрооборудование пуска",
    "ELECTRONIC CONTROL MODULE WIRING HARNESS": "Жгут проводов электронного модуля управления",
    "ENGINE CONTROL MODULE": "Электронный модуль управления двигателем",
    "ENGINE LUBRICATING PRIMER": "Насос предпусковой прокачки масла",
    "ENGINE OIL COOLER": "Масляный радиатор двигателя",
    "ENGINE PISTON": "Поршень",
    "EXHAUST MANIFOLD": "Выпускной коллектор",
    "FAN DRIVE": "Привод вентилятора",
    "FAN DRIVE PLUMBING": "Трубопроводы привода вентилятора",
    "FAN PILOT SPACER": "Проставка ступицы вентилятора",
    "FLYWHEEL": "Маховик",
    "FLYWHEEL HOUSING": "Картер маховика",
    "FLYWHEEL HOUSING PLUMBING": "Трубопроводы картера маховика",
    "FRONT COVER PLUMBING": "Трубопроводы передней крышки",
    "FRONT ENGINE SUPPORT": "Передняя опора двигателя",
    "FRONT ENGINE SUPPORT PLUMBING": "Трубопроводы передней опоры двигателя",
    "FRONT GEAR COVER": "Передняя крышка шестерён",
    "FUEL CONTROL MODULE": "Модуль управления подачей топлива",
    "FUEL DRAIN PLUMBING": "Трубопроводы слива топлива",
    "FUEL FILTER": "Топливный фильтр",
    "FUEL FILTER PLUMBING": "Трубопроводы топливного фильтра",
    "FUEL INLET FITTING": "Впускной штуцер топлива",
    "FUEL PLUMBING": "Топливные трубопроводы",
    "FUEL PUMP": "Топливный насос",
    "FUEL PUMP DRIVE": "Привод топливного насоса",
    "FUEL PUMP PLUMBING": "Трубопроводы топливного насоса",
    "GEAR COVER MOUNTING": "Крепление крышки шестерён",
    "GUARD PACKAGE": "Комплект защитных ограждений",
    "HAND HOLE COVER": "Крышка смотрового люка",
    "LIFTING BRACKET": "Кронштейн подъёма (рым)",
    "LUBRICATING OIL FILTER": "Масляный фильтр",
    "LUBRICATING OIL PUMP": "Масляный насос",
    "OIL FILL ARRANGEMENT": "Горловина заливки масла",
    "OIL FILTER HEAD PLUMBING": "Трубопроводы головки масляного фильтра",
    "OIL LEVEL GAUGE LOCATION": "Указатель уровня масла",
    "OIL PAN": "Масляный поддон",
    "OIL PRESSURE SENSOR": "Датчик давления масла",
    "OIL TEMPERATURE SENSOR LOCATION": "Датчик температуры масла",
    "PERFORMANCE PARTS": "Детали настройки характеристик",
    "PRESSURE TEMPERATURE SENSOR": "Датчик давления и температуры",
    "REFRIGERANT COMPRESSOR": "Компрессор кондиционера",
    "ROCKER LEVER": "Коромысло клапана",
    "STARTING MOTOR": "Стартер",
    "STARTING MOTOR MOUNTING": "Крепление стартера",
    "THERMOSTAT HOUSING": "Корпус термостата",
    "THERMOSTAT HOUSING PLUMBING": "Трубопроводы корпуса термостата",
    "TURBOCHARGER ARRANGEMENT": "Турбокомпрессор (компоновка)",
    "TURBOCHARGER COOLANT PLUMBING": "Трубопроводы охлаждения турбокомпрессора",
    "TURBOCHARGER OIL PLUMBING": "Масляные трубопроводы турбокомпрессора",
    "VALVE COVER": "Крышка клапанов",
    "VIBRATION DAMPER": "Гаситель крутильных колебаний",
    "WATER INLET CONNECTION": "Впускной патрубок охлаждающей жидкости",
    "WATER MANIFOLD": "Водяной коллектор",
    "WATER PUMP": "Водяной насос",
    "WATER PUMP PLUMBING": "Трубопроводы водяного насоса",
}


def decode(name):
    return re.sub(r"#U([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), name)


def reconstruct_tree():
    """Rebuild the PDF tree from the split zip in the repo root; return its dir."""
    z = sorted(glob.glob(os.path.join(ROOT, "sources", "qsk50-engine", "QSK50*.zip"))
               or glob.glob(os.path.join(ROOT, "QSK50*.zip")))
    if not z:
        raise SystemExit("QSK50 source zip not found; pass the extracted dir or zip")
    workdir = tempfile.mkdtemp(prefix="qsk50_")
    combined = os.path.join(workdir, "combined.zip")
    subprocess.run(["zip", "-q", "-s", "0", z[0], "--out", combined],
                   check=True, cwd=ROOT)
    with zipfile.ZipFile(combined) as zf:
        zf.extractall(os.path.join(workdir, "ex"))
    return os.path.join(workdir, "ex")


# ---- table parsing (band-per-part, name assigned to nearest part by y) ----
def parse_page(page):
    ws = [w for w in page.get_text("words")
          if 45 < w[1] < 805 and w[4] not in HDR and ord(w[4][0]) < 0xE000
          and not w[4].startswith("http") and not re.match(r"\d+/\d+$", w[4])]
    pns = sorted([w for w in ws if 105 < w[0] < 225 and PN.match(w[4])], key=lambda w: w[1])
    if not pns:
        return []
    buckets = [dict(ref=[], qty=[], name=[], dim=[]) for _ in pns]
    for w in ws:
        if 105 < w[0] < 225 and PN.match(w[4]):
            continue
        b = buckets[min(range(len(pns)), key=lambda i: abs(pns[i][1] - w[1]))]
        if w[0] < 105 and re.fullmatch(r"\d{1,3}", w[4]):
            b["ref"].append(w)
        elif 340 < w[0] < 430 and re.fullmatch(r"\d{1,4}", w[4]):
            b["qty"].append(w)
        elif 220 < w[0] < 345:
            b["name"].append(w)
        elif w[0] >= 430:
            b["dim"].append(w)
    out = []
    for pw, b in zip(pns, buckets):
        out.append({
            "nc": "", "lvl": 0, "pn": pw[4],
            "ref": "".join(w[4] for w in b["ref"]),
            "qty": (sorted(b["qty"], key=lambda w: w[0])[0][4] if b["qty"] else ""),
            "zh": " ".join(w[4] for w in sorted(b["name"], key=lambda w: (w[1], w[0]))),
            "en": " ".join(w[4] for w in sorted(b["dim"], key=lambda w: (w[1], w[0]))),
        })
    return out


def option_name_ru(doc):
    lines = [l.strip() for l in doc[0].get_text().splitlines() if l.strip()]
    try:
        i = lines.index("Дата")
    except ValueError:
        return ""
    ru, j = [], i + 2  # skip the code line
    while j < len(lines) and lines[j] != "Не" and not lines[j].startswith("Не пред"):
        ru.append(lines[j]); j += 1
    return " ".join(ru)


def save_drawing(doc, code):
    """Prefer the embedded exploded diagram; else render the first content page."""
    best = None
    for i in range(1, doc.page_count):
        for img in doc[i].get_images(full=True):
            try:
                pix = fitz.Pixmap(doc, img[0])
            except Exception:
                continue
            area = pix.width * pix.height
            if area > 200000 and (best is None or area > best[0]):
                best = (area, pix, i)
    fname = "QSK50-%s-1.jpg" % code
    path = os.path.join(DRAW_DIR, fname)
    if best:
        pix = best[1]
        if pix.n >= 5 or pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(path, jpg_quality=JPEG_QUALITY)
    else:
        page = doc[1] if doc.page_count > 1 else doc[0]
        page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE)).save(path, jpg_quality=JPEG_QUALITY)
    return "drawings/" + fname


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src and src.lower().endswith(".zip"):
        src = None  # fall through to reconstruct
    tree = src or reconstruct_tree()
    # the archive nests the name twice; the base is the dir holding the numbered
    # system folders, i.e. the one with <system>/<subsystem>/<pdf> below it
    base = None
    for d in sorted(glob.glob(os.path.join(tree, "**"), recursive=True), key=len):
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*", "*", "*.pdf")):
            base = d; break
    if not base:
        raise SystemExit("could not locate system folders under %s" % tree)

    os.makedirs(DRAW_DIR, exist_ok=True)
    chapters, sections = [], []
    seen_chap = {}
    systems = sorted([d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))],
                     key=lambda n: int(re.match(r"\s*(\d+)", n).group(1)) if re.match(r"\s*\d+", n) else 999)
    for sysdir in systems:
        m = re.match(r"\s*(\d+)\s+(.*)", decode(sysdir))
        if not m:
            continue
        snum, sname = int(m.group(1)), m.group(2).strip()
        chap = "Q%02d" % snum
        if chap not in seen_chap:
            seen_chap[chap] = True
            chapters.append({"code": chap, "zh": sname, "en": ""})
        subs = sorted(os.listdir(os.path.join(base, sysdir)),
                      key=lambda n: int(re.match(r"\s*(\d+)", n).group(1)) if re.match(r"\s*\d+", n) else 999)
        for subdir in subs:
            subpath = os.path.join(base, sysdir, subdir)
            if not os.path.isdir(subpath):
                continue
            en_name = re.sub(r"^\s*\d+\s+", "", decode(subdir)).strip()
            for pdf in sorted(glob.glob(os.path.join(subpath, "*.pdf"))):
                pdfcode = os.path.splitext(os.path.basename(pdf))[0].strip()
                # the same assembly is cross-referenced under several systems, so
                # scope the identity by chapter to keep codes/hashes/drawings unique
                uid = "%s-%s" % (chap, pdfcode)
                doc = fitz.open(pdf)
                parts = []
                for i in range(1, doc.page_count):
                    parts.extend(parse_page(doc[i]))
                img = save_drawing(doc, uid)
                ru_sub = SUBSYS_RU.get(en_name.upper(), "")
                zh = option_name_ru(doc) or ru_sub or en_name
                # subtitle keeps both languages: Russian subsystem (unless it just
                # repeats the primary name) + English subsystem + Cummins code
                sub = []
                if ru_sub and ru_sub.lower() != zh.lower():
                    sub.append(ru_sub)
                sub += [en_name, pdfcode]
                sections.append({
                    "code": uid, "chapter": chap,
                    "zh": zh, "en": " · ".join(sub),
                    "figures": [{"images": [img], "parts": parts}],
                })
                doc.close()
                print("  %-4s %-14s %-26s parts=%d" % (chap, pdfcode, en_name[:24], len(parts)))

    # ---- merge ----
    data = json.loads(open(DATA_JS, encoding="utf-8").read()[len("window.CATALOG = "):-2])
    data["sections"] = [s for s in data["sections"] if not str(s["chapter"]).startswith("Q")]
    data["chapters"] = [c for c in data["chapters"] if not str(c["code"]).startswith("Q")]
    data["chapters"].extend(chapters)
    data["sections"].extend(sections)
    data["stats"] = {"sections": len(data["sections"]),
                     "parts": sum(len(f["parts"]) for s in data["sections"] for f in s["figures"])}
    with open(DATA_JS, "w", encoding="utf-8") as fh:
        fh.write("window.CATALOG = ")
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")

    np = sum(len(f["parts"]) for s in sections for f in s["figures"])
    print("\nQSK50: %d chapters, %d assemblies, %d parts, %d drawings"
          % (len(chapters), len(sections), np, len(sections)))
    print("Catalog totals -> sections: %d  parts: %d"
          % (data["stats"]["sections"], data["stats"]["parts"]))


if __name__ == "__main__":
    main()
