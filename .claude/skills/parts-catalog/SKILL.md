---
name: parts-catalog
description: >-
  Build an interactive, clickable web parts catalog from a manufacturer's spare-
  parts book and price list — section drawings paired with their position lists,
  full-text search, a required-quantity order cart, prices, and CSV/print export.
  Use this whenever the user wants to turn a parts book / каталог запчастей /
  parts manual into a browsable or clickable catalog, extract the parts tables or
  catalog numbers from such a book, pull a price list into it, or fix/extend a
  catalog built this way — including when the source is a PDF (often split-zip),
  a binary Word .doc, or an .xlsx price list, and even if they don't say "catalog"
  explicitly (e.g. "make these drawings clickable with an order basket", "extract
  all unique part numbers", "add prices to the parts table"). Handles bilingual
  (Chinese/English) NHL/GE-style mining-equipment books and their quirks.
---

# Interactive parts catalog

Turn OEM spare-parts books (illustrations + parts tables) and a price list into a
static, dependency-free web catalog: each drawing shown with exactly its position
list, search across every part number, and an order cart with required quantities
and prices.

## Pipeline

1. **Get the source readable.**
   - Split-zip PDF (`*.zip.001..00N`): concatenate the parts, then unzip.
   - Binary `.doc`: read it directly (see below) — do not rely on LibreOffice.
   - `.xlsx` price list: `openpyxl`.
   - Dependencies: `pip install pymupdf olefile openpyxl`.

2. **Understand the structure before parsing.** Dump text of the first ~15 pages
   and inspect word coordinates on one dense table page. Identify: section-code
   pattern (e.g. `020-0040` or `600-0020-200`), the table header tokens, and how
   drawing pages and table pages alternate. Chinese/English books put the parts
   list as `注/NC 序号/REF 数量/QTY 件号/PART NO. 中文名称/ZH 英文名称/EN`.

3. **Extract** with the bundled scripts (adapt column anchors / section regex to
   the book). They emit the `figures`-based `window.CATALOG` schema and render
   drawings.
   - `scripts/extract_pdf_catalog.py` — PDF parts book (value-based table parser,
     figure grouping, drawing rendering).
   - `scripts/extract_doc_catalog.py` — binary Word `.doc` (piece-table text +
     PNG drawings from the `Data` stream) merged as a new chapter.
   - `scripts/extract_prices.py` — `.xlsx` price list → `window.PRICES` + a
     unique-numbers CSV carrying every attribute.
   - **Read `references/extraction.md` first** — it lists the failure modes
     (value-based columns, `AR`/blank/alphanumeric quantities, no-part-number kit
     rows, image→section mapping) that a spot-check will miss.

4. **Verify — every time.** Run `scripts/verify_completeness.py parts.js source.pdf`.
   The token cross-check must report **0 missing part numbers**; confirm each
   flagged position gap is legitimate (the number is a quantity or a drawing-only
   callout, not a dropped row). This step is not optional — table parsers drop
   rows silently, and the user *will* notice a missing number.

5. **Build / update the web app.** Mirror `catalog/` — see `references/webapp.md`
   for the schema, the figure/carousel/quantity/cart/export UI, and the rendering
   bugs to avoid (sticky-header-hides-row-001, scroll anchoring). Theme via CSS
   variables so a client brand (colors + logo, e.g. from a supplied template)
   swaps cleanly.

6. **Smoke-test in the real browser** (Chromium + Playwright are preinstalled)
   before declaring done: first row is 001 everywhere, drawings load, cart totals
   update, exports download, zero console errors. Then commit and push.

## Working style that fit this task
- The user iterates by pointing a phone photo at a specific screen. Treat each as
  a concrete bug: reproduce that exact section, find the mechanism, fix the class
  of problem (not the one instance), and re-verify across many sections.
- Prefer a reproducible script committed to `tools/` over one-off commands, so the
  whole catalog can be regenerated from source.
- Keep the deliverable openable by double-clicking `index.html` (data as JS
  globals, images by relative path) — no server, no build step.
