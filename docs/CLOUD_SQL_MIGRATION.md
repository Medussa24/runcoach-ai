# Cloud SQL Migration Plan

RunCoach AI supports SQLite and PostgreSQL. The existing public capstone service
still uses SQLite; this release adds the database foundation without provisioning
paid infrastructure or moving user data. Cloud Run's local files remain ephemeral
and non-shared until the live service is explicitly switched to managed storage.

## Database foundation (September 11, 2026)

- `database.py` selects PostgreSQL for a `postgresql://` `DATABASE_URL`, or SQLite
  at `RUNCOACH_DATABASE` when no URL is configured. Configuration and connection
  errors never fall back to SQLite.
- `migrations/v001.py` contains the existing schema and legacy column upgrades.
  `schema_migrations` records applied versions. Transactional migration locks
  serialize startup across workers; failed upgrades roll back, and a database
  newer than the application is rejected. Add a new migration for future changes.
- PostgreSQL identity columns replace SQLite autoincrement during schema creation.
  Explicit `ON CONFLICT DO NOTHING`, `RETURNING id`, schema introspection, and
  per-user transaction locks preserve storage and message-rate-limit behavior.
- The same application test suite runs against both engines. New tests cover
  legacy data preservation, migration rollback, foreign keys, parameter binding,
  concurrent startup, and concurrent rate limiting.

## Configuration and migrations

Set `DATABASE_URL` through Secret Manager for a managed PostgreSQL deployment.
For local testing, use a disposable PostgreSQL database and local credentials.
The driver supports standard PostgreSQL URI options, including `sslmode` and
Cloud SQL Unix-socket host parameters. Never commit or print a credentialed URI.

Run `python -m migrations` with the same environment as the candidate service to
apply schema upgrades without demo seeding. Flask also applies pending migrations
at first-request initialization. Back up real data before any production upgrade.

This adapter opens and closes connections per operation; connection pooling and
database connection limits must be sized before a multi-instance production cutover.

## Migration gates

1. Introduce a database adapter selected by `DATABASE_URL`, while keeping
   SQLite as the zero-configuration local and test backend.
2. Move schema creation into versioned migrations and provide equivalent
   SQLite and PostgreSQL definitions for every table, index, foreign key, and
   uniqueness constraint.
3. Replace SQLite-only SQL (`PRAGMA`, `AUTOINCREMENT`, and `INSERT OR IGNORE`)
   with adapter-owned operations or portable conflict clauses.
4. Run the complete isolation, CSRF, planner, messaging, and Tier 1 suites
   against both backends.
5. Add a one-time export/import command with row-count and foreign-key
   verification. Never migrate the privacy-safe demo database as user data.
6. Define Cloud SQL, Secret Manager bindings, Cloud Run connectivity, backups,
   deletion protection, and least-privilege IAM in Terraform.
7. Deploy with zero traffic, run the public smoke flow against the candidate
   revision, then shift traffic only after the migration checks pass.

## Production defaults

- PostgreSQL 16 with automated backups and point-in-time recovery.
- A dedicated application database and least-privilege database user.
- Credentials stored in Secret Manager, never in source or workflow logs.
- Cloud Run runtime service account granted only Cloud SQL Client and required
  secret access.
- Connection pooling sized for Cloud Run instance and concurrency limits.
- Cloud SQL deletion protection enabled outside disposable test environments.

Gates 1–4 passed for this foundation release: 157 tests on each backend and a
successful PostgreSQL HTTP Tier 1 flow, alongside the existing live SQLite
baseline smoke check. Export/import tooling, managed infrastructure,
pool sizing, backup recovery tests, and the live data cutover remain separate
work. Do not treat a successful schema migration as a completed data migration.
