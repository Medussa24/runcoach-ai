"""Private, workout-linked reflection persistence."""

from database import insert_id

_connection_factory = None


def configure(connection_factory):
    global _connection_factory
    _connection_factory = connection_factory


def create(user_id, stage, message, rico_response, planner_event_id=None, run_id=None):
    if stage not in {"pre_run", "post_run"}:
        raise ValueError("Invalid reflection stage.")
    message = (message or "").strip()
    if not message:
        raise ValueError("Write a short reflection first.")
    connection = _connection_factory()
    try:
        new_id = insert_id(connection,
            """INSERT INTO workout_reflections
               (user_id, planner_event_id, run_id, stage, message, rico_response)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, planner_event_id, run_id, stage, message[:2000], (rico_response or "")[:2000]),
        )
        connection.commit()
        return new_id
    finally:
        connection.close()


def list_for_user(user_id, limit=20):
    connection = _connection_factory()
    try:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM workout_reflections WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(int(limit), 100))),
        ).fetchall()]
    finally:
        connection.close()
