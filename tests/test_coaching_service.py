from datetime import date

import pytest

import app as runcoach
from services.coaching_service import (
    format_daily_recommendation_response,
    get_daily_recommendation,
)


@pytest.fixture()
def coaching_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "coaching_service.db")
    runcoach.app.config.update(
        TESTING=True,
        SECRET_KEY="coaching-test-secret",
        WTF_CSRF_ENABLED=False,
        DEMO_MODE=True,
    )
    if hasattr(runcoach.app, "_db_setup_done"):
        delattr(runcoach.app, "_db_setup_done")
    with runcoach.app.test_client() as client:
        runcoach.setup_database()
        runcoach.seed_coach_library()
        yield client


def create_and_login(client, email):
    user_id = runcoach.create_user(email, "safe-password")
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return user_id


def save_workout(user_id, **overrides):
    form = {
        "run_date": "2026-07-20",
        "distance": "2.0",
        "duration": "22",
        "mood": "Good",
        "notes": "Easy.",
    }
    form.update(overrides)
    runcoach.save_manual_workout(user_id, form)


def test_daily_recommendation_starts_new_users_safely(coaching_client):
    user_id = create_and_login(coaching_client, "starter@example.test")

    recommendation = get_daily_recommendation(user_id, date(2026, 7, 21))

    assert recommendation.title == "20-minute walk-run starter"
    assert recommendation.intensity == "easy"
    assert recommendation.plan_adjusted is False


def test_daily_recommendation_uses_open_planned_workout_first(coaching_client):
    user_id = create_and_login(coaching_client, "planned@example.test")
    planned_events = [
        {
            "event_type": "workout",
            "title": "Planned Easy Run",
            "duration_minutes": 35,
            "main_workout": "Run easy and conversational.",
            "is_completed": 0,
        }
    ]

    recommendation = get_daily_recommendation(
        user_id,
        date(2026, 7, 21),
        planned_events=planned_events,
    )

    assert recommendation.action_type == "planned_workout"
    assert recommendation.title == "Planned Easy Run"
    assert recommendation.reason == "Run easy and conversational."


def test_daily_recommendation_protects_recovery_after_demanding_yesterday(
    coaching_client,
):
    user_id = create_and_login(coaching_client, "recovery@example.test")
    save_workout(
        user_id,
        run_date="2026-07-20",
        distance="3.0",
        duration="36",
        mood="Sore",
        notes="Hard hills.",
    )

    recommendation = get_daily_recommendation(user_id, date(2026, 7, 21))

    assert recommendation.title == "20-minute recovery walk"
    assert recommendation.intensity == "recovery"
    assert recommendation.plan_adjusted is True
    assert recommendation.warnings


def test_daily_recommendation_adjusts_after_distance_jump(coaching_client):
    user_id = create_and_login(coaching_client, "jump@example.test")
    save_workout(user_id, run_date="2026-07-18", distance="1.5")
    save_workout(user_id, run_date="2026-07-20", distance="2.5")

    recommendation = get_daily_recommendation(user_id, date(2026, 7, 21))

    assert recommendation.title == "20-minute easy run"
    assert "distance jumped" in recommendation.reason
    assert recommendation.plan_adjusted is True


def test_dashboard_planner_and_chat_share_daily_recommendation(coaching_client):
    user_id = create_and_login(coaching_client, "surface@example.test")
    recommendation = get_daily_recommendation(user_id, date.today())

    dashboard_html = coaching_client.get("/").get_data(as_text=True)
    planner_html = coaching_client.get("/planner").get_data(as_text=True)
    chat_answer = runcoach.respond_with_memory(
        user_id,
        runcoach.AGENT_RICO,
        "What should I do today?",
    )

    assert recommendation.title in dashboard_html
    assert recommendation.title in planner_html
    assert format_daily_recommendation_response(recommendation) == chat_answer
