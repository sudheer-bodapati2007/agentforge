from typing import List


def moving_average(values: List[float], window: int) -> List[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if window > len(values):
        return []
    result = []
    for i in range(len(values) - window + 1):
        result.append(sum(values[i:i + window]) / window)
    return result
