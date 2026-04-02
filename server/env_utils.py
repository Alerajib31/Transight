"""Environment helpers shared by the backend startup scripts."""

from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

SERVER_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SERVER_DIR, ".."))
DEFAULT_DATABASE_URL = "postgresql://postgres:R%40jibale3138@localhost:5432/transight_db"


def _strip_optional_quotes(value: str) -> str:
    """Remove a single matching quote pair from an env value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: str) -> bool:
    """Load KEY=VALUE pairs from a .env file without overriding process env."""
    if not os.path.exists(path):
        return False

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_optional_quotes(value.strip())
            if key and key not in os.environ:
                os.environ[key] = value

    return True


def load_project_env_files() -> list[str]:
    """Load the standard project env files if present."""
    loaded_paths = []
    for path in (
        os.path.join(SERVER_DIR, ".env"),
        os.path.join(PROJECT_ROOT, ".env"),
    ):
        if load_env_file(path):
            loaded_paths.append(path)
    return loaded_paths


def get_database_url() -> str:
    """Return the configured DATABASE_URL with the project default fallback."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_database_admin_config() -> dict[str, object]:
    """Build psycopg2 connection settings from DATABASE_URL."""
    parsed = urlparse(get_database_url())
    db_name = parsed.path.lstrip("/") or "transight_db"

    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or "postgres"),
        "password": unquote(parsed.password or ""),
        "target_db_name": db_name,
    }
