"""The database report is written inside the sandbox, so it is untrusted: it is parsed
with size caps and rebuilt in exactly the expected shape."""

import json

from app.infrastructure.sandbox.docker_sandbox import DockerSandbox, _clean_table

GOOD_TABLE = {
    "name": "books",
    "columns": [{"name": "id", "type": "INTEGER", "nullable": False, "default": None, "primary_key": True}],
    "foreign_keys": [{"columns": ["author_id"], "references": "authors(id)"}],
    "unique": [["title"]],
    "indexes": [{"name": "ix", "columns": ["author_id"], "unique": False}],
}


def parse(tmp_path, payload) -> object:
    path = tmp_path / "database.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return DockerSandbox._database_report(path)


def test_a_well_formed_report_round_trips(tmp_path):
    report = parse(tmp_path, {"migrations": [{"file": "0001.sql", "ok": True, "error": None}], "schema": [GOOD_TABLE], "error": None})
    assert report.migrated and report.schema == [GOOD_TABLE]


def test_garbage_is_dropped_or_reshaped_never_passed_on(tmp_path):
    hostile = {
        "migrations": [{"file": "x" * 5000, "ok": 1, "error": "e" * 5000}],
        "schema": [
            "not a table",
            {"name": None},
            {"name": "t", "columns": "nope", "foreign_keys": {"a": 1}, "unique": [["a"], "bad"], "indexes": [1, {"name": "i"}], "extra": "<script>"},
            {"name": "u", "columns": [{"name": "c", "type": {"nested": True}, "nullable": "yes", "primary_key": 0, "evil": 1}]},
        ],
    }
    report = parse(tmp_path, hostile)
    assert len(report.migrations[0].file) == 200 and len(report.migrations[0].error) == 1000
    t, u = report.schema
    assert t == {"name": "t", "columns": [], "foreign_keys": [], "unique": [["a"], []], "indexes": [{"name": "i", "columns": [], "unique": False}]}
    assert u["columns"] == [{"name": "c", "type": "{'nested': True}", "nullable": True, "default": None, "primary_key": False}]
    assert "extra" not in t and "evil" not in u["columns"][0]


def test_unreadable_or_missing_reports_are_errors_not_crashes(tmp_path):
    assert "could not be read" in parse(tmp_path, "{not json").error
    assert "could not be read" in parse(tmp_path, []).error
    assert "did not report" in DockerSandbox._database_report(tmp_path / "missing.json").error
    big = tmp_path / "database.json"
    big.write_bytes(b" " * 1_000_001)
    assert "did not report" in DockerSandbox._database_report(big).error


def test_clean_table_rejects_non_tables():
    assert _clean_table(None) is None and _clean_table({"columns": []}) is None and _clean_table([]) is None
