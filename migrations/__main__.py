"""Apply migrations without starting the web server or seeding demo data."""

import os
from pathlib import Path

from database import connect, is_postgres
from migrations import migrate


def main():
    default_path = Path(__file__).resolve().parents[1] / "runs.db"
    connection = connect(os.environ.get("RUNCOACH_DATABASE", default_path), os.environ.get("DATABASE_URL"))
    try:
        migrate(connection)
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        backend = "postgresql" if is_postgres(connection) else "sqlite"
        print(f"Migrations applied: backend={backend}, versions={versions}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
