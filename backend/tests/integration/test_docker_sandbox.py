"""The real Docker sandbox: isolation guarantees and true test execution.

Skipped automatically when Docker or the sandbox image is unavailable.
Build the image with: docker build -t agentforge-sandbox-python:2 docker/sandbox
"""

import pytest

from app.infrastructure.llm import scripted
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox

pytestmark = pytest.mark.docker

SANDBOX = DockerSandbox(image="agentforge-sandbox-python:2", timeout_seconds=90)
if not SANDBOX.status().available:
    pytest.skip(f"sandbox unavailable: {SANDBOX.status().detail}", allow_module_level=True)

PROBES = '''
import os, socket, subprocess

def test_no_network():
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2)
    except OSError:
        return
    raise AssertionError("network is reachable from the sandbox")

def test_cannot_modify_workspace():
    try:
        open("/workspace/app/__init__.py", "w").write("tampered")
    except OSError:
        return
    raise AssertionError("workspace is writable")

def test_cannot_write_root_filesystem():
    try:
        open("/usr/local/lib/evil.py", "w")
    except OSError:
        return
    raise AssertionError("root filesystem is writable")

def test_runs_unprivileged():
    assert os.getuid() == 10001 and os.geteuid() != 0

def test_host_env_is_not_leaked():
    leaked = [k for k in os.environ if any(s in k for s in ("DATABASE", "SUPABASE", "LLM", "API_KEY", "SECRET"))]
    assert leaked == []
'''


def test_isolation_guarantees_hold():
    report = SANDBOX.run_tests({"app/__init__.py": "", "tests/test_probes.py": PROBES})
    failed = [f.name for f in report.failures]
    assert report.succeeded, f"isolation probes failed: {failed}\n{report.output_excerpt[-2000:]}"
    assert report.total == 5


def test_real_results_drive_the_report():
    files = {
        "app/__init__.py": "",
        "app/models.py": scripted.MODELS_PY,
        "app/store.py": scripted.STORE_PY_TEMPLATE.format(op="!="),
        "app/main.py": scripted.MAIN_PY,
        "tests/test_api.py": scripted.TESTS_PY,
    }
    buggy = SANDBOX.run_tests(files)
    assert (buggy.total, buggy.failed) == (6, 1)
    assert buggy.failures[0].name.endswith("test_list_filters_by_done")
    files["app/store.py"] = scripted.STORE_PY_TEMPLATE.format(op="==")
    assert SANDBOX.run_tests(files).succeeded


def test_infinite_loops_are_stopped():
    report = SANDBOX.run_tests({"tests/test_hang.py": "def test_forever():\n    while True:\n        pass\n"})
    assert not report.succeeded
    assert "Timeout" in report.failures[0].message


def test_syntax_errors_are_reported_not_hidden():
    report = SANDBOX.run_tests({"app/__init__.py": "", "app/broken.py": "def oops(:\n", "tests/test_x.py": "from app.broken import oops\n\ndef test_x():\n    assert oops\n"})
    assert report.executed and not report.succeeded and report.errors >= 1


def test_static_analysis_finds_security_issues():
    findings = SANDBOX.run_static_analysis(
        {
            "app/__init__.py": "",
            "app/db.py": 'import sqlite3\n\ndef find(conn, name):\n    return conn.execute(f"SELECT * FROM users WHERE name = \'{name}\'")\n',
            "app/shell.py": "import subprocess\n\ndef run(cmd):\n    return subprocess.call(cmd, shell=True)\n",
        }
    )
    codes = {f.title.split(":")[0] for f in findings}
    assert "S608" in codes  # SQL injection
    assert "S602" in codes  # shell=True
    assert all(f.tool_name == "ruff" and f.file_path for f in findings)
