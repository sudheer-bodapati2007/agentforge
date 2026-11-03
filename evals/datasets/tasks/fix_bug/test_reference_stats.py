"""Hidden reference tests for the fix_bug task (the planted bug drops the last window)."""

import pytest

from app.stats import moving_average


def test_includes_the_last_window():
    assert moving_average([1, 2, 3, 4], 2) == pytest.approx([1.5, 2.5, 3.5])


def test_window_equal_to_length_gives_one_average():
    assert moving_average([1, 2, 3], 3) == pytest.approx([2.0])


def test_window_of_one_returns_each_value():
    assert moving_average([5, 7], 1) == pytest.approx([5.0, 7.0])


def test_floats():
    assert moving_average([0.1, 0.2, 0.3], 2) == pytest.approx([0.15, 0.25])


@pytest.mark.parametrize("values, window", [([1, 2], 3), ([], 1)])
def test_window_larger_than_values_is_empty(values, window):
    assert moving_average(values, window) == []


@pytest.mark.parametrize("window", [0, -1])
def test_non_positive_window_raises(window):
    with pytest.raises(ValueError):
        moving_average([1, 2, 3], window)
