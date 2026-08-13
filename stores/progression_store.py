"""User-scoped append-only progression ledger."""

_connection_factory = None


def configure(connection_factory):
    global _connection_factory
    _connection_factory = connection_factory


def award(user_id, source_type, source_id, reason, xp, rule_version):
    connection = _connection_factory()
    try:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO progression_events
               (user_id, source_type, source_id, reason, xp, rule_version)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, source_type, str(source_id), reason, int(xp), rule_version),
        )
        connection.commit()
        return cursor.rowcount == 1
    finally:
        connection.close()


def list_events(user_id, limit=100):
    connection = _connection_factory()
    try:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM progression_events WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(int(limit), 500))),
        ).fetchall()]
    finally:
        connection.close()


def summary(user_id):
    events = list_events(user_id, 500)
    total = sum(int(event["xp"]) for event in events)
    level = total // 500 + 1
    return {"total_xp": total, "level": level, "level_xp": total % 500, "next_level_xp": 500, "events": events}
