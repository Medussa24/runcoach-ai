"""Deterministic workout analysis; no generative decisions live here."""

from datetime import date, timedelta


def analyze_workouts(workouts, today=None, limit=3):
    today = today or date.today()
    ordered = sorted(workouts, key=lambda item: (str(item.get("run_date") or ""), item.get("id") or 0), reverse=True)
    if not ordered:
        return []
    insights = []
    recent = [item for item in ordered if _day(item) and _day(item) >= today - timedelta(days=7)]
    weekly_distance = round(sum(float(item.get("distance") or 0) for item in recent), 1)
    if recent:
        insights.append(_insight("weekly_consistency", 0.98, f"{len(recent)} workout{'s' if len(recent) != 1 else ''} this week", {"workout_count": len(recent), "distance_miles": weekly_distance}, 70 + len(recent)))
    if len(ordered) >= 2:
        latest, prior = ordered[0], ordered[1]
        latest_pace, prior_pace = float(latest.get("pace") or 0), float(prior.get("pace") or 0)
        if latest_pace and prior_pace and latest_pace < prior_pace:
            change = round((prior_pace - latest_pace) * 60)
            insights.append(_insight("pace_improvement", 0.82, f"Pace improved by {change} sec/mi versus your previous run", {"pace_change_sec_per_mile": -change, "comparison_runs": 2}, 88))
        if float(latest.get("distance") or 0) > max(float(item.get("distance") or 0) for item in ordered[1:]):
            insights.append(_insight("longest_run", 1.0, f"New longest run: {float(latest.get('distance') or 0):g} miles", {"distance_miles": float(latest.get("distance") or 0)}, 100))
    latest_day = _day(ordered[0])
    if latest_day and (today - latest_day).days >= 10:
        insights.append(_insight("comeback", 1.0, "Your next run will restart momentum after time away", {"inactive_days": (today - latest_day).days}, 92))
    return sorted(insights, key=lambda item: item["relevance"], reverse=True)[:limit]


def weekly_recap(workouts, today=None):
    """Return a compact factual recap Rico can narrate without invention."""
    today = today or date.today()
    week = [item for item in workouts if _day(item) and _day(item) >= today - timedelta(days=6)]
    miles = round(sum(float(item.get("distance") or 0) for item in week), 1)
    minutes = round(sum(float(item.get("duration") or 0) for item in week))
    return {"workout_count": len(week), "distance_miles": miles, "duration_minutes": minutes, "top_insight": next(iter(analyze_workouts(workouts, today=today, limit=1)), None)}


def _insight(kind, confidence, message, evidence, relevance):
    return {"type": kind, "confidence": confidence, "message": message, "evidence": evidence, "relevance": relevance}


def _day(workout):
    try:
        return date.fromisoformat(str(workout.get("run_date") or "")[:10])
    except ValueError:
        return None
