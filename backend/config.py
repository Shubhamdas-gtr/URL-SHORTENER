"""Simple configuration constants for local development."""

import os
from pathlib import Path

# Project root (parent of the `backend/` package).
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# SQLite database file lives in the project root and is created at runtime.
DB_PATH: Path = BASE_DIR / "urls.db"
SQLALCHEMY_DATABASE_URL: str = f"sqlite:///{DB_PATH}"

# Base URL used to build short links, e.g. http://localhost:8000/Ab3xYz
# Set the BASE_URL environment variable in deployment (e.g. Render);
# it falls back to localhost for local development.
BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000")
