"""Run the same application tests on isolated SQLite files or PostgreSQL schemas."""

import os
import uuid
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import app as runcoach


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    # Never let an ambient production DATABASE_URL redirect the normal test suite.
    monkeypatch.setattr(runcoach, "DATABASE_URL", None)
    url = os.environ.get("RUNCOACH_TEST_POSTGRES_URL")
    if not url:
        yield
        return
    # Only a specifically named disposable test database can receive test schemas.
    from psycopg.conninfo import conninfo_to_dict
    if conninfo_to_dict(url).get("dbname") != "runcoach_test":
        pytest.fail("RUNCOACH_TEST_POSTGRES_URL must name the disposable runcoach_test database")
    schema = "test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        # URL options are escaped by the driver, not concatenated into SQL.
        scoped_url = make_conninfo(url, options=f"-c search_path={schema}")
        from database import PostgresConnection
        # PostgresConnection accepts a driver conninfo internally; public config
        # still validates DATABASE_URL as a PostgreSQL URI.
        monkeypatch.setattr(runcoach, "DATABASE_URL", "postgresql://test-schema")
        monkeypatch.setattr(runcoach, "connect", lambda path, database_url=None: PostgresConnection(scoped_url))
        try:
            yield
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
