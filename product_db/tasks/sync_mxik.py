"""Celery задача: ночная синхронизация MXIK через API."""
import logging

from .celery_app import app

logger = logging.getLogger(__name__)

MXIK_API_URL = "https://tasnif.soliq.uz/api/cl-api/integration-mxik/get/all/history/time-json"


@app.task
def sync_mxik():
    """Скачивает актуальный MXIK-реестр и обновляет базу.

    Реализация будет в Этапе 2 (сейчас используем load_mxik_from_file.py).
    """
    logger.info("sync_mxik: запуск (stub)")
