import pytest

import app as runcoach
from stores import user_store


@pytest.fixture()
def user_store_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "user_store.db")
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


def test_user_store_create_read_and_app_compatibility(user_store_client):
    user_id = runcoach.create_user("UserStore@Example.Test", "safe-password")

    by_id = user_store.get_user(user_id)
    by_email = user_store.get_user_by_email(" userstore@example.test ")

    assert by_id["email"] == "userstore@example.test"
    assert by_email["id"] == user_id
    assert runcoach.get_user_by_id(user_id)["id"] == user_id
    assert runcoach.get_user_by_email("userstore@example.test")["id"] == user_id


def test_update_user_only_updates_target_user(user_store_client):
    user_one = runcoach.create_user("target@example.test", "safe-password")
    user_two = runcoach.create_user("other-target@example.test", "safe-password")

    assert user_store.update_user(user_one, language="es") is True

    assert user_store.get_user(user_one)["language"] == "es"
    assert user_store.get_user(user_two)["language"] == "en"


def test_set_language_route_uses_user_store_boundary(user_store_client, monkeypatch):
    user_id = runcoach.create_user("language-route@example.test", "safe-password")
    calls = []
    original_update = runcoach.user_store.update_user

    def recording_update(*args, **kwargs):
        calls.append((args, kwargs))
        return original_update(*args, **kwargs)

    monkeypatch.setattr(runcoach.user_store, "update_user", recording_update)
    with user_store_client.session_transaction() as session:
        session["user_id"] = user_id

    response = user_store_client.post("/set-language", data={"language": "es"})

    assert response.status_code == 302
    assert calls == [((user_id,), {"language": "es"})]
    assert runcoach.get_user_by_id(user_id)["language"] == "es"
