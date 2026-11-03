# Testing guide

## Layout
Tests live in `tests/`, mirroring the package structure. Unit tests must not touch the network,
the clock or the real database; integration tests may use the database started by docker compose.

## Fixtures and factories
Build test data with the factories in `tests/factories.py` instead of hand-written dictionaries,
so a new required field only has to be added in one place.

## Coverage
CI fails if line coverage drops below 85 percent. Coverage is a floor, not a goal: every bug fix
starts with a test that fails before the fix.

## Time
Code that depends on the current time takes a clock argument. Tests pass a frozen clock rather
than sleeping, so the suite stays fast and deterministic.

## Flaky tests
A test that fails intermittently is quarantined with the `flaky` marker within one day and fixed
within one week; quarantined tests are listed on the team dashboard.
