"""Настройка структурированного логирования (JSON в продакшне, текст в dev)."""
import logging
import logging.config
import sys

from product_db.config import settings


class _JsonFormatter(logging.Formatter):
    """Минимальный JSON-форматтер без внешних зависимостей."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        data: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = traceback.format_exception(*record.exc_info)[-1].strip()
        # Дополнительные поля из extra={}
        for key, val in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno", "module",
                "msecs", "message", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread", "threadName",
            }:
                data[key] = val
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s — %(message)s")
        )

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # Заглушаем шумных соседей
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
