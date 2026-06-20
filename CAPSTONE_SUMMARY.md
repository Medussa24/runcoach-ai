# RunCoach AI Capstone Summary

## Project Title

RunCoach AI

## Track

Concierge Agents

## Problem

Many beginner runners track workouts but do not know how to interpret pace, distance, mood, notes, and progress. They may also miss important context such as weather, route difficulty, or wearable-style effort data.

## Solution

RunCoach AI is a web-based movement coach agent app. It lets users create an account, log runs, import historical Apple Health `export.xml` or workout CSV data, calculate pace, store history, review progress, and get safe next-workout guidance. Rico Runner coaches running progress, Iggy the iguana helps new runners start with walking routines, and Luna Recovery is a passive Puerto Rican rooster support layer for hydration, stretching, rest, breathing, gratitude, and gentle recovery reminders. The app includes optional context fields for weather, route/map context, and wearable-style data such as heart rate, cadence, and steps.

## Project Layers

1. User identity: signup, login, logout, hashed passwords, Flask sessions.
2. Core run logging: date, distance, duration, mood, notes.
3. Training metrics: pace, distance changes, recent-run comparison, pace trends.
4. RunCoach agents: Rico Runner chat, Iggy beginner-walk chat, Luna Recovery reminder cards, and `/agent` endpoint.
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

## Architecture

```text
Browser run form + Rico/Iggy agent chats + Luna reminder cards
-> Flask routes in app.py
-> Flask session user_id
-> SQLite runs.db
-> RunCoachAgent, IggyWalkAgent, and LunaRecoveryAgent in runcoach_agent.py
-> HTML response or JSON /agent response
```

## Tools Used

- Python
- Flask
- SQLite
- HTML/CSS
- Werkzeug password hashing
- Gunicorn
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

RunCoach AI acts like a personal training concierge. It watches the user's logged training history, interprets the data in plain language, and gives safe, simple next steps. Rico, Iggy, and Luna turn workout history into personalized movement guidance without paid APIs or complex integrations. It does not replace a coach, doctor, or therapist; it helps a beginner runner make better everyday training decisions.

## User Identity And Privacy

RunCoach AI stores users in a SQLite `users` table with `email`, `password_hash`, and `created_at`. Passwords are hashed with Werkzeug. Runs and imported workouts include `user_id`, and the dashboard, importer, Previous Runs list, and RunCoach Agent filter by the logged-in user's `user_id`.

Evaluators can click **Try Demo** to log in as `demo@runcoach.test` without creating an account. Demo mode uses fake seeded workout data for privacy-safe testing and does not remove authentication or user-level data separation.

Health and workout data is sensitive, so the app keeps imports local, ignores real Apple Health export files in Git, and provides a fake `sample_health_export.xml` for demos.

Wellness guidance is general and not medical advice. The app does not diagnose, treat, or provide therapy. If a user expresses crisis, self-harm, or immediate danger, the support language should encourage them to contact emergency help or a crisis hotline right away.

## Future Integration Notes

Real Apple Watch or Apple HealthKit sync should be added later through a native Apple-platform app. Google login, Apple login, and OAuth are also future upgrades. For this capstone, local accounts, Apple Health `export.xml` import, CSV import, and wearable-style fields keep the agent workflow stable and easy to explain.
