# Web-app reference — interactive catalog

A dependency-free static site (vanilla JS, no build). Opens from `index.html`
via `file://` — so data is delivered as JS globals, not `fetch()`ed JSON.
`catalog/` in this repo is the canonical, working example; mirror its structure.

## Files
```
catalog/
  index.html            # markup + <script> tags
  styles.css            # theme via CSS variables
  app.js                # all logic
  data/parts.js         # window.CATALOG = {...}
  data/prices.js        # window.PRICES = {...}
  data/all_part_numbers.csv
  drawings/*.jpg|*.png  # one file per drawing page
```

## Data schema (`window.CATALOG`)
```
{ chapters:[{code,zh,en}],
  sections:[{ code, chapter, zh, en,
    figures:[{ images:[path...], parts:[{nc,ref,qty,pn,zh,en,lvl}] }] }],
  stats:{sections,parts} }
```
Store parts inside `figures` only (one source of truth); flatten in JS when you
need a whole-section list. `window.PRICES` is `{ pn: {p:price,g:group,x:xref,n:ru_name} }`.

## UI that matched what the user actually wanted
- **Figure = drawing(s) + its own position list**, side by side on wide screens
  (drawing sticky, list scrolls). Multiple drawings in one figure → a carousel
  (`‹ ›` + counter), not a tall stack. Header "Рисунок N / M · позиции a–b".
- **Parts table**: № | Номер детали | Наименование | Цена, CNY | Кол-во | Нужно | ＋.
  - Показать RU name from the price list when it differs from EN; group as a chip;
    interchangeable article under the part number.
  - **Нужно** = a per-row required-quantity input (default = on-scheme qty); ＋ adds
    that amount. Positions without a part number show `—` and no ＋.
- **Cart** (localStorage): editable qty, machine serial field, per-line
  `price × qty = sum` and an order total in the price-list currency.
- **Exports**: order CSV + print sheet (with price/sum); and an
  "export all unique catalog numbers" action that includes **every** analytic
  column (RU name, price, group, interchangeable article, source, sections).
- **Branding**: theme via CSS variables so a client palette/logo swaps cleanly.
  A pinned top contact bar is an easy, expected touch.

## Rendering gotchas (all cost real debugging time)
- **Sticky `<thead>` + `border-collapse` hides the first row.** The header paints
  *over* row 001 (getBoundingClientRect disagrees with the paint), so 001 looks
  missing in almost every section. Do **not** make the table header sticky.
- **Scroll anchoring** shifts the view when a drawing loads async, pushing the
  first row out. Set `html{overflow-anchor:none}`.
- Zero-pad numeric positions for a consistent № column (`1` → `001`).
- Building HTML by string concat: a single mismatched quote (`... </tr>";` vs
  `';`) breaks the whole file. `node --check app.js` after edits.
- Theme both fills and text: a bright brand color works as a button fill but is
  unreadable as link text — keep a separate darker "ink" variable.

## Always smoke-test in the real browser
Chromium + Playwright are preinstalled (`executablePath:'/opt/pw-browsers/chromium'`).
Load several sections and assert: first visible row is 001, zero rows overlap the
header, drawing images load (`naturalWidth>0`), add-to-cart updates totals, search
returns rows, exports download, and `pageerror`/console-error count is 0.
