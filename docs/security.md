# Security model

This document separates what is implemented from what is only planned.

## Implemented (Phase 1)

| Control | Where |
| --- | --- |
| Secrets only from the environment; `LLM_API_KEY` held as `SecretStr`; the API reports only `api_key_present` | `infrastructure/config.py`, `test_status_never_exposes_the_api_key` |
| Strict input validation: length limits, enum allowlists, unknown fields rejected (`extra="forbid"`), plus domain invariants re-checked independently | `api/schemas/project.py`, `domain/project.py` |
| Validation errors never echo submitted input | `api/errors.py`, `test_validation_errors_do_not_echo_input` |
| Unhandled errors return a generic 500; details go to server logs only | `api/errors.py` |
| Request body limit enforced on `Content-Length` and on streamed/chunked bodies; nginx also caps at 1 MB | `api/middleware.py`, `frontend/nginx.conf` |
| LIKE-wildcard escaping in search; all SQL parameterised through SQLAlchemy | `project_repository.py` |
| CORS allowlist (no wildcard), limited methods and headers | `main.py` |
| DB connect timeout, TLS configurable (`require` for Supabase) | `database.py` |
| Containers run as non-root (uid 10001); ports bound to `127.0.0.1` | `docker/`, `docker-compose.yml` |
| `.env`, local databases and virtualenvs git-ignored | `.gitignore` |
| Google sign-in, JWT verification, per-user data isolation | see *Authentication and authorization* |

## Authentication and authorization

- **Identity:** Supabase Auth with Google (OAuth authorization code + PKCE) or email +
  password (email confirmation required; reset by emailed link). Password-reset requests
  respond identically whether or not the account exists (no account enumeration).
- **Verification (backend):** every `/api` route except `/api/health` requires
  `Authorization: Bearer <token>`. Tokens are verified against the project's JWKS. Only
  ES256/RS256 are accepted (HS256 is refused, which prevents alg-confusion), and
  `iss`, `aud=authenticated`, `exp`, `iat`, `sub` and `role=authenticated` are required.
  Signing keys are cached for 10 minutes, so key rotation is picked up.
  `app/infrastructure/auth/supabase_jwt.py`, `tests/unit/test_supabase_jwt.py`.
- **Fails closed:** with `SUPABASE_URL` unset, protected routes return 503 rather than
  allowing anonymous access. If the key endpoint is unreachable, the API returns 503.
- **Authorization:** projects carry `owner_id`. The repository port has no unscoped read,
  update or delete. Other users' projects return 404 (not 403), so ids cannot be probed.
  Dashboard aggregates are scoped the same way. Pre-auth rows (`owner_id IS NULL`) are
  visible to no one. `tests/integration/test_auth_api.py`.
- **Supabase Data API:** RLS is enabled on every table with no policies, so the public
  publishable/anon key cannot read or write data; only the backend (table owner) can.
- **Frontend:** the route guard is a usability feature only. A backend 401 clears the local
  session, and the query cache is cleared on sign-out so no other user's data is shown.
  Post-login redirects accept same-origin relative paths only (no open redirect).

## Agent execution (implemented)

| Control | Where / evidence |
| --- | --- |
| Generated code runs only in a throwaway container: `--network none`, read-only root FS, read-only workspace mount, 64 MB tmpfs, `--cap-drop ALL`, `no-new-privileges`, uid 10001, memory/CPU/PID limits, per-test 30 s and per-run wall-clock timeouts | `infrastructure/sandbox/docker_sandbox.py`; `tests/integration/test_docker_sandbox.py` proves no network, no writes, non-root, no host env leakage, infinite loops stopped |
| Only two fixed commands are ever executed (pytest, ruff); nothing from model output reaches a command line | `docker_sandbox.py` |
| Every model-proposed path is normalised and validated (no absolute paths, `..`, hidden files, unknown file types; 64 KB/file, 60 files, 600 KB/run); validated again before writing to disk and before zipping (no zip-slip) | `domain/workspace.py`; `tests/unit/test_workspace_rules.py` |
| Role-scoped writes: the coder cannot write tests, the tester can only write `tests/`, the documenter only `README.md` | `application/workflow/steps.py`; `test_unsafe_files_from_the_model_are_rejected` |
| Test results come only from pytest's JUnit XML, parsed with `defusedxml` (XML bombs refused) | `docker_sandbox.py`; `test_xml_bombs_are_refused` |
| Prompt injection: requirements, retrieved documents, code, findings and test output are fenced as untrusted data; fences cannot be closed from inside | `application/agents/prompts.py`; `test_untrusted_fence_cannot_be_closed_from_inside` |
| Deterministic review tools (secret scanner, ruff security rules incl. SQL injection and `shell=True`) are reported separately from LLM opinions | `secret_scanner.py`, `docker_sandbox.py` |
| Human approval before code generation and before applying fixes for blocking findings; decisions are owner-only and compare-and-set (cannot be decided twice) | `run_repository.decide_approval`; `test_human_approval_flow` |
| Cost/abuse limits: per-user active-run quota, hourly run limit (429 + `Retry-After`), idempotent run creation | `application/runs/service.py`; `test_active_run_quota` |
| LangGraph checkpoint tables in Supabase get RLS enabled at startup | `infrastructure/workflow/checkpointer.py` |
| Every application table has RLS enabled; a test fails if a future migration forgets it | `test_every_table_has_row_level_security` |

## Databases for generated projects

| Control | Where / evidence |
| --- | --- |
| Each database test run gets its own `--internal` Docker network (no route to the internet) with a throwaway PostgreSQL container: tmpfs storage, memory/CPU/PID limits, all capabilities dropped except the five its entrypoint needs, `no-new-privileges`, never published to the host | `docker_sandbox._database`; `test_database_runs_are_isolated` |
| The generated code connects as a non-superuser role with a random per-run password, so SQL cannot use superuser features such as `COPY … PROGRAM` (shell commands) | `test_database_runs_are_isolated` (`test_sql_cannot_run_shell_commands` probe) |
| Migrations are applied by a fixed, trusted runner baked into the image; model output is never on a command line | `docker/sandbox/run_database_tests.py` |
| A migration that never finishes is killed by the run's wall-clock limit; containers and networks are removed after every run, and labelled leftovers from a crash are removed at startup | `test_a_migration_that_never_finishes_is_stopped_and_cleaned_up`, `test_nothing_is_left_behind_and_leftovers_can_be_cleaned` |
| The migration/schema report is written inside the sandbox, so it is size-capped and rebuilt field by field in the expected shape before it is stored or shown | `docker_sandbox._clean_table`; `tests/unit/test_database_report.py` |
| A run is only verified when every migration applied; the coder cannot rewrite the schema (only the database agent writes it, the debugger may fix it) | `domain/testing.TestReport.succeeded`; `test_the_coder_cannot_rewrite_the_schema_but_the_debugger_can_fix_it` |

## Knowledge base (Phase 4)

| Control | Where / evidence |
| --- | --- |
| Documents are owner-scoped through their project; another user gets 404 on every endpoint (list, upload, chunks, re-index, delete, search) | `application/knowledge/service.py`; `test_other_users_cannot_see_or_touch_documents` |
| Retrieved text reaches agents inside an `<untrusted-retrieved-documents>` fence that a document cannot close; tested end to end with a poisoned document in a real run | `steps._context`; `test_agents_receive_relevant_documents_fenced_as_untrusted` |
| Lines that look like credentials are replaced before anything is stored or embedded, so a pasted key never reaches a prompt or the vector store | `service.redact_secrets`; `test_secrets_never_reach_storage` |
| Uploads: text only (no NUL bytes), ≤ 400 KB, allow-listed extensions, directory parts of names dropped, no control or path characters | `domain/knowledge.py`; `test_bad_uploads_are_rejected` |
| Bounded cost: 50 documents and 5,000 chunks per project; queries cut to 2,000 characters at a word boundary; `k` ≤ 20 | `test_total_chunks_per_project_are_capped`, `test_unknown_ids_and_bad_queries` |
| A relevance gate keeps irrelevant documents out of prompts (measured: 75% of off-topic queries get no context with the lexical reranker, 100% with the LLM reranker) | `application/knowledge/pipeline.py`; `tests/unit/test_retrieval_eval.py` |
| An embedding outage fails uploads with 503 and leaves nothing half-indexed; during a run it gives the agents no context instead of failing the run | `test_embedding_outage_is_a_clear_unavailable_error`; `infrastructure/knowledge/retriever.py` |
| `knowledge_documents` and `knowledge_chunks` have RLS; deleting a project deletes its documents (database cascade) | migration `0006`; `test_deleting_the_project_deletes_its_documents` |

## Benchmark (Phase 6)

| Control | Where / evidence |
| --- | --- |
| Generated code and the hidden reference tests run only in the sandbox; the benchmark refuses to start without it and stops if it disappears mid-run (no task silently drops out of the averages) | `application/evaluation/benchmark.py`; `test_benchmark_stops_when_the_sandbox_dies_instead_of_recording_not_run` |
| A system is graded on its `app/` code only: its own tests, `conftest.py` and pytest configuration files are removed first, so it cannot deselect, skip or add reference tests | `domain/evaluation.grading_files`; `test_a_systems_pytest_configuration_never_takes_part_in_grading` |
| The reference tests are themselves tested: known-good solutions must pass, known-bad code (the planted bug, an unauthenticated app, plausible "improvements") must fail | `tests/e2e/test_benchmark_dataset.py` |
| Benchmark ids name files: validated (no path characters) before any model call; saved attempt files are re-validated with `normalize_path` before writing | `validate_benchmark_id`; `test_saved_attempt_files_cannot_escape_the_report_folder` |
| The dataset loader keeps prompt and test paths inside the dataset folder | `infrastructure/evaluation/task_loader.py`; `test_loader_rejects_files_outside_the_dataset` |
| The scripted demo model cannot be benchmarked (it is not AI) | `bootstrap.build_benchmark`; `test_benchmark_refuses_the_scripted_demo_model` |
| `evaluation_runs` has RLS; results are readable by any signed-in user (they describe the platform, not a user) and writable only by the benchmark command | migration `0005`; `test_results_are_the_same_for_every_user` |

## Known limitations (honest)

- Code under test runs in the same container as pytest, so deliberately malicious generated
  code could interfere with its own test report. The sandbox prevents harm to the host and
  network; it does not make results tamper-proof against adversarial code. The same holds
  for benchmark grading: code that deliberately forged pytest's report file from inside the
  container could inflate its own score.
- The sandbox needs Docker. On hosts without it (e.g. Render's free plan) tests are reported
  as **not executed**, never as passed.
- No per-IP rate limiting on non-run endpoints; dependency installation in generated
  projects is not supported (the sandbox is offline with a fixed package set).
