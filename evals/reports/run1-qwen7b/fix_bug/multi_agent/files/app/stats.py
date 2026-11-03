from typing import List


def moving_average(values: List[float], window: int) -> List[float]:
    if window < 1:
        raise ValueError('Window size must be at least 1')
    if window > len(values):
        return []
    return [sum(values[i:i+window]) / window for i in range(len(values) - window + 1)]