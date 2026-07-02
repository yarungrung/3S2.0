"""Walking speed formulas preserved from the notebook."""


def calculate_walk_speed(age: int, gender: str) -> float:
    """Return walking speed in km/h using the notebook's age/gender formula."""
    if 0 <= age < 65:
        return 5.62 if gender == "男性" else 5.26
    return 4.73 if gender == "男性" else 4.27


def fare_identity(age: int) -> str:
    """Return fare identity used by the original fare formulas."""
    if 0 <= age <= 12:
        return "child"
    if 13 <= age <= 22:
        return "student"
    if 23 <= age <= 64:
        return "adult"
    return "senior"
