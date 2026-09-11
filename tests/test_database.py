"""Storage behavior and migration safety, exercised against both database engines."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest
import app as runcoach
import database
import migrations
from stores import community_message_store


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "storage.db")
    connection = runcoach.get_database_connection()
    try:
        yield connection
    finally:
        connection.close()


def test_migration_preserves_legacy_rows_and_is_idempotent(storage):
    storage.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)")
    storage.execute("INSERT INTO users (id, email, password_hash) VALUES (41, 'legacy@example.test', 'existing-hash')")
    storage.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, run_date TEXT NOT NULL, distance REAL NOT NULL, duration REAL NOT NULL, pace REAL NOT NULL, mood TEXT NOT NULL, notes TEXT, feedback TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    storage.execute("INSERT INTO runs (id, run_date, distance, duration, pace, mood, feedback) VALUES (23, '2026-09-01', 2, 20, 10, 'good', 'original')")
    storage.commit()
    migrations.migrate(storage)
    migrations.migrate(storage)
    user = storage.execute("SELECT * FROM users WHERE id = 41").fetchone()
    assert user["password_hash"] == "existing-hash"
    assert user["language"] == "en"
    assert storage.execute("SELECT feedback FROM runs WHERE id = 23").fetchone()[0] == "original"
    assert "workout_type" in database.table_columns(storage, "runs")
    assert [row[0] for row in storage.execute("SELECT version FROM schema_migrations").fetchall()] == [1]


def test_failed_migration_rolls_back_schema_and_version(storage, monkeypatch):
    migrations.migrate(storage)

    def failing_upgrade(connection):
        connection.execute("CREATE TABLE should_rollback (id INTEGER PRIMARY KEY)")
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS + ((2, failing_upgrade),))
    with pytest.raises(RuntimeError, match="simulated"):
        migrations.migrate(storage)
    assert "should_rollback" not in database.schema_objects(storage)
    assert [row[0] for row in storage.execute("SELECT version FROM schema_migrations").fetchall()] == [1]


def test_newer_schema_fails_closed(storage):
    migrations.migrate(storage)
    storage.execute("INSERT INTO schema_migrations (version) VALUES (999)")
    storage.commit()
    with pytest.raises(RuntimeError, match="newer"):
        migrations.migrate(storage)


def test_parameter_values_and_sql_literals_remain_distinct(storage):
    value = "What? 100% 'quoted'; DROP TABLE users; --"
    row = storage.execute("SELECT ? AS bound_value, 'Why? 100%' AS literal_value -- ignored ?\n", (value,)).fetchone()
    assert row[0] == value
    assert row["literal_value"] == "Why? 100%"
    assert dict(row)["bound_value"] == value


def test_insert_id_constraints_and_rollback(storage):
    migrations.migrate(storage)
    first = database.insert_id(storage, "INSERT INTO users (email, password_hash) VALUES (?, ?)", ("first@example.test", "hash"))
    second = database.insert_id(storage, "INSERT INTO users (email, password_hash) VALUES (?, ?)", ("second@example.test", "hash"))
    assert second > first
    storage.commit()
    ignored = database.insert_id(storage, "INSERT INTO users (email, password_hash) VALUES (?, ?) ON CONFLICT DO NOTHING", ("first@example.test", "hash"))
    assert ignored is None
    storage.commit()
    with pytest.raises(database.INTEGRITY_ERRORS):
        storage.execute("INSERT INTO community_messages (conversation_id, sender_id, body) VALUES (?, ?, ?)", (999999, first, "unrelated"))
    storage.rollback()
    assert storage.execute("SELECT COUNT(*) FROM community_messages").fetchone()[0] == 0


def test_rate_limit_remains_atomic_under_concurrent_requests(storage):
    migrations.migrate(storage)
    user_id = database.insert_id(storage, "INSERT INTO users (email, password_hash) VALUES (?, ?)", ("rate@example.test", "hash"))
    storage.commit()
    with ThreadPoolExecutor(max_workers=8) as executor:
        allowed = list(executor.map(lambda _: community_message_store.allow_start_attempt(user_id, 1000, limit=5), range(12)))
    assert sum(allowed) == 5
    assert community_message_store.allow_start_attempt(user_id, 1701, limit=5)


def test_invalid_database_url_does_not_create_sqlite_file(tmp_path):
    path = tmp_path / "must-not-exist.db"
    with pytest.raises(ValueError, match="DATABASE_URL"):
        database.connect(path, "mysql://unsupported")
    assert not path.exists()


def test_concurrent_startup_applies_migration_once(storage):
    def startup(_):
        connection = runcoach.get_database_connection()
        try:
            migrations.migrate(connection)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(startup, range(4)))
    assert [row[0] for row in storage.execute("SELECT version FROM schema_migrations").fetchall()] == [1]


def test_explicit_sqlite_connection_enforces_foreign_keys(tmp_path):
    connection = database.connect(tmp_path / "sqlite.db")
    try:
        assert isinstance(connection, sqlite3.Connection)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()
