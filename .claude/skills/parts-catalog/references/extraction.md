# Extraction reference — parts books and price lists

The value of this skill is the failure modes below. Each was a real bug that a
visual spot-check missed and a completeness check caught. Read the relevant
section before touching a parser.

## PDF parts tables (`extract_pdf_catalog.py`)

Source shape: A4 landscape pages, alternating **drawing** pages (illustrations
with numbered callouts) and **table** pages. Tables are usually **two columns**
(left/right), each with headers `注/NC 序号/REF 数量/QTY 件号/PART NO. 中文名称/ZH 英文名称/EN`.

### Parse by VALUE, not by fixed column x
The single most important lesson. Column x-positions drift page to page, and on
many pages the part-number data sits a few px left of its own header — so
nearest-anchor assignment drops the 8-digit number into the QTY column and the
whole row is lost (one page lost *every* row this way). Instead:
1. Detect per-page column anchors from the page's own header row (`_detect_anchors`).
2. Cluster words into rows by y.
3. In each row, **find the part-number token by its pattern** (`_is_pn`: alnum,
   has a digit, ≥5 chars, not a 1–4 digit count). Then REF/QTY are the numeric
   tokens to its left, ZH/EN the name tokens to its right. Position only breaks
   ties (nearest ref vs qty anchor).

### Rows that look empty but are real
- **Quantity `AR`** ("As Required" / по потребности) instead of a number. Accept
  `\d{1,4}|AR|A/R` as QTY, or the row loses its position number.
- **Blank quantity**: `REF PART-NO ZH EN` with no QTY. If the token before the
  part number is the only leading number, it is the REF, not the QTY.
- **Alphanumeric positions** like `4A`. Match REF as `\d{1,3}[A-Z]?`.
- **Kit sub-components** have a REF + name but **no part number** (e.g.
  `009 001 ·壳体 ·HOUSING`). Keep them (empty pn) so the on-screen position list
  matches the drawing callouts; mark them not-orderable. `·`/`•` prefixes encode
  sub-assembly depth (`lvl`).

### Figures — pair each drawing with its own positions
Do not dump every drawing then one long list. Walk a section's pages in order and
group each run of drawing pages + the following table pages into a **figure**
(`D..T..` repeating). Interleaved sections (`D T D T`) then split so each drawing
shows exactly its positions; sections where several sheets share one list become
one figure with a carousel. REF numbering usually continues across a section's
tables (not reset per figure), which is why a single combined parse is correct
before grouping.

## Binary Word `.doc` parts books (`extract_doc_catalog.py`)

LibreOffice may be unavailable/broken in the sandbox (it failed to load *any*
file here, including native ODF, and got signal-killed on convert). Do not fight
it — read the OLE2 file directly with `olefile`:

- **Text**: parse the FIB in the `WordDocument` stream for the piece table
  (`fcClx`/`lcbClx` at 0x01A2/0x01A6 → CLX in the `0Table`/`1Table` stream),
  decode each piece (compressed = CP1252 at fc/2, else UTF-16LE). Preserve `\r`
  (paragraph) and `\x07` (cell) marks. Fields land as separate paragraph tokens
  in order: `[NC] REF [QTY] PART-NO ZH EN`.
- **Drawings**: images are PNG blobs in the `Data` stream — scan for the PNG
  signature and slice to `IEND`.
- **Mapping images → sections**: pictures and their inline anchors (`\x01` chars
  in the text) are both stored in document order. Count `\x01` per section; the
  counts slice the ordered picture list. Confirm `sum(counts) == len(pngs)` (one
  extra anchor is usually a cover logo).

Same leading-token rules as the PDF apply (AR / blank qty / alphanumeric REF).

## Price list `.xlsx` (`extract_prices.py`)

Header is below a contract preamble — find the row containing `Артикул`. Build
`pn -> {price, group, xref, name_ru}` keyed by article, and also index by the
interchangeable article so a number listed only as a cross-reference resolves.
Match to catalog part numbers; expect partial coverage (≈58% here). Emit a small
`window.PRICES` (only catalog-referenced rows) plus the unique-numbers CSV with
every attribute ("аналитик") column.

## Always verify — `verify_completeness.py`
After any parser change: token cross-check must report **0 missing**, and every
flagged position gap must be confirmed legitimate (the number is not printed in
the REF column — it is a quantity, a kit sub-item, or a drawing-only callout).
Note single- vs three-digit REF formatting (`1` vs `001`) is cosmetic — pad in
display, don't treat as missing.
