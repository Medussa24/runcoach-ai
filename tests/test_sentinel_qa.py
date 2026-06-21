import subprocess

import pytest

import app as runcoach
from sentinel_qa import SentinelQA


@pytest.fixture()
def sentinel_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "sentinel_test.db")
    monkeypatch.setattr(runcoach, "SCREENSHOT_UPLOAD_DIR", tmp_path / "screenshots")
    monkeypatch.setattr(
        runcoach,
        "sentinel_qa",
        SentinelQA(runcoach.app, tmp_path),
    )
    runcoach.app.config.update(
        TESTING=True,
        SECRET_KEY="sentinel-test-secret",
        WTF_CSRF_ENABLED=False,
    )

    if hasattr(runcoach.app, "_db_setup_done"):
        delattr(runcoach.app, "_db_setup_done")

    with runcoach.app.test_client() as client:
        runcoach.setup_database()
        runcoach.seed_coach_library()
        runcoach.seed_demo_data()
        runcoach.app._db_setup_done = True
        demo_user = runcoach.get_user_by_email(runcoach.DEMO_EMAIL)
        with client.session_transaction() as session:
            session["user_id"] = demo_user["id"]
        yield client, demo_user["id"]


def test_sentinel_lightweight_check_verifies_routes_and_rendering(sentinel_client):
    _client, demo_user_id = sentinel_client

    report = runcoach.sentinel_qa.run_health_check(
        demo_user_id,
        include_test_suite=False,
    )

    assert report["status"] == "Healthy"
    assert report["app_status"] == "Online"
    assert report["checks_passed"] == report["checks_total"]
    assert report["warnings_count"] == 0
    assert report["last_check_time"] != "Never"
    assert all(
        status in {"Available", "Healthy"}
        for status in report["agent_statuses"].values()
    )


def test_periodic_sentinel_is_hidden_and_respects_interval(sentinel_client, monkeypatch):
    client, demo_user_id = sentinel_client
    sentinel = runcoach.sentinel_qa
    original_check = sentinel.run_health_check
    calls = []

    def tracked_check(*args, **kwargs):
        calls.append(1)
        return original_check(*args, **kwargs)

    monkeypatch.setattr(sentinel, "run_health_check", tracked_check)
    first = sentinel.run_periodic_if_due(demo_user_id, now=100)
    second = sentinel.run_periodic_if_due(demo_user_id, now=101)
    third = sentinel.run_periodic_if_due(demo_user_id, now=1001)

    response = client.get("/")
    html = response.get_data(as_text=True)
    hidden_endpoint = client.get("/sentinel/health")
    agent_registry = client.get("/agent").get_json()

    assert response.status_code == 200
    assert "System Health" not in html
    assert "Run Health Check" not in html
    assert hidden_endpoint.status_code == 404
    assert "internal_sentinel_qa" not in agent_registry
    assert len(calls) == 2
    assert first["status"] == second["status"] == third["status"] == "Healthy"


def test_sentinel_summarizes_pytest_pass_count(tmp_path, monkeypatch):
    sentinel = SentinelQA(runcoach.app, tmp_path, temp_root=tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="....................  [100%]\n20 passed in 1.23s\n",
            stderr="",
        ),
    )

    result = sentinel._run_pytest()

    assert result == {
        "passed": 20,
        "warning": None,
        "summary": "20 passed in 1.23s",
    }
