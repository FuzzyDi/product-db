from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/product_db"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/product_db"
    redis_url: str = "redis://localhost:6379/0"

    # Авторизация: comma-separated API keys. Пусто = auth отключена (dev)
    api_keys: set[str] = set()

    # Sentry DSN (пусто = Sentry отключён)
    sentry_dsn: str = ""

    # Логирование
    log_level: str = "INFO"
    log_json: bool = False   # True в продакшне

    # Backup
    backup_dir: str = "/backups"

    class Config:
        env_file = ".env"


settings = Settings()
