from app.stats import moving_average

import pytest


def test_moving_average_value_error():
    with pytest.raises(ValueError):
        moving_average([1, 2, 3], 0)


def test_moving_average_empty_list():
    assert moving_average([1, 2, 3], 4) == []


def test_moving_average_correct_result():
    assert moving_average([1, 2, 3, 4, 5], 2) == [1.5, 2.5, 3.5, 4.5]


def test_moving_average_single_value():
    assert moving_average([1], 1) == [1.0]
