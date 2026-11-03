# CLAUDE.md

AgentForge is a multi-agent software engineering platform: FastAPI + LangGraph backend,
React 19 + Vite + TypeScript frontend, Supabase (Postgres + Auth), and a Docker test sandbox.

**Start here: read [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the full picture, then [TODO.md](TODO.md).** It has the current status, the remaining work with
acceptance criteria, setup steps and known pitfalls. Update it when you finish a task.

## Commands

```bash
# Backend (from backend/; on Windows PowerShell prefix executables with .\)
.venv/Scripts/uvicorn app.main:app --reload --port 8000
.venv/Scripts/python -m pytest -q                         # SQLite; add TEST_DATABASE_URL for PostgreSQL
.venv/Scripts/alembic upgrade head | revision --autogenerate -m "..." | check

# Frontend (from frontend/)
npm run dev          # http://localhost:5173, proxies /api to :8000
npm test && npx oxlint && npx tsc -b && npm run build

# Sandbox image (needed for real test execution)
docker build -t agentforge-sandbox-python:2 docker/sandbox && docker pull postgres:17-alpine
```

## Rules

- **Clean architecture, both sides.** `domain` ← `application` (use cases + ports) ←
  `infrastructure` / `api` / `presentation`. Concrete classes are chosen only in
  `backend/app/bootstrap.py` and `frontend/src/app/main.tsx`. New external dependency =
  new port + adapter + fake for tests.
- **Never fabricate results.** Tests count as passed only when the sandbox's pytest run says
  so; metrics come from the database; `null` renders as "—". Label the scripted demo model
  as not AI.
- **Security:** every user-data query is owner-scoped (other users get 404); every new table
  gets RLS enabled in its migration; validate model-produced paths with
  `domain/workspace.normalize_path`; fence untrusted text with `prompts.untrusted()`; never
  put model output on a command line; never commit `.env` or secret-shaped literals (build
  fake keys at runtime in tests: GitHub push protection blocks them).
- **Workflow:** side effects are idempotent keyed upserts (LangGraph re-runs interrupted
  nodes); every graph loop has a capped counter with a test.
- **Migrations:** generate against the local DB, give new NOT NULL columns `server_default`,
  test upgrade/downgrade/upgrade and `alembic check`, then apply to Supabase.
- **Tests first-class:** add tests with every change; tests use `make_settings()` (never the
  developer's `.env`) and `drain(app)` to process queued runs.
- **Done = verified:** run the full check list in TODO.md, then commit and push. End commit
  messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Environment notes

Windows dev machine: use `127.0.0.1` not `localhost` for Postgres; read files as UTF-8 in
scripts; the Supabase password in `DATABASE_URL` is percent-encoded. Git in this repo is
pinned to the `Poornesh-2006` account with non-interactive credentials.
