"""Evidence-based runner traits and stable identity rules."""

from datetime import date, timedelta


def calculate_traits(workouts, today=None):
    today = today or date.today()
    dated = [_date(item) for item in workouts]
    recent = [item for item, day in zip(workouts, dated) if day and day >= today - timedelta(days=28)]
    distances = [float(item.get("distance") or 0) for item in workouts]
    frequency = min(100, len(recent) * 9)
    endurance = min(100, round(max(distances, default=0) * 12))
    consistency = min(100, frequency + (10 if len(recent) >= 3 else 0))
    resilience = min(100, 35 + len(recent) * 5) if workouts else 0
    recovery = 50 if workouts else 0
    speed = _speed_score(workouts)
    return {
        "consistency": consistency,
        "endurance": endurance,
        "speed": speed,
        "resilience": resilience,
        "recovery": recovery,
    }


def derive_identity(traits, workout_count):
    if workout_count < 3:
        return "First Steps"
    strongest = max(traits, key=traits.get)
    labels = {
        "consistency": "Consistent Runner",
        "endurance": "Endurance Builder",
        "speed": "Pace Chaser",
        "resilience": "Resilient Runner",
        "recovery": "Balanced Runner",
    }
    return labels[strongest]


def _date(workout):
    try:
        return date.fromisoformat(str(workout.get("run_date") or "")[:10])
    except ValueError:
        return None


def _speed_score(workouts):
    paces = [float(item.get("pace") or 0) for item in workouts if float(item.get("pace") or 0) > 0]
    if not paces:
        return 0
    return max(0, min(100, round(120 - min(paces) * 7)))
