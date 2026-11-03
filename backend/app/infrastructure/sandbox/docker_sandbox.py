"""Docker implementation of the `Sandbox` port.

Generated code runs only inside a throwaway container:
  --network none          no network at all
  --read-only + tmpfs     immutable root filesystem; /tmp is a small RAM disk
  workspace mount :ro     generated files cannot be modified by the code under test
  --cap-drop ALL, no-new-privileges, non-root uid 10001
  --memory/--cpus/--pids-limit and a wall-clock timeout (container is killed)
Only fixed commands are ever executed (pytest, ruff, and the image's database runner);
nothing from model output is interpolated into a command line. Test counts come from
pytest's JUnit XML.

Projects with a database get, per test run, a private Docker network created with
--internal (no route to the internet) holding the sandbox and a throwaway PostgreSQL
container (tmpfs storage, resource limits, minimal capabilities, never published to the
host). The code under test connects as a non-superuser role with a random password, so
SQL cannot use superuser-only features such as COPY ... PROGRAM. Both containers and the
network are removed after the run; leftovers from a crash carry a label and are removed
at the next start (`remove_leftovers`).
"""

import json
import logging
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from defusedxml import ElementTree

from app.application.workflow.ports import SandboxStatus
from app.domain.enums import FindingSeverity, FindingSource
from app.domain.review import Finding
from app.domain.testing import DatabaseReport, MigrationResult, TestCaseFailure, TestReport
from app.domain.workspace import normalize_path

logger = logging.getLogger("agentforge.sandbox")

TEST_COMMAND = "python -m pytest -q -p no:cacheprovider --timeout=30 --junitxml=/out/junit.xml"
DATABASE_TEST_COMMAND = ["python", "/opt/agentforge/run_database_tests.py"]
MAX_OUTPUT_CHARS = 16_000
MAX_JUNIT_BYTES = 2_000_000
MAX_DATABASE_REPORT_BYTES = 1_000_000
LABEL = "agentforge.sandbox=1"
CREATED_LABEL = "agentforge.created"  # unix time, so cleanup only touches abandoned resources
LEFTOVER_MARGIN_SECONDS = 600
DATABASE_READY_SECONDS = 45
# The PostgreSQL entrypoint needs these to set up its data directory and drop to its own user.
_DATABASE_CAPS = ("CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER")


class DatabaseStartError(RuntimeError):
    """The throwaway test database could not be started."""

# ruff rule codes -> severity. S = flake8-bandit (security), F = pyflakes, E9 = syntax.
_HIGH_RULES = {"S102", "S105", "S106", "S107", "S301", "S307", "S506", "S602", "S604", "S605", "S608", "S701", "F821", "E999"}
_SECURITY_PREFIX = "S"
# Normal in test code (asserts, fake credentials, temp paths).
_TEST_EXEMPT_RULES = ("S101", "S105", "S106", "S108", "B011")


def _severity(code: str) -> FindingSeverity:
    if code in _HIGH_RULES or code.startswith("E9"):
        return FindingSeverity.HIGH
    if code.startswith(_SECURITY_PREFIX):
        return FindingSeverity.MEDIUM
    if code.startswith("B"):
        return FindingSeverity.LOW
    return FindingSeverity.INFO


def _tail(text: str) -> str:
    return text[-MAX_OUTPUT_CHARS:]


class DockerSandbox:
    def __init__(
        self,
        *,
        image: str,
        timeout_seconds: int = 120,
        memory_mb: int = 512,
        cpus: float = 1.0,
        enabled: bool = True,
        docker_binary: str = "docker",
        database_image: str = "postgres:17-alpine",
    ) -> None:
        self._image = image
        self._database_image = database_image
        self._timeout = timeout_seconds
        self._memory = memory_mb
        self._cpus = cpus
        self._enabled = enabled
        self._docker = docker_binary
        self._status_cache: tuple[float, SandboxStatus] | None = None

    # ------------------------------------------------------------------ status

    def status(self) -> SandboxStatus:
        if not self._enabled:
            return SandboxStatus(False, "Sandbox disabled by configuration (SANDBOX_ENABLED=false)")
        if self._status_cache and time.monotonic() - self._status_cache[0] < 30:
            return self._status_cache[1]
        if shutil.which(self._docker) is None:
            result = SandboxStatus(False, "Docker is not installed on this host")
        else:
            try:
                probe = subprocess.run(
                    [self._docker, "image", "inspect", "--format", "{{.Id}}", self._image],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if probe.returncode == 0:
                    result = SandboxStatus(True, self._image)
                elif "Cannot connect" in probe.stderr or "daemon" in probe.stderr.lower():
                    result = SandboxStatus(False, "Docker daemon is not running")
                else:
                    result = SandboxStatus(False, f"Sandbox image {self._image} is not built (see docker/sandbox)")
            except (OSError, subprocess.TimeoutExpired):
                result = SandboxStatus(False, "Docker did not respond")
        self._status_cache = (time.monotonic(), result)
        return result

    # ------------------------------------------------------------------ running

    def _docker_args(
        self, name: str, workspace: Path, out: Path | None, *, network: str = "none", env: dict[str, str] | None = None
    ) -> list[str]:
        args = [
            self._docker, "run", "--rm", "--name", name, *self._labels(),
            "--network", network,
            "--memory", f"{self._memory}m", "--memory-swap", f"{self._memory}m",
            "--cpus", str(self._cpus),
            "--pids-limit", "256",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001",
            "--mount", f"type=bind,src={workspace},dst=/workspace,readonly",
            "-e", "PYTHONPATH=/workspace", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-w", "/workspace",
        ]
        if out is not None:
            args += ["--mount", f"type=bind,src={out},dst=/out"]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        return args + [self._image]

    @staticmethod
    def _labels() -> list[str]:
        return ["--label", LABEL, "--label", f"{CREATED_LABEL}={int(time.time())}"]

    def _cli(self, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run([self._docker, *args], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")

    @contextmanager
    def _database(self, run_name: str) -> Iterator[tuple[str, str]]:
        """A private network and a throwaway PostgreSQL server for one test run.
        Yields (network name, SQLAlchemy URL for the non-superuser app role)."""
        network, host = f"{run_name}-net", f"{run_name}-db"
        app_password = secrets.token_hex(16)
        try:
            created = self._cli("network", "create", "--internal", *self._labels(), network)
            if created.returncode != 0:
                raise DatabaseStartError(f"could not create the test network: {created.stderr.strip()[:300]}")
            caps = [arg for cap in _DATABASE_CAPS for arg in ("--cap-add", cap)]
            started = self._cli(
                "run", "-d", "--pull", "never", "--name", host, *self._labels(), "--network", network,
                "--memory", f"{self._memory}m", "--cpus", str(self._cpus), "--pids-limit", "256",
                "--cap-drop", "ALL", *caps, "--security-opt", "no-new-privileges",
                "--tmpfs", "/var/lib/postgresql/data:rw,size=256m",
                "-e", f"POSTGRES_PASSWORD={secrets.token_hex(16)}",
                self._database_image,
            )
            if started.returncode != 0:
                detail = started.stderr.strip()[:300]
                if "No such image" in detail or "pull" in detail.lower():
                    detail = f"database image {self._database_image} is not available (run: docker pull {self._database_image})"
                raise DatabaseStartError(f"could not start the test database: {detail}")
            deadline = time.monotonic() + DATABASE_READY_SECONDS
            while self._cli("exec", host, "pg_isready", "-U", "postgres", "-h", "127.0.0.1", timeout=15).returncode != 0:
                if time.monotonic() > deadline:
                    raise DatabaseStartError(f"the test database was not ready after {DATABASE_READY_SECONDS}s")
                time.sleep(0.5)
            # The application role owns its database but is not a superuser. The password is
            # ours (random hex), never model output.
            role = self._cli(
                "exec", host, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                "-c", f"CREATE ROLE app LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB PASSWORD '{app_password}'",
                "-c", "CREATE DATABASE app OWNER app",
            )
            if role.returncode != 0:
                raise DatabaseStartError(f"could not prepare the test database: {role.stderr.strip()[:300]}")
            yield network, f"postgresql+psycopg://app:{app_password}@{host}:5432/app"
        finally:
            self._cli("rm", "-f", host)
            self._cli("network", "rm", network)

    def remove_leftovers(self, now: float | None = None) -> int:
        """Remove sandbox containers and networks left behind by a crashed process. Only
        resources older than the longest a run can take are touched: other processes (a
        benchmark, another backend) may be using younger ones right now."""
        if shutil.which(self._docker) is None:
            return 0
        cutoff = (now or time.time()) - (self._timeout + DATABASE_READY_SECONDS + LEFTOVER_MARGIN_SECONDS)
        fmt = "{{.ID}} {{.Label \"" + CREATED_LABEL + "\"}}"

        def abandoned(listing: str) -> list[str]:
            ids = []
            for line in listing.splitlines():
                parts = line.split()
                created = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0  # unlabelled = from an old version
                if parts and created < cutoff:
                    ids.append(parts[0])
            return ids

        try:
            containers = abandoned(self._cli("ps", "-a", "--filter", f"label={LABEL}", "--format", fmt).stdout)
            if containers:
                self._cli("rm", "-f", *containers)
            networks = abandoned(self._cli("network", "ls", "--filter", f"label={LABEL}", "--format", fmt).stdout)
            for network in networks:
                self._cli("network", "rm", network)
            return len(containers) + len(networks)
        except (OSError, subprocess.TimeoutExpired):
            return 0

    def _materialise(self, root: Path, files: dict[str, str]) -> Path:
        workspace = root / "workspace"
        for raw_path, content in files.items():
            relative = normalize_path(raw_path)  # re-validated: never trust upstream
            target = (workspace / relative).resolve()
            if workspace.resolve() not in target.parents:
                raise ValueError(f"path escapes workspace: {raw_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return workspace

    def _run(self, args: list[str], name: str) -> tuple[int | None, str, bool]:
        """Returns (exit_code, combined_output, timed_out)."""
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=self._timeout, encoding="utf-8", errors="replace")
            return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), False
        except subprocess.TimeoutExpired as exc:
            subprocess.run([self._docker, "kill", name], capture_output=True, timeout=30)
            partial = (exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            return None, partial, True

    def run_tests(self, files: dict[str, str], *, database: bool = False) -> TestReport:
        status = self.status()
        if not status.available:
            return TestReport(executed=False, command=TEST_COMMAND, unavailable_reason=status.detail)

        root = Path(tempfile.mkdtemp(prefix="agentforge-run-"))
        name = f"agentforge-test-{uuid.uuid4().hex[:12]}"
        try:
            workspace = self._materialise(root, files)
            out = root / "out"
            out.mkdir()
            out.chmod(0o777)  # writable by the container's unprivileged user
            if database:
                with self._database(name) as (network, url):
                    report = self._execute(
                        name, self._docker_args(name, workspace, out, network=network, env={"DATABASE_URL": url}) + DATABASE_TEST_COMMAND, out
                    )
                return replace(report, database=self._database_report(out / "database.json"))
            return self._execute(name, self._docker_args(name, workspace, out) + TEST_COMMAND.split(), out)
        except DatabaseStartError as exc:
            logger.warning("test database unavailable: %s", exc)
            return TestReport(executed=False, command=TEST_COMMAND, unavailable_reason=f"Test database unavailable: {exc}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            logger.exception("sandbox run failed")
            return TestReport(executed=False, command=TEST_COMMAND, unavailable_reason=f"Sandbox error: {exc}")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def _execute(self, name: str, args: list[str], out: Path) -> TestReport:
        started = time.monotonic()
        exit_code, output, timed_out = self._run(args, name)
        duration_ms = int((time.monotonic() - started) * 1000)
        if timed_out:
            return TestReport(
                executed=True,
                command=TEST_COMMAND,
                exit_code=None,
                errors=1,
                duration_ms=duration_ms,
                output_excerpt=_tail(output + f"\n[AgentForge] Test run killed after {self._timeout}s timeout."),
                failures=[TestCaseFailure(name="(test run)", message=f"Timed out after {self._timeout}s")],
            )
        return self._parse_junit(out / "junit.xml", exit_code, output, duration_ms)

    @staticmethod
    def _database_report(path: Path) -> DatabaseReport:
        """Parse the runner's report. It is written inside the sandbox, so it is size-capped
        and shape-checked like any other untrusted file."""
        if not path.exists() or path.stat().st_size > MAX_DATABASE_REPORT_BYTES:
            return DatabaseReport(error="the database runner did not report (it may have timed out or crashed)")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            migrations = [
                MigrationResult(file=str(m["file"])[:200], ok=bool(m["ok"]), error=(str(m["error"])[:1000] if m.get("error") else None))
                for m in data.get("migrations", [])[:200]
            ]
            schema = [t for t in (_clean_table(t) for t in data.get("schema", [])[:200]) if t]
            error = data.get("error")
            return DatabaseReport(migrations=migrations, schema=schema, error=str(error)[:1000] if error else None)
        except (ValueError, KeyError, TypeError, AttributeError):
            return DatabaseReport(error="the database runner's report could not be read")

    def _parse_junit(self, path: Path, exit_code: int | None, output: str, duration_ms: int) -> TestReport:
        base = {"executed": True, "command": TEST_COMMAND, "exit_code": exit_code, "duration_ms": duration_ms, "output_excerpt": _tail(output)}
        if not path.exists() or path.stat().st_size > MAX_JUNIT_BYTES:
            # pytest could not start (syntax/import error in conftest) or produced no report.
            return TestReport(**base, errors=1, failures=[TestCaseFailure(name="(collection)", message=_tail(output)[-2000:])])
        root = ElementTree.parse(path).getroot()
        total = passed = failed = errors = skipped = 0
        failures: list[TestCaseFailure] = []
        for case in root.iter("testcase"):
            total += 1
            name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
            problem = case.find("failure")
            kind = "failed"
            if problem is None:
                problem = case.find("error")
                kind = "error"
            if problem is not None:
                if kind == "failed":
                    failed += 1
                else:
                    errors += 1
                detail = (problem.get("message") or "") + "\n" + (problem.text or "")
                failures.append(TestCaseFailure(name=name, message=detail.strip()[:3000], file_path=case.get("file"), line=_int(case.get("line"))))
            elif case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1
        if total == 0 and exit_code not in (0, None):
            errors = 1
            failures.append(TestCaseFailure(name="(collection)", message=_tail(output)[-2000:]))
        return TestReport(**base, total=total, passed=passed, failed=failed, errors=errors, skipped=skipped, failures=failures)

    def run_static_analysis(self, files: dict[str, str]) -> list[Finding]:
        if not self.status().available or not any(p.endswith(".py") for p in files):
            return []
        root = Path(tempfile.mkdtemp(prefix="agentforge-lint-"))
        name = f"agentforge-lint-{uuid.uuid4().hex[:12]}"
        try:
            workspace = self._materialise(root, files)
            command = [
                "ruff", "check", "--no-cache", "--output-format", "json", "--exit-zero",
                "--select", "F,E9,B,S",
                "--per-file-ignores", ",".join(f"tests/*:{code}" for code in _TEST_EXEMPT_RULES), ".",
            ]
            exit_code, output, timed_out = self._run(self._docker_args(name, workspace, None) + command, name)
            if timed_out or exit_code != 0:
                logger.warning("static analysis did not complete (exit=%s)", exit_code)
                return []
            start = output.find("[")
            items = json.loads(output[start:]) if start >= 0 else []
        except (OSError, ValueError, json.JSONDecodeError):
            logger.exception("static analysis failed")
            return []
        finally:
            shutil.rmtree(root, ignore_errors=True)

        findings: list[Finding] = []
        for item in items[:200]:
            code = item.get("code") or "?"
            filename = str(item.get("filename", "")).replace("\\", "/")
            relative = filename.split("/workspace/", 1)[-1].lstrip("./")
            findings.append(
                Finding(
                    severity=_severity(code),
                    category="security" if code.startswith("S") else "correctness",
                    title=f"{code}: {item.get('message', '')}"[:256],
                    description=item.get("message", ""),
                    source=FindingSource.TOOL,
                    file_path=relative or None,
                    line=(item.get("location") or {}).get("row"),
                    suggestion=((item.get("fix") or {}).get("message")) or (item.get("url") and f"See {item['url']}"),
                    tool_name="ruff",
                )
            )
        return findings


def _text(value: object, limit: int = 200) -> str:
    return str(value)[:limit] if value is not None else ""


def _names(value: object) -> list[str]:
    return [_text(v, 100) for v in value[:50]] if isinstance(value, list) else []


def _clean_table(table: object) -> dict | None:
    """Rebuild one schema table from the (untrusted) report with exactly the expected
    shape and bounded sizes; anything malformed is dropped rather than passed on."""
    if not isinstance(table, dict) or not table.get("name"):
        return None
    columns = [
        {
            "name": _text(c.get("name"), 100),
            "type": _text(c.get("type"), 100),
            "nullable": bool(c.get("nullable")),
            "default": None if c.get("default") is None else _text(c.get("default")),
            "primary_key": bool(c.get("primary_key")),
        }
        for c in (table.get("columns") if isinstance(table.get("columns"), list) else [])[:200]
        if isinstance(c, dict)
    ]
    foreign_keys = [
        {"columns": _names(fk.get("columns")), "references": _text(fk.get("references"))}
        for fk in (table.get("foreign_keys") if isinstance(table.get("foreign_keys"), list) else [])[:50]
        if isinstance(fk, dict)
    ]
    unique = [_names(u) for u in (table.get("unique") if isinstance(table.get("unique"), list) else [])[:50]]
    indexes = [
        {"name": _text(i.get("name"), 100), "columns": _names(i.get("columns")), "unique": bool(i.get("unique"))}
        for i in (table.get("indexes") if isinstance(table.get("indexes"), list) else [])[:50]
        if isinstance(i, dict)
    ]
    return {"name": _text(table["name"], 100), "columns": columns, "foreign_keys": foreign_keys, "unique": unique, "indexes": indexes}


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
