"""SQLite persistence helpers for RunCoach users."""

from __future__ import annotations

_connection_factory = None


def configure(connection_factory):
    """Configure the database connection factory used by user queries."""
    global _connection_factory
    _connection_factory = connection_factory


def _connect():
    if _connection_factory is None:
        raise RuntimeError("User store connection factory is not configured.")
    return _connection_factory()


def get_user(user_id):
    """Find one user by id."""
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row
    finally:
        connection.close()


def get_user_by_email(email):
    """Find one user by email address."""
    connection = _connect()
    try:
        return connection.execute(
            "SELECT * FROM users WHERE email = ?",
            ((email or "").lower().strip(),),
        ).fetchone()
    finally:
        connection.close()


def create_user(email, password_hash, **fields):
    """Create a user with a precomputed password hash."""
    allowed_fields = {
        "timezone",
        "language",
        "accessibility_mode",
    }
    values = {
        key: value
        for key, value in fields.items()
        if key in allowed_fields and value is not None
    }
    columns = ["email", "password_hash", *values.keys()]
    placeholders = ", ".join("?" for _column in columns)
    parameters = [(email or "").lower().strip(), password_hash, *values.values()]

    connection = _connect()
    try:
        cursor = connection.execute(
            f"""
            INSERT INTO users ({", ".join(columns)})
            VALUES ({placeholders})
            """,
            parameters,
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def update_user(user_id, **fields):
    """Update allowed user fields only for the requested user."""
    allowed_fields = {
        "email",
        "password_hash",
        "timezone",
        "language",
        "accessibility_mode",
    }
    updates = [
        (field, fields[field])
        for field in fields
        if field in allowed_fields and fields[field] is not None
    ]
    if not updates:
        return False

    set_clause = ", ".join(f"{field} = ?" for field, _value in updates)
    parameters = [value for _field, value in updates]
    parameters.append(user_id)

    connection = _connect()
    try:
        cursor = connection.execute(
            f"""
            UPDATE users
            SET {set_clause}
            WHERE id = ?
            """,
            parameters,
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def delete_user(user_id):
    """Delete one user row by id."""
    connection = _connect()
    try:
        cursor = connection.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()
