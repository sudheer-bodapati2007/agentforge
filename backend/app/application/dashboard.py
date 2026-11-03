"""Dashboard use case.

Infrastructure supplies raw aggregates through `DashboardReadModel`; this module owns
the business rules for turning them into metrics (e.g. a rate is undefined, not zero,
when there is nothing to divide by). No sample or synthetic data is ever produced.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.enums import TERMINAL_RUN_STATUSES, RunStatus
from app.domain.user import User

RECENT_LIMIT = 5


@dataclass(frozen=True)
class RecentRun:
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    status: RunStatus
    created_at: datetime
    duration_seconds: float | None


@dataclass(frozen=True)
class RecentProject:
    id: uuid.UUID
    name: str
    updated_at: datetime


@dataclass(frozen=True)
class DashboardSnapshot:
    total_projects: int
    run_status_counts: dict[RunStatus, int]
    executed_test_suites: int
    tests_passed: int
    tests_total: int
    run_durations_seconds: list[float]
    total_estimated_cost_usd: float | None
    recent_runs: list[RecentRun]
    recent_projects: list[RecentProject]


class DashboardReadModel(Protocol):
    def snapshot(self, owner_id: uuid.UUID, recent_limit: int) -> DashboardSnapshot:
        """Aggregates over the owner's projects (and their runs) only."""
        ...


@dataclass(frozen=True)
class DashboardMetrics:
    total_projects: int
    total_runs: int
    runs_by_status: dict[RunStatus, int]
    completion_rate: float | None
    test_pass_rate: float | None
    executed_test_suites: int
    average_duration_seconds: float | None
    total_estimated_cost_usd: float | None
    recent_runs: list[RecentRun]
    recent_projects: list[RecentProject]


def build_metrics(snapshot: DashboardSnapshot) -> DashboardMetrics:
    runs_by_status = {status: snapshot.run_status_counts.get(status, 0) for status in RunStatus}
    terminal = sum(runs_by_status[s] for s in TERMINAL_RUN_STATUSES)
    durations = snapshot.run_durations_seconds
    return DashboardMetrics(
        total_projects=snapshot.total_projects,
        total_runs=sum(runs_by_status.values()),
        runs_by_status=runs_by_status,
        completion_rate=runs_by_status[RunStatus.COMPLETED] / terminal if terminal else None,
        # Only suites the test runner actually executed contribute.
        test_pass_rate=snapshot.tests_passed / snapshot.tests_total if snapshot.tests_total else None,
        executed_test_suites=snapshot.executed_test_suites,
        average_duration_seconds=sum(durations) / len(durations) if durations else None,
        total_estimated_cost_usd=snapshot.total_estimated_cost_usd,
        recent_runs=snapshot.recent_runs,
        recent_projects=snapshot.recent_projects,
    )


class DashboardService:
    def __init__(self, read_model: DashboardReadModel) -> None:
        self._read_model = read_model

    def metrics(self, actor: User) -> DashboardMetrics:
        return build_metrics(self._read_model.snapshot(actor.id, RECENT_LIMIT))
