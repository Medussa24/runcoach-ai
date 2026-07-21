import pytest

import app as runcoach
from stores import coach_message_store


@pytest.fixture()
def message_store_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "coach_message_store.db")
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


def test_user_cannot_read_another_users_messages(message_store_client):
    user_one = runcoach.create_user("message-one@example.test", "safe-password")
    user_two = runcoach.create_user("message-two@example.test", "safe-password")
    message_id = coach_message_store.insert_agent_message(
        user_one,
        "user",
        "Private training note.",
        "rico",
    )

    assert coach_message_store.get_agent_message(user_two, message_id) is None
    assert coach_message_store.get_agent_message(user_one, message_id)["message"] == (
        "Private training note."
    )


def test_user_cannot_delete_another_users_conversation(message_store_client):
    user_one = runcoach.create_user("delete-one@example.test", "safe-password")
    user_two = runcoach.create_user("delete-two@example.test", "safe-password")
    coach_message_store.insert_agent_message(user_one, "user", "Keep this.", "rico")
    coach_message_store.insert_agent_message(user_two, "user", "Delete mine.", "rico")

    deleted = coach_message_store.delete_coach_conversation(user_two, "rico")

    assert deleted == 1
    assert len(coach_message_store.get_agent_messages(user_one, "rico")) == 1
    assert coach_message_store.get_agent_messages(user_two, "rico") == []


def test_agent_message_app_compatibility_and_empty_message_behavior(message_store_client):
    user_id = runcoach.create_user("compat-message@example.test", "safe-password")

    runcoach.save_agent_message(user_id, "user", "  Hello Rico.  ", "rico")
    runcoach.save_agent_message(user_id, "user", "   ", "rico")

    messages = runcoach.get_agent_messages(user_id, "rico")

    assert len(messages) == 1
    assert messages[0]["message"] == "Hello Rico."


def test_user_memory_is_scoped_by_user_and_coach(message_store_client):
    user_one = runcoach.create_user("memory-one-store@example.test", "safe-password")
    user_two = runcoach.create_user("memory-two-store@example.test", "safe-password")

    coach_message_store.upsert_user_memory(user_one, "goal", "5K", agent_name="shared")
    coach_message_store.upsert_user_memory(user_one, "tone", "gentle", agent_name="luna")
    coach_message_store.upsert_user_memory(user_two, "goal", "marathon", agent_name="shared")

    assert coach_message_store.get_user_memories(user_one, "luna") == {
        "goal": "5K",
        "tone": "gentle",
    }
    assert coach_message_store.get_user_memories(user_two, "luna") == {
        "goal": "marathon",
    }
