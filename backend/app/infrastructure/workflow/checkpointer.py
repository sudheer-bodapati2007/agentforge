"""LangGraph checkpoint persistence.

PostgreSQL (Supabase or local): `PostgresSaver` over a small psycopg connection pool, so
a run survives process restarts and resumes from its last completed step. SQLite (tests):
in-memory saver. LangGraph creates its own tables; because Supabase exposes the public
schema through its Data API, Row Level Security is enabled on them right after setup.
"""

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.engine import make_url

from app.infrastructure.config import Settings
from app.infrastructure.persistence.database import uses_transaction_pooler

logger = logging.getLogger("agentforge.checkpointer")

CHECKPOINT_TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations")


def libpq_conninfo(settings: Settings) -> str:
    url = make_url(settings.database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


class Checkpointer:
    """Owns the saver and any connection pool behind it."""

    def __init__(self, saver: BaseCheckpointSaver, pool=None) -> None:
        self.saver = saver
        self._pool = pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()


def build_checkpointer(settings: Settings) -> Checkpointer:
    backend = make_url(settings.database_url).get_backend_name()
    if backend != "postgresql":
        logger.info("Using in-memory checkpoints (%s database): runs cannot resume after a restart", backend)
        return Checkpointer(InMemorySaver())

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    kwargs = {
        "autocommit": True,
        "row_factory": dict_row,
        # Supabase's transaction pooler cannot use prepared statements.
        "prepare_threshold": None if uses_transaction_pooler(settings) else 0,
        "connect_timeout": settings.database_connect_timeout_seconds,
    }
    if settings.database_ssl_mode:
        kwargs["sslmode"] = settings.database_ssl_mode
    pool = ConnectionPool(
        libpq_conninfo(settings), min_size=1, max_size=settings.worker_concurrency + 2, kwargs=kwargs, open=True
    )
    saver = PostgresSaver(pool)
    saver.setup()
    with pool.connection() as conn:
        for table in CHECKPOINT_TABLES:
            conn.execute(f'ALTER TABLE IF EXISTS "{table}" ENABLE ROW LEVEL SECURITY')
    return Checkpointer(saver, pool)
