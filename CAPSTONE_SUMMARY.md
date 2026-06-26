# RunCoach AI Capstone Summary

## Project Title

RunCoach AI

## Track

Concierge Agents

## Problem

Many beginner runners track workouts but do not know how to interpret pace, distance, mood, notes, and progress. They may also miss important context such as weather, route difficulty, or wearable-style effort data.

## Solution

RunCoach AI is a web-based movement coach agent app. It lets users create an account, log runs, import historical Apple Health `export.xml` or workout CSV data, calculate pace, store history, review progress, and get safe next-workout guidance. Gemini 2.5 Flash powers all six agents through Vertex AI in production or an API key locally, while established scripted fallbacks keep coaching, planning, analysis, and health reporting reliable offline.

Live capstone demo: <https://runcoach-ai-212640849356.us-central1.run.app>

## Project Layers

1. User identity: signup, login, logout, hashed passwords, Flask sessions.
2. Core run logging: date, distance, duration, mood, notes.
3. Training metrics: pace, distance changes, recent-run comparison, pace trends.
4. RunCoach agents: Rico Runner chat, Iggy beginner-walk chat, Luna Recovery reminder cards, Data Analyst summaries, Sentinel QA health checks, Weekly Planner calendars, and the `/agent` endpoint.
5. Context layer: weather, route/map notes, wearable-style data.
6. Capstone documentation: README, architecture, test plan, deployment notes, screenshot checklist.

## Agent Workflow

1. User signs up, logs in, or clicks Try Demo for privacy-safe fake workout data.
2. Flask stores the user's `user_id` in the session.
3. User logs a run.
4. Flask calculates pace and saves the run in SQLite with that `user_id`.
5. User may also import old Apple Health or Apple Watch workout history from `export.xml` or CSV.
6. Optional context is saved with each run: weather, route type, route notes, average heart rate, max heart rate, calories, steps, cadence.
7. RunCoach Agent reads only the logged-in user's saved runs, imported history, and context data.
8. User asks Rico or Iggy a coaching question through the chat box or `/agent`.
9. Rico summarizes progress, compares recent runs, mentions pace trends, considers context, and suggests a safe next workout.
10. Iggy creates an easy walking routine, checklist guidance, breathing task, stretch, or nature-count prompt.
11. Luna reads the same logged-in user's workout context and displays passive hydration, recovery, stretching, breathing, gratitude, and bad-day reset reminders.
12. Backend-only Sentinel QA runs a lightweight, request-driven check at most once every 15 minutes during app activity. It verifies authentication boundaries, controlled SQL-injection rejection, CSRF enforcement, routes, Try Demo, agents, history, imports, and chat contracts, then reports only to server logs. Deeper penetration tests remain isolated in pytest/CI.
13. Try Demo creates a real CSRF-protected, authenticated session for the privacy-safe demo user; Sentinel is scheduled only after safe responses so it cannot disturb authentication.
14. Gemini receives only bounded data selected after the logged-in `user_id` filter through approved Python tools. Cloud Run uses Vertex AI with its service account, local development may use an AI Studio key, and missing credentials or provider errors activate the local fallback.
15. Mood signals for stress, sadness, burnout, or frustration trigger gentle, persona-specific support without medical advice.
16. Data Analyst produces user-scoped chart JSON for responsive distance, pace, weekly mileage, mood, walking, and recovery visuals; full run details remain available in a disclosure.
17. Server-side validation rejects malformed or unsafe manual run values before pace calculation and persistence, returning a clear form message instead of an application error.
18. All six agents are Gemini-capable and retain scripted fallbacks. Data Analyst gives Gemini only its calculated summary, while Sentinel gives Gemini only a completed deterministic report; neither model can change metrics or security verdicts.
19. Weekly Planner builds a private seven-day calendar from the user's structured training summary, validates every generated workout, and substitutes a complete scripted plan when Gemini is unavailable.
20. Users can add personal dated events, mark items complete, download `.ics` calendar files, and optionally email the visible week through environment-configured SMTP.

## Architecture

```text
Browser run form + Rico/Iggy agent chats + Luna reminder cards
-> Flask routes in app.py
-> Flask session user_id
-> SQLite runs.db
-> RicoRunnerAgent, IggyWalkAgent, and LunaRecoveryAgent in runcoach_agent.py
-> user-scoped Python tools (no Text-to-SQL and no model-selected user_id)
-> GeminiService -> Gemini 2.5 Flash when GEMINI_API_KEY is configured
-> deterministic coach fallback when Gemini is unavailable
-> DataAnalystAgent summaries + hidden SentinelQA periodic local quality checks
-> WeeklyPlannerAgent -> validated planner_events calendar rows
-> optional SMTP email + local .ics calendar export
-> HTML response or JSON /agent response
```

## Tools Used

- Python
- Flask
- SQLite
- HTML/CSS
- Werkzeug password hashing
- Gunicorn
- Google GenAI SDK / Gemini 2.5 Flash
- Google Cloud Run

## How To Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## How To Deploy

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud run deploy runcoach-ai --source . --region us-central1 --allow-unauthenticated
```

The June 25, 2026 audited release passed Python and JavaScript syntax checks, 52 pytest tests, authenticated demo transactions, live coach requests, browser asset checks, and a Cloud Run error-log review.

## Screenshots To Capture

- Homepage with the run logging form.
- Signup or login page with the Try Demo button and demo privacy note.
- Context fields for weather, route, and wearable-style data.
- Import Workouts page with Apple Health XML and CSV upload.
- Saved run with calculated pace.
- Previous runs list.
- Agent answer to `Summarize my progress`.
- Agent answer to `What should my next workout be?`.
- Iggy walking checklist and answer to `Create my beginner walking routine`.
- Luna Recovery cards with hydration, recovery, gratitude, and wellness disclaimer.
- Expanded Coach Library flash-card categories.
- `/agent` JSON response.
- Cloud Run public URL.

## Why It Fits Concierge Agents

RunCoach AI acts like a personal training concierge. It watches the user's logged training history, interprets the data in plain language, and gives safe, simple next steps. All six agents are Gemini-capable and use local fallbacks when Gemini is unavailable. It does not replace a coach, doctor, or therapist; it helps a beginner runner make better everyday training decisions.

## User Identity And Privacy

RunCoach AI stores users in a SQLite `users` table with `email`, `password_hash`, and `created_at`. Passwords are hashed with Werkzeug. Runs and imported workouts include `user_id`, and the dashboard, importer, Previous Runs list, and RunCoach Agent filter by the logged-in user's `user_id`.

Evaluators can click **Try Demo** to log in as `demo@runcoach.test` without creating an account. Demo mode uses fake seeded workout data for privacy-safe testing and does not remove authentication or user-level data separation.

Health and workout data is sensitive, so the app keeps imports local, ignores real Apple Health export files in Git, and provides a fake `sample_health_export.xml` for demos.

Wellness guidance is general and not medical advice. The app does not diagnose, treat, or provide therapy. If a user expresses crisis, self-harm, or immediate danger, the support language should encourage them to contact emergency help or a crisis hotline right away.

## Future Integration Notes

Real Apple Watch or Apple HealthKit sync should be added later through a native Apple-platform app. Google login, Apple login, and OAuth are also future upgrades. For this capstone, local accounts, Apple Health `export.xml` import, CSV import, and wearable-style fields keep the agent workflow stable and easy to explain.

## Final Judge-Facing Polish

The final pass reduces dashboard decision overload by highlighting the six primary actions and the user's next planned activity. The personal planner now respects a user-selected timezone in its weekly view, email copy, and `.ics` calendar export. Planner persistence was extracted from the Flask route module into `planner_store.py`, and a reproducible agent contract dataset was added for Rico, Iggy, Luna, Data Analyst, and Weekly Planner fallback behavior.

The deployed application remains a demonstration architecture: Gemini/Vertex AI is real, authentication and `user_id` separation are real, and fallbacks are fully functional. Durable multi-instance persistence and production email delivery require separately provisioned infrastructure and credentials; those are documented rather than hidden behind demo claims.
