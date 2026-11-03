"""SQLAlchemy engine construction for PostgreSQL (Supabase or local) and SQLite (tests)."""

import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.application.system import ComponentStatus
from app.infrastructure.config import Settings

logger = logging.getLogger("agentforge.database")

SUPABASE_TRANSACTION_POOLER_PORT = 6543


def uses_transaction_pooler(settings: Settings) -> bool:
    """Supabase's transaction pooler (port 6543) cannot use prepared statements."""
    if settings.database_pooler_mode != "auto":
        return settings.database_pooler_mode == "transaction"
    return make_url(settings.database_url).port == SUPABASE_TRANSACTION_POOLER_PORT


def engine_options(settings: Settings) -> dict:
    """Keyword arguments for `create_engine`, derived from settings (pure, unit-testable)."""
    backend = make_url(settings.database_url).get_backend_name()
    options: dict = {"echo": settings.database_echo, "pool_pre_ping": True}
    connect_args: dict = {}

    if backend == "sqlite":
        # FastAPI runs sync endpoints in a thread pool.
        connect_args["check_same_thread"] = False
    else:
        # Fail fast instead of hanging when the database (or an IPv6 route) is unreachable.
        connect_args["connect_timeout"] = settings.database_connect_timeout_seconds
        if settings.database_ssl_mode:
            connect_args["sslmode"] = settings.database_ssl_mode
        if uses_transaction_pooler(settings):
            # The pooler already pools connections and does not support prepared
            # statements, so disable both on our side.
            connect_args["prepare_threshold"] = None
            options["poolclass"] = NullPool
            del options["pool_pre_ping"]

    options["connect_args"] = connect_args
    return options


def build_engine(settings: Settings) -> Engine:
    engine = create_engine(settings.database_url, **engine_options(settings))

    if engine.dialect.name == "sqlite":
        # SQLite ignores ON DELETE CASCADE unless foreign keys are switched on per connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class SqlAlchemyDatabaseProbe:
    def __init__(self, session: Session) -> None:
        self._session = session

    def check(self) -> ComponentStatus:
        try:
            self._session.execute(text("SELECT 1"))
            return ComponentStatus("ok")
        except Exception as exc:  # report, never raise: status must answer when the DB is down
            logger.warning("Database health check failed: %s", exc.__class__.__name__)
            self._session.rollback()
            return ComponentStatus("error", "Database is unreachable")

    def backend_name(self) -> str:
        return self._session.get_bind().dialect.name
