"""Deterministic demo "model" (LLM_PROVIDER=scripted).

It is NOT an AI: it ignores the requirements and returns a fixed sample project (a small
task-tracking REST API). It exists so the full pipeline (sandboxed tests, the debugging
loop, review, documentation) can be demonstrated and tested without an API key. The
first version deliberately contains one bug, so the real test run fails, the debugging
step patches it, and the second real test run passes. The UI labels runs that use it.
"""

from app.application.agents.schemas import (
    ApiEndpoint,
    ArchitectureSpec,
    CodeChangeSet,
    Component,
    DataModel,
    DebugPatch,
    Documentation,
    FileContent,
    LLMFinding,
    PlannedFile,
    PlanTask,
    ProjectPlan,
    ReviewReport,
    SchemaDesign,
    TablePlan,
    TestSuite,
)
from app.application.llm import LLMError, LLMResult, T, TokenUsage

MODELS_PY = '''from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class Task(TaskCreate):
    id: int
'''

STORE_PY_TEMPLATE = '''from app.models import Task, TaskCreate


class TaskStore:
    """In-memory task repository."""

    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {{}}
        self._next_id = 1

    def add(self, data: TaskCreate) -> Task:
        task = Task(id=self._next_id, **data.model_dump())
        self._tasks[task.id] = task
        self._next_id += 1
        return task

    def list(self, *, done: bool | None = None) -> list[Task]:
        return [t for t in self._tasks.values() if done is None or t.done {op} done]

    def get(self, task_id: int) -> Task | None:
        return self._tasks.get(task_id)

    def complete(self, task_id: int) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        updated = task.model_copy(update={{"done": True}})
        self._tasks[task_id] = updated
        return updated

    def delete(self, task_id: int) -> bool:
        return self._tasks.pop(task_id, None) is not None
'''

MAIN_PY = '''from fastapi import FastAPI, HTTPException, Response, status

from app.models import Task, TaskCreate
from app.store import TaskStore


def create_app(store: TaskStore | None = None) -> FastAPI:
    app = FastAPI(title="Task API")
    tasks = store or TaskStore()

    def _require(task: Task | None) -> Task:
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    @app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
    def create_task(data: TaskCreate) -> Task:
        return tasks.add(data)

    @app.get("/tasks", response_model=list[Task])
    def list_tasks(done: bool | None = None) -> list[Task]:
        return tasks.list(done=done)

    @app.get("/tasks/{task_id}", response_model=Task)
    def get_task(task_id: int) -> Task:
        return _require(tasks.get(task_id))

    @app.post("/tasks/{task_id}/complete", response_model=Task)
    def complete_task(task_id: int) -> Task:
        return _require(tasks.complete(task_id))

    @app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_task(task_id: int) -> Response:
        if not tasks.delete(task_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
'''

TESTS_PY = '''import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_create_task_returns_201(client):
    response = client.post("/tasks", json={"title": "Write report"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "title": "Write report", "done": False}


def test_empty_title_is_rejected(client):
    assert client.post("/tasks", json={"title": ""}).status_code == 422


def test_list_filters_by_done(client):
    client.post("/tasks", json={"title": "a"})
    client.post("/tasks", json={"title": "b", "done": True})
    done = client.get("/tasks", params={"done": "true"}).json()
    assert [t["title"] for t in done] == ["b"]
    assert len(client.get("/tasks").json()) == 2


def test_missing_task_is_404(client):
    assert client.get("/tasks/99").status_code == 404


def test_complete_task(client):
    task_id = client.post("/tasks", json={"title": "a"}).json()["id"]
    assert client.post(f"/tasks/{task_id}/complete").json()["done"] is True


def test_delete_task(client):
    task_id = client.post("/tasks", json={"title": "a"}).json()["id"]
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404
'''

README_MD = """# Task API (AgentForge demo project)

> Produced by AgentForge's **scripted demo model**, not by an AI model. The same sample
> project is generated for every request so the pipeline can be demonstrated offline.

A small REST API for tracking tasks, built with FastAPI and an in-memory store.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/tasks` | Create a task (`title` 1-200 chars) |
| GET | `/tasks?done=` | List tasks, optionally filtered by completion |
| GET | `/tasks/{id}` | Get one task (404 if missing) |
| POST | `/tasks/{id}/complete` | Mark a task done |
| DELETE | `/tasks/{id}` | Delete a task |

## Run

```bash
pip install fastapi uvicorn
uvicorn app.main:app --reload
```

## Tests

```bash
pip install pytest httpx
pytest
```

## Limitations

- Data is kept in memory and lost on restart.
- No authentication.
"""


class ScriptedLLM:
    def __init__(self) -> None:
        self._name = "scripted-demo"

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def is_demo(self) -> bool:
        return True

    def generate(self, *, task: str, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        builder = getattr(self, f"_{task}", None)
        if builder is None:
            raise LLMError(f"The demo model has no scripted answer for {task!r}")
        value = builder()
        if not isinstance(value, schema):
            raise LLMError(f"The demo model produced {type(value).__name__}, expected {schema.__name__}")
        return LLMResult(value=value, usage=TokenUsage(), model=self._name)

    # Scripted answers, one per agent ------------------------------------------------

    def _planner(self) -> ProjectPlan:
        return ProjectPlan(
            summary=(
                "DEMO MODE: the scripted demo model ignores your requirements and always plans "
                "a small task-tracking REST API so the pipeline can be shown without an AI model."
            ),
            functional_requirements=[
                "Create tasks with a title",
                "List tasks, optionally filtered by completion",
                "Get, complete and delete a task by id",
            ],
            non_functional_requirements=["Input validation on all request bodies"],
            assumptions=["In-memory storage is acceptable for the demo"],
            open_questions=["Should tasks persist across restarts?"],
            tasks=[
                PlanTask(id="T1", title="Data models", description="Pydantic models for tasks"),
                PlanTask(id="T2", title="Task store", description="In-memory repository"),
                PlanTask(id="T3", title="HTTP API", description="FastAPI routes with 404 handling"),
            ],
            acceptance_criteria=[
                "POST /tasks returns 201 with the created task",
                "An empty title is rejected with 422",
                "GET /tasks?done=true returns only completed tasks",
                "Unknown ids return 404",
                "Completing and deleting tasks works",
            ],
            risks=["Data loss on restart (in-memory)"],
        )

    def _architect(self) -> ArchitectureSpec:
        return ArchitectureSpec(
            summary="Single FastAPI service with a repository class behind the routes.",
            components=[
                Component(name="API", responsibility="HTTP routes and error mapping"),
                Component(name="TaskStore", responsibility="In-memory persistence"),
            ],
            technology_decisions=["FastAPI + Pydantic for validation", "No database for the demo"],
            files=[
                PlannedFile(path="app/models.py", purpose="Pydantic models"),
                PlannedFile(path="app/store.py", purpose="In-memory repository"),
                PlannedFile(path="app/main.py", purpose="FastAPI application factory"),
            ],
            api_endpoints=[
                ApiEndpoint(method="POST", path="/tasks", description="Create"),
                ApiEndpoint(method="GET", path="/tasks", description="List"),
                ApiEndpoint(method="GET", path="/tasks/{id}", description="Read"),
                ApiEndpoint(method="POST", path="/tasks/{id}/complete", description="Complete"),
                ApiEndpoint(method="DELETE", path="/tasks/{id}", description="Delete"),
            ],
            data_models=[DataModel(name="Task", fields=["id: int", "title: str (1-200)", "done: bool"])],
            security_considerations=["Validate all input with Pydantic"],
            implementation_notes=["Use an app factory so tests get a fresh store"],
        )

    def _schema(self) -> SchemaDesign:
        # Only used for projects with a database. The scripted demo app itself keeps tasks in
        # memory; this migration still shows the schema step and the real database working.
        return SchemaDesign(
            summary="DEMO MODE: one tasks table with a title, a completion flag and a creation time.",
            tables=[TablePlan(name="tasks", purpose="One task to do")],
            migration_sql=(
                "CREATE TABLE tasks (\n"
                "    id BIGSERIAL PRIMARY KEY,\n"
                "    title TEXT NOT NULL CHECK (length(trim(title)) > 0),\n"
                "    completed BOOLEAN NOT NULL DEFAULT FALSE,\n"
                "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()\n"
                ");\n"
                "CREATE INDEX ix_tasks_completed ON tasks (completed);"
            ),
        )

    def _coder(self) -> CodeChangeSet:
        return CodeChangeSet(
            files=[
                FileContent(path="app/__init__.py", content=""),
                FileContent(path="app/models.py", content=MODELS_PY),
                # Deliberate bug for the demo: the completion filter is inverted.
                FileContent(path="app/store.py", content=STORE_PY_TEMPLATE.format(op="!=")),
                FileContent(path="app/main.py", content=MAIN_PY),
            ],
            notes="Routes delegate to TaskStore.",
        )

    def _tester(self) -> TestSuite:
        return TestSuite(files=[FileContent(path="tests/test_api.py", content=TESTS_PY)])

    def _debugger(self) -> DebugPatch:
        return DebugPatch(
            diagnosis="test_list_filters_by_done fails: TaskStore.list keeps tasks whose done flag differs from the filter.",
            root_causes=["Inverted comparison in TaskStore.list"],
            files=[FileContent(path="app/store.py", content=STORE_PY_TEMPLATE.format(op="=="))],
        )

    def _reviewer(self) -> ReviewReport:
        return ReviewReport(
            summary="Small, readable service. No security issues for an unauthenticated demo API.",
            findings=[
                LLMFinding(
                    severity="low",
                    category="maintainability",
                    title="In-memory store loses data on restart",
                    description="TaskStore keeps tasks in a dict.",
                    file_path="app/store.py",
                    suggestion="Back the repository with SQLite for persistence.",
                )
            ],
        )

    def _corrector(self) -> CodeChangeSet:
        return CodeChangeSet(files=[], notes="No corrections needed.")

    def _documenter(self) -> Documentation:
        return Documentation(readme=README_MD)
