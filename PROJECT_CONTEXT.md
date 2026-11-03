# AgentForge: full project context for AI agents

Read this first if you are an AI coding agent (or a person) picking up this project with no
prior context. It explains what the project is, how it works, what state it is in, what
was learned while running it, and what to do next. More detail lives in:

- [TODO.md](TODO.md): task list with acceptance criteria, setup, verification commands, pitfalls
- [CLAUDE.md](CLAUDE.md): short rules for coding agents
- [docs/](docs/): `architecture.md`, `security.md`, `api.md`, `development.md`, `deployment.md`
- [README.md](README.md): public overview, end-to-end validation results, known limitations

Last updated: 2026-10-16 (after commit `19fa9a5`).

---

## 1. What AgentForge is

A **multi-agent software engineering platform**, built as a portfolio project for an AI
Engineer internship. A user describes the software they want; a LangGraph workflow of
specialised AI agents plans it, designs it, writes the code, writes tests, **runs the tests
for real in an isolated Docker sandbox**, debugs failures in a bounded loop, reviews the
code (static tools + LLM), and documents the result.

### The problem it addresses

Typical AI coding assistants produce code in one shot and leave verification to the user:
the code is never executed, success claims can be fabricated, and there is no record of how
the result was reached. AgentForge treats code generation as an engineering process: each
agent has one job, tests are really executed, failures loop back for repair, and every step
is persisted and visible in the UI.

### The owner's non-negotiable rules

1. **Never fabricate results.** Tests count as passed only when the sandbox's pytest run
   says so. Metrics come only from the database. Missing values render as "—", never as 0.
   The scripted demo model must be labelled "not AI".
2. **Clean architecture** on backend and frontend (see section 4).
3. Production-style system design: job queue, idempotency keys, checkpoints, event log.
4. Test after every change; keep `main` working at every commit; commit and push when verified.
5. Be honest in docs about limitations.

### Use cases

- Describe a small Python program or API and get code + real test results + review + docs.
- Watch the agents work live (server-sent events), approve or reject the plan.
- See the debugger fix failing tests by itself, within a retry limit.
- Upload your own docs so agents follow them (RAG, Phase 4), and test retrieval directly.
- Benchmark multi-agent vs a single LLM call on fixed tasks graded by hidden tests (Phase 6).

---

## 2. Tech stack

| Area | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Workflow | **LangGraph** (`langgraph`, `langgraph-checkpoint-postgres`) |
| LLM access | **LangChain** chat models only (`langchain-core`, `langchain-ollama`, `langchain-google-genai`) |
| Models | Ollama `qwen2.5-coder:7b` (local, free, currently configured), Google Gemini (needs `LLM_API_KEY`), or `scripted` (deterministic demo, labelled not AI) |
| Database + auth | Supabase (Postgres + Auth: Google OAuth and email/password), RLS on every table |
| Sandbox | Docker image `agentforge-sandbox-python:2` (offline, runs pytest) |
| Frontend | React 19, Vite, TypeScript, TanStack Query, Tailwind, Vitest |
| Deploy config | `render.yaml` (backend), `frontend/vercel.json` (not deployed yet) |

**How LangChain/LangGraph are used:** LangGraph is the workflow engine (graph of nodes,
conditional edges, `interrupt()` for human approval, Postgres checkpointer for resume).
LangChain is used *only* as the adapter to call models with structured (Pydantic) output.
No LangChain agents, chains or retrievers. All agent logic is our own code, and both
libraries sit behind our own ports so tests run with fakes.

---

## 3. How a run works

### The graph

```
plan -> architect -> plan_approval --approved--> code -> write_tests -> run_tests
            ^              |--rejected+feedback--^ (max 2 revisions)
                           '--rejected--> report
run_tests --pass--> review --blocking findings--> correction_approval --approved--> correct -> run_tests
    |                  '--clean--------------------------------------------------> document
    |--fail, retries left--> debug -> run_tests
    '--fail at retry limit / sandbox unavailable --> document -> report -> END
```

| Node | Agent | What it does |
| --- | --- | --- |
| `plan` | Planner | Requirements → tasks, acceptance criteria, assumptions |
| `architect` | Architect | Components and planned files |
| `plan_approval` | (human) | Pauses for approve/reject/feedback if the run requires approval |
| `code` | Coder | Writes application files under `app/` |
| `write_tests` | Tester | Writes pytest files under `tests/` |
| `run_tests` | (sandbox) | Runs pytest in Docker; the **only** source of test outcomes |
| `debug` | Debugger | Reads real failures and patches files (bounded loop) |
| `review` | Reviewer | Secret scan + static analysis tools + LLM review |
| `correction_approval` | (human) | Pauses before applying fixes for blocking findings |
| `correct` | Coder | Applies review fixes, then tests re-run |
| `document` | Documenter | Writes README with a verified-results section |
| `report` | (none) | Final outcome: `completed`, `partially_completed` or `cancelled` |

### Rules that surprise people

- **Review only runs when tests pass.** If tests still fail at the debug limit, the graph goes
  straight to `document`, so review and correction approval are skipped
  (`routing.after_tests`). Unverified code is never reviewed.
- **Correction approval only appears for blocking findings:** tool findings of severity
  high/critical, or LLM findings of severity critical (`domain/review.Finding.blocking`).
  Clean code goes straight to documentation.
- **Limits (settings):** `max_debug_iterations=3`, `max_review_corrections=1`, plan revisions 2,
  `worker_concurrency=2`, `max_active_runs_per_user=2`, `max_runs_per_user_per_hour=20`,
  LLM timeout 180 s with 2 retries.
- **Only Python projects can run.** The project form offers Python, TypeScript and JavaScript
  (the owner wants all shown), but `RunService.start` rejects non-Python projects with a 422
  ("only Python projects can be executed by this version of AgentForge") because the sandbox
  only runs pytest. The error toast now shows that reason. Supporting JS/TS for real needs a
  Node sandbox image, tester prompts for a JS test runner, and report parsing.
- **Sandbox packages:** generated code may only import the standard library plus `pytest`,
  `fastapi`, `httpx`, `pydantic`, `sqlalchemy` (`prompts.SANDBOX_PACKAGES`; a test keeps this
  in sync with `docker/sandbox/Dockerfile`). No network inside the sandbox.

### Debugger memory (added 2026-10-16)

A real run with `qwen2.5-coder:7b` repeated the same wrong fix three times (it kept editing
`app/main.py` while the traceback named `app/routers/counter_router.py`). Now:

- State keeps `debug_history`: per attempt the diagnosis, files changed and a fingerprint of
  the failures it targeted (`steps.failure_signature`).
- The debugger prompt lists earlier attempts (fenced as untrusted text) with whether each one
  changed the failures (`steps.attempts_for_prompt`), and adds an explicit note when the
  failures are identical (`prompts.UNCHANGED_FAILURES_NOTE`).
- `debug.patch` events carry `unchanged_failures`.
- Not yet measured on a real model run: verify with a rehearsal run.

### Persistence and reliability

- Runs go into a database-backed job queue (`run journal`); background workers claim them.
- LangGraph checkpoints are stored in Postgres (`checkpoints`, `checkpoint_blobs`,
  `checkpoint_writes`, `checkpoint_migrations`; created by `PostgresSaver.setup()`, RLS
  enabled in `build_checkpointer`, ignored by `alembic check` via `migrations/env.py`).
- LangGraph re-runs an interrupted node from its start, so all side effects are idempotent
  keyed upserts. Every loop has a capped counter with a test.
- Every step is written to `workflow_events` and streamed to the UI over SSE.

---

## 4. Code map and architecture rules

```
backend/app/
  domain/          entities and rules, no frameworks (project, run state machine, workspace paths, testing, review)
  application/     use cases + ports: projects, dashboard, system, auth, runs/, workflow/, agents/
    workflow/steps.py     one method per graph node (all agent logic)
    workflow/routing.py   conditional edges as pure functions (all loops bounded)
    workflow/state.py     WorkflowState TypedDict
    agents/prompts.py     prompts + untrusted-content fencing; SANDBOX_PACKAGES
    agents/schemas.py     Pydantic structured outputs per agent
    runs/service.py       quotas, idempotency, approvals, cancel, resume, language check
  infrastructure/  adapters: persistence/ (ORM, repos, run journal = job queue), llm/ (factory,
                   LangChain adapter, scripted model), sandbox/ (Docker), workflow/ (LangGraph
                   engine, checkpointer), worker/, auth/ (Supabase JWT), config.py
  api/             FastAPI routes, schemas, error mapping (domain invariant -> 422), middleware
  bootstrap.py     composition root: the ONLY place that picks concrete classes
backend/migrations/versions/   0001..0004
backend/tests/                 unit/, integration/, e2e/ (real Docker), fakes.py, conftest.py
frontend/src/
  domain/          types and rules (run.ts: WORKFLOW_NODES, nodeStates)
  application/     ports.ts, use-case hooks, errors.ts (AppError, errorMessage)
  infrastructure/  http client, gateways (DTO -> domain), Supabase auth adapter, SSE parser
  presentation/    components/, layouts/, pages/
  app/main.tsx     composition root
docker/sandbox/Dockerfile      sandbox image
```

Rules (from CLAUDE.md / TODO.md):

1. Dependencies point inward: `domain` ← `application` ← `infrastructure`/`api`/`presentation`.
2. New external dependency = new port + adapter + fake for tests, wired only in a composition root.
3. Every new table gets RLS enabled in its migration; every user-data query is owner-scoped
   (another user's resource returns 404, not 403).
4. Never trust model output: validate paths with `domain/workspace.normalize_path`, fence
   untrusted text with `prompts.untrusted()`, never put model output on a command line.
5. Migrations: autogenerate against the local DB, `server_default` for new NOT NULL columns,
   test upgrade/downgrade/upgrade and `alembic check`, then apply to Supabase.
6. Tests use `make_settings()` (never the developer's `.env`) and `drain(app)` to process runs.
7. Never commit `.env` or secret-shaped literals (GitHub push protection blocks even fakes).
8. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

## 5. Current status

| Phase | Scope | State |
| --- | --- | --- |
| 1 | App shell, projects, schema, dashboard, Supabase, Google + email auth | done |
| 2 | 7 agents, LangGraph engine, Docker sandbox, queue + workers, SSE, run UI | done |
| 3 | Debug loop, review, approvals, report, end-to-end validation | done |
| 3+ | Debugger memory, clearer error toasts, alembic check fix (2026-10-16) | done |
| 4 | RAG knowledge base (hybrid retrieval, reranking, retrieval eval) + execution history | done (2026-10-22) |
| 5 | Advanced UI (React Flow graph, code workspace, testing dashboard, agent activity) | done (2026-10-22) |
| 6 | Benchmark vs single-agent baseline (hidden reference tests), evaluations page | done (2026-10-22); stronger-model run pending |
| + | Real PostgreSQL per test run for projects with Database = PostgreSQL (schema agent, migrations, schema read-back, Database tab, benchmark task 7) | done (2026-10-22) |

Phase 6 was built before Phases 4–5 at the owner's request. Its benchmark (README) showed
the 7B local model is the main limit. Migrations 0005–0007 are local only. The owner does not
want to pay for Gemini; the free tier ran out of quota quickly. **Next: switch to a stronger model (Gemini; set
`LLM_PROVIDER=google`, `LLM_MODEL`, `LLM_API_KEY`) and re-run every eval set**, then the final
docs pass (screenshots, deployment). Migrations 0005 and 0006 are applied to
the local database only: **Supabase is still at 0004 until the owner approves.**

Evaluation sets to re-run after every phase (owner's rule): `tests/e2e/test_benchmark_dataset.py`
(Docker), `evals/scripts/run_benchmark.py`, `tests/unit/test_retrieval_eval.py` and
`evals/scripts/run_retrieval_eval.py --embedder ollama` (needs `ollama pull nomic-embed-text`).

Verified on 2026-10-16: backend **213 passed, 1 skipped** (SQLite + PostgreSQL + real Docker
sandbox; the skipped test is the optional real-LLM test), frontend **61 passed**, oxlint,
`tsc -b` and build clean, `alembic check` clean against Supabase (migration 0004).

Environment state on the owner's machine (2026-10-16): `.env` configured for Supabase and
`LLM_PROVIDER=ollama`, `LLM_MODEL=qwen2.5-coder:7b`; `LLM_API_KEY` is empty (only needed for
Gemini). Docker Desktop, the local Postgres container, the sandbox image and Ollama with the
model are installed and working. The model runs 100% on GPU.

---

## 6. Running it locally (Windows)

```powershell
# Prerequisites running: Docker Desktop, Ollama app

# Backend (from backend/). IMPORTANT: uvicorn.exe is blocked by Windows Application
# Control on this machine; start it through python instead:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# Frontend (from frontend/)
npm run dev        # open http://localhost:5173 (use localhost, not 127.0.0.1)

# Warm up the model before a demo (cold start took 89 s; it unloads after 5 idle minutes)
Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -Body '{"model":"qwen2.5-coder:7b","prompt":"hi","stream":false,"keep_alive":"2h","options":{"num_ctx":16384}}'
```

Verification before every commit (see TODO.md for the exact commands):
backend `pytest` with `TEST_DATABASE_URL` set to the local `agentforge_test` database,
`alembic check`, `pip_audit`; frontend `npm test`, `npx oxlint`, `npx tsc -b`, `npm run build`.

Known machine quirks: use `127.0.0.1` for Postgres (not `localhost`); read files as UTF-8 in
scripts; PowerShell 5.1 breaks `git commit -m` messages containing double quotes (use
`git commit -F <file>`); `ruff` is not installed in the venv.

---

## 7. Lessons from real runs (2026-10-16)

**Run `301a6995` (prompt: counter app with dark/light mode, language Python, qwen 7B):**
plan → architect → plan approved → coder wrote 8 files (FastAPI routers, services,
repository, SQLite) → tester wrote 2 test files → tests 0/2 with 2 collection errors →
3 debug attempts, all failing the same way → debug limit reached → document → report
`partially_completed`. Took about 3 minutes. Review and correction approval were skipped by
design (tests never passed). Root cause: `counter_router.py` used `Repository` without
importing it; the debugger edited the wrong file each time. Further latent bugs: tests
imported a non-existent `app.repository`, `main.py` passed router modules to `include_router`.

**Takeaways:**

- A 7B local model over-engineers vague prompts into multi-file apps it cannot debug.
  Small, specific, single-file Python prompts succeed far more often.
- UI behaviour (a theme toggle's look) cannot be verified: the sandbox runs pytest only.
  Ask for the *logic* (a `toggle_theme()` method) instead.
- A stronger model (Gemini) is a config change: `LLM_PROVIDER=google`, `LLM_MODEL=<model>`,
  `LLM_API_KEY=<key>`. Without price settings the cost shows "—". Rehearse before switching.

**A project created as JavaScript** returned 422 on run start (see section 3).

---

## 8. Demo plan (interview)

Recommended demo prompt (Python project):

> Build a counter in Python in a single file `app/counter.py`. Create a `Counter` class with
> `increment()`, `decrement()` and `reset()`, and a `value` that starts at 0. Add a theme
> setting that starts as "light", with `toggle_theme()` switching between "light" and
> "dark", and `set_theme(name)` that raises `ValueError` for anything other than "light" or
> "dark". Keep everything in memory: no web framework and no database. Write pytest tests
> in `tests/test_counter.py`.

Flow to show: log in (email/password is safer than Google on localhost) → create project
(Language: Python) → Run Project with approval on → watch agents live → approve plan →
real test results from Docker → debug loop if needed → review → README/report. Have a
finished rehearsal run open as a fallback if the live model is slow. In a terminal, show
`docker ps` and `docker images agentforge-sandbox-python` during the run.

Talking points: why multi-agent (narrow roles, structured outputs, testable); LangGraph
(conditional edges, bounded loops, interrupts for human approval, Postgres checkpoints for
resume); queue + idempotency; sandbox security (no network, paths validated, untrusted text
fenced, model output never on a command line); clean architecture with a composition root;
RLS and owner-scoped queries; honest reporting (`partially_completed` instead of fake success).

Honest limitations to state: not benchmarked yet (Phase 6); Python-only execution; free
Render plan has no Docker, so a deployed backend cannot execute tests; small local models
are slow and fail on larger tasks.

---

## 9. What to do next (priority order)

1. **Rehearsal run** with the demo prompt; confirm the debugger memory helps and record the time.
2. **Phase 6 benchmark** (strongest interview story): 6 tasks, multi-agent vs single-agent
   baseline, real numbers in the README. See TODO.md for the spec.
3. **Phase 4 RAG**: `Document`/`Chunk`, `Embedder` and `VectorIndex` ports, pgvector,
   upload API + Knowledge Base page, retrieval eval (hit@k, MRR). The workflow already calls
   a `Retriever` port (currently `NullRetriever`).
4. **Phase 5 UI**: React Flow graph, code workspace, charts, Agent Activity page.
5. Possible improvements: Node sandbox for JS/TS projects; early stop when debug failures
   repeat; reviewer pass on failing code (currently skipped by design).

When you finish a task: update [TODO.md](TODO.md) and this file, run the full verification
list, then commit and push.
