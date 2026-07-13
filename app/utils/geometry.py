import math


def circumference_to_radius(circumference_cm: float) -> float:
    """radio = circunferencia / 2π. Ambos en cm."""
    if circumference_cm <= 0:
        raise ValueError("La circunferencia debe ser positiva.")
    return circumference_cm / (2 * math.pi)