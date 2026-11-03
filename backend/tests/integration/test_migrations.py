"""Migrations stay in sync with the models, alongside tables other libraries own."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.persistence.orm import Base
from tests.conftest import BACKEND_ROOT, make_settings


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.attributes["settings"] = make_settings(database_url)
    return config


def test_alembic_check_ignores_langgraph_checkpoint_tables(migrated_database_url):
    # PostgresSaver.setup() creates these at runtime; Alembic must not try to drop them.
    engine = create_engine(migrated_database_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS checkpoint_migrations (v INTEGER PRIMARY KEY)"))
    try:
        command.check(alembic_config(migrated_database_url))  # raises if models and DB differ
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS checkpoint_migrations"))
        engine.dispose()


def test_every_table_has_row_level_security(migrated_database_url):
    """Supabase exposes `public` through its Data API: a table without RLS is readable
    with the public anon key. This covers tables added in future migrations too."""
    if not migrated_database_url.startswith("postgresql"):
        pytest.skip("row level security is a PostgreSQL feature")
    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as conn:
            enabled = dict(
                conn.execute(text("SELECT relname, relrowsecurity FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'")).all()
            )
    finally:
        engine.dispose()
    missing = [table for table in [*Base.metadata.tables, "alembic_version"] if not enabled.get(table)]
    assert missing == []


def test_every_migration_downgrades_and_upgrades_cleanly(tmp_path):
    url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    config = alembic_config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    engine = create_engine(url)
    try:
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
        command.upgrade(config, "head")
        assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
        command.check(config)
    finally:
        engine.dispose()
