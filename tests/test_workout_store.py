import pytest

import app as runcoach
from stores import workout_store


@pytest.fixture()
def workout_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "workout_store.db")
    runcoach.app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
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


def manual_workout_form(**overrides):
    data = {
        "run_date": "2026-07-14",
        "distance": "2.5",
        "duration": "25",
        "mood": "Good",
        "notes": "Store test workout.",
    }
    data.update(overrides)
    return data


def test_workout_store_creates_lists_and_preserves_order(workout_client):
    user_id = create_and_login(workout_client, "ordering@example.test")

    runcoach.save_manual_workout(
        user_id,
        manual_workout_form(run_date="2026-07-10", distance="1", duration="10"),
    )
    runcoach.save_manual_workout(
        user_id,
        manual_workout_form(run_date="2026-07-12", distance="2", duration="20"),
    )

    runs = workout_store.get_all_runs(user_id)

    assert [run["run_date"] for run in runs] == ["2026-07-12", "2026-07-10"]
    assert runs[0]["source"] == "Manual"
    assert runs[0]["workout_type"] == "Running"
    assert runcoach.get_all_runs(user_id) == runs


def test_workout_store_isolates_retrieve_update_and_delete(workout_client):
    owner_id = create_and_login(workout_client, "owner@example.test")
    other_id = runcoach.create_user("other@example.test", "safe-password")
    runcoach.save_manual_workout(owner_id, manual_workout_form())
    workout_id = runcoach.get_all_runs(owner_id)[0]["id"]

    assert workout_store.get_workout(other_id, workout_id) is None
    assert workout_store.update_workout(
        other_id,
        workout_id,
        {"notes": "Other user should not change this."},
    ) is False
    assert workout_store.delete_workout(other_id, workout_id) is False

    owner_workout = workout_store.get_workout(owner_id, workout_id)
    assert owner_workout["notes"] == "Store test workout."

    assert workout_store.update_workout(
        owner_id,
        workout_id,
        {"notes": "Owner update."},
    ) is True
    assert workout_store.get_workout(owner_id, workout_id)["notes"] == "Owner update."

    assert workout_store.delete_workout(owner_id, workout_id) is True
    assert workout_store.get_workout(owner_id, workout_id) is None


def test_existing_workout_route_and_app_patch_targets_still_work(workout_client, monkeypatch):
    user_id = create_and_login(workout_client, "route@example.test")
    calls = []
    original_insert = runcoach.insert_manual_workout

    def recording_insert(*args, **kwargs):
        calls.append(args)
        return original_insert(*args, **kwargs)

    monkeypatch.setattr(runcoach, "insert_manual_workout", recording_insert)

    response = workout_client.post(
        "/log-workout",
        data=manual_workout_form(),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/log-workout?saved=1")
    assert calls
    assert calls[0][0] == user_id
    assert len(runcoach.get_all_runs(user_id)) == 1
