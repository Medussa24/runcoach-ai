import pytest
import sqlite3
from datetime import date
import calendar
import app as runcoach

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "test_challenges.db")
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

def test_challenges_database_setup(client):
    _, _ = client
    conn = runcoach.get_database_connection()
    try:
        tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "monthly_challenges" in tables
        assert "user_challenge_entries" in tables
        
        challenges = conn.execute("SELECT * FROM monthly_challenges").fetchall()
        assert len(challenges) == 6
    finally:
        conn.close()

def test_challenges_page_loads_and_bilingual_labels(client):
    client, demo_user = client
    
    response = client.get("/challenges")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Challenges" in html
    assert "Monthly Challenge" in html
    assert "Join Challenge" in html
    
    conn = runcoach.get_database_connection()
    try:
        challenge = conn.execute("SELECT * FROM monthly_challenges LIMIT 1").fetchone()
    finally:
        conn.close()
        
    join_resp = client.post(f"/challenge/{challenge['id']}/join", follow_redirects=True)
    assert join_resp.status_code == 200
    html_joined = join_resp.get_data(as_text=True)
    
    assert 'role="progressbar"' in html_joined
    assert 'aria-valuenow=' in html_joined
    assert 'aria-label=' in html_joined
    
    client.post("/set-language", data={"language": "es"})
    resp_es = client.get("/challenges")
    html_es = resp_es.get_data(as_text=True)
    assert "Desafíos" in html_es
    assert "Desafío Mensual" in html_es
    assert "Unirse al Desafío" in html_es

def test_join_and_leave_routes_are_idempotent(client):
    client, demo_user = client
    
    conn = runcoach.get_database_connection()
    try:
        challenge = conn.execute("SELECT * FROM monthly_challenges LIMIT 1").fetchone()
    finally:
        conn.close()
        
    r1 = client.post(f"/challenge/{challenge['id']}/join", follow_redirects=True)
    assert r1.status_code == 200
    assert runcoach.is_user_joined_challenge(demo_user["id"], challenge["id"]) is True
    
    r2 = client.post(f"/challenge/{challenge['id']}/join", follow_redirects=True)
    assert r2.status_code == 200
    
    conn = runcoach.get_database_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM user_challenge_entries WHERE user_id = ? AND challenge_id = ?",
            (demo_user["id"], challenge["id"])
        ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()
        
    l1 = client.post(f"/challenge/{challenge['id']}/leave", follow_redirects=True)
    assert l1.status_code == 200
    assert runcoach.is_user_joined_challenge(demo_user["id"], challenge["id"]) is False
    
    l2 = client.post(f"/challenge/{challenge['id']}/leave", follow_redirects=True)
    assert l2.status_code == 200

def test_progress_calculations(client):
    client, demo_user = client
    
    today = date.today()
    this_month_start = date(today.year, today.month, 1).strftime("%Y-%m-%d")
    
    conn = runcoach.get_database_connection()
    try:
        conn.execute(
            """
            INSERT INTO runs (run_date, distance, duration, pace, mood, notes, feedback, workout_type, user_id)
            VALUES (?, 5.0, 45.0, 9.0, 'Good', 'First run', 'Feedback', 'run', ?)
            """,
            (this_month_start, demo_user["id"])
        )
        conn.execute(
            """
            INSERT INTO runs (run_date, distance, duration, pace, mood, notes, feedback, workout_type, user_id)
            VALUES (?, 3.0, 30.0, 10.0, 'Good', 'Second walk', 'Feedback', 'walk', ?)
            """,
            (f"{this_month_start} 08:30:00", demo_user["id"])
        )
        conn.commit()
    finally:
        conn.close()
        
    ch_run = [c for c in runcoach.get_all_challenges() if c["title"] == "Run 10 Miles"][0]
    p_run = runcoach.calculate_challenge_progress(demo_user["id"], ch_run)
    assert p_run["current"] == 5.0
    assert p_run["target"] == 10.0
    assert p_run["percent"] == 50
    assert p_run["completed"] is False
    
    ch_walk = [c for c in runcoach.get_all_challenges() if c["title"] == "Walk 20 Miles"][0]
    p_walk = runcoach.calculate_challenge_progress(demo_user["id"], ch_walk)
    assert p_walk["current"] == 3.0
    assert p_walk["target"] == 20.0
    assert p_walk["percent"] == 15
    
    ch_cnt = [c for c in runcoach.get_all_challenges() if c["title"] == "Complete 12 Workouts"][0]
    p_cnt = runcoach.calculate_challenge_progress(demo_user["id"], ch_cnt)
    assert p_cnt["current"] == 2
    assert p_cnt["percent"] == 16
    
    ch_days = [c for c in runcoach.get_all_challenges() if c["title"] == "Active Days Challenge"][0]
    p_days = runcoach.calculate_challenge_progress(demo_user["id"], ch_days)
    assert p_days["current"] == 1
    assert p_days["percent"] == 6

def test_calories_unavailable_disclaimer(client):
    client, demo_user = client
    
    ch_cal = [c for c in runcoach.get_all_challenges() if c["title"] == "Burn 2,000 Calories"][0]
    p_cal = runcoach.calculate_challenge_progress(demo_user["id"], ch_cal)
    assert p_cal["available"] is False
    assert p_cal["message"] == "Calorie tracking requires imported activity data or manual calorie entry."
    
    today = date.today()
    this_month_start = date(today.year, today.month, 1).strftime("%Y-%m-%d")
    
    conn = runcoach.get_database_connection()
    try:
        conn.execute(
            """
            INSERT INTO runs (run_date, distance, duration, pace, mood, notes, feedback, calories, user_id)
            VALUES (?, 4.0, 36.0, 9.0, 'Good', 'Burn run', 'Feedback', 400, ?)
            """,
            (this_month_start, demo_user["id"])
        )
        conn.commit()
    finally:
        conn.close()
        
    p_cal_after = runcoach.calculate_challenge_progress(demo_user["id"], ch_cal)
    assert p_cal_after["available"] is True
    assert p_cal_after["current"] == 400
    assert p_cal_after["percent"] == 20

def test_privacy_safe_details_and_leaderboard(client):
    client, demo_user = client
    
    conn = runcoach.get_database_connection()
    try:
        challenge = conn.execute("SELECT * FROM monthly_challenges LIMIT 1").fetchone()
    finally:
        conn.close()
        
    client.post(f"/challenge/{challenge['id']}/join")
    
    resp = client.get(f"/challenge/{challenge['id']}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    email = demo_user["email"]
    email_prefix = email.split("@")[0]
    assert email not in html
    assert email_prefix not in html
    assert f"Runner #{demo_user['id']}" in html
