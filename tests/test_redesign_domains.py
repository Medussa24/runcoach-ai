from datetime import date

import pytest

import app as runcoach
from domain.runner_traits import calculate_traits, derive_identity
from services.insight_service import analyze_workouts
from services.story_service import build_story
from stores import calendar_subscription_store, progression_store, reflection_store


@pytest.fixture
def redesign_client(tmp_path, monkeypatch):
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "redesign.db")
    runcoach._database_ready = False
    runcoach.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    runcoach.setup_database()
    with runcoach.app.test_client() as client:
        yield client


def login(client, email="runner@example.test"):
    user_id = runcoach.create_user(email, "safe-password")
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return user_id


def test_progression_ledger_is_idempotent_and_has_provenance(redesign_client):
    user_id = login(redesign_client)
    assert progression_store.award(user_id, "workout", 7, "workout_completed", 100, "2026.1")
    assert not progression_store.award(user_id, "workout", 7, "workout_completed", 100, "2026.1")
    event = progression_store.list_events(user_id)[0]
    assert (event["source_type"], event["source_id"], event["reason"], event["xp"], event["rule_version"]) == ("workout", "7", "workout_completed", 100, "2026.1")


def test_insights_traits_and_story_use_only_workout_evidence():
    workouts = [
        {"id": 2, "run_date": "2026-08-13", "distance": 4, "duration": 36, "pace": 9, "avg_heart_rate": 145},
        {"id": 1, "run_date": "2026-08-10", "distance": 3, "duration": 30, "pace": 10, "avg_heart_rate": 144},
    ]
    insights = analyze_workouts(workouts, today=date(2026, 8, 13))
    assert insights[0]["type"] == "longest_run"
    assert insights[0]["evidence"]["distance_miles"] == 4
    traits = calculate_traits(workouts, today=date(2026, 8, 13))
    assert derive_identity(traits, 2) == "First Steps"
    story = build_story(workouts[0], insights, [{"reason": "workout_completed", "xp": 100}])
    assert story["story_type"] == "milestone"
    assert story["xp_total"] == 100
    assert story["workout"]["distance"] == 4


def test_reflections_are_user_scoped_and_not_memories(redesign_client):
    first = login(redesign_client, "first@example.test")
    reflection_store.create(first, "pre_run", "I feel uncertain.", "We can keep it easy.")
    second = runcoach.create_user("second@example.test", "safe-password")
    assert len(reflection_store.list_for_user(first)) == 1
    assert reflection_store.list_for_user(second) == []
    assert runcoach.get_user_memories(first, "rico") == {}


def test_calendar_tokens_are_hashed_revocable_and_user_scoped(redesign_client):
    user_id = login(redesign_client)
    token = calendar_subscription_store.issue(user_id)
    assert token not in str(calendar_subscription_store.resolve(token))
    assert calendar_subscription_store.resolve(token)["user_id"] == user_id
    calendar_subscription_store.revoke(user_id)
    assert calendar_subscription_store.resolve(token) is None


def test_exact_log_coach_planner_flow(redesign_client):
    login(redesign_client)
    saved = redesign_client.post("/log-workout", data={"run_date": "2026-08-13", "duration_hours": "0", "duration_minutes": "30", "duration_seconds": "0", "distance": "3", "distance_unit": "mi", "avg_heart_rate": "145"})
    assert saved.status_code == 302
    story = redesign_client.get(saved.headers["Location"])
    assert b"Run complete" in story.data and b"+100 XP" in story.data
    coach = redesign_client.post("/agent", json={"agent": "rico", "question": "What do you recommend for me today?"})
    answer = coach.get_json()["answer"]
    assert "saved workout history" not in answer
    planner = redesign_client.get("/planner")
    assert planner.status_code == 200
    assert b"Planner synced with 1 saved workout" in planner.data
