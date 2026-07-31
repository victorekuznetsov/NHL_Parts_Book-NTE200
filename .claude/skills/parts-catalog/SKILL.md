---
name: parts-catalog
description: >-
  Build a complete interactive, clickable web parts catalog from a
  manufacturer's spare-parts book, price list and service manuals — section
  drawings paired with their position lists, search, an order cart with prices
  and order analysis, per-section links to the repair-manual page, and CSV/print
  export. Use whenever the user wants to turn a parts book / каталог запчастей /
  parts manual into a browsable or clickable catalog, extract the parts tables or
  catalog numbers, pull a price list or repair/operator/wiring manuals into it,
  or fix/extend a catalog built this way — sources may be a PDF (often
  split-zip), a binary Word .doc, a Cummins QuickServe folder of PDFs, an .xlsx
  price list, or manual PDFs, even if they don't say "catalog" (e.g. "make these
  drawings clickable with an order basket", "extract all unique part numbers",
  "add prices/repair guides"). Bilingual Chinese/English/Russian OEM books.
---

# Interactive parts catalog — complete kit

Turn OEM spare-parts books (illustrations + parts tables), a price list and
service manuals into a **self-contained static web catalog**: each drawing shown
with exactly its position list, search over every part number, an order cart
with required quantities, prices and per-system analysis, and a repair-manual
page one click from each section. No server, no build — it opens by
double-clicking `index.html`.

This skill is a full kit: proven **extractors** in `scripts/`, a ready
**data-driven web app** in `assets/webapp/`, and the hard-won parsing/rendering
lessons in `references/`. The app is generic — it renders any catalog that
follows the data schema below, so you rarely touch its code; you mostly generate
data for it.

## Deliverable layout
```
catalog/                 ← self-contained; this is what the user downloads
  index.html app.js styles.css   (copied from assets/webapp/, then customised)
  data/  parts.js · prices.js · manuals.js · all_part_numbers.csv
  drawings/  one image per drawing page
  manuals/   the service PDFs (clean ASCII names)
sources/   raw inputs, one subfolder per source (not needed to run the catalog)
tools/     the extractors (copies of scripts/, adapted to the sources)
```
Keep `catalog/` self-contained so the user can download just that folder. Put raw
inputs under `sources/<kind>/` and point the extractors there.

## Workflow

1. **Survey the sources.** Identify each input and its shape before parsing —
   they differ a lot. Dump the first pages / word coordinates / bookmarks. See
   `references/extraction.md`, which documents every format this skill handles
   (split-zip PDF book, binary Word `.doc`, Cummins QuickServe folder-of-PDFs,
   `.xlsx` price list, repair/operator/wiring manual PDFs) and the failure modes
   a visual spot-check misses.

2. **Stand up the app.** Copy `assets/webapp/{index.html,app.js,styles.css}` into
   `catalog/`. Customise only the surface: `<title>`, the brand mark/logo, the
   top contact line, and the CSS theme variables (`--acc`, `--acc-ink`, `--acc2`,
   brand color) — all near the top of the files. The logic is data-driven and
   stays as-is.

3. **Generate the data** with the extractors (adapt column anchors / section
   regex / source paths per book):
   - `scripts/extract_pdf_catalog.py` — PDF parts book (value-based table parser,
     figure grouping, drawing rendering) → `window.CATALOG`.
   - `scripts/extract_doc_catalog.py` — binary Word `.doc` (piece-table text +
     images from the `Data` stream), merged as a new chapter.
   - `scripts/extract_qsk50.py` — Cummins QuickServe folder tree (one-assembly
     PDFs, Russian tables), merged as its own chapters.
   - `scripts/extract_prices.py` — `.xlsx` price list → `window.PRICES` + a
     unique-numbers CSV carrying every attribute.
   - `scripts/extract_manuals.py` — operator/repair/wiring PDFs → per-section
     repair deep-links + a Documents drawer (`window.MANUALS`).
   Load the scripts as `<script>` in `index.html` in this order:
   parts.js, prices.js, manuals.js, app.js.

4. **Verify — every time, twice.** `scripts/verify_completeness.py
   catalog/data/parts.js <source.pdf>` must report **0 missing part-number
   tokens**; confirm each flagged position gap is legitimate (a quantity, a kit
   sub-item or a drawing-only callout — not a dropped row). Table parsers drop
   rows silently and users *will* notice a missing number.

5. **Smoke-test in the real browser** (Chromium + Playwright are preinstalled).
   Across sections of every source type assert: first row is 001, drawings load
   (`naturalWidth>0`), prices show, add-to-cart updates totals, repair links open
   the right page, and console-error count is 0. Then commit and push.

## Data schema (what the app reads)
```
window.CATALOG = { chapters:[{code,zh,en}],
  sections:[{ code, chapter, zh, en,
    figures:[{ images:[path...], parts:[{nc,ref,qty,pn,zh,en,lvl}] }] }],
  stats:{sections,parts} }
window.PRICES  = { "<pn>": {p:price, g:group, x:interchangeable, n:name} }
window.MANUALS = { files:[{id,title,file,pages,desc}], repairByCode:{code:page},
  repairByChapter:{chapter:page}, repairToc:[{code,title,page}], wiring:[{title,page}] }
```
`zh` is the primary display name (use the local language there — Chinese or
Russian), `en` the subtitle. Store parts only inside `figures`; flatten in JS.
Full UI/schema detail and the rendering bugs to avoid are in
`references/webapp.md`.

## Working style that fit this work
- Users iterate by pointing a phone photo at one screen — treat each as a
  concrete bug: reproduce that exact section, find the mechanism, fix the class
  of problem, re-verify across many sections.
- Prefer a reproducible script in `tools/` over one-off commands, so the whole
  catalog regenerates from source.
- Keep the deliverable double-click-openable (data as JS globals, assets by
  relative path) — no server, no build step.
