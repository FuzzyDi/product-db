from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/product_db"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/product_db"
    redis_url: str = "redis://localhost:6379/0"

    # Авторизация: comma-separated. Пусто = auth отключена (dev)
    api_keys: str = ""

    # Sentry DSN (пусто = Sentry отключён)
    sentry_dsn: str = ""

    # Логирование
    log_level: str = "INFO"
    log_json: bool = False

    # Backup
    backup_dir: str = "/backups"

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
