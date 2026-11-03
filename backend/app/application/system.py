"""System status use case: reports what is configured and working, honestly."""

from dataclasses import dataclass
from typing import Literal, Protocol

ComponentState = Literal["ok", "error", "not_configured", "not_implemented"]


@dataclass(frozen=True)
class ComponentStatus:
    state: ComponentState
    detail: str | None = None


@dataclass(frozen=True)
class LLMConfiguration:
    provider: str | None
    model: str | None
    api_key_present: bool
    configured: bool = False
    demo: bool = False
    detail: str | None = None


@dataclass(frozen=True)
class LLMStatus(ComponentStatus):
    provider: str | None = None
    model: str | None = None
    api_key_present: bool = False
    demo: bool = False


@dataclass(frozen=True)
class SystemStatus:
    app_name: str
    version: str
    environment: str
    database: ComponentStatus
    database_backend: str
    llm: LLMStatus
    workflow_engine: ComponentStatus
    sandbox: ComponentStatus
    max_debug_iterations: int


class SandboxProbe(Protocol):
    def status(self) -> "SandboxStatusLike": ...


class SandboxStatusLike(Protocol):
    available: bool
    detail: str | None


class DatabaseProbe(Protocol):
    def check(self) -> ComponentStatus: ...

    def backend_name(self) -> str: ...


@dataclass(frozen=True)
class AppInfo:
    app_name: str
    version: str
    environment: str
    max_debug_iterations: int


class SystemStatusService:
    def __init__(
        self,
        app_info: AppInfo,
        llm: LLMConfiguration,
        database: DatabaseProbe,
        sandbox: SandboxProbe | None = None,
        worker_running: bool = False,
    ) -> None:
        self._app_info = app_info
        self._llm = llm
        self._database = database
        self._sandbox = sandbox
        self._worker_running = worker_running

    def is_healthy(self) -> bool:
        return self._database.check().state == "ok"

    def status(self) -> SystemStatus:
        llm = LLMStatus(
            state="ok" if self._llm.configured else "not_configured",
            detail=("Demo model: scripted output, not AI" if self._llm.demo else None)
            if self._llm.configured
            else self._llm.detail or "Set LLM_PROVIDER and LLM_MODEL",
            provider=self._llm.provider,
            model=self._llm.model if not self._llm.demo else "scripted-demo",
            api_key_present=self._llm.api_key_present,
            demo=self._llm.demo,
        )
        if not self._llm.configured:
            engine = ComponentStatus("not_configured", "Needs a configured LLM provider")
        elif not self._worker_running:
            engine = ComponentStatus("not_configured", "Run workers are disabled (WORKER_ENABLED=false)")
        else:
            engine = ComponentStatus("ok", "LangGraph workflow with background workers")

        if self._sandbox is None:
            sandbox = ComponentStatus("not_configured", "No sandbox configured")
        else:
            probe = self._sandbox.status()
            sandbox = ComponentStatus("ok", probe.detail) if probe.available else ComponentStatus("not_configured", probe.detail)

        return SystemStatus(
            app_name=self._app_info.app_name,
            version=self._app_info.version,
            environment=self._app_info.environment,
            database=self._database.check(),
            database_backend=self._database.backend_name(),
            llm=llm,
            workflow_engine=engine,
            sandbox=sandbox,
            max_debug_iterations=self._app_info.max_debug_iterations,
        )
