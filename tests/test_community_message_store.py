import pytest

import app as runcoach
from stores import community_message_store


@pytest.fixture()
def message_client(tmp_path, monkeypatch):
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "community_messages.db")
    runcoach.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    runcoach.setup_database()
    with runcoach.app.test_client() as client:
        yield client


def create_users(*names):
    return [
        runcoach.create_user(f"{name}@example.test", "safe-password")
        for name in names
    ]


def test_private_message_schema_and_indexes_exist(message_client):
    connection = runcoach.get_database_connection()
    try:
        foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert foreign_keys_enabled == 1
    assert {
        "message_conversations",
        "message_participants",
        "community_messages",
        "user_blocks",
        "message_reports",
    } <= tables
    assert {
        "idx_message_participants_user",
        "idx_community_messages_conversation",
        "idx_community_messages_sender",
        "idx_user_blocks_blocked",
        "idx_message_reports_status",
    } <= indexes


def test_conversation_is_one_to_one_and_deduplicated(message_client):
    alice, bob = create_users("pair-alice", "pair-bob")

    first = community_message_store.create_conversation(alice, bob)
    second = community_message_store.create_conversation(bob, alice)

    assert first == second
    assert community_message_store.create_conversation(alice, alice) is None
    assert community_message_store.create_conversation(alice, 999999) is None


def test_nonparticipant_cannot_discover_or_read_conversation(message_client):
    alice, bob, mallory = create_users("read-alice", "read-bob", "read-mallory")
    conversation_id = community_message_store.create_conversation(alice, bob)
    message_id = community_message_store.send_message(
        alice, conversation_id, "Private hello."
    )

    assert message_id is not None
    assert community_message_store.get_conversation(mallory, conversation_id) is None
    assert community_message_store.list_messages(mallory, conversation_id) == []
    assert community_message_store.list_conversations(mallory) == []
    assert community_message_store.list_messages(bob, conversation_id)[0]["body"] == (
        "Private hello."
    )


def test_nonparticipant_cannot_send_or_change_read_state(message_client):
    alice, bob, mallory = create_users("write-alice", "write-bob", "write-mallory")
    conversation_id = community_message_store.create_conversation(alice, bob)
    message_id = community_message_store.send_message(
        alice, conversation_id, "For Bob only."
    )

    assert community_message_store.send_message(
        mallory, conversation_id, "Forged message"
    ) is None
    assert community_message_store.mark_conversation_read(
        mallory, conversation_id
    ) is False
    assert community_message_store.list_conversations(bob)[0]["unread_count"] == 1
    assert community_message_store.mark_conversation_read(bob, conversation_id) is True
    assert community_message_store.list_conversations(bob)[0]["unread_count"] == 0
    messages = community_message_store.list_messages(alice, conversation_id)
    assert len(messages) == 1
    assert messages[0]["id"] == message_id
    assert messages[0]["sender_id"] == alice
    assert messages[0]["body"] == "For Bob only."


def test_block_target_is_derived_and_blocks_both_directions(message_client):
    alice, bob, mallory = create_users("block-alice", "block-bob", "block-mallory")
    conversation_id = community_message_store.create_conversation(alice, bob)

    assert community_message_store.block_conversation_participant(
        mallory, conversation_id
    ) is False
    assert community_message_store.block_conversation_participant(
        alice, conversation_id
    ) is True
    assert community_message_store.send_message(alice, conversation_id, "Blocked") is None
    assert community_message_store.send_message(bob, conversation_id, "Also blocked") is None

    connection = runcoach.get_database_connection()
    try:
        block = connection.execute(
            "SELECT blocker_id, blocked_id FROM user_blocks"
        ).fetchone()
    finally:
        connection.close()
    assert (block["blocker_id"], block["blocked_id"]) == (alice, bob)


def test_only_participants_can_report_visible_messages(message_client):
    alice, bob, mallory = create_users("report-alice", "report-bob", "report-mallory")
    conversation_id = community_message_store.create_conversation(alice, bob)
    message_id = community_message_store.send_message(alice, conversation_id, "Reportable")

    assert community_message_store.report_message(
        mallory, message_id, "spam"
    ) is None
    report_id = community_message_store.report_message(bob, message_id, "spam")
    assert report_id is not None
    assert community_message_store.report_message(bob, message_id, "spam") is None
    assert community_message_store.report_message(bob, message_id, "invalid") is None
