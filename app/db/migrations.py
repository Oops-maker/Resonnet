"""Alembic migration runner."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .session import get_alembic_ini_path, get_database_url


def run_db_migrations() -> None:
    ini_path = get_alembic_ini_path()
    config = Config(str(ini_path))
    config.set_main_option("sqlalchemy.url", get_database_url().replace("%", "%%"))
    config.set_main_option("script_location", str(Path(ini_path).resolve().parent / "migrations"))
    command.upgrade(config, "head")
