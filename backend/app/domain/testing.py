"""Results of executing a test suite. Produced only by the real test runner."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TestCaseFailure:
    __test__ = False  # not a pytest class

    name: str
    message: str
    file_path: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class MigrationResult:
    file: str
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class DatabaseReport:
    """What happened to the project's real PostgreSQL database during a test run: which
    migrations applied, and the schema read back from the database afterwards (tables
    with their columns, keys and indexes, as plain JSON-compatible dicts)."""

    migrations: list[MigrationResult] = field(default_factory=list)
    schema: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def migrated(self) -> bool:
        """Every migration applied and the schema could be read."""
        return self.error is None and all(m.ok for m in self.migrations)


@dataclass(frozen=True)
class TestReport:
    """`executed` is False when the suite could not run (e.g. sandbox unavailable)."""

    __test__ = False

    executed: bool
    command: str
    exit_code: int | None = None
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int | None = None
    output_excerpt: str = ""
    failures: list[TestCaseFailure] = field(default_factory=list)
    unavailable_reason: str | None = None
    database: DatabaseReport | None = None  # only for projects with a database

    @property
    def succeeded(self) -> bool:
        """Verified success: the runner executed, found tests, all of them passed, and (for
        database projects) every migration applied."""
        return (
            self.executed
            and self.exit_code == 0
            and self.total > 0
            and self.failed == 0
            and self.errors == 0
            and (self.database is None or self.database.migrated)
        )
