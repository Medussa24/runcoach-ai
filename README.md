# RunCoach AI

RunCoach AI is a polished Kaggle Capstone project for the **Concierge Agents** track. It is a beginner-friendly movement coach web app that logs runs, calculates pace, stores history, and uses Gemini-backed coach agents to explain progress, suggest safe next workouts, help new runners start with walking, and support hydration and recovery basics.

## Project Organization

1. Core run logging
2. Training metrics
3. RunCoach Agent
4. Context layer: weather, maps/routes, wearable-style data
5. Capstone documentation

## Why Concierge Agents

RunCoach AI behaves like a lightweight personal running assistant. It helps beginner runners understand their own training data, adds context around each run, and gives plain-language guidance without requiring advanced coaching knowledge.

## Core Features

- Log a run with date, distance, duration, mood, and notes.
- Create an account, log in, and log out.
- Protect every POST form and agent request with Flask-WTF CSRF tokens.
- Store Rico and Iggy conversations plus durable user memories in SQLite.
- Give coaches the latest 10 messages and remembered names, goals, pace improvements, favorite activities, struggles, and previous advice.
- Save runs locally in SQLite.
- Calculate pace automatically.
- Show previous runs and feedback.
- Ask the RunCoach Agent questions in the web chat box.
- Chat with Rico Runner for run coaching and Iggy the iguana for beginner walking help.
- Use Google Gemini 2.5 Flash for natural Rico, Iggy, and Luna responses when `GEMINI_API_KEY` is configured.
- Review Luna Recovery's passive Puerto Rican rooster support cards for hydration, stretching, rest, breathing, gratitude, and recovery reminders.
- Use Iggy's walking checklist for warmups, walking, nature-count tasks, breathing, stretching, and reflection.
- Use `/agent` as a JSON endpoint.
- Import Apple Health-style historical workouts from CSV.
- Import Apple Health `export.xml` workout history safely.
- Summarize imported CSV/XML workout data for Rico, Iggy, and Luna through the AI Data Analyst panel.
- Use an internal, non-chatting `DataAnalystAgent` for weekly mileage, longest run, average pace, mood trends, walk frequency, and recovery frequency.
- Use an internal, non-chatting `SentinelQA` agent for bounded route, rendering, demo-login, and defensive-test health checks.
- Store a demo workout screenshot locally and show an honest OCR-unavailable placeholder analysis.
- Add optional weather, route, and wearable-style data.
- Browse a visual coaching library for hydration, rest, recovery, stretching, warmups, cooldowns, meditation, gratitude, breathing, walking, easy runs, motivation, bad day resets, sleep, consistency, and pace awareness.
- Open a collapsible weekly schedule with three basic Rico run workouts and three Iggy walking workouts.

## User Identity

RunCoach AI uses a beginner-friendly email and password system:

- `/signup` creates a user account.
- `/login` checks the password and stores `user_id` in the Flask session.
- `/logout` clears the session.
- Passwords are stored with Werkzeug password hashing, not plain text.

Each saved run and imported workout has a `user_id`. The dashboard, Previous Runs list, Apple Health import, CSV import, and RunCoach Agent all filter by the logged-in user's `user_id`, so one user cannot see another user's workout history.

Conversation rows and memory facts also include `user_id`. Shared facts can be used by Rico, Iggy, and Luna for the same account, but are never queried across users. DataAnalystAgent has no chat endpoint and only supplies structured summaries to the three coaches.

Demo account for Capstone testing:

```text
Email: demo@runcoach.test
Password: demo123
```

Evaluators can also click **Try Demo** on the login page. Demo mode uses fake workout data for privacy-safe testing and resets the demo account to seeded sample data.

Google login, Apple login, and OAuth are future upgrades. This version keeps identity simple and local for the capstone.

## Context Layer

The app keeps real integrations simple for the capstone. Instead of requiring Apple Watch, Apple Health, maps, or a weather API, it provides optional input fields:

- Weather: summary, temperature, wind.
- Route/map context: road, trail, track, treadmill, hilly, route notes.
- Wearable-style data: average heart rate, steps, cadence.

Real Apple Watch or HealthKit sync is documented as future work because HealthKit requires a native Apple-platform app. For the capstone, Apple Health `export.xml`, CSV import, and wearable-style fields demonstrate how the agent would use that data.

## Apple Health Historical Import

RunCoach AI supports two safe local import options:

1. Apple Health `export.xml` from an Apple Health export zip.
2. CSV files from Apple Health shortcuts or third-party converters.

The app imports only running and walking workouts. It does not import private route files, raw health records, or unrelated workout types.

Apple Health XML fields used when available:

```text
startDate, endDate, workoutActivityType, duration, totalDistance, totalEnergyBurned, sourceName, device
```

The importer converts distance to miles, duration to minutes, calculates pace, and stores the workout in the same Previous Runs list as manual runs.

Privacy note: do not commit real Apple Health exports. This project ignores `export.xml`, zip files, `apple_health_export` folders, `health-data` folders, and `workout-routes` folders. Imported workout data is tied to the logged-in user's `user_id`. Use `sample_health_export.xml` for demos and GitHub screenshots.

Screenshot uploads accept PNG, JPG, JPEG, or WebP files up to 5 MB. They are stored under the ignored `uploads/` folder and recorded by `user_id`. OCR is intentionally unavailable in this local/free version.

Flask also enforces a 10 MB maximum request size for CSV and XML imports so large files are rejected before parsing and cannot exhaust local or cloud memory.

`Flask-WTF` initializes `CSRFProtect(app)`. HTML forms include hidden CSRF tokens, while Rico and Iggy's JSON chat requests send the token through the `X-CSRFToken` header.

Duplicate protection checks:

```text
date + distance + duration + source
```

Import page:

```text
http://127.0.0.1:5000/import
```

CSV is still supported for simple demos and converted exports.

Expected CSV columns:

```text
date,workout_type,distance_miles,duration_minutes,avg_heart_rate,max_heart_rate,calories,source
```

Supported workout types:

```text
Running, Run, Walking, Outdoor Run
```

Real Apple HealthKit sync is a future upgrade. This version does not use HealthKit directly.

## RunCoach Agents

The app has three beginner-friendly coach agents and two internal agents:

- Rico Runner is a warm, playful Puerto Rican coquí coach who occasionally says “Wepa!” and focuses on discipline, pace, and consistency.
- Iggy is a curious green iguana and calm beginner coach who promotes small wins, nature tasks, breathing, and gentle walks.
- Luna Recovery is a gentle Caribbean bird focused on hydration, gratitude, stretching, mindfulness, rest, and recovery reminders.
- Data Analyst creates structured training summaries for the coaches and has no chat endpoint.
- Sentinel QA checks key Flask routes, Try Demo markup, coach and Previous Runs rendering, imports, chat endpoint availability, and the pytest suite. It has no chat panel and uses no paid service.

The small **System Health** card shows Sentinel's cached app status, last check time, pytest pass count, warnings, and a manual **Run Health Check** button. Checks run only when requested; there is no polling loop. The cached report is also available to logged-in users at `/sentinel/health`.

Rico, Iggy, and Luna each have a separate Gemini system prompt and personality. Every Gemini request is assembled only from the logged-in user's recent runs, agent-specific chat history, walking checklist, mood/recovery context, memories, and imported-workout summaries. Data Analyst and Sentinel QA remain deterministic internal agents.

Gemini never receives a Text-to-SQL capability. Approved Python tool functions capture the authenticated `user_id` on the server and expose no account selector to the model. Those tools call the existing parameterized data-access functions for profile, agent-specific chat, recent workouts, walks, recovery context, and import summaries.

### Gemini configuration

Set the API key in the environment before starting Flask. Never place the key in source code or commit it to Git.

```powershell
$env:GEMINI_API_KEY="your-key"
python app.py
```

The default model is `gemini-2.5-flash`. `GEMINI_MODEL` may override the model name. If the key or SDK is unavailable, Gemini returns no text, or the provider request fails, the existing local rule-based response runs automatically so Try Demo and offline demonstrations continue working.

Wellness guidance is general and not medical advice. The app does not diagnose, treat, or provide therapy. If a user expresses crisis, self-harm, or immediate danger, the coaching response should be supportive and direct them to emergency help or a crisis hotline.

Stress, sadness, burnout, and frustration signals lower the pressure: Rico reduces intensity while preserving consistency, Iggy offers walk-and-talk or breathing/nature tasks, and Luna suggests one small hydration, gratitude, stretching, or mindfulness step. Data Analyst reports these signals concisely without adopting an emotional persona.

They can answer questions like:

- `Summarize my progress`
- `Compare my recent runs`
- `What is my pace trend?`
- `What should my next workout be?`
- `How did weather affect my run?`
- `Give me a breathing exercise`

## Project Structure

```text
RunCoach AI/
|-- app.py
|-- runcoach_services.py
|-- data_analyst.py
|-- gemini_service.py
|-- sentinel_qa.py
|-- runcoach_agent.py
|-- templates/
|   |-- auth.html
|   |-- import.html
|   `-- index.html
|-- static/
|   |-- app.js
|   |-- coqui-coach.svg
|   |-- iggy-coach.svg
|   |-- luna-recovery.svg
|   |-- runcoach-logo.svg
|   `-- style.css
|-- sample_health_export.xml
|-- requirements.txt
|-- Procfile
|-- .gitignore
|-- README.md
|-- CAPSTONE_SUMMARY.md
|-- ARCHITECTURE.md
|-- TEST_PLAN.md
|-- GOOGLE_CLOUD_DEPLOYMENT.md
|-- PROJECT_PLAN.md
|-- SUBMISSION_BRIEF.md
|-- TIER1_CHECKLIST.md
|-- tests/
`-- runs.db
```

## How To Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

The dashboard redirects to `/login` until you log in.

## Agent API

```bash
curl -X POST http://127.0.0.1:5000/agent \
  -H "Content-Type: application/json" \
  -d "{\"agent\":\"rico\",\"question\":\"What should my next workout be?\"}"
```

Ask Iggy for beginner walking help:

```bash
curl -X POST http://127.0.0.1:5000/agent \
  -H "Content-Type: application/json" \
  -d "{\"agent\":\"iggy\",\"question\":\"Create my beginner walking routine\"}"
```

Other endpoints:

```text
GET/POST /signup
GET/POST /login
POST /demo-login
GET /logout
GET /health
GET /coach-library
GET/POST /import
POST /walk-task/<task_id>/toggle
POST /walk-task/reset
```

## Deployment

This project is prepared for Google Cloud Run.

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud run deploy runcoach-ai --source . --region us-central1 --allow-unauthenticated
```

See `GOOGLE_CLOUD_DEPLOYMENT.md` for more detail.

## Screenshots To Capture

- Homepage with the run logging form.
- Login page with Try Demo and the RunCoach AI brand logo.
- Optional context fields for weather, route, and wearable-style data.
- Import Workouts page.
- A saved run with calculated pace and context.
- RunCoach Agent answering a progress or next-workout question.
- Rico, Iggy, and Luna agent cards.
- Luna Recovery reminder cards with the wellness disclaimer.
- Coach Library section showing expanded flash-card categories.
- `/agent` JSON response.
- Public Cloud Run URL after deployment.

## Database Reset

Stop the Flask server and delete `runs.db`.

Windows PowerShell:

```powershell
Remove-Item runs.db
```

macOS/Linux:

```bash
rm runs.db
```

Then restart:

```bash
python app.py
```
