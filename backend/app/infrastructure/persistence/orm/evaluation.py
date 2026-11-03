"""Benchmark results: one row per (benchmark, task, system). Written only by the
benchmark command; platform-level data, not owned by a user."""

import uuid

from sqlalchemy import Boolean, Float, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.evaluation import SystemKind
from app.infrastructure.persistence.orm.base import Base, TimestampMixin, str_enum


class EvaluationRunModel(TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "task_id", "system", name="uq_evaluation_runs_benchmark_id_task_id_system"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    benchmark_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    system: Mapped[SystemKind] = mapped_column(str_enum(SystemKind), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    demo_model: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The system's own final test run.
    own_tests_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    own_tests_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    own_tests_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    own_tests_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The task's hidden reference tests against the system's final code.
    reference_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reference_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reference_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reference_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    debug_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    test_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocking_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    human_interventions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
