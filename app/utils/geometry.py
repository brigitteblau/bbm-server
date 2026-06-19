from math import pi


def circumference_to_radius(circumference_cm: float) -> float:
    if circumference_cm <= 0:
        raise ValueError("circumference_cm must be positive")

    return circumference_cm / (2 * pi)
