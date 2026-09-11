"""User-scoped database persistence for private community messages."""

from __future__ import annotations

from database import insert_id, lock_message_attempts

_connection_factory = None


def configure(connection_factory):
    """Configure the database connection factory used by message queries."""
    global _connection_factory
    _connection_factory = connection_factory


def _connect():
    if _connection_factory is None:
        raise RuntimeError("Community message store connection factory is not configured.")
    return _connection_factory()


def create_conversation(user_id, other_user_id):
    """Create or return a one-to-one conversation for two existing users.

    This ID-based primitive intentionally performs no email lookup. A future HTTP
    endpoint must apply rate limiting and return the same neutral response whether
    or not an email maps to a user.
    """
    user_id = int(user_id)
    other_user_id = int(other_user_id)
    if user_id == other_user_id:
        return None
    user_low_id, user_high_id = sorted((user_id, other_user_id))

    connection = _connect()
    try:
        existing_users = connection.execute(
            "SELECT COUNT(*) FROM users WHERE id IN (?, ?)",
            (user_low_id, user_high_id),
        ).fetchone()[0]
        if existing_users != 2:
            return None

        connection.execute(
            """
            INSERT INTO message_conversations (user_low_id, user_high_id)
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            (user_low_id, user_high_id),
        )
        conversation = connection.execute(
            """
            SELECT id FROM message_conversations
            WHERE user_low_id = ? AND user_high_id = ?
            """,
            (user_low_id, user_high_id),
        ).fetchone()
        if not conversation:
            return None

        conversation_id = conversation["id"]
        connection.executemany(
            """
            INSERT INTO message_participants (conversation_id, user_id)
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            ((conversation_id, user_low_id), (conversation_id, user_high_id)),
        )
        connection.commit()
        return conversation_id
    finally:
        connection.close()


def get_conversation(user_id, conversation_id):
    """Return a conversation only when the requesting user participates in it."""
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT c.id, c.user_low_id, c.user_high_id, c.created_at,
                   p.last_read_message_id
            FROM message_conversations AS c
            JOIN message_participants AS p ON p.conversation_id = c.id
            WHERE c.id = ? AND p.user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def list_conversations(user_id):
    """List only conversations in which the requesting user participates."""
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT c.id, c.user_low_id, c.user_high_id, c.created_at,
                   p.last_read_message_id,
                   MAX(m.id) AS latest_message_id,
                   SUM(CASE WHEN m.id > COALESCE(p.last_read_message_id, 0)
                            AND m.sender_id != ? THEN 1 ELSE 0 END) AS unread_count
            FROM message_conversations AS c
            JOIN message_participants AS p ON p.conversation_id = c.id
            LEFT JOIN community_messages AS m ON m.conversation_id = c.id
            WHERE p.user_id = ?
            GROUP BY c.id, p.last_read_message_id
            ORDER BY COALESCE(MAX(m.id), 0) DESC, c.id DESC
            """,
            (user_id, user_id),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_messages(user_id, conversation_id, limit=100):
    """Return messages only for an authorized participant."""
    limit = max(1, min(int(limit), 200))
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT m.id, m.conversation_id, m.sender_id, m.body, m.created_at
            FROM community_messages AS m
            JOIN message_participants AS p
              ON p.conversation_id = m.conversation_id
            WHERE m.conversation_id = ? AND p.user_id = ?
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (conversation_id, user_id, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        connection.close()


def send_message(user_id, conversation_id, body):
    """Send as the authenticated participant, unless either participant blocked."""
    body = (body or "").strip()
    if not body or len(body) > 2000:
        return None

    connection = _connect()
    try:
        new_id = insert_id(connection,
            """
            INSERT INTO community_messages (conversation_id, sender_id, body)
            SELECT c.id, ?, ?
            FROM message_conversations AS c
            JOIN message_participants AS sender
              ON sender.conversation_id = c.id AND sender.user_id = ?
            WHERE c.id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM user_blocks AS b
                  WHERE (b.blocker_id = ? AND b.blocked_id IN (c.user_low_id, c.user_high_id))
                     OR (b.blocked_id = ? AND b.blocker_id IN (c.user_low_id, c.user_high_id))
              )
            """,
            (user_id, body, user_id, conversation_id, user_id, user_id),
        )
        connection.commit()
        return new_id
    finally:
        connection.close()


def mark_conversation_read(user_id, conversation_id):
    """Advance only the requesting participant's read marker."""
    connection = _connect()
    try:
        cursor = connection.execute(
            """
            UPDATE message_participants
            SET last_read_message_id = (
                SELECT MAX(id) FROM community_messages WHERE conversation_id = ?
            )
            WHERE conversation_id = ? AND user_id = ?
            """,
            (conversation_id, conversation_id, user_id),
        )
        connection.commit()
        return cursor.rowcount == 1
    finally:
        connection.close()


def block_conversation_participant(user_id, conversation_id):
    """Block the other participant, derived from an authorized conversation."""
    connection = _connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO user_blocks (blocker_id, blocked_id)
            SELECT ?, CASE WHEN c.user_low_id = ? THEN c.user_high_id ELSE c.user_low_id END
            FROM message_conversations AS c
            JOIN message_participants AS p
              ON p.conversation_id = c.id AND p.user_id = ?
            WHERE c.id = ?
            ON CONFLICT DO NOTHING
            """,
            (user_id, user_id, user_id, conversation_id),
        )
        connection.commit()
        return cursor.rowcount == 1
    finally:
        connection.close()


def report_message(user_id, message_id, reason):
    """Report a message only when it is visible to the requesting participant."""
    reason = (reason or "").strip().lower()
    if reason not in {"harassment", "spam", "unsafe", "other"}:
        return None

    connection = _connect()
    try:
        new_id = insert_id(connection,
            """
            INSERT INTO message_reports (message_id, reporter_id, reason)
            SELECT m.id, ?, ?
            FROM community_messages AS m
            JOIN message_participants AS p
              ON p.conversation_id = m.conversation_id AND p.user_id = ?
            WHERE m.id = ?
            ON CONFLICT DO NOTHING
            """,
            (user_id, reason, user_id, message_id),
        )
        connection.commit()
        return new_id
    finally:
        connection.close()


def allow_start_attempt(user_id, attempted_at, limit=5, window_seconds=600):
    """Atomically rate-limit discovery without storing the submitted address."""
    attempted_at = float(attempted_at)
    cutoff = attempted_at - int(window_seconds)
    connection = _connect()
    try:
        lock_message_attempts(connection, user_id)
        connection.execute(
            "DELETE FROM message_start_attempts WHERE attempted_at <= ?",
            (cutoff,),
        )
        attempts = connection.execute(
            """
            SELECT COUNT(*) FROM message_start_attempts
            WHERE user_id = ? AND attempted_at > ?
            """,
            (user_id, cutoff),
        ).fetchone()[0]
        if attempts >= int(limit):
            connection.commit()
            return False
        connection.execute(
            """
            INSERT INTO message_start_attempts (user_id, attempted_at)
            VALUES (?, ?)
            """,
            (user_id, attempted_at),
        )
        connection.commit()
        return True
    finally:
        connection.close()
