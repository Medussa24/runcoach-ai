import pytest

import app as runcoach
from blueprints import messages as messages_blueprint
from stores import community_message_store


@pytest.fixture()
def messages_client(tmp_path, monkeypatch):
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "messages_workspace.db")
    runcoach.app.config.update(
        TESTING=True,
        SECRET_KEY="messages-test-secret",
        WTF_CSRF_ENABLED=False,
    )
    runcoach.setup_database()
    with runcoach.app.test_client() as client:
        yield client


def create_user(email):
    return runcoach.create_user(email, "safe-password")


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_messages_workspace_requires_authentication(messages_client):
    response = messages_client.get("/community/messages")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_inbox_renders_only_authenticated_users_conversations(messages_client):
    alice = create_user("alice-inbox@example.test")
    bob = create_user("bob-inbox@example.test")
    mallory = create_user("mallory-inbox@example.test")
    alice_thread = community_message_store.create_conversation(alice, bob)
    hidden_thread = community_message_store.create_conversation(bob, mallory)
    community_message_store.send_message(bob, alice_thread, "Visible to Alice")
    community_message_store.send_message(mallory, hidden_thread, "Hidden from Alice")
    login_as(messages_client, alice)

    response = messages_client.get("/community/messages")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Messages" in html
    assert "bob-inbox" in html
    assert "Visible to Alice" in html
    assert "1 unread messages" in html
    assert "mallory-inbox" not in html
    assert "Hidden from Alice" not in html


def test_participant_can_render_read_only_thread(messages_client):
    alice = create_user("alice-thread@example.test")
    bob = create_user("bob-thread@example.test")
    conversation_id = community_message_store.create_conversation(alice, bob)
    community_message_store.send_message(alice, conversation_id, "First private note")
    community_message_store.send_message(bob, conversation_id, "Second private note")
    login_as(messages_client, alice)

    response = messages_client.get(f"/community/messages/{conversation_id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "alice-thread@example.test" not in html
    assert "bob-thread@example.test" in html
    assert "First private note" in html
    assert "Second private note" in html
    assert "Reply controls will be enabled" in html
    assert "name=\"body\"" not in html


def test_nonparticipant_gets_not_found_without_thread_content(messages_client):
    alice = create_user("alice-private@example.test")
    bob = create_user("bob-private@example.test")
    mallory = create_user("mallory-private@example.test")
    conversation_id = community_message_store.create_conversation(alice, bob)
    community_message_store.send_message(alice, conversation_id, "Never expose this")
    login_as(messages_client, mallory)

    response = messages_client.get(f"/community/messages/{conversation_id}")

    assert response.status_code == 404
    assert "Never expose this" not in response.get_data(as_text=True)


def test_empty_inbox_has_accessible_empty_states(messages_client):
    user_id = create_user("empty-inbox@example.test")
    login_as(messages_client, user_id)

    html = messages_client.get("/community/messages").get_data(as_text=True)

    assert "Your inbox is ready" in html
    assert "Select a conversation" in html
    assert 'aria-label="Private messages"' in html
    assert 'aria-label="Conversations"' in html


def test_start_discovery_is_neutral_and_does_not_create_conversations(messages_client):
    requester = create_user("requester@example.test")
    create_user("known@example.test")
    login_as(messages_client, requester)

    known = messages_client.post(
        "/community/messages/start",
        data={"email": "known@example.test"},
        follow_redirects=True,
    )
    requester_two = create_user("requester-two@example.test")
    login_as(messages_client, requester_two)
    unknown = messages_client.post(
        "/community/messages/start",
        data={"email": "unknown@example.test"},
        follow_redirects=True,
    )

    assert known.status_code == unknown.status_code == 200
    assert messages_blueprint.NEUTRAL_START_NOTICE in known.get_data(as_text=True)
    assert messages_blueprint.NEUTRAL_START_NOTICE in unknown.get_data(as_text=True)
    assert community_message_store.list_conversations(requester) == []


def test_start_discovery_rate_limits_authenticated_account(messages_client):
    requester = create_user("rate-limited@example.test")
    login_as(messages_client, requester)

    for attempt in range(messages_blueprint.START_RATE_LIMIT):
        response = messages_client.post(
            "/community/messages/start",
            data={"email": f"person-{attempt}@example.test"},
        )
        assert response.status_code == 303

    limited = messages_client.post(
        "/community/messages/start",
        data={"email": "one-more@example.test"},
    )

    assert limited.status_code == 429
    assert "one-more@example.test" not in limited.get_data(as_text=True)
