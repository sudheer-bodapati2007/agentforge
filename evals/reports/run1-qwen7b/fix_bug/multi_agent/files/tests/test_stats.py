import pytest
from app.stats import moving_average


def test_moving_average_valid_input():
    values = [1, 2, 3, 4, 5]
    window = 3
    expected = [2.0, 3.0, 4.0]
    assert moving_average(values, window) == expected


def test_moving_average_window_less_than_1():
    values = [1, 2, 3, 4, 5]
    window = 0
    with pytest.raises(ValueError):
        moving_average(values, window)


def test_moving_average_window_larger_than_values():
    values = [1, 2, 3, 4, 5]
    window = 6
    assert moving_average(values, window) == []
