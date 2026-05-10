# Product DB — Система качества товарных данных

Универсальная база товаров с единой правдой о каждом продукте.
Любой источник данных вносит вклад в одну карточку товара.

## Архитектура

```
Источники данных
    │
    ▼
POST /api/v1/intake
    │
    ▼
Pipeline (9 шагов):
  1. Intake       — raw_input_log (иммутабельно)
  2. Barcode      — тип штрихкода (EAN13/EAN8/UPC-A/GS1/внутренний)
  3. Normalize    — язык, uz-cyrl→latn, токенизация
  4. Extract      — бренд (fuzzy), тип товара (keywords+lemmatize),
                    объём (regex), упаковка (regex)
  5. Match        — по штрихкоду → по имени → pg_trgm fuzzy → create_candidate
  6. MXIK         — по штрихкоду (0.95) → FTS (0.60) → групповой код
  7. Generate     — canonical / pos(≤20) / receipt(≤40) / catalog
  8. Quality      — confidence + completeness, список проблем
  9. Route        — ≥0.85 → verified; иначе → review queue
    │
    ▼
PostgreSQL (products, raw_input_log, ...)
    │
    ▼
Operator UI (React) — review queue, MXIK selector, brand manager
    │
    ▼
Learner — новые brand_aliases из решений операторов
```

## Стек

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| DB | PostgreSQL 16 (pg_trgm, tsvector, pgcrypto) |
| Очереди | Redis 7, Celery, Celery Beat |
| NLP | pymorphy3, rapidfuzz, langdetect, ijson |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Tailwind CSS |
| Инфраструктура | Docker, Docker Compose |
| Мониторинг | Sentry, структурированное JSON-логирование |

## Быстрый старт

```bash
# 1. Клонировать и настроить env
cp .env.example .env
# Отредактировать .env при необходимости

# 2. Запустить контейнеры
docker-compose up -d

# 3. Применить миграции
docker-compose exec backend alembic upgrade head

# 4. Заполнить справочники (бренды, типы товаров, UOM)
docker-compose exec backend python -m product_db.scripts.seed_refs

# 5. Загрузить реестр ИКПУ (~390MB, ~5-10 мин)
docker-compose exec backend python -m product_db.scripts.load_mxik_from_file

# UI: http://localhost:3000
# API: http://localhost:8000/docs
```

## API

Все ответы: `{"success": true, "data": ..., "meta": {}, "error": null}`

Авторизация: `X-API-Key: <key>` (если `API_KEYS` задан в .env)

### Intake
| Метод | Путь | Описание |
|-------|------|---------|
| POST | `/api/v1/intake/single` | Один товар (sync, <2 сек) |
| POST | `/api/v1/intake/batch` | Пакет товаров (async, Celery) |
| GET  | `/api/v1/intake/{id}/status` | Статус обработки |

### Товары
| Метод | Путь | Описание |
|-------|------|---------|
| GET  | `/api/v1/products` | Список (фильтры: status, brand_id, review_required) |
| GET  | `/api/v1/products/search?q=` | Полнотекстовый + trigram поиск |
| GET  | `/api/v1/products/{id}` | Полная карточка |
| PUT  | `/api/v1/products/{id}` | Обновить безопасные поля |

### Ревью (оператор)
Требует: `X-Operator-Id: <id>`

| Метод | Путь | Описание |
|-------|------|---------|
| GET  | `/api/v1/review/queue` | Очередь (сортировка: confidence ASC) |
| GET  | `/api/v1/review/{id}` | Контекст + MXIK-кандидаты + похожие |
| POST | `/api/v1/review/{id}/decide` | Решение оператора |

Типы решений: `confirm_product`, `correct_field`, `confirm_mxik`, `confirm_package_code`, `reject_match`, `merge_products`

### ИКПУ (MXIK)
| Метод | Путь | Описание |
|-------|------|---------|
| GET  | `/api/v1/mxik/search?q=` | Поиск по тексту или штрихкоду |
| GET  | `/api/v1/mxik/{mxik}/packages` | Упаковки ИКПУ |
| GET  | `/api/v1/mxik/sync/status` | Статус синхронизации |

### Справочники
| Метод | Путь |
|-------|------|
| GET/POST | `/api/v1/refs/brands` |
| POST | `/api/v1/refs/brands/{id}/aliases` |
| GET  | `/api/v1/refs/product-types` |
| GET  | `/api/v1/refs/categories` |
| GET  | `/api/v1/refs/uom` |
| GET  | `/api/v1/refs/packages` |

### Статистика
| Путь | Описание |
|------|---------|
| `/api/v1/stats/pipeline` | Состояние базы |
| `/api/v1/stats/quality` | История качества + обучение |
| `/api/v1/stats/mxik-health` | Здоровье синхронизации MXIK |

## Правила качества

**Критические** (блокируют авто-подтверждение):
- `BARCODE_CONFLICT` — штрихкод привязан к другому товару
- `INTERNAL_BC_AS_GLOBAL` — внутренний штрихкод передан как глобальный
- `BRAND_TYPE_MISMATCH` — бренд не соответствует типу товара

**Предупреждения** (штраф к confidence):
- `MISSING_BRAND` −0.15
- `MISSING_PRODUCT_TYPE` −0.20
- `MISSING_QUANTITY` −0.10
- `MISSING_MXIK` −0.10
- `MXIK_GROUP_CODE` −0.10

**Авто-подтверждение**: confidence ≥ 0.85 и нет критических проблем

## Опасные поля

Изменяются **только через решение оператора** (никогда автоматически):
`mxik_code`, `mxik_package_code`, `label_required`, `label_for_check`, `cash_sale`

## Бэкап

```bash
# Ручной бэкап
docker-compose exec backend python -m product_db.scripts.backup_db

# С параметрами
docker-compose exec backend python -m product_db.scripts.backup_db \
  --dir /backups --keep 14
```

## Обучение системы

После каждого решения оператора `learner.learn_from_decision()` вызывается синхронно:
- `correct_field(brand_id)` → добавляет вариант написания в `brand_aliases`
- Celery задача `batch_learn` перепроверяет решения каждый час (catch-all)

Новые aliases вступают в силу немедленно (кэш в `extract.py` сбрасывается).

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async URL |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://...` | Sync URL (Celery, скрипты) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis |
| `API_KEYS` | `` | Comma-separated API ключи (пусто = auth отключена) |
| `SENTRY_DSN` | `` | Sentry DSN (пусто = Sentry отключён) |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `LOG_JSON` | `false` | JSON-формат логов (для продакшна: `true`) |
| `BACKUP_DIR` | `/backups` | Папка для бэкапов |
