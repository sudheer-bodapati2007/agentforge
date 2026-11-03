from logging.config import fileConfig

from alembic import context

from app.infrastructure.config import get_settings
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.persistence.orm import Base
from app.infrastructure.persistence.orm.base import UTCDateTime
from app.infrastructure.persistence.orm.vector import Vector
from app.infrastructure.workflow.checkpointer import CHECKPOINT_TABLES

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Programmatic callers (the test suite) pass complete Settings so nothing leaks in from a
# developer's .env; the CLI uses application settings.
settings = config.attributes.get("settings") or get_settings()

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Render app-specific column types as plain SQLAlchemy types in migration files."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    if type_ == "type" and isinstance(obj, Vector):
        return "VECTOR  # define as in 0006: sa.Text().with_variant(<pgvector type>, 'postgresql')"
    return False


def include_name(name, type_, parent_names):
    """Skip LangGraph's checkpoint tables: PostgresSaver.setup() creates and migrates them
    itself (and build_checkpointer enables RLS on them), so Alembic must not drop them."""
    return not (type_ == "table" and name in CHECKPOINT_TABLES)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        include_name=include_name,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Same engine construction as the app, so SSL/pooler settings (e.g. Supabase) apply.
    connectable = build_engine(settings)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            include_name=include_name,
            # Batch mode lets ALTER-style migrations work on SQLite too.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
