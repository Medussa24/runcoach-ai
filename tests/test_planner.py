import smtplib
from datetime import date

import pytest

import app as runcoach
from notification_service import PlanEmailService, build_calendar_ics
from planner_agent import WeeklyPlannerAgent


class RecordingService:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(
        self,
        system_prompt,
        question,
        context,
        tools=None,
        max_output_tokens=500,
        response_mime_type=None,
        thinking_budget=None,
    ):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "question": question,
                "context": context,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": response_mime_type,
                "thinking_budget": thinking_budget,
            }
        )
        return self.response


@pytest.fixture()
def planner_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_USE_VERTEX", raising=False)
    for variable in (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM_EMAIL",
        "SMTP_USE_TLS",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "planner.db")
    runcoach.app.config.update(
        TESTING=True,
        SECRET_KEY="planner-test-secret",
        WTF_CSRF_ENABLED=False,
    )
    runcoach.setup_database()
    runcoach.seed_coach_library()
    with runcoach.app.test_client() as client:
        yield client


def create_and_login(client, email):
    user_id = runcoach.create_user(email, "safe-password")
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return user_id


def test_fallback_week_has_complete_workout_outline():
    planner = WeeklyPlannerAgent(llm_service=RecordingService(None))

    events, source = planner.generate(
        date(2026, 6, 29),
        "07:30",
        "build consistency",
        {"recovery_frequency": 1},
    )

    assert source == "Scripted fallback"
    assert len(events) == 3
    for event in events:
        assert event["date"].startswith("2026-")
        assert event["start_time"] == "07:30"
        assert event["duration_minutes"] >= 10
        assert event["hydration"]
        assert event["warmup"]
        assert event["main_workout"]
        assert event["cooldown"]


def test_gemini_plan_is_parsed_and_normalized():
    service = RecordingService(
        """
        [
          {
            "date": "2026-06-30",
            "start_time": "06:45",
            "duration_minutes": 30,
            "title": "Easy Run",
            "coach": "Rico",
            "hydration": "Drink water.",
            "warmup": "Walk five minutes.",
            "main_workout": "Run easy for twenty minutes.",
            "cooldown": "Walk five minutes.",
            "notes": "Conversational pace."
          },
          {
            "date": "2026-07-02",
            "start_time": "06:45",
            "duration_minutes": 25,
            "title": "Nature Walk",
            "coach": "Iggy",
            "hydration": "Bring water.",
            "warmup": "Walk gently.",
            "main_workout": "Notice colors and sounds.",
            "cooldown": "Slow down and stretch.",
            "notes": ""
          },
          {
            "date": "2026-07-04",
            "start_time": "06:45",
            "duration_minutes": 20,
            "title": "Recovery Reset",
            "coach": "Luna",
            "hydration": "Sip water.",
            "warmup": "Breathe and mobilize.",
            "main_workout": "Easy mobility and walking.",
            "cooldown": "Quiet breathing.",
            "notes": ""
          }
        ]
        """
    )
    planner = WeeklyPlannerAgent(llm_service=service)

    events, source = planner.generate(
        date(2026, 6, 29),
        "06:45",
        "prepare for a 5K",
        {"weekly_mileage": 4},
    )

    assert source == "Gemini"
    assert [event["coach"] for event in events] == ["Rico", "Iggy", "Luna"]
    assert service.calls[0]["context"]["training_summary"]["weekly_mileage"] == 4
    assert service.calls[0]["max_output_tokens"] == 3000
    assert service.calls[0]["response_mime_type"] == "application/json"
    assert service.calls[0]["thinking_budget"] == 0


def test_planner_page_generation_completion_and_user_separation(
    planner_client,
):
    client = planner_client
    user_one = create_and_login(client, "planner-one@example.test")

    generated = client.post(
        "/planner/generate",
        data={
            "week_start": "2026-06-29",
            "preferred_time": "07:00",
            "goal": "build consistency",
        },
        follow_redirects=True,
    )
    assert generated.status_code == 200
    assert "My Plan" in generated.get_data(as_text=True)
    events = runcoach.get_planner_events(
        user_one,
        "2026-06-29",
        "2026-07-05",
    )
    assert len(events) == 3
    assert all(event["user_id"] == user_one for event in events)

    toggled = client.post(
        f"/planner/event/{events[0]['id']}/toggle",
        follow_redirects=True,
    )
    assert toggled.status_code == 200
    assert runcoach.get_planner_events(user_one)[0]["is_completed"] == 1

    user_two = create_and_login(client, "planner-two@example.test")
    assert runcoach.get_planner_events(user_two) == []
    client.post(f"/planner/event/{events[0]['id']}/toggle")
    assert runcoach.get_planner_events(user_one)[0]["is_completed"] == 1


def test_personal_event_and_calendar_export(planner_client):
    client = planner_client
    user_id = create_and_login(client, "calendar@example.test")

    response = client.post(
        "/planner/event",
        data={
            "title": "Community 5K",
            "event_date": "2026-07-04",
            "start_time": "08:30",
            "duration_minutes": "60",
            "details": "Meet at the park entrance.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    event = runcoach.get_planner_events(user_id)[0]
    assert event["event_type"] == "personal"

    exported = client.get("/planner/calendar.ics?week_start=2026-06-29")
    assert exported.status_code == 200
    assert exported.mimetype == "text/calendar"
    assert b"Community 5K" in exported.data
    assert b"BEGIN:VEVENT" in exported.data
    assert b"X-WR-TIMEZONE:America/New_York" in exported.data
    assert b"DTSTART;TZID=America/New_York:20260704T083000" in exported.data


def test_user_can_update_planner_timezone(planner_client):
    client = planner_client
    user_id = create_and_login(client, "timezone@example.test")

    updated = client.post(
        "/planner/timezone",
        data={
            "timezone": "America/Los_Angeles",
            "week_start": "2026-06-29",
        },
        follow_redirects=True,
    )

    assert updated.status_code == 200
    assert "Planner timezone updated" in updated.get_data(as_text=True)
    assert runcoach.get_user_by_id(user_id)["timezone"] == "America/Los_Angeles"

    client.post(
        "/planner/event",
        data={
            "title": "West coast walk",
            "event_date": "2026-07-01",
            "start_time": "07:15",
            "duration_minutes": "20",
            "details": "Easy movement.",
        },
    )
    exported = client.get("/planner/calendar.ics?week_start=2026-06-29")
    assert b"X-WR-TIMEZONE:America/Los_Angeles" in exported.data
    assert b"DTSTART;TZID=America/Los_Angeles:20260701T071500" in exported.data


def test_regenerating_week_preserves_personal_events(planner_client):
    client = planner_client
    user_id = create_and_login(client, "preserve@example.test")
    client.post(
        "/planner/event",
        data={
            "title": "Race registration deadline",
            "event_date": "2026-07-01",
            "start_time": "12:00",
            "duration_minutes": "10",
            "details": "Submit registration.",
        },
    )
    generation = {
        "week_start": "2026-06-29",
        "preferred_time": "07:00",
        "goal": "build consistency",
    }
    client.post("/planner/generate", data=generation)
    client.post("/planner/generate", data=generation)

    events = runcoach.get_planner_events(
        user_id,
        "2026-06-29",
        "2026-07-05",
    )
    assert sum(event["event_type"] == "personal" for event in events) == 1
    assert sum(event["event_type"] == "workout" for event in events) == 3


def test_email_fallback_and_configured_smtp(planner_client, monkeypatch):
    client = planner_client
    user_id = create_and_login(client, "email@example.test")
    client.post(
        "/planner/event",
        data={
            "title": "Morning walk",
            "event_date": date.today().isoformat(),
            "start_time": "08:00",
            "duration_minutes": "20",
            "details": "Easy walk.",
        },
    )

    unconfigured = client.post("/planner/email", follow_redirects=True)
    assert "Email reminders are not configured" in unconfigured.get_data(as_text=True)

    sent_messages = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            return None

        def login(self, username, password):
            return None

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "coach@example.test")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    events = runcoach.get_planner_events(user_id)
    service = PlanEmailService()
    sent, message = service.send_week(
        "email@example.test",
        events,
        build_calendar_ics(events),
    )
    assert sent is True
    assert "sent" in message
    assert len(sent_messages) == 1


def test_planner_routes_require_authentication(planner_client):
    client = planner_client
    assert client.get("/planner").status_code == 302
    assert client.post("/planner/generate").status_code == 401
    assert client.post("/planner/event").status_code == 401
    assert client.post("/planner/timezone").status_code == 401
    assert client.post("/planner/email").status_code == 401
