The function below, in `app/stats.py`, has a bug. Rewrite `app/stats.py` with the bug fixed, keeping the same function name and parameters.

`moving_average(values: list[float], window: int) -> list[float]` must return the average of every run of `window` consecutive values, in order. It raises `ValueError` when `window` is less than 1, and returns an empty list when `window` is larger than the number of values.

```python
def moving_average(values, window):
    if window <= 0:
        raise ValueError("window must be positive")
    result = []
    for i in range(len(values) - window):
        result.append(sum(values[i:i + window]) / window)
    return result
```
