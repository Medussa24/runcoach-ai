"""Progression orchestration built on deterministic rules."""

from domain.runner_traits import calculate_traits, derive_identity
from domain.xp_rules import RULE_VERSION, planner_awards, workout_awards


def record_workout(store, user_id, workout, previous_workouts=()):
    awarded = []
    for item in workout_awards(workout, previous_workouts):
        if store.award(user_id, "workout", workout["id"], item["reason"], item["xp"], RULE_VERSION):
            awarded.append(item)
    return awarded


def record_planner_completion(store, user_id, event_id):
    awarded = []
    for item in planner_awards():
        if store.award(user_id, "planner_event", event_id, item["reason"], item["xp"], RULE_VERSION):
            awarded.append(item)
    return awarded


def runner_profile(workouts):
    traits = calculate_traits(workouts)
    return {"traits": traits, "identity": derive_identity(traits, len(workouts))}
