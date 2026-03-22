from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="MusicKit", alias="APP_NAME")
    app_base_url: str = Field(alias="APP_BASE_URL")
    app_secret_key: str = Field(alias="APP_SECRET_KEY")
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_bot_username: str = Field(alias="TELEGRAM_BOT_USERNAME")
    telegram_webapp_url: str = Field(alias="TELEGRAM_WEBAPP_URL")
    jwt_expire_hours: int = Field(default=24, alias="JWT_EXPIRE_HOURS")
    jwt_cookie_secure: bool = Field(default=False, alias="JWT_COOKIE_SECURE")
    music_root: Path = Field(default=Path("/music"), alias="MUSIC_ROOT")
    app_db_path: Path = Field(default=Path("/app/data/app.db"), alias="APP_DB_PATH")
    download_dir_name: str = Field(default="Telegram Downloads", alias="DOWNLOAD_DIR_NAME")
    search_result_limit: int = Field(default=8, alias="SEARCH_RESULT_LIMIT")
    navidrome_internal_url: str = Field(default="http://navidrome:4533", alias="NAVIDROME_INTERNAL_URL")
    navidrome_external_base_url: str = Field(alias="NAVIDROME_EXTERNAL_BASE_URL")

    @property
    def download_root(self) -> Path:
        return self.music_root / self.download_dir_name

    @property
    def cookie_name(self) -> str:
        return "musickit_session"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.music_root.mkdir(parents=True, exist_ok=True)
    settings.download_root.mkdir(parents=True, exist_ok=True)
    settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
