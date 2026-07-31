# NHL_Parts_Book-NTE200

Единый интерактивный каталог запчастей карьерного самосвала **NTE200** (NHL):
самосвал, привод **GE**, двигатель **Cummins QSK50**, цены и руководства по
ремонту/эксплуатации.

## Структура репозитория

```
catalog/     ← ГОТОВЫЙ каталог (это и нужно скачивать). Самодостаточный:
             открывается двойным щелчком по catalog/index.html, без сервера.
  index.html app.js styles.css
  data/      parts.js · prices.js · manuals.js · all_part_numbers.csv
  drawings/  чертежи (355 файлов)
  manuals/   PDF-руководства (ремонт, оператор, электросхема 24В)

sources/     ← исходники (нужны только для пересборки, скачивать не обязательно)
  nte200-parts/  книга NTE200 (многотомный zip)
  ge-drive/      книга привода GE (Word .doc)
  qsk50-engine/  каталог двигателя Cummins QSK50 (zip)
  manuals/       PDF-руководства (оригиналы)
  price/         прайс-лист (xlsx)
  brand/         фирменный шаблон «Развитие» (pptx)

tools/       ← скрипты пересборки каталога из исходников
docs/        ← инструкции: как пользоваться, промт для новых каталогов, отчёт проверки
.claude/skills/parts-catalog/  ← навык для создания таких каталогов
```

## Что скачивать

Для работы достаточно **одной папки `catalog/`** — в ней уже лежат все данные,
чертежи и руководства. Откройте `catalog/index.html`.

## Пересборка из исходников

```bash
pip install pymupdf olefile openpyxl
python3 tools/extract_catalog.py    # книга NTE200 (PDF)
python3 tools/extract_ge.py         # привод GE (Word .doc)  → глава 600
python3 tools/extract_qsk50.py      # двигатель QSK50 (Cummins) → главы Q01–Q12
python3 tools/extract_prices.py     # цены и аналитики (XLSX)
python3 tools/extract_manuals.py    # руководства + ссылки на ремонт
python3 tools/verify_completeness.py catalog/data/parts.js   # проверка полноты
```

Документация: [`docs/КАК_ПОЛЬЗОВАТЬСЯ.md`](docs/), [`docs/ОТЧЁТ_ПРОВЕРКИ.md`](docs/),
[`catalog/README.md`](catalog/README.md). Контакты: Кузнецов В.Е.,
KuznetsovVE@industrservice.ru.
