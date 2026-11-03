# AgentForge: handoff and TODO

This file is for whoever continues the project next (a person or an AI coding agent).
Read it fully before changing code. The original product brief is summarised in
[Goal](#goal); the authoritative technical docs are in `docs/`.

Last updated: 2026-10-16. Phase 3 completed on `main`
(https://github.com/Poornesh-2006/agentforce).

---

## Goal

AgentForge is a portfolio project for an AI Engineer internship. It is a multi-agent
software engineering platform: a user describes software, and a LangGraph workflow of
specialised agents (planner, architect, coder, tester, debugger, reviewer, documenter)
plans it, writes code, runs real tests in an isolated Docker sandbox, debugs failures in a
bounded loop, reviews code with deterministic tools plus an LLM, and documents the result.

Non-negotiable product rules from the owner:

- **Never fabricate results.** Test outcomes come only from the real test runner. Metrics
  come only from persisted data. `null` is shown as "—", never as 0.
- **Clean architecture** on both backend and frontend (see [Rules](#rules-for-changing-code)).
- System design patterns used at scale (queues, idempotency, checkpoints, event logs).
- Test after every phase, then commit and push. Keep `main` working at every commit.
- Be honest in docs about limitations. Label the scripted demo model as "not AI".

## Status

| Phase | Scope | State |
| --- | --- | --- |
| 1 | App shell, projects, schema, dashboard, Supabase Postgres, Google + email auth | ✅ done |
| 2 | 7 agents, LangGraph engine, Docker sandbox, job queue + workers, SSE, run UI | ✅ done |
| 3 | Debug loop, review, approvals, report + end-to-end validation against the real sandbox | ✅ done |
| 4 | RAG knowledge base (hybrid retrieval, reranking, eval set) + execution history | ✅ done |
| 5 | Advanced UI (React Flow graph, code workspace, testing dashboard, agent activity) | ✅ done |
| 6 | Evaluation benchmark vs single-agent baseline, evaluations page | ✅ done (stronger-model run pending) |

Verified at the last commit: 206 backend tests pass (SQLite + PostgreSQL, including 5
end-to-end scenarios and 5 isolation tests against the real Docker sandbox); 60 frontend tests pass; lint,
type-check and build are clean; `pip-audit` / `npm audit` are clean. One real-model run
(local `qwen2.5-coder:7b`) fixed its own failing tests in 2 debug iterations and passed 6/6.

---

## Setup on a new machine

Prerequisites: Python 3.12, Node 24, Docker Desktop (running), Git. Optional: Ollama.

```bash
# 1. Secrets: .env is NOT in the repo. Create it from the template and fill in values.
cp .env.example .env
#    Needed: DATABASE_URL (+ DATABASE_SSL_MODE=require for Supabase), SUPABASE_URL,
#    VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY, LLM_PROVIDER, LLM_MODEL (+ LLM_API_KEY for Gemini).
#    Ask the project owner for the values. Never commit .env.

# 2. Local Postgres (used by the PostgreSQL test run; optional for the app if using Supabase)
docker compose up -d db          # user agentforge, password = POSTGRES_PASSWORD in .env
docker compose exec db psql -U agentforge -d agentforge -c "CREATE DATABASE agentforge_test"

# 3. Sandbox image (required for real test execution)
docker build -t agentforge-sandbox-python:2 docker/sandbox && docker pull postgres:17-alpine

# 4. Backend
cd backend
py -3.12 -m venv .venv                      # Linux/macOS: python3.12 -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/alembic upgrade head          # applies to DATABASE_URL from ../.env
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# 5. Frontend
cd ../frontend && npm install && npm run dev   # http://localhost:5173

# 6. Optional free local model
ollama pull qwen2.5-coder:7b                # then LLM_PROVIDER=ollama, LLM_MODEL=qwen2.5-coder:7b
```

On Windows PowerShell, run executables as `.\.venv\Scripts\uvicorn ...`.

## Verify everything (run before every commit)

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://agentforge:<POSTGRES_PASSWORD>@127.0.0.1:5432/agentforge_test \
  .venv/Scripts/python -m pytest -q                       # unit + integration + docker e2e
.venv/Scripts/python -m pip_audit -r requirements.txt
.venv/Scripts/alembic check                               # models and migrations in sync
AGENTFORGE_E2E_LLM=ollama:qwen2.5-coder:7b .venv/Scripts/python -m pytest -q -s tests/e2e/test_real_llm.py   # optional, slow
.venv/Scripts/python ../evals/scripts/run_benchmark.py --no-db   # regression benchmark (real model, ~25 min with a 7B model)
.venv/Scripts/python ../evals/scripts/run_retrieval_eval.py --embedder ollama   # retrieval eval with real embeddings (hash version runs in pytest)

cd ../frontend
npm test && npx oxlint && npx tsc -b && npm run build && npm audit --omit=dev
```

Tests marked `docker` skip automatically when Docker or the sandbox image is missing;
`tests/e2e/test_real_llm.py` runs only when `AGENTFORGE_E2E_LLM` is set.

---

## Where things are

```
backend/app/
  domain/          entities and rules, no frameworks (project, run state machine, workspace paths, testing, review)
  application/     use cases and ports: projects, dashboard, system, auth, runs/, workflow/, agents/
    workflow/steps.py     one method per graph node (all agent logic)
    workflow/routing.py   conditional edges as pure functions (all loops bounded)
    agents/prompts.py     prompts + untrusted-content fencing; SANDBOX_PACKAGES
    agents/schemas.py     Pydantic structured outputs per agent
    runs/service.py       quotas, idempotency, approvals, cancel, resume
  infrastructure/  adapters: persistence/ (ORM, repos, run journal = job queue), llm/, sandbox/,
                   workflow/ (LangGraph engine, checkpointer), worker/, auth/ (Supabase JWT), config.py
  api/             FastAPI routes, schemas, error mapping, middleware
  bootstrap.py     composition root (the ONLY place that picks concrete classes)
  main.py          create_app(); lifespan starts/stops workers
backend/migrations/versions/   0001..0004 (Alembic)
backend/tests/                 unit/, integration/, e2e/, fakes.py, conftest.py (drain() runs the queue)
frontend/src/
  domain/          types and rules (run.ts has WORKFLOW_NODES + nodeStates)
  application/     ports.ts, use-case hooks (use-cases/*.ts), auth-context, gateways-context
  infrastructure/  http-client, http gateways (DTO -> domain), supabase auth adapter, SSE parser
  presentation/    components/ (ui/, runs/, code/), layouts/, pages/
  app/             main.tsx (composition root), routes.tsx, AppProviders
  test/            fakes.ts (fake gateways), render.tsx (renderApp with real routes)
docker/sandbox/Dockerfile      sandbox image (keep packages in sync with SANDBOX_PACKAGES)
docs/                          architecture.md (system design), security.md, api.md, development.md, deployment.md
render.yaml, frontend/vercel.json   deployment config (owner has not deployed yet)
```

## Rules for changing code

1. **Dependencies point inward.** `domain` imports nothing from other layers;
   `application` imports only `domain`; infrastructure/api/presentation implement or use
   ports. Never import infrastructure from application, or `infrastructure/` from
   `presentation/` in the frontend.
2. **New concrete dependency → new port + adapter**, wired in `backend/app/bootstrap.py` or
   `frontend/src/app/main.tsx`. Tests inject fakes through `create_app(llm=..., sandbox=...)`
   or `renderApp(path, gateways)`.
3. **Every new DB table needs RLS enabled** (Supabase exposes `public` through its Data API).
   Add it in the migration. Every query on user data must be owner-scoped. Another user's
   resource must return 404, not 403.
4. **Workflow side effects must be idempotent** (keyed upserts). LangGraph re-runs an
   interrupted node from its start on resume.
5. **Every loop in the graph needs a capped counter.** Add a routing unit test proving it ends.
6. **Never trust model output**: validate paths with `domain/workspace.normalize_path`, fence
   untrusted text with `prompts.untrusted()`, and never put model output on a command line.
7. Migrations: autogenerate against the **local** database (not Supabase), add
   `server_default` to new NOT NULL columns, test upgrade → downgrade → upgrade, run
   `alembic check`, then apply to Supabase with `alembic upgrade head`.
8. Commit after each tested phase, ending the message with
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit `.env`.

## Known pitfalls (learned the hard way)

- **`localhost` hangs on Windows** (IPv6 `::1` first). Use `127.0.0.1` for local Postgres.
- **Supabase password contains `@`**: it must stay percent-encoded (`%40`) in `DATABASE_URL`.
  Use the **session pooler** (IPv4, port 5432); the direct host is IPv6-only.
- **GitHub push protection** rejects secret-shaped literals, even fake ones in tests.
  Build fake keys at runtime (see `tests/unit/test_routing_and_tools.py`).
- This repo's local git config pins `credential.https://github.com.username=Poornesh-2006`
  and `credential.interactive=false` (the owner wants no account-picker pop-ups).
- Python edit scripts on Windows: always `read_text(encoding="utf-8")` (the default cp1252 breaks).
- In a class, don't name a method `list`: it shadows `list[...]` in later annotations.
- Bash heredocs with complex quoting sometimes break in this environment; write scripts to a file.
- `ruff --per-file-ignores` needs `pattern:CODE` **per code** (`tests/*:S101,tests/*:S105`).
- The test fixtures disable workers (`run_workers=False`); call `drain(app)` to process runs.
- Tests must not read the developer's `.env`: use `make_settings()` (it passes `_env_file=None`).

---

## Remaining work

### Phase 3: done (2026-10-16)
- [x] End-to-end validation section in README (5 real-sandbox scenarios, all pass)
- [x] Frontend test for the corrections approval panel
- [x] Review and refactor pass, same behavior, fully re-tested:
  - backend `infrastructure/persistence/mapping.to_view()`: generic row-to-read-model
    mapping (run_repository.py 451 → 354 lines)
  - backend `steps.StepContext`: every model call goes through `step.ask()`, and usage is
    attached by `step.result()`; named write policies (`source_files`, `test_files`, ...)
    replace inline lambdas; `_File` stand-in removed
  - frontend `infrastructure/gateways/wire.ts` (`fromWire`, `toCamel`, `toSnake`) replaces
    hand-written DTO mapping (`http-run-gateway.ts` 361 → 148 lines, `dto.ts` deleted)
  - frontend test async budget raised (3 s) so tests are stable on loaded machines
- [x] Debugger memory (2026-10-16): a real `qwen2.5-coder:7b` run repeated the same wrong fix
      three times (edited `main.py` while the traceback named `counter_router.py`). State now
      keeps `debug_history` (diagnosis, files changed, failure fingerprint per attempt); the
      debugger prompt lists earlier attempts (fenced as untrusted) with whether each changed
      the failures, and says so explicitly when the failures are identical. `debug.patch`
      events carry `unchanged_failures`. Helpers: `steps.failure_signature`,
      `steps.attempts_for_prompt`.
- [x] Error toasts include the backend's reasons (`application/errors.errorMessage`), e.g.
      starting a run on a non-Python project no longer shows only "Request validation failed".
- [x] `alembic check` ignores LangGraph's checkpoint tables (`migrations/env.py include_name`);
      they are created by `PostgresSaver.setup()` and get RLS in `build_checkpointer`.

**Review checklist to repeat after every phase:** look for duplicated mapping or boilerplate
and extract a tested helper; keep layer boundaries; run the full verification list; never
change behavior in a refactor without a test proving it is unchanged.

### Phase 4: RAG knowledge base + execution history (done 2026-10-22)
- [x] `domain/knowledge.py` (upload rules, structure-aware chunking with line ranges),
      `application/knowledge/` (ports `Embedder`/`KnowledgeRepository`/`Reranker`, BM25 + RRF,
      lexical and LLM rerankers, `RetrievalPipeline`, `KnowledgeService`), infrastructure
      (pgvector repository via a custom `Vector` type, hash/Ollama/Gemini embedders, the
      workflow `KnowledgeRetriever`, an in-memory repository for evals). Migration 0006
      (`vector` extension, two tables, RLS).
- [x] API: `/api/projects/{id}/documents` (list/upload/chunks/reindex/delete) and
      `/api/projects/{id}/knowledge/search` (every stage's score). JSON upload, 400 KB cap.
- [x] UI: Knowledge Base page (upload, documents, chunk viewer, stale/re-index, delete,
      "test retrieval") and Execution History page (filters + per-run event log).
- [x] Retrieval eval: `evals/datasets/retrieval/` (9 docs, 36 labelled queries incl. negatives),
      `evals/scripts/run_retrieval_eval.py`, regression test `tests/unit/test_retrieval_eval.py`.
      Results and the design changes they caused are in the README.
- [x] Prompt-injection test: a poisoned document stays inside its fence in a real run.
- [x] Break-it fixes: secret redaction, name sanitising (incl. Unicode names), size/NUL/type
      checks, document and chunk quotas, concurrent same-name uploads (409 not 500), query
      cut at word boundaries, embedding outage handling, stale vectors after switching embedders.
- [ ] **Apply migration 0006 to Supabase** (with 0005), when the owner approves.
- [ ] Measure whether retrieval improves generated code: benchmark tasks that depend on
      project documents (needs a stronger model to be meaningful).

### Phase 5: advanced UI (done 2026-10-22)
- [x] Interactive workflow graph (`@xyflow/react` 12.12.0, lazy-loaded chunk): real topology
      from `WORKFLOW_EDGES` (mirrors the LangGraph wiring, incl. the three bounded loops),
      states from `nodeStates()`, attempt counts, the taken path highlighted. Selecting a step
      shows every attempt (status, summary/error, duration, tokens, next steps). An accessible
      step list is the keyboard/screen-reader view and the only view on phones. Layout checked
      in a real browser (headless Edge screenshot) and fixed (clipped labels, merged edges).
- [x] Code workspace: tree marks files with review findings and files revised by the
      debugger; findings render under their line (also findings citing lines past the end);
      jump to `file:line` from findings and from failing tests.
- [x] Testing dashboard: per-attempt stacked bar chart (HTML, no chart library) and failure
      links to files that exist.
- [x] Agent Activity page: active runs with the running agent, step, attempt and time in step
      (polls every 4 s), plus recently finished runs.
- [x] Keyboard: tabs now move focus with selection (arrow keys, Home/End); was a real bug.
      Fixed a racy dashboard test.

### Shared run memory + debugger guards (done 2026-10-22)
- [x] `application/workflow/memory.py`: shared notebook in state (`memory`), written by every
      agent and by AgentForge (facts per test run, measured verdicts per debug attempt:
      confirmed / partly / refuted / regressed), read by schema/coder/tester/debugger/corrector,
      streamed as `memory.added` events, Memory tab on the run page, in the final report.
- [x] `application/workflow/failures.py`: failure locations from the real traceback, files the
      debugger changed without effect, real-change detection.
- [x] Debugger: numbered files (+ stripping copied numbers), "Where the failures happen",
      STUCK note, tests may be fixed when they use the code incorrectly, regressed fixes are
      reverted, repeated failed diagnoses rejected with a restricted retry.
- [x] Replay of the real stuck run documented in the README (guards work; 7B still can't find the fix).

### Real PostgreSQL databases for generated projects (done 2026-10-22)
- [x] Sandbox image v2 (`psycopg[binary]`, trusted runner `run_database_tests.py`): per test run,
      an `--internal` network + throwaway `postgres:17-alpine` (tmpfs, limits, minimal caps),
      a non-superuser role with a random password, migrations applied in order, schema read
      back, then pytest. Cleanup always; labelled leftovers removed at startup.
- [x] Workflow: `schema` node (Database agent, `SchemaDesign`) for projects whose database
      preference is PostgreSQL; `DATABASE_ENVIRONMENT` added to every agent's request; coder
      cannot write migrations; debugger gets migration SQL errors; success requires migrations.
- [x] `test_results.database` (migration 0007); API and Database tab on the run page; graph
      node; project form hints and realistic placeholders.
- [x] Benchmark task 7 `db_schema` with reference tests that check database-enforced rules,
      a known-good solution and two known-bad schemas.
- [x] Break-it: endless migration (killed + cleaned), hostile/garbage schema report (rebuilt
      field by field), crash leftovers, `COPY … PROGRAM`, internet access, superuser checks.
- [ ] Supabase: apply migration 0007 together with 0005/0006 when the owner approves.

### Phase 6: evaluation (done 2026-10-22, except the stronger-model run and final docs)
- [x] `evals/datasets/tasks.json` + `tasks/<id>/prompt.md`: 6 tasks (REST API, input
      validation, CRUD, fix a planted bug, write tests for an existing function, add auth).
      Each has **hidden reference tests** and a known-good solution in `evals/datasets/solutions/`.
- [x] `tests/e2e/test_benchmark_dataset.py` (Docker): known-good solutions pass, known-bad
      variants fail, the runner scores a perfect system 100% and a crashing one 0%.
- [x] `evals/scripts/run_benchmark.py` (wired by `bootstrap.build_benchmark`): multi-agent
      workflow vs single-agent baseline, same prompt/sandbox/model. Grades with the reference
      tests against the system's `app/` code only. Records reference + own test tallies,
      debug iterations, findings, latency, tokens, cost, crashes. Stores rows in
      `evaluation_runs` (migration 0005 + RLS), writes `evals/reports/<id>.json` and saves
      every attempt's files and reference output under `evals/reports/<id>/`.
- [x] `GET /api/evaluations` and the Evaluations page (summary table, per-task bar chart,
      all-results table). Built with HTML/CSS bars, no chart library needed.
- [x] Break-it fixes: benchmark-id path traversal, a system's conftest/pytest config
      tampering with grading, Docker dying mid-run, malformed dataset, Ctrl+C keeps results.
- [x] Fixes found by the benchmark: agents after the planner now receive the original
      request (they lost details through the plan); output-token cap + per-call time budget
      (a looping model ran 56 min / 164k tokens).
- [ ] **Apply migration 0005 to Supabase** (`alembic upgrade head` with the Supabase
      `DATABASE_URL`) so the Evaluations page works in the deployed app.
- [ ] Re-run the benchmark with a stronger model (Gemini) once Phases 4–5 are done; the
      7B local model is the limiting factor (see README).
- [ ] Final docs pass: README screenshots, architecture diagram, limitations, deployment.

## Deployment (owner will do it; guide in docs/deployment.md)
Render (backend, `render.yaml`) + Vercel (frontend, root `frontend`) + Supabase. Render's
free plan has no Docker, so tests are reported as "not executed" there; full execution
needs a Docker-capable host. Supabase is at migration 0004 (re-run `alembic upgrade head`
after adding migrations).
