import pytest
from app.stats import moving_average


def test_moving_average_positive_window():
    values = [1, 2, 3, 4, 5]
    window = 2
    expected = [1.5, 2.5, 3.5, 4.5]
    assert moving_average(values, window) == expected


def test_moving_average_negative_window():
    values = [1, 2, 3, 4, 5]
    window = -1
    with pytest.raises(ValueError):
        moving_average(values, window)


def test_moving_average_large_window():
    values = [1, 2, 3, 4, 5]
    window = 10
    assert moving_average(values, window) == []


def test_moving_average_empty_values():
    values = []
    window = 2
    assert moving_average(values, window) == []
