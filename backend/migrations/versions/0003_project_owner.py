"""project owner

Adds `projects.owner_id` (the Supabase Auth user id). Nullable so the migration works on
databases that already hold projects: rows created before authentication have no owner
and are visible to nobody, because every query filters on the signed-in user's id.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13 22:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Uuid(), nullable=True))
        batch_op.create_index(batch_op.f("ix_projects_owner_id"), ["owner_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_projects_owner_id"))
        batch_op.drop_column("owner_id")
