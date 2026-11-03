import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.orm.base import Base, TimestampMixin, str_enum
from app.domain.enums import ProgrammingLanguage

if TYPE_CHECKING:
    from app.infrastructure.persistence.orm.run import WorkflowRunModel


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Supabase Auth user id (auth.users.id). No FK: auth.users lives in another schema
    # that plain PostgreSQL deployments do not have. Rows from before auth existed are
    # NULL and therefore visible to nobody.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    requirements: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[ProgrammingLanguage] = mapped_column(
        str_enum(ProgrammingLanguage), nullable=False, default=ProgrammingLanguage.PYTHON
    )
    framework: Mapped[str | None] = mapped_column(String(80))
    database_preference: Mapped[str | None] = mapped_column(String(80))
    constraints: Mapped[str | None] = mapped_column(Text)

    runs: Mapped[list["WorkflowRunModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(WorkflowRunModel.created_at)",
    )
