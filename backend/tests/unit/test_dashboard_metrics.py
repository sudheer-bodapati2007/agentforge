from app.application.dashboard import DashboardSnapshot, build_metrics
from app.domain.enums import RunStatus


def _snapshot(**overrides) -> DashboardSnapshot:
    base = {
        "total_projects": 0,
        "run_status_counts": {},
        "executed_test_suites": 0,
        "tests_passed": 0,
        "tests_total": 0,
        "run_durations_seconds": [],
        "total_estimated_cost_usd": None,
        "recent_runs": [],
        "recent_projects": [],
    }
    return DashboardSnapshot(**{**base, **overrides})


def test_empty_data_yields_null_rates_not_zero():
    metrics = build_metrics(_snapshot())
    assert metrics.total_runs == 0
    assert metrics.completion_rate is None
    assert metrics.test_pass_rate is None
    assert metrics.average_duration_seconds is None
    assert metrics.total_estimated_cost_usd is None
    assert set(metrics.runs_by_status) == set(RunStatus)


def test_completion_rate_ignores_in_flight_runs():
    metrics = build_metrics(
        _snapshot(
            run_status_counts={
                RunStatus.COMPLETED: 3,
                RunStatus.FAILED: 1,
                RunStatus.RUNNING: 5,  # not terminal, must not dilute the rate
            }
        )
    )
    assert metrics.total_runs == 9
    assert metrics.completion_rate == 0.75


def test_pass_rate_and_average_duration():
    metrics = build_metrics(
        _snapshot(tests_passed=9, tests_total=12, run_durations_seconds=[10.0, 20.0])
    )
    assert metrics.test_pass_rate == 0.75
    assert metrics.average_duration_seconds == 15.0
