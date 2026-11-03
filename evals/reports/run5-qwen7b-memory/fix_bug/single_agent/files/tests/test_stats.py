from app.stats import moving_average


def test_moving_average_positive_window():
    assert moving_average([1, 2, 3, 4, 5], 2) == [1.5, 2.5, 3.5, 4.5]


def test_moving_average_negative_window():
    try:
        moving_average([1, 2, 3, 4, 5], -1)
    except ValueError as e:
        assert str(e) == "window must be positive"


def test_moving_average_large_window():
    assert moving_average([1, 2, 3, 4, 5], 10) == []