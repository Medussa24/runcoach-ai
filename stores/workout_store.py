"""SQLite persistence helpers for user-scoped workouts."""

from __future__ import annotations

_connection_factory = None


def configure(connection_factory):
    """Configure the database connection factory used by workout queries."""
    global _connection_factory
    _connection_factory = connection_factory


def _connect():
    if _connection_factory is None:
        raise RuntimeError("Workout store connection factory is not configured.")
    return _connection_factory()


def get_previous_run(user_id):
    """Return the most recent run before a new run is saved."""
    connection = _connect()
    try:
        return connection.execute(
            """
            SELECT * FROM runs
            WHERE user_id = ?
            ORDER BY run_date DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        connection.close()


def get_all_runs(user_id):
    """Return all saved runs for one user, newest first."""
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT * FROM runs
            WHERE user_id = ?
            ORDER BY run_date DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_recent_workouts(user_id, target_date=None, limit=10):
    """Return recent workouts for one user, optionally ending on a target date."""
    safe_limit = max(1, min(int(limit), 50))
    parameters = [user_id]
    date_filter = ""
    if target_date is not None:
        date_filter = "AND date(run_date) <= date(?)"
        parameters.append(target_date.isoformat())
    parameters.append(safe_limit)

    connection = _connect()
    try:
        rows = connection.execute(
            f"""
            SELECT * FROM runs
            WHERE user_id = ?
            {date_filter}
            ORDER BY run_date DESC, id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_workout(user_id, workout_id):
    """Return one workout only when it belongs to the requested user."""
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT * FROM runs
            WHERE id = ? AND user_id = ?
            """,
            (workout_id, user_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def insert_manual_workout(user_id, run, pace, feedback):
    """Insert one manually logged workout for the requested user."""
    connection = _connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO runs (
                run_date, distance, duration, pace, mood, notes, feedback,
                weather_summary, temperature_f, wind_mph, route_type,
                route_notes, avg_heart_rate, steps, cadence, source,
                workout_type, imported_from, user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["run_date"],
                run["distance"],
                run["duration"],
                pace,
                run["mood"],
                run["notes"],
                feedback,
                run["weather_summary"],
                run["temperature_f"],
                run["wind_mph"],
                run["route_type"],
                run["route_notes"],
                run["avg_heart_rate"],
                run["steps"],
                run["cadence"],
                "Manual",
                "Running",
                None,
                user_id,
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def update_workout(user_id, workout_id, fields):
    """Update allowed workout columns only when the row belongs to the user."""
    allowed_columns = {
        "run_date",
        "distance",
        "duration",
        "pace",
        "mood",
        "notes",
        "feedback",
        "weather_summary",
        "temperature_f",
        "wind_mph",
        "route_type",
        "route_notes",
        "avg_heart_rate",
        "max_heart_rate",
        "calories",
        "steps",
        "cadence",
        "source",
        "workout_type",
        "imported_from",
        "end_date",
        "device",
    }
    updates = [
        (column, fields[column])
        for column in fields
        if column in allowed_columns
    ]
    if not updates:
        return False

    set_clause = ", ".join(f"{column} = ?" for column, _value in updates)
    parameters = [value for _column, value in updates]
    parameters.extend([workout_id, user_id])

    connection = _connect()
    try:
        cursor = connection.execute(
            f"""
            UPDATE runs
            SET {set_clause}
            WHERE id = ? AND user_id = ?
            """,
            parameters,
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def delete_workout(user_id, workout_id):
    """Delete one workout only when it belongs to the requested user."""
    connection = _connect()
    try:
        cursor = connection.execute(
            """
            DELETE FROM runs
            WHERE id = ? AND user_id = ?
            """,
            (workout_id, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()
