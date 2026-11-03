"""Workflow steps: one method per graph node, each returning a partial state update.

Steps depend only on ports (LLM, sandbox, retriever, journal). They never touch the
database, the filesystem or Docker directly, which keeps them unit-testable with fakes.
Test outcomes come exclusively from the sandbox's real test runner.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime

from app.application.agents import prompts
from app.application.agents.schemas import (
    ArchitectureSpec,
    CodeChangeSet,
    DebugPatch,
    Documentation,
    FileContent,
    LLMFinding,
    ProjectPlan,
    ReviewReport,
    SchemaDesign,
    TestSuite,
)
from app.application.llm import Pricing, StructuredLLM, T, TokenUsage
from app.application.workflow import routing
from app.application.workflow.failures import changed_paths, failure_locations, ineffective_files
from app.application.workflow.memory import (
    ASSUMPTION,
    DECISION,
    FACT,
    HYPOTHESIS,
    NOTE,
    REVERTED,
    VERDICT,
    entry as memory_entry,
    memory_for_prompt,
    remember,
    similar,
    test_fact,
    verdict,
)
from app.application.workflow.ports import Retriever, RunJournal, Sandbox
from app.application.workflow.secret_scanner import scan_for_secrets
from app.application.workflow.state import WorkflowState
from app.domain.enums import AgentRole, FindingSeverity, FindingSource
from app.domain.errors import InvariantViolationError
from app.domain.review import Finding
from app.domain.run import RunCancelledError
from app.domain.testing import TestReport
from app.domain.workspace import SourceFile, merge_files

logger = logging.getLogger("agentforge.workflow")


def usage_dict(usage: TokenUsage) -> dict[str, int]:
    return {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}


def report_to_dict(report: TestReport) -> dict:
    data = asdict(report)
    data["succeeded"] = report.succeeded
    return data


def finding_to_dict(finding: Finding) -> dict:
    return {**asdict(finding), "severity": finding.severity.value, "source": finding.source.value}


def failure_signature(report: dict) -> str:
    """Fingerprint of a test report's failures: equal when a fix changed nothing."""
    failures = sorted((f.get("name", ""), f.get("message", "")) for f in report.get("failures") or [])
    raw = json.dumps([failures, report.get("passed"), report.get("failed"), report.get("errors")])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def attempts_for_prompt(history: list[dict], current_signature: str) -> list[dict]:
    """Earlier debugging attempts, each with whether it changed the failures it targeted.
    An attempt's effect is visible in the next report: the next attempt's target, or the
    current failures for the latest one."""
    if not history:
        return []
    after = [entry["failure_signature"] for entry in history[1:]] + [current_signature]
    return [
        {
            "attempt": entry["iteration"],
            "diagnosis": entry["diagnosis"],
            "files_changed": entry["files_changed"],
            "result": (
                "no file was actually changed"
                if not entry["files_changed"]
                else "failures unchanged"
                if entry["failure_signature"] == next_sig
                else "failures changed but tests still fail"
            ),
        }
        for entry, next_sig in zip(history, after, strict=True)
    ]


class WorkflowSteps:
    def __init__(
        self,
        *,
        llm: StructuredLLM,
        sandbox: Sandbox,
        journal: RunJournal,
        retriever: Retriever,
        pricing: Pricing | None = None,
    ) -> None:
        self.llm = llm
        self.sandbox = sandbox
        self.journal = journal
        self.retriever = retriever
        self.pricing = pricing

    # ------------------------------------------------------------------ helpers

    @contextmanager
    def _step(self, node: str, agent: AgentRole | None, attempt: int = 1) -> Iterator[StepContext]:
        if self.journal.is_cancel_requested():
            raise RunCancelledError()
        self.journal.step_started(node, agent, attempt)
        started = time.monotonic()
        step = StepContext(self.llm)
        try:
            yield step
        except RunCancelledError:
            raise
        except Exception as exc:
            self.journal.step_failed(node, agent, attempt, _describe(exc))
            raise
        self.journal.step_finished(node, agent, attempt, step.summary, step.usage)
        logger.info("run=%s node=%s done in %.1fs", self.journal.run_id, node, time.monotonic() - started)

    def _context(self, state: WorkflowState, query: str) -> str | None:
        chunks = self.retriever.retrieve(owner_id=state["owner_id"], project_id=state["project_id"], query=query, k=4)
        if not chunks:
            return None
        self.journal.emit(
            "tool.called",
            tool="retrieve_documentation",
            results=[{"source": c.source, "location": c.location, "score": round(c.score, 3)} for c in chunks],
        )
        body = "\n\n".join(f"[source: {c.source}{f' {c.location}' if c.location else ''}]\n{c.text}" for c in chunks)
        return prompts.untrusted("retrieved-documents", body)

    @staticmethod
    def _env(state: WorkflowState, user: str, *, with_memory: bool = False) -> str:
        """What every agent should know besides its own inputs: for database projects, what
        the sandbox really provides; for agents after the plan, the shared run memory."""
        if with_memory and state.get("memory"):
            user = f"{user}\n\n{prompts.memory_section(memory_for_prompt(state['memory']))}"
        return f"{user}\n\n{prompts.DATABASE_ENVIRONMENT}" if state.get("database") else user

    def _remember(self, state: WorkflowState, *entries: dict) -> list[dict]:
        """Append to the shared memory (and the event log, so the UI shows it live)."""
        added = [e for e in entries if e["text"]]
        for item in added:
            self.journal.emit("memory.added", **item)
        return remember(state.get("memory"), *added)

    def _apply(
        self, state: WorkflowState, proposed: list[FileContent], author: AgentRole, allow: WritePolicy
    ) -> tuple[dict[str, str], list[str]]:
        """Validate proposed files, keep those the author may write, persist them.
        Returns (new workspace snapshot, changed paths)."""
        existing = state.get("files") or {}
        accepted: list[SourceFile] = []
        rejected: list[str] = []
        for item in proposed:
            try:
                source = SourceFile.create(item.path, item.content)
            except InvariantViolationError as exc:
                rejected.append(f"{item.path}: {exc.message}")
                continue
            if allow(source.path, existing):
                accepted.append(source)
            else:
                rejected.append(f"{source.path}: not permitted for the {author.value} agent")
        if rejected:
            self.journal.emit("files.rejected", author=author.value, files=rejected)
        changed = {f.path: f.content for f in accepted}
        if changed:
            self.journal.save_files(changed, author)
            self.journal.emit("tool.called", tool="write_files", author=author.value, paths=sorted(changed))
        return merge_files(existing, accepted), sorted(changed)

    # -------------------------------------------------------------------- nodes

    def plan(self, state: WorkflowState) -> dict:
        attempt = state.get("plan_revisions", 0) + 1
        with self._step(routing.PLAN, AgentRole.PLANNER, attempt) as step:
            plan = step.ask(
                "planner",
                prompts.PLANNER_SYSTEM,
                self._env(
                    state,
                    prompts.planner_user(
                        state["requirements"],
                        state.get("preferences") or {},
                        state.get("plan_feedback"),
                        self._context(state, state["requirements"]),
                    ),
                ),
                ProjectPlan,
            )
            step.summary = (
                f"{len(plan.tasks)} tasks, {len(plan.acceptance_criteria)} acceptance criteria, "
                f"{len(plan.assumptions)} assumptions"
            )
            # A re-plan starts a fresh notebook: earlier assumptions were for a rejected plan.
            memory = self._remember(
                {**state, "memory": []},
                *(memory_entry(routing.PLAN, "planner", ASSUMPTION, a) for a in plan.assumptions[:6]),
            )
            return step.result(plan=plan.model_dump(), plan_revisions=attempt, memory=memory)

    def architect(self, state: WorkflowState) -> dict:
        with self._step(routing.ARCHITECT, AgentRole.ARCHITECT, state.get("plan_revisions", 1)) as step:
            spec = step.ask(
                "architect",
                prompts.ARCHITECT_SYSTEM,
                self._env(
                    state, prompts.architect_user(state["requirements"], state["plan"], self._context(state, state["plan"]["summary"]))
                ),
                ArchitectureSpec,
            )
            step.summary = f"{len(spec.components)} components, {len(spec.files)} planned files"
            memory = self._remember(
                state,
                *(memory_entry(routing.ARCHITECT, "architect", DECISION, d) for d in spec.technology_decisions[:4]),
                *(memory_entry(routing.ARCHITECT, "architect", NOTE, n) for n in spec.implementation_notes[:3]),
            )
            return step.result(architecture=spec.model_dump(), memory=memory)

    def plan_approval_request(self, state: WorkflowState) -> dict:
        """Payload for the human approval interrupt (idempotent)."""
        architecture = state["architecture"]
        ticket = self.journal.ensure_approval(
            kind="plan",
            cycle=state.get("plan_revisions", 1),
            reason="Review the plan and architecture before code is generated and executed in the sandbox.",
            affected_resources=[f["path"] for f in architecture.get("files", [])],
            security_notes=(
                "Generated code will run in an isolated container without network access. "
                + " ".join(architecture.get("security_considerations", [])[:3])
            ).strip(),
            details={"plan_summary": state["plan"]["summary"], "architecture_summary": architecture["summary"]},
        )
        return asdict(ticket)

    def schema(self, state: WorkflowState) -> dict:
        """Database projects only: the schema as a SQL migration, applied to a real
        PostgreSQL before every test run."""
        with self._step(routing.SCHEMA, AgentRole.DATABASE) as step:
            design = step.ask(
                "schema",
                prompts.SCHEMA_SYSTEM,
                self._env(state, prompts.schema_user(state["requirements"], state["plan"], state["architecture"]), with_memory=True),
                SchemaDesign,
            )
            if not design.migration_sql.strip():
                raise InvariantViolationError("migration", "the database agent produced an empty migration")
            migration = FileContent(path=INITIAL_MIGRATION, content=design.migration_sql.strip() + "\n")
            snapshot, _ = self._apply(state, [migration], AgentRole.DATABASE, allow=migration_files)
            self.journal.emit("schema.designed", tables=[t.name for t in design.tables][:50], summary=design.summary[:300])
            step.summary = f"{len(design.tables)} table(s): {', '.join(t.name for t in design.tables[:8])}"
            memory = self._remember(
                state,
                memory_entry(routing.SCHEMA, "database", DECISION, design.summary, files=[INITIAL_MIGRATION]),
                memory_entry(routing.SCHEMA, "database", NOTE, design.notes, files=[INITIAL_MIGRATION]),
            )
            return step.result(files=snapshot, memory=memory)

    def code(self, state: WorkflowState) -> dict:
        with self._step(routing.CODE, AgentRole.CODER) as step:
            existing = state.get("files") or {}
            migrations = {p: c for p, c in existing.items() if is_migration(p)}
            changes = step.ask(
                "coder",
                prompts.CODER_SYSTEM,
                self._env(
                    state,
                    prompts.coder_user(
                        state["requirements"],
                        state["plan"],
                        state["architecture"],
                        self._context(state, state["architecture"]["summary"]),
                        migrations=migrations,
                    ),
                    with_memory=True,
                ),
                CodeChangeSet,
            )
            files = list(changes.files)
            if not any(f.path == PACKAGE_INIT for f in files) and PACKAGE_INIT not in existing:
                files.append(FileContent(path=PACKAGE_INIT, content=""))
            snapshot, changed = self._apply(state, files, AgentRole.CODER, allow=application_files)
            if not set(changed) - {PACKAGE_INIT}:
                raise InvariantViolationError("files", "the coding agent produced no valid source files")
            step.summary = f"wrote {len(changed)} file(s)"
            memory = self._remember(state, memory_entry(routing.CODE, "coder", NOTE, changes.notes, files=changed))
            return step.result(files=snapshot, memory=memory)

    def write_tests(self, state: WorkflowState) -> dict:
        with self._step(routing.WRITE_TESTS, AgentRole.TESTER) as step:
            sources = {p: c for p, c in state["files"].items() if not is_test(p)}
            suite = step.ask(
                "tester",
                prompts.TESTER_SYSTEM,
                self._env(state, prompts.tester_user(state["requirements"], state["plan"], sources), with_memory=True),
                TestSuite,
            )
            snapshot, changed = self._apply(state, suite.files, AgentRole.TESTER, allow=test_files)
            if not changed:
                raise InvariantViolationError("files", "the testing agent produced no valid test files")
            step.summary = f"wrote {len(changed)} test file(s)"
            memory = self._remember(state, memory_entry(routing.WRITE_TESTS, "tester", NOTE, suite.notes, files=changed))
            return step.result(files=snapshot, memory=memory)

    def run_tests(self, state: WorkflowState) -> dict:
        attempt = state.get("test_attempt", 0) + 1
        with self._step(routing.RUN_TESTS, AgentRole.TESTER, attempt) as step:
            self.journal.emit("tool.called", tool="run_tests", attempt=attempt)
            report = self.sandbox.run_tests(state["files"], database=bool(state.get("database")))
            self.journal.save_test_report(attempt, report)
            self.journal.emit(
                "tests.completed",
                attempt=attempt,
                migrated=report.database.migrated if report.database else None,
                **{k: getattr(report, k) for k in ("executed", "total", "passed", "failed", "errors", "skipped", "duration_ms", "unavailable_reason")},
            )
            step.summary = (
                f"{report.passed}/{report.total} passed, {report.failed} failed, {report.errors} errors"
                if report.executed
                else f"not executed: {report.unavailable_reason}"
            )
            if report.database and not report.database.migrated:
                step.summary += " (database migrations failed)"
            after = report_to_dict(report)
            after_locations = failure_locations(after, state["files"])
            entries = [memory_entry(routing.RUN_TESTS, "agentforge", FACT, test_fact(attempt, after, after_locations))]
            update: dict = {"test_attempt": attempt, "test_report": after}

            # Verify the last debugging attempt from measurements, not from the model's opinion.
            history = state.get("debug_history") or []
            if history and "outcome" not in history[-1]:
                before = state.get("test_report") or {}
                last = history[-1]
                outcome, why = verdict(
                    before, after, failure_locations(before, state["files"]), after_locations, last["files_changed"]
                )
                entries.append(
                    memory_entry(
                        routing.RUN_TESTS,
                        "agentforge",
                        VERDICT,
                        f"Debug attempt {last['iteration']} ({last['diagnosis'][:150]}): {why}.",
                        files=last["files_changed"],
                        outcome=outcome,
                    )
                )
                update["debug_history"] = [*history[:-1], {**last, "outcome": outcome}]
                if outcome == "regressed":
                    # Undo it: the next attempt (or the final result) starts from the better code.
                    restored = {p: c for p, c in (last.get("previous") or {}).items() if c is not None}
                    if restored:
                        self.journal.save_files(restored, AgentRole.DEBUGGER)
                        self.journal.emit("debug.reverted", iteration=last["iteration"], files=sorted(restored))
                        update["files"] = {**state["files"], **restored}
                        update["test_report"] = before  # the code is back to what that report measured
                        entries.append(
                            memory_entry(
                                routing.RUN_TESTS,
                                "agentforge",
                                FACT,
                                f"Debug attempt {last['iteration']} was reverted because it made things worse; "
                                f"{', '.join(sorted(restored))} are back to their previous version.",
                                files=sorted(restored),
                                outcome=REVERTED,
                            )
                        )
            return step.result(**update, memory=self._remember(state, *entries))

    def debug(self, state: WorkflowState) -> dict:
        iteration = state.get("debug_iterations", 0) + 1
        with self._step(routing.DEBUG, AgentRole.DEBUGGER, iteration) as step:
            report = state["test_report"] or {}
            history = state.get("debug_history") or []
            signature = failure_signature(report)
            unchanged = bool(history) and history[-1]["failure_signature"] == signature
            locations = failure_locations(report, state["files"])
            ineffective = ineffective_files(history, signature)

            def ask(repeat_of: dict | None = None) -> DebugPatch:
                return step.ask(
                    "debugger",
                    prompts.DEBUGGER_SYSTEM,
                    self._env(
                        state,
                        prompts.debugger_user(
                            state["requirements"],
                            state["plan"],
                            state["files"],
                            report.get("output_excerpt", ""),
                            report.get("failures", []),
                            previous_attempts=attempts_for_prompt(history, signature),
                            unchanged_failures=unchanged,
                            migration_errors=migration_errors(report),
                            locations=locations,
                            ineffective=ineffective,
                            repeat_of=repeat_of,
                        ),
                        with_memory=True,
                    ),
                    DebugPatch,
                )

            patch = ask()
            # A fix that repeats one already measured as not working is rejected; the model
            # gets one more try, told so explicitly (bounded: at most one extra call). On that
            # try it may only change the files where the failures are reported and that were
            # not already tried: telling a small model to look elsewhere is not enough.
            allow = project_files
            repeated = repeats_failed_attempt(history, patch)
            if repeated:
                self.journal.emit("debug.repeat_rejected", iteration=iteration, repeats=repeated["iteration"])
                patch = ask(repeat_of=repeated)
                untried = {l["file"] for l in locations} - set(repeated["files_changed"])
                if untried:
                    allow = only_files(untried)

            proposed = [FileContent(path=f.path, content=strip_line_numbers(f.content)) for f in patch.files]
            snapshot, written = self._apply(state, proposed, AgentRole.DEBUGGER, allow=allow)
            changed = changed_paths(state["files"], snapshot, written)
            self.journal.emit(
                "debug.patch",
                iteration=iteration,
                diagnosis=patch.diagnosis,
                root_causes=patch.root_causes,
                files=changed,
                unchanged_failures=unchanged,
                failure_locations=[f"{l['file']}:{l['line']}" for l in locations[:5]],
                no_change=not changed,
            )
            step.summary = (
                f"iteration {iteration}: {patch.diagnosis[:160]} "
                + (f"({len(changed)} file(s) changed)" if changed else "(no file actually changed)")
            )
            entry = {
                "iteration": iteration,
                "diagnosis": patch.diagnosis[:500],
                "files_changed": changed,
                "failure_signature": signature,
                # What the changed files held before, so a fix that makes things worse can be undone.
                "previous": {p: state["files"].get(p) for p in changed},
                "repeat_rejected": bool(repeated),
            }
            # Only the newest attempt can be undone; older snapshots are dropped to keep state small.
            history = [{k: v for k, v in h.items() if k != "previous"} for h in history]
            memory = self._remember(
                state,
                memory_entry(routing.DEBUG, "debugger", HYPOTHESIS, f"Attempt {iteration}: {patch.diagnosis}", files=changed),
            )
            # A fresh list (not a reducer), so re-running this node on resume is idempotent.
            return step.result(files=snapshot, debug_iterations=iteration, debug_history=[*history, entry], memory=memory)

    def review(self, state: WorkflowState) -> dict:
        cycle = state.get("review_cycle", 0) + 1
        files = state["files"]
        with self._step(routing.REVIEW, AgentRole.REVIEWER, cycle) as step:
            secrets = scan_for_secrets(files)
            self.journal.emit("tool.called", tool="secret_scan", findings=len(secrets))
            static = self.sandbox.run_static_analysis(files)
            self.journal.emit("tool.called", tool="static_analysis", findings=len(static))
            tool_findings = secrets + static

            review = step.ask(
                "reviewer",
                prompts.REVIEWER_SYSTEM,
                prompts.reviewer_user(state["plan"], files, [finding_to_dict(f) for f in tool_findings]),
                ReviewReport,
            )
            findings = tool_findings + [llm_finding(f, files) for f in review.findings]
            self.journal.save_findings(cycle, findings)
            step.summary = f"{len(findings)} findings ({sum(f.blocking for f in findings)} blocking): {review.summary[:120]}"
            memory = self._remember(
                state,
                *(
                    memory_entry(
                        routing.REVIEW,
                        "agentforge" if f.source is FindingSource.TOOL else "reviewer",
                        FACT if f.source is FindingSource.TOOL else NOTE,
                        f"Blocking finding: {f.title}" + (f" at {f.file_path}:{f.line}" if f.file_path and f.line else ""),
                        files=[f.file_path] if f.file_path else [],
                    )
                    for f in findings
                    if f.blocking
                ),
            )
            return step.result(review_cycle=cycle, findings=[finding_to_dict(f) for f in findings], memory=memory)

    def correction_approval_request(self, state: WorkflowState) -> dict:
        blocking = routing.blocking_findings(state)
        ticket = self.journal.ensure_approval(
            kind="corrections",
            cycle=state.get("review_cycle", 1),
            reason=f"Apply fixes for {len(blocking)} blocking review finding(s), then re-run the tests.",
            affected_resources=sorted({f["file_path"] for f in blocking if f.get("file_path")}),
            security_notes="; ".join(f["title"] for f in blocking[:5]),
            details={"findings": blocking},
        )
        return asdict(ticket)

    def correct(self, state: WorkflowState) -> dict:
        attempt = state.get("corrections_applied", 0) + 1
        with self._step(routing.CORRECT, AgentRole.CODER, attempt) as step:
            changes = step.ask(
                "corrector",
                prompts.CORRECTION_SYSTEM,
                self._env(
                    state, prompts.correction_user(state["requirements"], state["files"], routing.blocking_findings(state)), with_memory=True
                ),
                CodeChangeSet,
            )
            snapshot, changed = self._apply(state, changes.files, AgentRole.CODER, allow=application_files)
            step.summary = f"applied corrections to {len(changed)} file(s)"
            return step.result(files=snapshot, corrections_applied=attempt)

    def document(self, state: WorkflowState) -> dict:
        with self._step(routing.DOCUMENT, AgentRole.DOCUMENTER) as step:
            docs = step.ask(
                "documenter",
                prompts.DOCUMENTER_SYSTEM,
                prompts.documenter_user(
                    state.get("plan") or {}, state.get("architecture") or {}, state.get("files") or {}, known_limitations(state)
                ),
                Documentation,
            )
            readme = FileContent(path=README, content=docs.readme.rstrip() + "\n\n" + verified_results_section(state))
            snapshot, _ = self._apply(state, [readme], AgentRole.DOCUMENTER, allow=readme_only)
            step.summary = "README.md written"
            return step.result(files=snapshot, readme_written=True)

    def report(self, state: WorkflowState) -> dict:
        with self._step(routing.REPORT, None) as step:
            outcome = routing.decide_outcome(state)
            step.summary = f"outcome: {outcome}"
            self.journal.emit("run.report", outcome=outcome)
            return step.result(outcome=outcome, report=build_final_report(state, outcome, self.llm, self.pricing))


class StepContext:
    """Per-step accumulator: every model call goes through `ask`, so token usage is
    recorded once, in one place, and attached to the state update by `result`."""

    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm
        self.summary = ""
        self.usage = TokenUsage()

    def ask(self, task: str, system: str, user: str, schema: type[T]) -> T:
        result = self._llm.generate(task=task, system=system, user=user, schema=schema)
        self.usage = self.usage + result.usage
        return result.value

    def result(self, **update: object) -> dict:
        return {**update, "usage": usage_dict(self.usage)} if self.usage.total else update


# ---------------------------------------------------------------- write policies
# Which agent may write which files. A policy sees the path and the current workspace.

WritePolicy = Callable[[str, dict[str, str]], bool]
PACKAGE_INIT = "app/__init__.py"
README = "README.md"
INITIAL_MIGRATION = f"{prompts.MIGRATIONS_DIR}/0001_initial.sql"


def is_test(path: str) -> bool:
    return path.startswith("tests/")


def is_migration(path: str) -> bool:
    return path.startswith(f"{prompts.MIGRATIONS_DIR}/") and path.endswith(".sql")


def source_files(path: str, existing: dict[str, str]) -> bool:
    return not is_test(path)


def application_files(path: str, existing: dict[str, str]) -> bool:
    """The coder's files: not tests, and not the schema (the database agent owns it; the
    debugger may still fix a failing migration)."""
    return not is_test(path) and not is_migration(path)


def migration_files(path: str, existing: dict[str, str]) -> bool:
    return is_migration(path)


def only_files(paths: set[str]) -> WritePolicy:
    def allow(path: str, existing: dict[str, str]) -> bool:
        return path in paths

    return allow


def repeats_failed_attempt(history: list[dict], patch: DebugPatch) -> dict | None:
    """An earlier attempt, measured as not working, that this patch repeats: (nearly) the
    same diagnosis applied to the same files."""
    proposed = {f.path for f in patch.files}
    for entry in reversed(history):
        if entry.get("outcome") in ("refuted", "regressed", "partly") and similar(entry["diagnosis"], patch.diagnosis):
            if proposed and proposed <= set(entry["files_changed"] or proposed):
                return entry
    return None


_NUMBER_PREFIX = re.compile(r"^\s{0,4}\d{1,5} \| ?")


def strip_line_numbers(content: str) -> str:
    """Debugger safety net: it sees files with "  12 | " prefixes and may copy them back.
    Strip them only when (nearly) every non-empty line has one, so real code is never touched."""
    lines = content.split("\n")
    filled = [line for line in lines if line.strip()]
    if not filled or sum(bool(_NUMBER_PREFIX.match(line)) for line in filled) < 0.9 * len(filled):
        return content
    return "\n".join(_NUMBER_PREFIX.sub("", line, count=1) for line in lines)


def migration_errors(report: dict) -> list[dict]:
    """Failed migrations (and runner errors) from a test report, for the debugger."""
    database = report.get("database") or {}
    errors = [{"file": m["file"], "error": m.get("error")} for m in database.get("migrations", []) if not m.get("ok")]
    if database.get("error"):
        errors.append({"file": None, "error": database["error"]})
    return errors


def test_files(path: str, existing: dict[str, str]) -> bool:
    return is_test(path)


def project_files(path: str, existing: dict[str, str]) -> bool:
    return path in existing or path.startswith(("app/", "tests/"))


def readme_only(path: str, existing: dict[str, str]) -> bool:
    return path == README


def llm_finding(finding: LLMFinding, files: dict[str, str]) -> Finding:
    """Convert a reviewer opinion to a Finding; references to unknown files are dropped."""
    known = finding.file_path in files
    return Finding(
        severity=FindingSeverity(finding.severity),
        category=finding.category[:64],
        title=finding.title[:256],
        description=finding.description,
        source=FindingSource.LLM,
        file_path=finding.file_path if known else None,
        line=finding.line if known else None,
        suggestion=finding.suggestion,
    )


def _describe(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:500]


def known_limitations(state: WorkflowState) -> list[str]:
    items: list[str] = []
    report = state.get("test_report") or {}
    if not report:
        items.append("Tests were not run.")
    elif not report.get("executed"):
        items.append(f"Tests were generated but not executed: {report.get('unavailable_reason')}.")
    elif not report.get("succeeded"):
        items.append(
            f"{report.get('failed', 0)} test(s) failed and {report.get('errors', 0)} errored after "
            f"{state.get('debug_iterations', 0)} debugging iteration(s)."
        )
    if migration_errors(report):
        items.append("The database migrations did not apply cleanly; the schema may be incomplete.")
    blocking = routing.blocking_findings(state)
    if blocking:
        items.append(f"{len(blocking)} blocking review finding(s) remain unresolved.")
    for assumption in (state.get("plan") or {}).get("assumptions", [])[:5]:
        items.append(f"Assumption: {assumption}")
    items.append("Generated by AI agents; review the code before using it in production.")
    return items


def verified_results_section(state: WorkflowState) -> str:
    """Written by AgentForge from the test runner's report, not by the model."""
    report = state.get("test_report") or {}
    lines = ["## Verified results", "", "_This section is generated by AgentForge from the real test runner output._", ""]
    if report.get("executed"):
        lines += [
            f"- Command: `{report.get('command')}`",
            f"- Result: {report.get('passed')}/{report.get('total')} passed, {report.get('failed')} failed, "
            f"{report.get('errors')} errors, {report.get('skipped')} skipped",
            f"- Test runs: {state.get('test_attempt', 0)} (debugging iterations: {state.get('debug_iterations', 0)})",
        ]
        database = report.get("database")
        if database:
            applied = [m["file"] for m in database.get("migrations", []) if m.get("ok")]
            tables = [t.get("name") for t in database.get("schema", [])]
            lines.append(
                f"- Database: PostgreSQL 17, {len(applied)} migration(s) applied"
                + ("" if not migration_errors(report) else ", MIGRATION FAILED")
                + (f"; tables: {', '.join(tables)}" if tables else "")
            )
    else:
        lines.append(f"- Tests were not executed: {report.get('unavailable_reason') or 'not reached'}")
    blocking = routing.blocking_findings(state)
    lines.append(f"- Review: {len(state.get('findings') or [])} findings, {len(blocking)} blocking")
    return "\n".join(lines) + "\n"


def build_final_report(state: WorkflowState, outcome: str, llm: StructuredLLM, pricing: Pricing | None) -> dict:
    usage = state.get("usage") or {}
    tokens = TokenUsage(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    plan = state.get("plan") or {}
    findings = state.get("findings") or []
    report = state.get("test_report")
    return {
        "outcome": outcome,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": {"name": llm.model_name, "demo": llm.is_demo},
        # Everything under "verified" comes from tools and the test runner.
        "verified": {
            "tests": report,
            "test_runs": state.get("test_attempt", 0),
            "debug_iterations": state.get("debug_iterations", 0),
            "tool_findings": [f for f in findings if f["source"] == FindingSource.TOOL.value],
            "files": sorted((state.get("files") or {}).keys()),
            "database": (report or {}).get("database"),  # migrations + schema read from the real database
            # Facts and verdicts in the run memory are measured; the rest is agent notes.
            "memory": state.get("memory") or [],
        },
        # Everything under "generated" is model output and may be wrong.
        "generated": {
            "summary": plan.get("summary"),
            "features": plan.get("functional_requirements", []),
            "acceptance_criteria": plan.get("acceptance_criteria", []),
            "assumptions": plan.get("assumptions", []),
            "open_questions": plan.get("open_questions", []),
            "llm_findings": [f for f in findings if f["source"] == FindingSource.LLM.value],
        },
        "limitations": known_limitations(state) if outcome != "cancelled" else ["The plan was rejected; no code was generated."],
        # Without a passing suite no task can be considered verified.
        "tasks_not_verified": [] if outcome == "completed" else [t.get("title") for t in plan.get("tasks", [])][:20],
        "usage": {
            "input_tokens": tokens.input_tokens,
            "output_tokens": tokens.output_tokens,
            "estimated_cost_usd": round(pricing.cost(tokens), 6) if pricing else None,
        },
    }
