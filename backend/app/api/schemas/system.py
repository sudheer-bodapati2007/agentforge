import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

ComponentState = Literal["ok", "error", "not_configured", "not_implemented"]


class ComponentStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: ComponentState
    detail: str | None = None


class LLMStatus(ComponentStatus):
    provider: str | None
    model: str | None
    api_key_present: bool
    demo: bool = False


class SystemStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    app_name: str
    version: str
    environment: str
    database: ComponentStatus
    database_backend: str
    llm: LLMStatus
    workflow_engine: ComponentStatus
    sandbox: ComponentStatus
    max_debug_iterations: int


class Health(BaseModel):
    status: Literal["ok", "degraded"]


class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    name: str | None
    avatar_url: str | None
