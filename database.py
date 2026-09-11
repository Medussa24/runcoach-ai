"""Small database boundary shared by the application and schema migrations.

Stores use bound qmark parameters on both backends. SQL dialect differences
belong in explicit helpers here; arbitrary application SQL is not rewritten.
"""

from collections.abc import Mapping
from datetime import date, datetime
import re
import sqlite3

import psycopg


INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)


class Row(Mapping):
    """Preserve named and positional access, including SQLite timestamp text."""

    def __init__(self, names, values):
        self._names = names
        self._values = tuple(
            value.isoformat(sep=" ") if isinstance(value, datetime)
            else value.isoformat() if isinstance(value, date) else value
            for value in values
        )
        self._lookup = dict(zip(names, self._values))

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, (int, slice)) else self._lookup[key]

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)


def _row_factory(cursor):
    names = tuple(column.name for column in cursor.description or ())
    return lambda values: Row(names, values)


def postgres_parameters(query):
    """Translate qmarks outside SQL strings/comments; escape literal percent signs.

    Dollar-quoted SQL is deliberately unsupported in store statements. Migration
    SQL without parameters is sent unchanged to the driver.
    """
    tokens = re.split(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*[\s\S]*?\*/)", query)
    return "".join(
        token.replace("%", "%%") if i % 2
        else token.replace("%", "%%").replace("?", "%s")
        for i, token in enumerate(tokens)
    )


class PostgresConnection:
    dialect = "postgresql"

    def __init__(self, url):
        self.raw = psycopg.connect(url, row_factory=_row_factory, connect_timeout=10)

    def execute(self, query, parameters=None):
        if parameters is None:
            return self.raw.execute(query)
        return self.raw.execute(postgres_parameters(query), parameters)

    def executemany(self, query, parameters):
        cursor = self.raw.cursor()
        cursor.executemany(postgres_parameters(query), parameters)
        return cursor

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def connect(sqlite_path, database_url=None):
    """Use PostgreSQL only when explicitly configured; never silently fall back."""
    if database_url:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must use postgresql:// or postgres://")
        return PostgresConnection(database_url)
    connection = sqlite3.connect(sqlite_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def is_postgres(connection):
    return isinstance(connection, PostgresConnection)


def insert_id(connection, query, parameters):
    """Return the inserted id, or None when an authorized INSERT inserts no row."""
    row = connection.execute(query.rstrip().rstrip(";") + " RETURNING id", parameters).fetchone()
    return row[0] if row else None


def table_columns(connection, table):
    if is_postgres(connection):
        return {row[0] for row in connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?", (table,)
        ).fetchall()}
    if not re.fullmatch(r"[a-z_]+", table):
        raise ValueError("Invalid schema table name")
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def schema_objects(connection, kind="table"):
    if kind not in {"table", "index"}:
        raise ValueError("Expected table or index")
    if is_postgres(connection):
        query = ("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
                 if kind == "table" else
                 "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
        return {row[0] for row in connection.execute(query).fetchall()}
    return {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
    ).fetchall()}


def lock_message_attempts(connection, user_id):
    """Serialize each user's rate-limit check and insert in one transaction."""
    if is_postgres(connection):
        connection.execute("SELECT pg_advisory_xact_lock(72631, ?)", (int(user_id),))
    else:
        connection.execute("BEGIN IMMEDIATE")
