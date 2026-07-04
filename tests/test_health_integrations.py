import pytest
import sqlite3
import app as runcoach

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "test_integrations.db")
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

def test_database_tables_exist(client):
    _, _ = client
    conn = runcoach.get_database_connection()
    try:
        tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "health_connections" in tables
        assert "imported_activities" in tables
    finally:
        conn.close()

def test_integrations_page_loads_and_has_privacy_notices(client):
    client, _ = client
    response = client.get("/integrations")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Health Integrations" in html
    assert "Apple Health requires iOS companion app" in html or "iOS App Required" in html
    assert "Google Health Connect requires Android companion app" in html or "Android App Required" in html
    assert "GPS routes and location maps are not synced" in html
    assert "No data is imported or stored until you explicitly connect" in html

def test_mock_provider_connect_and_disconnect(client):
    client, demo_user = client
    conns = runcoach.get_health_connections(demo_user["id"])
    assert len(conns) == 0

    resp = client.post("/integrations/connect/strava", follow_redirects=True)
    assert resp.status_code == 200
    conns = runcoach.get_health_connections(demo_user["id"])
    assert len(conns) == 1
    assert conns[0]["provider"] == "strava"
    assert conns[0]["sync_enabled"] == 1

    resp = client.post("/integrations/toggle/strava", follow_redirects=True)
    assert resp.status_code == 200
    conns = runcoach.get_health_connections(demo_user["id"])
    assert conns[0]["sync_enabled"] == 0

    resp = client.post("/integrations/disconnect/strava", follow_redirects=True)
    assert resp.status_code == 200
    conns = runcoach.get_health_connections(demo_user["id"])
    assert len(conns) == 0

def test_sync_activities_and_duplicate_prevention(client):
    client, demo_user = client
    client.post("/integrations/connect/strava")

    resp = client.post("/integrations/sync", follow_redirects=True)
    assert resp.status_code == 200
    
    activities = runcoach.get_imported_activities(demo_user["id"])
    assert len(activities) >= 1
    
    act = activities[0]
    with pytest.raises(sqlite3.IntegrityError):
        runcoach.save_imported_activity(
            user_id=demo_user["id"],
            provider=act["provider"],
            external_activity_id=act["external_activity_id"],
            activity_type="run",
            start_time="2026-07-04 10:00:00",
            end_time=None,
            distance=5.0,
            duration=45.0,
            pace=9.0
        )

def test_activity_approval_and_conversion_to_run(client):
    client, demo_user = client
    client.post("/integrations/connect/strava")
    client.post("/integrations/sync")
    
    activities = runcoach.get_imported_activities(demo_user["id"])
    pending_act = [a for a in activities if not a["is_approved"]][0]
    
    resp = client.post(f"/integrations/activity/{pending_act['id']}/approve", follow_redirects=True)
    assert resp.status_code == 200
    
    activities_after = runcoach.get_imported_activities(demo_user["id"])
    approved_act = [a for a in activities_after if a["id"] == pending_act["id"]][0]
    assert approved_act["is_approved"] == 1
    
    conn = runcoach.get_database_connection()
    try:
        runs = conn.execute("SELECT * FROM runs WHERE user_id = ?", (demo_user["id"],)).fetchall()
        matching_runs = [r for r in runs if r["imported_from"] == "Strava"]
        assert len(matching_runs) == 1
        run_entry = matching_runs[0]
        assert run_entry["distance"] == pending_act["distance"]
        assert run_entry["duration"] == pending_act["duration"]
        assert "Strava" in run_entry["feedback"]
    finally:
        conn.close()
