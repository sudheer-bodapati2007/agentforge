from app.stats import moving_average
from typing import List


def test_moving_average_positive_window():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    window = 2
    expected = [1.5, 2.5, 3.5, 4.5]
    assert moving_average(values, window) == expected


def test_moving_average_negative_window():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    window = -1
    with pytest.raises(ValueError):
        moving_average(values, window)


def test_moving_average_large_window():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    window = 10
    assert moving_average(values, window) == []