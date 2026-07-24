"""SQLite persistence helpers for coach conversations and memories."""

from __future__ import annotations

_connection_factory = None


def configure(connection_factory):
    """Configure the database connection factory used by conversation queries."""
    global _connection_factory
    _connection_factory = connection_factory


def _connect():
    if _connection_factory is None:
        raise RuntimeError("Coach message store connection factory is not configured.")
    return _connection_factory()


def get_agent_message(user_id, message_id):
    """Return one message only when it belongs to the requested user."""
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT id, user_id, agent_name, sender, message, created_at
            FROM agent_messages
            WHERE id = ? AND user_id = ?
            """,
            (message_id, user_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_agent_messages(user_id, agent_name="rico", limit=30):
    """Return recent chat messages for one user and one coach."""
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT sender, message, created_at
            FROM agent_messages
            WHERE user_id = ?
              AND (agent_name = ? OR (? = 'rico' AND agent_name IS NULL))
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, agent_name, agent_name, limit),
        ).fetchall()
    finally:
        connection.close()

    return [dict(row) for row in reversed(rows)]


def insert_agent_message(user_id, sender, message, agent_name="rico"):
    """Insert one coach conversation message for the requested user."""
    connection = _connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO agent_messages (user_id, agent_name, sender, message)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, agent_name, sender, message),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def delete_coach_conversation(user_id, agent_name=None):
    """Delete one user's coach messages, optionally scoped to one coach."""
    if agent_name is None:
        query = "DELETE FROM agent_messages WHERE user_id = ?"
        parameters = (user_id,)
    else:
        query = "DELETE FROM agent_messages WHERE user_id = ? AND agent_name = ?"
        parameters = (user_id, agent_name)

    connection = _connect()
    try:
        cursor = connection.execute(query, parameters)
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def upsert_user_memory(user_id, memory_key, memory_value, agent_name="shared"):
    """Store one user-scoped memory without creating duplicate keys."""
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO user_memories (
                user_id, agent_name, memory_key, memory_value
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, agent_name, memory_key)
            DO UPDATE SET
                memory_value = excluded.memory_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, agent_name, memory_key, memory_value),
        )
        connection.commit()
    finally:
        connection.close()


def get_user_memories(user_id, agent_name):
    """Return shared and agent-specific memory for one user only."""
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT memory_key, memory_value
            FROM user_memories
            WHERE user_id = ? AND agent_name IN ('shared', ?)
            ORDER BY updated_at, id
            """,
            (user_id, agent_name),
        ).fetchall()
    finally:
        connection.close()

    return {row["memory_key"]: row["memory_value"] for row in rows}
