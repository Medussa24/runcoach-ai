# Personal Calendar and Weekly Workout Planner

## Overview

RunCoach AI now gives every authenticated user a private **My Plan** calendar.
The feature turns coaching guidance into an organized, actionable weekly
schedule instead of leaving users with only conversational recommendations.

Users can:

- Generate a personalized week of workouts.
- Review events in a seven-day calendar.
- Navigate to previous and future weeks.
- Add personal events such as races, appointments, group walks, or deadlines.
- Mark workouts and events complete.
- Download the visible week as an `.ics` calendar file.
- Optionally email the visible week to their account address.

The feature is available from the dashboard through **My Plan** and at:

```text
/planner
```

## Why This Was Added

Beginner runners often understand advice but still struggle to turn it into a
routine. A calendar answers the practical questions that chat alone cannot:

- What am I doing?
- On which day?
- At what time?
- How long will it take?
- How should I prepare?
- What should I do afterward?

The planner turns RunCoach AI from a reactive chat experience into a lightweight
personal movement concierge.

## Weekly Planner Agent

`WeeklyPlannerAgent` is a Gemini-first internal planning agent.

It receives only:

- The selected seven-day window.
- The user's preferred workout time.
- The user's stated weekly goal.
- A precomputed, user-scoped training summary.

It does not receive:

- A selectable `user_id`.
- Raw SQL access.
- SMTP credentials.
- API keys or hidden configuration.
- Another user's workouts or calendar.

Gemini returns three or four structured workout objects. Every workout must
contain:

| Field | Purpose |
| --- | --- |
| Date | Places the workout in the selected week |
| Start time | Makes the schedule actionable |
| Duration | Sets a clear time commitment |
| Coach | Identifies Rico, Iggy, or Luna |
| Hydration | Gives a before/after water reminder |
| Warm-up | Prepares the user for movement |
| Main workout | Provides the session instructions |
| Cool-down | Guides a gradual finish |
| Notes | Explains the purpose or adjustment |

Python validates the model response before database storage. Dates must fall
inside the selected week, duration must be reasonable, and all required workout
sections must be present.

## Scripted Fallback

The calendar does not depend on Gemini being available.

If Gemini:

- Is not configured.
- Times out.
- Returns no text.
- Returns malformed JSON.
- Omits required workout fields.
- Returns dates outside the selected week.

RunCoach AI automatically creates a complete three-session local plan:

1. Rico easy run-walk foundation.
2. Iggy nature reset walk.
3. Rico steady endurance session.

The fallback includes the same date, time, duration, hydration, warm-up,
workout, and cool-down structure as the Gemini plan. Users are never left with
an empty or partially generated week.

## Personal Events and Completion

Users can add non-workout events with:

- Title
- Date
- Start time
- Duration
- Details

Generated workouts and personal events share the calendar but remain distinct.
Regenerating a week replaces only agent-generated workouts for that user and
week. Personal events are preserved.

Completion updates use both the event ID and authenticated `user_id`, preventing
one account from changing another account's events.

## User Isolation and Security

Planner records are stored in the `planner_events` table. Every row contains a
required `user_id`.

All planner reads, updates, generation, completion, export, and email operations
filter by the logged-in user's session identity.

Additional protections:

- Flask-WTF CSRF protection covers every planner POST route.
- Gemini receives summarized data only.
- No Text-to-SQL capability exists.
- Model output is validated before storage.
- SMTP credentials are environment-only.
- Emails are never sent automatically.
- Wellness guidance remains general and non-medical.

## Email and Calendar Export

The `.ics` export is always available and requires no paid service.

Email is optional and user-triggered through **Email My Week**. The server must
be configured with:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM_EMAIL
SMTP_USE_TLS
```

If SMTP is missing or unavailable:

- The app does not crash.
- The calendar remains saved.
- The user receives a clear message.
- The `.ics` download remains available.

There is no automatic background email scheduler in this lightweight version.

## Routes

| Route | Method | Purpose |
| --- | --- | --- |
| `/planner` | GET | Display the selected calendar week |
| `/planner/generate` | POST | Generate and store a weekly workout plan |
| `/planner/event` | POST | Add a personal event |
| `/planner/event/<id>/toggle` | POST | Toggle completion for a user-owned event |
| `/planner/calendar.ics` | GET | Download the selected week |
| `/planner/email` | POST | Email the selected week when SMTP is configured |

## Files Added or Updated

- `planner_agent.py` — Gemini generation, response validation, and fallback.
- `notification_service.py` — SMTP delivery and `.ics` generation.
- `templates/planner.html` — Calendar and planner interface.
- `static/style.css` — Responsive calendar design.
- `app.py` — Database table, data access, routes, and user scoping.
- `sentinel_qa.py` — Planner route health verification.
- `tests/test_planner.py` — Planner, privacy, export, email, and fallback tests.

## Validation Evidence

The planner release passed:

- Python syntax checks.
- JavaScript syntax checks.
- **60 pytest tests**.
- User-separation tests.
- Completion ownership tests.
- Gemini structured-output validation.
- Scripted fallback validation.
- Week-regeneration preservation tests.
- `.ics` export tests.
- Configured and unconfigured SMTP tests.
- Live Cloud Run demo login and planner generation.
- Live Vertex AI plan generation.
- Live calendar export.
- Cloud Run error-log review.

Production revision verified during the release audit:

```text
runcoach-ai-00018-svv
```

Live application:

<https://runcoach-ai-212640849356.us-central1.run.app>

## Known Limitations

- Cloud Run currently uses instance-local SQLite storage. Calendar data can be
  lost when an instance is replaced or scaled. Production persistence should
  move to Cloud SQL or Firestore.
- SMTP must be configured by the deployment administrator.
- Email is manual rather than scheduled.
- Calendar times use the entered wall-clock time and do not yet store a
  per-user timezone.
- The planner provides general wellness guidance and is not medical advice.

These limitations are intentionally documented rather than hidden so reviewers
can distinguish the capstone-ready demo from a future production deployment.
