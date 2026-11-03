# API

Interactive docs: `http://localhost:8000/api/docs` (OpenAPI at `/api/openapi.json`).

Every error has the same shape:

```json
{ "error": { "code": "validation_error", "message": "Request validation failed",
             "details": [{ "loc": ["body", "requirements"], "msg": "...", "type": "string_too_short" }] } }
```

Codes: `unauthorized` (401), `not_found` (404), `conflict` (409), `payload_too_large` (413),
`validation_error` (422), `rate_limited` (429, with `Retry-After`),
`auth_unavailable` / `database_unavailable` / `capability_unavailable` (503), `internal_error` (500).

**Authentication:** every endpoint except `/api/health` requires
`Authorization: Bearer <Supabase access token>`. All project and dashboard data is scoped
to the authenticated user; another user's project id returns 404.

## Implemented (Phase 1)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | Public. `{"status":"ok"}`, or 503 `{"status":"degraded"}` when the DB is unreachable |
| GET | `/api/me` | The verified user: `id`, `email`, `name`, `avatar_url` |
| GET | `/api/system/status` | Component states: `ok`, `error`, `not_configured`, `not_implemented`. Never includes secrets |
| GET | `/api/projects?q=&limit=&offset=` | `{items, total}`; case-insensitive name search; `limit` ≤ 100 |
| POST | `/api/projects` | Body: `name`, `requirements` (20–20,000 chars), `language` (`python`, `typescript`, `javascript`), optional `framework`, `database_preference`, `constraints` |
| GET | `/api/projects/{id}` | Includes `run_count` and `latest_run_status` |
| PATCH | `/api/projects/{id}` | Partial update; blank optional fields clear; required fields cannot be null |
| DELETE | `/api/projects/{id}` | 204; cascades to runs and their records |
| GET | `/api/dashboard/metrics` | Totals, rates (null when undefined), recent runs and projects |

### Workflow runs

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/projects/{id}/runs` | Body `{require_approval}`. Optional `Idempotency-Key` header: a repeat returns the original run (200). 429 when quotas are exceeded, 503 without an LLM, 422 for non-Python projects |
| GET | `/api/runs?project_id=&status=&limit=&offset=` | The caller's runs, newest first |
| GET | `/api/runs/{id}` | Status, current node, tokens, cost, final report |
| POST | `/api/runs/{id}/cancel` | Immediate for queued/awaiting runs; otherwise observed at the next step |
| POST | `/api/runs/{id}/resume` | Retry a failed run from its last checkpoint |
| GET | `/api/runs/{id}/events?after=` | Event log (JSON) |
| GET | `/api/runs/{id}/stream` | Server-Sent Events; send `Last-Event-ID` to resume; ends with `event: end` |
| GET | `/api/runs/{id}/agents` | Agent executions (node, attempt, status, summary, tokens, timing) |
| GET | `/api/runs/{id}/artifacts` | Generated files (path, kind, sha256, size, author) |
| GET | `/api/runs/{id}/artifacts/content?path=` | One file's content (path validated) |
| GET | `/api/runs/{id}/download` | Zip of all generated files |
| GET | `/api/runs/{id}/tests` | Every test run: counts, exit code, failures, output excerpt; for PostgreSQL projects also `database`: `{migrations: [{file, ok, error}], schema: [{name, columns, foreign_keys, unique, indexes}], error}` (the schema is read back from the real database) |
| GET | `/api/runs/{id}/reviews` | Findings with severity, file/line, and `source` = `tool` or `llm` |
| GET | `/api/runs/{id}/approvals` | Approval requests |
| POST | `/api/runs/{id}/approvals/{approval_id}` | `{approve, comment}`; rejecting a plan with a comment sends it back to the planner |

### Knowledge base (Phase 4)

All owner-scoped through the project (another user's project returns 404).

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/projects/{id}/documents` | `{items, embedder}`; each item has `stale: true` if it was indexed by a different embedder (not searchable until re-indexed) |
| POST | `/api/projects/{id}/documents` | Body `{filename, content}` (UTF-8 text). `.md .markdown .txt .rst .py`, ≤ 400 KB, ≤ 50 documents and 5,000 chunks per project. 201 when created; 200 when a document with that name was replaced or is unchanged (`unchanged: true`). Directory parts of the name are dropped; lines that look like credentials are redacted (`redacted_lines`). 409 for quotas or a concurrent upload of the same name, 503 if the embedding model is unreachable |
| GET | `/api/projects/{id}/documents/{doc}/chunks` | Chunks with `heading` and `start_line`/`end_line` |
| POST | `/api/projects/{id}/documents/{doc}/reindex` | Re-chunk and re-embed with the current embedder |
| DELETE | `/api/projects/{id}/documents/{doc}` | 204; chunks are removed with it |
| GET | `/api/projects/{id}/knowledge/search?q=&k=` | The agents' retrieval pipeline with every stage's score: `dense_score` (cosine), `sparse_score` (BM25), `fused_score` (RRF), `rerank_score`, `score` (final). `q` 1–2000 chars, `k` 1–20. An empty `results` list means nothing relevant passed the gate |

### Evaluations (Phase 6)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/evaluations?limit=` | Recent benchmarks, newest first (`limit` 1–20, default 5): `{benchmarks: [{id, created_at, model_names, demo_model, summaries, results}]}`. Rates are `null` when undefined. Benchmark results are platform-level data written only by the benchmark command, so every signed-in user sees the same list |

Each `summaries` entry is one system (`multi_agent`, `single_agent`): `solved`/`tasks`,
`solve_rate` (every hidden reference test passed), `reference_pass_rate` (mean per task),
`own_suite_success_rate` (the system's own tests, where they ran), `mean_debug_iterations`,
`median_latency_seconds`, token totals, `total_cost_usd` (null unless every row is priced),
`blocking_findings`, `errors` (crashed attempts). Each `results` entry has
`own_tests` and `reference_tests` as `{executed, passed, total, errors}`.
