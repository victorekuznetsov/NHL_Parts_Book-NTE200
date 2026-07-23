# NHL_Parts_Book-NTE200

Книга запчастей карьерного самосвала **NTE200** (Inner Mongolia North Hauler,
NHL) и её интерактивная веб-версия.

- **Исходники** — книга запчастей NTE200 (`NTE200 PART номера Polyus.zip.001 … .004`,
  многотомный архив) и книга привода GE (`NTE200 GE备件手册20230805.doc`).
- **Интерактивный каталог** — [`catalog/`](catalog/): кликабельные чертежи,
  таблицы деталей, поиск, корзина для заказа и экспорт всех уникальных
  каталожных номеров. Откройте [`catalog/index.html`](catalog/index.html) в браузере.
- **Извлечение данных** — [`tools/extract_catalog.py`](tools/extract_catalog.py)
  разбирает PDF, а [`tools/extract_ge.py`](tools/extract_ge.py) — Word-документ
  привода GE (глава 600).
- **Все каталожные номера** — [`catalog/data/all_part_numbers.csv`](catalog/data/all_part_numbers.csv):
  2470 уникальных номеров (NTE200 + GE).

Подробности — в [`catalog/README.md`](catalog/README.md).
