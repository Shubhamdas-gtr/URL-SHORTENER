"""Simple configuration constants for local development."""

from pathlib import Path

# Project root (parent of the `backend/` package).
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# SQLite database file lives in the project root and is created at runtime.
DB_PATH: Path = BASE_DIR / "urls.db"
SQLALCHEMY_DATABASE_URL: str = f"sqlite:///{DB_PATH}"

# Base URL used to build short links, e.g. http://localhost:8000/Ab3xYz
BASE_URL: str = "http://localhost:8000"
