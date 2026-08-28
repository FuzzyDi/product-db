"""
Импорт товаров из XLSX в Product DB.

Использование:
    pip install openpyxl requests
    python import_xlsx.py --file products.xlsx
    python import_xlsx.py --file products.xlsx --url http://localhost:8000 --batch-size 100 --source-id mystore
"""
import argparse
import json
import sys
import time

try:
    import openpyxl
except ImportError:
    print("Установите: pip install openpyxl requests")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Установите: pip install openpyxl requests")
    sys.exit(1)

from product_db.pipeline.barcode import normalize_barcode, should_skip_import_barcode

# Маппинг колонок XLSX → поля API
COLUMN_MAP = {
    "наименование": "name",
    "название": "name",
    "name": "name",
    "штрихкод": "barcode",
    "barcode": "barcode",
    "ean": "barcode",
    "код": "internal_code",
    "код товара": "internal_code",
    "артикул": "internal_code",
    "базовая единица измерения": "uom",
    "единица измерения": "uom",
    "ед. изм.": "uom",
    "цена закупка": "price_purchase",
    "цена розница": "price_retail",
    "цена": "price_retail",
}


def map_header(header: str) -> str:
    return COLUMN_MAP.get(header.strip().lower(), header.strip().lower())


def read_xlsx(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = iter(ws.rows)
    headers = [map_header(str(cell.value or "")) for cell in next(rows)]
    records = []
    for row in rows:
        values = [cell.value for cell in row]
        if not any(values):
            continue
        records.append(dict(zip(headers, values)))
    wb.close()
    return records


def build_item(record: dict, source_id: str) -> tuple[dict | None, str | None]:
    name = str(record.get("name") or "").strip()
    if not name or name.lower() == "none":
        return None, "EMPTY_NAME"

    barcode = normalize_barcode(record.get("barcode"))
    skip, reason = should_skip_import_barcode(barcode)
    if skip:
        return None, reason

    extra = {}
    for key in ("internal_code", "uom", "price_purchase", "price_retail"):
        val = record.get(key)
        if val is not None and str(val).strip() not in ("", "None", "nan"):
            extra[key] = str(val).strip()

    return {"name": name, "barcode": barcode, "source_id": source_id, "extra": extra}, None


def send_batch(url: str, items: list[dict], api_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    resp = requests.post(
        f"{url}/api/v1/intake/batch",
        headers=headers,
        data=json.dumps({"items": items}),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Путь к XLSX файлу")
    parser.add_argument("--url", default="http://localhost:8000", help="URL API")
    parser.add_argument("--source-id", default="xlsx_import", help="Идентификатор источника")
    parser.add_argument("--batch-size", type=int, default=50, help="Размер пакета")
    parser.add_argument("--api-key", default=None, help="X-API-Key (если включена авторизация)")
    args = parser.parse_args()

    print(f"Читаю файл: {args.file}")
    records = read_xlsx(args.file)
    print(f"Строк в файле: {len(records)}")

    items = []
    skipped_empty = 0
    skipped_missing_barcode = 0
    skipped_internal_prefix = 0
    for rec in records:
        item, reason = build_item(rec, args.source_id)
        if item:
            items.append(item)
        else:
            if reason == "EMPTY_NAME":
                skipped_empty += 1
            elif reason == "MISSING_BARCODE":
                skipped_missing_barcode += 1
            elif reason == "INTERNAL_BARCODE_PREFIX":
                skipped_internal_prefix += 1

    total_skipped = skipped_empty + skipped_missing_barcode + skipped_internal_prefix
    print(
        f"Товаров к загрузке: {len(items)} | "
        f"пропущено: {total_skipped} "
        f"(пустые: {skipped_empty}, без ШК: {skipped_missing_barcode}, ШК 20-29: {skipped_internal_prefix})"
    )
    if not items:
        print("Нечего загружать.")
        return

    total = 0
    batch_num = 0
    for i in range(0, len(items), args.batch_size):
        batch = items[i : i + args.batch_size]
        batch_num += 1
        try:
            result = send_batch(args.url, batch, args.api_key)
            task_ids = result.get("data", {}).get("task_ids", [])
            skipped_count = result.get("data", {}).get("skipped_count", 0)
            total += len(batch)
            print(f"Пакет {batch_num}: отправлено {len(batch)} | задач Celery: {len(task_ids)} | пропущено API: {skipped_count}")
        except requests.HTTPError as e:
            print(f"Пакет {batch_num}: ошибка HTTP {e.response.status_code} — {e.response.text[:200]}")
        except Exception as e:
            print(f"Пакет {batch_num}: ошибка — {e}")
        time.sleep(0.1)

    print(f"\nГотово. Отправлено: {total} товаров. Обработка идёт в фоне (Celery).")
    print(f"Статус: {args.url}/api/v1/stats/pipeline")


if __name__ == "__main__":
    main()
