"""
Загрузка MXIK из локального JSON-файла (потоковый парсинг, ~390MB).

Использование:
    python -m product_db.scripts.load_mxik_from_file
    python -m product_db.scripts.load_mxik_from_file --path E:/Download/mxik_information.json
    python -m product_db.scripts.load_mxik_from_file --batch-size 1000
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import ijson
import psycopg2
import psycopg2.extras

from product_db.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_PATH = "E:/Download/mxik_information.json"
BATCH_SIZE = 500


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    return parser.parse_args()


def is_group_code(mxik: str) -> bool:
    return mxik.endswith("000000")


def load(path: str, batch_size: int) -> None:
    dsn = settings.database_url_sync.replace("postgresql+psycopg2://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    started_at = datetime.now(timezone.utc)
    cur.execute(
        "INSERT INTO mxik_sync_log (started_at, status) VALUES (%s, %s) RETURNING id",
        (started_at, "running"),
    )
    sync_log_id = cur.fetchone()[0]
    conn.commit()

    catalog_batch = []
    packages_map = {}   # mxik -> [packages]

    added = updated = deactivated = total = 0
    t0 = time.time()

    def flush(batch):
        nonlocal added, updated
        if not batch:
            return

        # Upsert mxik_catalog
        upsert_sql = """
            INSERT INTO mxik_catalog
                (mxik, mxik_name_ru, mxik_name_uz, mxik_name_lat,
                 international_code, label, label_for_check, cash_sale,
                 is_group_code, is_active, created_at_ms, updated_at_ms, synced_at)
            VALUES %s
            ON CONFLICT (mxik) DO UPDATE SET
                mxik_name_ru      = EXCLUDED.mxik_name_ru,
                mxik_name_uz      = EXCLUDED.mxik_name_uz,
                mxik_name_lat     = EXCLUDED.mxik_name_lat,
                international_code= EXCLUDED.international_code,
                label             = EXCLUDED.label,
                label_for_check   = EXCLUDED.label_for_check,
                cash_sale         = EXCLUDED.cash_sale,
                is_group_code     = EXCLUDED.is_group_code,
                is_active         = true,
                created_at_ms     = EXCLUDED.created_at_ms,
                updated_at_ms     = EXCLUDED.updated_at_ms,
                synced_at         = EXCLUDED.synced_at
            WHERE mxik_catalog.updated_at_ms IS DISTINCT FROM EXCLUDED.updated_at_ms
            RETURNING id, mxik, (xmax = 0) AS was_inserted
        """
        rows = [
            (
                r["mxik"], r["mxik_name_ru"], r["mxik_name_uz"], r["mxik_name_lat"],
                r["international_code"], r["label"], r["label_for_check"], r["cash_sale"],
                r["is_group_code"], True, r["created_at_ms"], r["updated_at_ms"],
                datetime.now(timezone.utc),
            )
            for r in batch
        ]
        results = psycopg2.extras.execute_values(cur, upsert_sql, rows, fetch=True)

        catalog_id_by_mxik = {}
        for row in results:
            catalog_id_by_mxik[row[1]] = row[0]
            if row[2]:
                added += 1
            else:
                updated += 1

        # Upsert packages
        pkg_rows = []
        for r in batch:
            catalog_id = catalog_id_by_mxik.get(r["mxik"])
            if catalog_id is None:
                continue
            for pkg in r["packages"]:
                pkg_rows.append((
                    catalog_id,
                    pkg["code"],
                    pkg["package_type"],
                    pkg.get("name_ru"),
                    pkg.get("name_uz"),
                    pkg.get("name_lat"),
                ))

        if pkg_rows:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO mxik_packages (catalog_id, code, package_type, name_ru, name_uz, name_lat)
                VALUES %s
                ON CONFLICT (code) DO UPDATE SET
                    catalog_id   = EXCLUDED.catalog_id,
                    package_type = EXCLUDED.package_type,
                    name_ru      = EXCLUDED.name_ru,
                    name_uz      = EXCLUDED.name_uz,
                    name_lat     = EXCLUDED.name_lat
                """,
                pkg_rows,
            )

        conn.commit()

    try:
        logger.info("Открываю файл: %s", path)
        with open(path, "rb") as f:
            for item in ijson.items(f, "item"):
                total += 1
                record = {
                    "mxik":              item.get("mxik", ""),
                    "mxik_name_ru":      item.get("mxikNameRu"),
                    "mxik_name_uz":      item.get("mxikNameUz"),
                    "mxik_name_lat":     item.get("mxikNameLat"),
                    "international_code": item.get("internationalCode"),
                    "label":             int(item.get("label", 0)),
                    "label_for_check":   int(item.get("labelForCheck", 0)),
                    "cash_sale":         int(item.get("cashSale", 1)),
                    "is_group_code":     is_group_code(item.get("mxik", "")),
                    "created_at_ms":     item.get("createdAt"),
                    "updated_at_ms":     item.get("updateAt"),
                    "packages": [
                        {
                            "code":         int(p["code"]),
                            "package_type": int(p.get("packageType", 3)),
                            "name_ru":      p.get("nameRu"),
                            "name_uz":      p.get("nameUz"),
                            "name_lat":     p.get("nameLat"),
                        }
                        for p in item.get("packages", [])
                    ],
                }
                catalog_batch.append(record)

                if len(catalog_batch) >= batch_size:
                    flush(catalog_batch)
                    catalog_batch.clear()
                    elapsed = time.time() - t0
                    logger.info(
                        "Обработано: %d | добавлено: %d | обновлено: %d | %.1f сек",
                        total, added, updated, elapsed,
                    )

        flush(catalog_batch)

        # Деактивируем коды, которые исчезли из реестра
        logger.info("Деактивация устаревших кодов...")
        cur.execute(
            """
            UPDATE mxik_catalog SET is_active = false
            WHERE is_active = true
              AND synced_at < %s
            """,
            (started_at,),
        )
        deactivated = cur.rowcount
        conn.commit()

        finished_at = datetime.now(timezone.utc)
        cur.execute(
            """
            UPDATE mxik_sync_log
            SET finished_at = %s, status = 'success',
                records_total = %s, records_added = %s,
                records_updated = %s, records_deactivated = %s
            WHERE id = %s
            """,
            (finished_at, total, added, updated, deactivated, sync_log_id),
        )
        conn.commit()

        elapsed = time.time() - t0
        logger.info(
            "Готово за %.1f сек. Всего: %d | добавлено: %d | обновлено: %d | деактивировано: %d",
            elapsed, total, added, updated, deactivated,
        )

    except Exception as exc:
        conn.rollback()
        cur.execute(
            "UPDATE mxik_sync_log SET finished_at = now(), status = 'failed', error_message = %s WHERE id = %s",
            (str(exc), sync_log_id),
        )
        conn.commit()
        logger.exception("Ошибка загрузки MXIK: %s", exc)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


def main():
    args = parse_args()
    load(args.path, args.batch_size)


if __name__ == "__main__":
    main()
