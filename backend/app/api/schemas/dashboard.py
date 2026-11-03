import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import RunStatus


class RecentRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    status: RunStatus
    created_at: datetime
    duration_seconds: float | None


class RecentProject(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    updated_at: datetime


class DashboardMetrics(BaseModel):
    """Rates and averages are null when there is no data; clients must not render null as 0."""

    model_config = ConfigDict(from_attributes=True)

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
