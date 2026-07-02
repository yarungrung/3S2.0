"""Fare formulas preserved from the notebook."""

import math


def ubike_fare(minutes: float, identity: str) -> float:
    """Calculate YouBike fare from the notebook formula."""
    if identity == "senior":
        if minutes <= 30:
            return 0.0
        return math.ceil((minutes - 30) / 30) * 10.0
    if identity == "child":
        extra = math.ceil((minutes - 30) / 30) * 5.0 if minutes > 30 else 0.0
        return 5.0 + extra
    if minutes <= 30:
        return 5.0
    return 5.0 + (math.ceil((minutes - 30) / 30) * 10.0)


def taxi_fare(length_km: float) -> float:
    """Calculate taxi fare from the notebook formula."""
    if length_km <= 1.25:
        return 85.0
    extra_dist_m = (length_km - 1.25) * 1000.0
    return 85.0 + (math.ceil(extra_dist_m / 200.0) * 5.0)


def bus_fare(identity: str) -> float:
    """Calculate bus fare from the notebook formula."""
    if identity == "adult":
        return 15.0
    if identity == "student":
        return 12.0
    return 8.0


def mrt_fare(length_km: float, identity: str) -> float:
    """Calculate MRT fare from the notebook formula."""
    if length_km <= 5.0:
        base_fare = 20.0
    else:
        base_fare = 20.0 + (math.ceil((length_km - 5.0) / 4.0) * 5.0)
    if identity in {"child", "senior"}:
        return float(math.ceil(base_fare * 0.5))
    return base_fare


def train_fare(length_km: float, identity: str) -> float:
    """Calculate TRA fare from the notebook formula."""
    base_fare = max(15.0, length_km * 1.46)
    if identity in {"child", "senior"}:
        return float(math.ceil(base_fare * 0.5))
    return float(math.ceil(base_fare))
