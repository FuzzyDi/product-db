# Windows Server Deployment

Текущая рабочая схема для `product-db` на Windows Server.

## Что развёрнуто

- Backend / worker / beat / PostgreSQL / Redis поднимаются через `docker-compose.server.yml`
- Frontend собирается в production и обслуживается отдельным Node-процессом на хосте Windows
- Frontend запускается через `Task Scheduler`
- Backend защищён через `X-API-Key`

## Почему нужен отдельный compose

На целевом сервере `docker pull` из публичных registry в SSH-сессии падает с ошибкой:

```text
error getting credentials - err: exit status 1, out: `A specified logon session does not exist. It may already have been terminated.`
```

Поэтому backend временно собирается из локального образа `sbg-root-portal-portal-api`, который уже существует на сервере.

Файл для этого:

- `Dockerfile.server`

## Backend stack

Используются порты:

- `8001` -> backend
- `5436` -> PostgreSQL
- `6382` -> Redis

Запуск:

```powershell
docker compose -f docker-compose.server.yml up -d --build
```

Миграции:

```powershell
docker compose -f docker-compose.server.yml exec -T backend alembic upgrade head
```

Заполнение базовых справочников:

```powershell
docker compose -f docker-compose.server.yml exec -T backend python -m product_db.scripts.seed_refs
```

## Frontend

Серверный production frontend использует:

- `frontend/server.mjs`
- `npm run build`
- `npm run serve:prod`
- `scripts/windows/run-frontend-prod.ps1`
- `scripts/windows/register-frontend-task.ps1`
- `scripts/windows/health-check.ps1`
- `scripts/windows/restart-stack.ps1`

Ручной запуск на сервере:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\run-frontend-prod.ps1
```

Только production build:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\run-frontend-prod.ps1 -BuildOnly
```

Регистрация автозапуска через `Task Scheduler`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\register-frontend-task.ps1 `
  -UserName 'Rashid' `
  -Password '<password>'
```

Если production build уже собран и не нужен rebuild на старте:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\register-frontend-task.ps1 `
  -UserName 'Rashid' `
  -Password '<password>' `
  -SkipBuild
```

Контролируемый restart:

```powershell
# backend + frontend
powershell -ExecutionPolicy Bypass -File .\scripts\windows\restart-stack.ps1

# только frontend
powershell -ExecutionPolicy Bypass -File .\scripts\windows\restart-stack.ps1 -FrontendOnly

# только backend stack
powershell -ExecutionPolicy Bypass -File .\scripts\windows\restart-stack.ps1 -BackendOnly
```

## Проверки

Backend:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/health
```

Frontend:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3002
```

API через frontend proxy:

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Headers @{ 'X-API-Key' = '<api-key>' } `
  http://127.0.0.1:3002/api/v1/stats/pipeline
```

Единая проверка стенда:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\health-check.ps1 `
  -ApiKey '<api-key>'
```

## Риски

- `Dockerfile.server` зависит от локального образа на сервере и не является переносимым production baseline
- проблема Docker Desktop credential helper на сервере ещё не устранена в корне
- `API_KEYS` и другие секреты должны оставаться только в серверном `.env`
