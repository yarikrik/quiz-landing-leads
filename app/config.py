from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    telegram_token: str = ""
    telegram_chat_id: str = ""
    sheet_id: str = ""
    google_credentials: Path = Path("data/credentials.json")
    service_zips: list[str] = field(default_factory=list)
    secret_key: str = "dev-secret"
    db_path: Path = Path("data/leads.db")
    rate_limit_per_hour: int = 5
    min_fill_seconds: float = 3.0      # швидше людина квіз не пройде
    token_ttl_seconds: int = 3 * 3600
    duplicate_window_minutes: int = 30
    timezone: str = "America/Chicago"   # час у повідомленнях і таблиці
    trust_proxy: bool = False           # брати IP з X-Forwarded-For (якщо стоїть за nginx/Cloudflare)

    def in_service_area(self, zip_code: str) -> bool:
        if not self.service_zips:
            return True
        return any(fnmatch.fnmatch(zip_code, p) for p in self.service_zips)


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    env = os.getenv
    return Settings(
        telegram_token=env("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=env("TELEGRAM_CHAT_ID", "").strip(),
        sheet_id=env("SHEET_ID", "").strip(),
        google_credentials=Path(env("GOOGLE_CREDENTIALS", "data/credentials.json")),
        service_zips=[z.strip() for z in env("SERVICE_ZIPS", "").split(",") if z.strip()],
        secret_key=env("SECRET_KEY", "dev-secret"),
        db_path=Path(env("DB_PATH", "data/leads.db")),
        rate_limit_per_hour=int(env("RATE_LIMIT_PER_HOUR", "5")),
        timezone=env("TIMEZONE", "America/Chicago"),
        trust_proxy=env("TRUST_PROXY", "0") in ("1", "true", "yes"),
    )
