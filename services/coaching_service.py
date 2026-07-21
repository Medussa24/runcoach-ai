"""Deterministic coaching recommendations shared by UI and chat."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from stores import user_store, workout_store

DEMANDING_MOODS = {"tired", "sore", "stressed", "low", "rough", "bad"}
DEMANDING_NOTE_WORDS = {
    "hard",
    "heavy",
    "tired",
    "sore",
    "pain",
    "rough",
    "exhausted",
}


@dataclass(frozen=True)
class DailyRecommendation:
    target_date: date
    action_type: str
    title: str
    duration_minutes: int | None
    distance_miles: float | None
    intensity: str
    reason: str
    warnings: tuple[str, ...]
    plan_adjusted: bool
    confidence: str


def get_daily_recommendation(user_id, target_date, planned_events=None):
    """Return the one daily coaching recommendation for the requested user."""
    planned_event = _first_open_workout_event(planned_events or [])
    if planned_event:
        return DailyRecommendation(
            target_date=target_date,
            action_type="planned_workout",
            title=planned_event["title"],
            duration_minutes=planned_event.get("duration_minutes"),
            distance_miles=None,
            intensity="planned",
            reason=(
                planned_event.get("main_workout")
                or planned_event.get("details")
                or "This is already on your plan for today."
            ),
            warnings=(),
            plan_adjusted=False,
            confidence="high",
        )

    if user_store.get_user(user_id) is None:
        return _starter_recommendation(target_date, confidence="low")

    recent_workouts = workout_store.list_recent_workouts(
        user_id,
        target_date=target_date,
        limit=10,
    )
    if not recent_workouts:
        return _starter_recommendation(target_date)

    latest = recent_workouts[0]
    latest_date = _workout_date(latest)
    if latest_date == target_date - timedelta(days=1) and _looks_demanding(latest):
        return DailyRecommendation(
            target_date=target_date,
            action_type="recovery",
            title="20-minute recovery walk",
            duration_minutes=20,
            distance_miles=None,
            intensity="recovery",
            reason="Yesterday looked demanding, so today protects recovery while keeping your routine alive.",
            warnings=("Skip or shorten this if pain changes your normal movement.",),
            plan_adjusted=True,
            confidence="high",
        )

    if _recent_distance_jump(recent_workouts):
        return DailyRecommendation(
            target_date=target_date,
            action_type="easy_run",
            title="20-minute easy run",
            duration_minutes=20,
            distance_miles=None,
            intensity="easy",
            reason="Your latest distance jumped compared with the previous session, so today should stay conversational.",
            warnings=(),
            plan_adjusted=True,
            confidence="medium",
        )

    if len(_workouts_since(recent_workouts, target_date - timedelta(days=10))) >= 3:
        return DailyRecommendation(
            target_date=target_date,
            action_type="easy_run",
            title="30-minute easy run",
            duration_minutes=30,
            distance_miles=None,
            intensity="easy",
            reason="You have recent consistency, so an easy aerobic session keeps momentum without forcing intensity.",
            warnings=(),
            plan_adjusted=False,
            confidence="medium",
        )

    return DailyRecommendation(
        target_date=target_date,
        action_type="easy_run",
        title="25-minute easy run",
        duration_minutes=25,
        distance_miles=None,
        intensity="easy",
        reason="Your recent history supports a simple, repeatable run at a conversational effort.",
        warnings=(),
        plan_adjusted=False,
        confidence="medium",
    )


def should_answer_with_daily_recommendation(question):
    """Return whether a chat question is asking for today's coaching decision."""
    normalized = (question or "").lower()
    decision_terms = (
        "today",
        "tonight",
        "tomorrow",
        "next workout",
        "what should i run",
        "recommend",
        "workout should",
        "run today",
    )
    return any(term in normalized for term in decision_terms)


def format_daily_recommendation_response(recommendation):
    """Format a daily recommendation for coach chat without changing the decision."""
    answer = (
        f"Today: {recommendation.title}. Keep it {recommendation.intensity}. "
        f"{recommendation.reason}"
    )
    if recommendation.warnings:
        answer = f"{answer} {' '.join(recommendation.warnings)}"
    return answer


def _starter_recommendation(target_date, confidence="high"):
    return DailyRecommendation(
        target_date=target_date,
        action_type="walk_run",
        title="20-minute walk-run starter",
        duration_minutes=20,
        distance_miles=None,
        intensity="easy",
        reason="You do not have saved workout history yet, so the safest useful next step is short and repeatable.",
        warnings=(),
        plan_adjusted=False,
        confidence=confidence,
    )


def _first_open_workout_event(planned_events):
    for event in planned_events:
        if event.get("is_completed"):
            continue
        if (event.get("event_type") or "workout") == "workout":
            return event
    return None


def _workout_date(workout):
    value = str(workout.get("run_date") or "")[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _looks_demanding(workout):
    mood = (workout.get("mood") or "").strip().lower()
    notes = (workout.get("notes") or "").strip().lower()
    if mood in DEMANDING_MOODS:
        return True
    return any(word in notes for word in DEMANDING_NOTE_WORDS)


def _recent_distance_jump(workouts):
    if len(workouts) < 2:
        return False
    latest = float(workouts[0].get("distance") or 0)
    previous = float(workouts[1].get("distance") or 0)
    return previous > 0 and latest >= previous * 1.35 and latest - previous >= 0.75


def _workouts_since(workouts, start_date):
    return [
        workout
        for workout in workouts
        if (_workout_date(workout) or date.min) >= start_date
    ]
