# Production Readiness

RunCoach AI is submission-ready as a public Cloud Run demonstration. This document separates what is already production-shaped from infrastructure that must be deliberately provisioned before long-term multi-user use.

## Ready now

- Authenticated and CSRF-protected Flask routes.
- `user_id` scoping for runs, imports, memory, chat, recovery, walking, and planner events.
- Gemini/Vertex AI with deterministic local fallbacks.
- Tool-calling functions that capture the authenticated user on the server; no raw Text-to-SQL agent.
- Calendar export, optional SMTP delivery, health checks, defensive tests, and agent contract evaluations.
- Configurable SQLite location through `RUNCOACH_DATABASE`.

## Durable database gate

Cloud Run container filesystems are ephemeral and different instances do not share a local SQLite database. The current SQLite configuration is appropriate for the capstone/demo, but it is not a durable multi-instance production database.

Before real user onboarding, choose one:

1. Migrate the parameterized repository functions to Cloud SQL for PostgreSQL.
2. Migrate suitable records to Firestore.
3. For a controlled single-instance demonstration only, mount supported persistent storage and point `RUNCOACH_DATABASE` to that mounted path.

Do not claim durable production persistence until a migration is provisioned, tested, backed up, and load-verified.

## Email delivery gate

Email is intentionally disabled unless these environment variables are configured:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

Users can always download a timezone-aware `.ics` file. The application does not automatically send background email, which avoids surprise messaging and keeps the demo lightweight.

## Timezones

Each user can select a supported calendar timezone. Event dates and times remain user-entered local wall times, while calendar exports label them with that timezone. The `tzdata` dependency keeps timezone lookup portable across Windows, containers, and Linux hosts.

## Evaluation gate

Run:

```bash
python agent_eval.py
python -m pytest -q
```

The contract evaluation validates deterministic fallback behavior and planner structure. Before a high-stakes production release, add a larger anonymized evaluation dataset and periodic human review of live Gemini responses.
