import pytest
import app as runcoach

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "test.db")
    runcoach.app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
    )
    if hasattr(runcoach.app, "_db_setup_done"):
        delattr(runcoach.app, "_db_setup_done")
    with runcoach.app.test_client() as client:
        runcoach.setup_database()
        runcoach.seed_demo_data()
        runcoach.app._db_setup_done = True
        demo_user = runcoach.get_user_by_email(runcoach.DEMO_EMAIL)
        with client.session_transaction() as session:
            session["user_id"] = demo_user["id"]
        yield client, demo_user

def test_language_and_accessibility_preference_saving(client):
    client, demo_user = client
    # Verify defaults
    user = runcoach.get_user_by_id(demo_user["id"])
    assert user["language"] == "en"
    assert user["accessibility_mode"] == "standard"

    # Save settings via post route
    response = client.post("/update-settings", data={
        "language": "es",
        "accessibility_mode": "visual_coaching"
    }, follow_redirects=True)
    assert response.status_code == 200

    # Verify updated preferences
    user = runcoach.get_user_by_id(demo_user["id"])
    assert user["language"] == "es"
    assert user["accessibility_mode"] == "visual_coaching"

def test_set_language_pre_login(client):
    client, demo_user = client
    # Set pre-login language
    response = client.post("/set-language", data={"language": "es"}, follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as session:
        assert session.get("language") == "es"

def test_create_and_rsvp_community_event(client):
    client, demo_user = client
    
    # Verify initially there are no events in DB
    events = runcoach.get_upcoming_events()
    assert len(events) == 0

    # Create event
    response = client.post("/events", data={
        "title": "Fun Run Walk",
        "description": "Come join a fun 5k walk or run in the park.",
        "event_type": "run",
        "event_date": "2026-07-10",
        "event_time": "08:00",
        "location": "Piedmont Park",
        "pace_group": "Conversational (11:00 min/mi)",
        "language": "Bilingual (En/Es)"
    }, follow_redirects=True)
    assert response.status_code == 200

    events = runcoach.get_upcoming_events()
    assert len(events) == 1
    event = events[0]
    assert event["title"] == "Fun Run Walk"
    assert event["event_type"] == "run"
    assert event["location"] == "Piedmont Park"

    # Detail page access (public, works without session user too)
    detail_resp = client.get(f"/event/{event['id']}")
    assert detail_resp.status_code == 200
    html = detail_resp.get_data(as_text=True)
    assert "Fun Run Walk" in html
    assert "Piedmont Park" in html
    assert "Share to Facebook" in html # Check Facebook share button exists
    assert "og:title" in html # Check Open Graph tag exists

    # RSVP toggle
    rsvp_resp = client.post(f"/event/{event['id']}/rsvp", follow_redirects=True)
    assert rsvp_resp.status_code == 200
    assert runcoach.is_user_rsvped(demo_user["id"], event["id"]) is True
    assert runcoach.get_event_rsvps_count(event["id"]) == 1

    # Cancel RSVP
    rsvp_resp2 = client.post(f"/event/{event['id']}/rsvp", follow_redirects=True)
    assert rsvp_resp2.status_code == 200
    assert runcoach.is_user_rsvped(demo_user["id"], event["id"]) is False
    assert runcoach.get_event_rsvps_count(event["id"]) == 0

def test_shop_page(client):
    client, demo_user = client
    response = client.get("/shop")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "RunCoach AI T-shirt" in html
    assert "Rico Runner hoodie" in html
    assert "Walker-friendly shirt" in html
    assert "Sticker pack" in html
    assert "Buy Now" in html
