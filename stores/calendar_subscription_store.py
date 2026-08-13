"""Revocable, hashed calendar feed credentials."""

import hashlib
import secrets

_connection_factory = None


def configure(connection_factory):
    global _connection_factory
    _connection_factory = connection_factory


def issue(user_id):
    token = secrets.token_urlsafe(32)
    digest = _hash(token)
    connection = _connection_factory()
    try:
        connection.execute("UPDATE calendar_subscriptions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL", (user_id,))
        connection.execute("INSERT INTO calendar_subscriptions (user_id, token_hash) VALUES (?, ?)", (user_id, digest))
        connection.commit()
        return token
    finally:
        connection.close()


def resolve(token):
    connection = _connection_factory()
    try:
        row = connection.execute("SELECT * FROM calendar_subscriptions WHERE token_hash = ? AND revoked_at IS NULL", (_hash(token),)).fetchone()
        if row:
            connection.execute("UPDATE calendar_subscriptions SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
            connection.commit()
        return dict(row) if row else None
    finally:
        connection.close()


def revoke(user_id):
    connection = _connection_factory()
    try:
        cursor = connection.execute("UPDATE calendar_subscriptions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL", (user_id,))
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def has_active(user_id):
    connection = _connection_factory()
    try:
        return connection.execute("SELECT 1 FROM calendar_subscriptions WHERE user_id = ? AND revoked_at IS NULL", (user_id,)).fetchone() is not None
    finally:
        connection.close()


def _hash(token):
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()
