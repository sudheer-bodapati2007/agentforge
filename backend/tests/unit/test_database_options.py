"""Engine options for the supported database targets, including Supabase specifics."""

from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.database import engine_options
from tests.conftest import make_settings

SUPABASE_DIRECT = "postgresql+psycopg://postgres:pw@db.example.supabase.co:5432/postgres"
SUPABASE_TRANSACTION_POOLER = (
    "postgresql+psycopg://postgres.ref:pw@aws-0-region.pooler.supabase.com:6543/postgres"
)


def test_sqlite_options():
    options = engine_options(make_settings("sqlite:///./x.db"))
    assert options["connect_args"] == {"check_same_thread": False}


def test_postgres_sets_connect_timeout_and_ssl_mode():
    options = engine_options(make_settings(SUPABASE_DIRECT, database_ssl_mode="require"))
    assert options["connect_args"]["sslmode"] == "require"
    assert options["connect_args"]["connect_timeout"] == 10
    assert "prepare_threshold" not in options["connect_args"]
    assert options["pool_pre_ping"] is True


def test_transaction_pooler_is_detected_from_port():
    options = engine_options(make_settings(SUPABASE_TRANSACTION_POOLER))
    assert options["connect_args"]["prepare_threshold"] is None
    assert options["poolclass"] is NullPool


def test_pooler_mode_can_be_forced():
    direct = engine_options(make_settings(SUPABASE_TRANSACTION_POOLER, database_pooler_mode="session"))
    assert "prepare_threshold" not in direct["connect_args"]
    forced = engine_options(make_settings(SUPABASE_DIRECT, database_pooler_mode="transaction"))
    assert forced["connect_args"]["prepare_threshold"] is None


def test_blank_optional_settings_are_treated_as_unset():
    settings = make_settings("sqlite://", database_ssl_mode="", llm_provider="  ", llm_api_key="")
    assert settings.database_ssl_mode is None
    assert settings.llm_provider is None
    assert settings.llm_api_key_present is False
