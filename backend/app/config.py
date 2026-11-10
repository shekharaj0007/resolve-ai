"""Paths and environment settings. A local .env file is optional."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")

MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
DEFAULT_POSTGRES_URL = "postgresql+psycopg://resolve:resolve@localhost:5432/resolveai"


def sqlite_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "resolve.db"


def sqlite_url() -> str:
    return "sqlite:///" + sqlite_path().as_posix()


class Settings:
    def __init__(self) -> None:
        origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
        )
        self.cors_origins = [item.strip() for item in origins.split(",") if item.strip()]
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or None
        self.openai_base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.openai_model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

    @staticmethod
    def database_url() -> str:
        if os.getenv("DATABASE_URL"):
            return os.environ["DATABASE_URL"]
        if os.getenv("USE_SQLITE", "").lower() in {"1", "true", "yes"}:
            return sqlite_url()
        return DEFAULT_POSTGRES_URL


settings = Settings()
