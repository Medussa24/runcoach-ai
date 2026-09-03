# Cloud SQL Migration Plan

RunCoach AI currently uses SQLite. This is appropriate for the public capstone
demo, but Cloud Run instances have ephemeral, non-shared filesystems. Durable
multi-instance operation requires a tested PostgreSQL storage path before any
Cloud SQL resource is provisioned.

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

Provisioning is intentionally blocked until gates 1–4 pass. This prevents a
paid but unusable database from becoming production state.
