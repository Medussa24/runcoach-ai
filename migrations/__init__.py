"""Transactional, serialized schema upgrades for both supported databases."""

from database import is_postgres
from migrations import v001

MIGRATIONS = ((1, v001.upgrade),)


def migrate(connection):
    """Commit each pending schema version atomically under a migration lock."""
    try:
        if is_postgres(connection):
            connection.execute("SELECT pg_advisory_xact_lock(72630, 1)")
        else:
            connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()}
        known = {version for version, _ in MIGRATIONS}
        if applied - known:
            raise RuntimeError("Database schema is newer than this application release")
        for version, upgrade in MIGRATIONS:
            if version not in applied:
                upgrade(connection)
                connection.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
