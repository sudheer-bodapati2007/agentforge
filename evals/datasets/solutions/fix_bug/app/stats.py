def moving_average(values, window):
    if window <= 0:
        raise ValueError("window must be positive")
    result = []
    for i in range(len(values) - window + 1):
        result.append(sum(values[i:i + window]) / window)
    return result
