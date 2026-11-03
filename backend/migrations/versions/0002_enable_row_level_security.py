"""enable row level security

Supabase exposes the `public` schema through its auto-generated Data API (PostgREST),
callable with the project's public anon key. Enabling RLS with no policies denies the
`anon` and `authenticated` roles, so the only way to the data is the AgentForge backend,
which connects as the table owner (owners bypass RLS unless FORCE is set).

Harmless on plain PostgreSQL; skipped on other dialects.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 21:40:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "projects",
    "workflow_runs",
    "agent_executions",
    "workflow_events",
    "artifacts",
    "test_results",
    "review_findings",
    "approval_requests",
    "alembic_version",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
