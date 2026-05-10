"""
Бэкап PostgreSQL через pg_dump.

Использование:
    python -m product_db.scripts.backup_db
    python -m product_db.scripts.backup_db --dir /path/to/backups
    python -m product_db.scripts.backup_db --keep 7   # удалять бэкапы старше 7 дней

Для автоматического запуска добавьте в crontab:
    0 1 * * * docker exec <container> python -m product_db.scripts.backup_db
"""
import argparse
import glob
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=None, help="Папка для бэкапов")
    parser.add_argument("--keep", type=int, default=7, help="Хранить N дней (0 = не удалять)")
    return parser.parse_args()


def backup(backup_dir: str, keep_days: int) -> str:
    from product_db.config import settings

    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(backup_dir, f"product_db_{ts}.sql.gz")

    # Парсим DATABASE_URL_SYNC для передачи параметров pg_dump
    url = urlparse(settings.database_url_sync.replace("+psycopg2", ""))
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password

    pg_dump_cmd = [
        "pg_dump",
        "-h", url.hostname or "localhost",
        "-p", str(url.port or 5432),
        "-U", url.username or "postgres",
        "-d", url.path.lstrip("/"),
        "--no-owner",
        "--no-acl",
        "-F", "p",   # plain SQL
    ]

    logger.info("Создаю бэкап: %s", filename)
    with open(filename, "wb") as f:
        dump = subprocess.Popen(pg_dump_cmd, stdout=subprocess.PIPE, env=env)
        gzip = subprocess.Popen(["gzip", "-c"], stdin=dump.stdout, stdout=f)
        dump.stdout.close()
        gzip.wait()
        dump.wait()

    if dump.returncode != 0:
        os.remove(filename)
        raise RuntimeError(f"pg_dump завершился с кодом {dump.returncode}")

    size_mb = os.path.getsize(filename) / 1024 / 1024
    logger.info("Бэкап создан: %s (%.1f MB)", filename, size_mb)

    # Удаляем старые бэкапы
    if keep_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        for old in glob.glob(os.path.join(backup_dir, "product_db_*.sql.gz")):
            mtime = datetime.fromtimestamp(os.path.getmtime(old), tz=timezone.utc)
            if mtime < cutoff:
                os.remove(old)
                logger.info("Удалён старый бэкап: %s", old)

    return filename


def main():
    args = parse_args()
    from product_db.config import settings
    backup_dir = args.dir or settings.backup_dir
    try:
        backup(backup_dir, args.keep)
    except Exception as exc:
        logger.exception("Ошибка бэкапа: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
