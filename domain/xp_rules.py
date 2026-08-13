"""Versioned, deterministic XP rules."""

RULE_VERSION = "2026.1"


def workout_awards(workout, previous_workouts=()):
    """Return auditable XP awards for a newly completed workout."""
    awards = [{"reason": "workout_completed", "xp": 100}]
    previous = list(previous_workouts)
    if previous:
        longest = max(float(item.get("distance") or 0) for item in previous)
        if float(workout.get("distance") or 0) > longest:
            awards.append({"reason": "distance_milestone", "xp": 50})
    return awards


def planner_awards():
    return [{"reason": "planned_workout_completed", "xp": 25}]
