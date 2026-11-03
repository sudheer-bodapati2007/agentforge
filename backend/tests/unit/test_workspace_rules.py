import pytest

from app.domain.errors import InvariantViolationError
from app.domain.run import ALLOWED_TRANSITIONS, check_transition, is_terminal
from app.domain.enums import RunStatus
from app.domain.workspace import MAX_FILE_BYTES, MAX_FILES, SourceFile, merge_files, normalize_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("app/main.py", "app/main.py"),
        ("./app//models.py", "app/models.py"),
        ("app\\windows.py", "app/windows.py"),
        ("README.md", "README.md"),
        (".env.example", ".env.example"),
        ("tests/test_api.py", "tests/test_api.py"),
    ],
)
def test_valid_paths_are_normalised(raw, expected):
    assert normalize_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "../secrets.py",
        "app/../../etc/passwd.py",
        "/etc/passwd",
        "C:/Windows/system.py",
        "",
        "   ",
        "app/.hidden/x.py",
        ".env",
        "app/run.sh",
        "app/binary.exe",
        "app/évil.py",
        "a" * 300 + ".py",
    ],
)
def test_unsafe_paths_are_rejected(raw):
    with pytest.raises(InvariantViolationError):
        normalize_path(raw)


def test_file_size_and_binary_limits():
    with pytest.raises(InvariantViolationError):
        SourceFile.create("app/big.py", "x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(InvariantViolationError):
        SourceFile.create("app/bin.py", "a\x00b")


def test_workspace_file_count_limit():
    current = {f"app/m{i}.py": "" for i in range(MAX_FILES)}
    with pytest.raises(InvariantViolationError):
        merge_files(current, [SourceFile.create("app/extra.py", "")])


def test_run_state_machine():
    check_transition(RunStatus.QUEUED, RunStatus.RUNNING)
    check_transition(RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL)
    check_transition(RunStatus.AWAITING_APPROVAL, RunStatus.QUEUED)
    check_transition(RunStatus.FAILED, RunStatus.QUEUED)  # explicit retry
    for terminal in (RunStatus.COMPLETED, RunStatus.PARTIALLY_COMPLETED, RunStatus.CANCELLED):
        assert ALLOWED_TRANSITIONS[terminal] == frozenset()
        assert is_terminal(terminal)
        with pytest.raises(InvariantViolationError):
            check_transition(terminal, RunStatus.RUNNING)
    with pytest.raises(InvariantViolationError):
        check_transition(RunStatus.QUEUED, RunStatus.COMPLETED)
