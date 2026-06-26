# RunCoach AI

RunCoach AI is a polished Kaggle Capstone project for the **Concierge Agents** track. It is a beginner-friendly movement coach web app that logs runs, calculates pace, stores history, and uses Gemini-backed coach agents to explain progress, suggest safe next workouts, help new runners start with walking, and support hydration and recovery basics.

## Live Demo And Current Release

- Cloud Run: <https://runcoach-ai-212640849356.us-central1.run.app>
- One-click evaluator access: select **Try Demo** on the login page.
- Current automated validation includes Python syntax, JavaScript syntax, Flask transactions, user-isolation tests, and browser-runtime checks.
- Detailed release history and the reasons behind each major change: [CHANGELOG.md](CHANGELOG.md).
- Full design, fallback, privacy, route, and validation explanation for the new calendar: [PERSONAL_PLANNER_FEATURE.md](PERSONAL_PLANNER_FEATURE.md).

The June 25, 2026 release adds real Gemini-backed coaching, user-scoped chart data, chart-first progress views, backend-only Sentinel QA, hardened demo authentication, clickable coach advice bubbles, a richer motivation feed, the visual coach introduction, and stricter manual-run input validation.

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
- Validate manual run values on the server so malformed, missing, zero, negative, or non-finite values cannot crash the route or enter the database.
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
- Use a backend-only, non-chatting `SentinelQA` agent for bounded route, authentication, injection-defense, rendering, and demo checks.
- Store a demo workout screenshot locally and show an honest OCR-unavailable placeholder analysis.
- Add optional weather, route, and wearable-style data.
- Browse a visual coaching library for hydration, rest, recovery, stretching, warmups, cooldowns, meditation, gratitude, breathing, walking, easy runs, motivation, bad day resets, sleep, consistency, and pace awareness.
- Open a collapsible weekly schedule with three basic Rico run workouts and three Iggy walking workouts.
- Open a private **My Plan** calendar with seven-day navigation, dated workouts, personal events, completion tracking, email delivery, and `.ics` calendar export.
- Generate organized weekly workouts with Gemini through `WeeklyPlannerAgent`, including date, time, duration, hydration, warm-up, main workout, and cool-down. A complete scripted week is used automatically when Gemini is unavailable or returns invalid structure.

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

The app has three beginner-friendly coach agents and three internal/planning agents. All six
are Gemini-capable and have deterministic scripted fallbacks:

- Rico Runner is a warm, playful Puerto Rican coquí coach who occasionally says “Wepa!” and focuses on discipline, pace, and consistency.
- Iggy is a curious green iguana and calm beginner coach who promotes small wins, nature tasks, breathing, and gentle walks.
- Luna Recovery is a gentle Caribbean bird focused on hydration, gratitude, stretching, mindfulness, rest, and recovery reminders.
- Data Analyst creates structured training summaries for the coaches and can ask Gemini to interpret those already-calculated metrics; its local analytical brief remains available if Gemini fails.
- Sentinel QA periodically checks key Flask routes, authentication boundaries, controlled SQL-injection rejection, CSRF enforcement, Try Demo markup, all four agent surfaces, Previous Runs, imports, and chat endpoint availability. Its checks and verdicts are always deterministic. Gemini can explain a completed report on demand, with a scripted explanation if Gemini fails.
- Weekly Planner converts the logged-in user's structured training summary into a dated workout calendar. It requires complete hydration, warm-up, workout, and cool-down fields and falls back to a safe three-session Rico/Iggy plan if Gemini fails.

Sentinel is completely backend-only. During app activity, the server schedules a lightweight check at most once every 15 minutes in one guarded daemon thread and writes a summary to server logs; there is no dashboard card, browser endpoint, polling loop, or automatic pytest process. Full prompt-injection, XSS, user-separation, and defensive penetration tests run in an isolated temporary database through pytest during development and CI.

Gemini is not called by Sentinel's periodic scheduler, so health checks remain free,
bounded, and reliable. Gemini interpretation is an optional internal capability and
never changes the deterministic report.

> **Demo access:** **Try Demo** posts a rendered CSRF token, resets only the privacy-safe `demo@runcoach.test` account, and creates an eight-hour authenticated demo session. Evaluators can then save runs, use mood fields and walking/recovery tools, import fake data, and chat with Rico or Iggy without typing credentials. Sentinel runs asynchronously only after safe authenticated/health responses so it cannot interfere with login cookies or CSRF state.

### Progress charts

The dashboard uses dependency-free responsive canvas charts generated from Data Analyst's user-scoped JSON summary. Progress includes distance and pace lines, weekly mileage bars, mood scores, and weekly walking/recovery activity. Previous Runs opens with growth insights and a visual overview; complete individual run cards remain available under **View run history**. Pace charts explicitly explain that lower minutes per mile indicates improvement. Empty accounts receive friendly chart states rather than fabricated trends.

Rico, Iggy, Luna, Data Analyst, and Sentinel QA each have a separate Gemini system prompt and scripted fallback. Every Gemini request is assembled from an intentionally bounded context. User-facing coaches receive only the logged-in user's recent runs, agent-specific chat history, walking checklist, mood/recovery context, memories, and imported-workout summaries. Data Analyst receives its precomputed structured summary, and Sentinel receives only its completed deterministic report.

Weekly Planner receives only the selected week, preferred time, user goal, and
precomputed user-scoped training summary. It never receives SMTP credentials or a
user selector.

Gemini never receives a Text-to-SQL capability. Approved Python tool functions capture the authenticated `user_id` on the server and expose no account selector to the model. Those tools call the existing parameterized data-access functions for profile, agent-specific chat, recent workouts, walks, recovery context, and import summaries.

### Gemini configuration

For local AI Studio development, set the API key in the environment before starting Flask. Never place the key in source code or commit it to Git.

```powershell
$env:GEMINI_API_KEY="your-key"
python app.py
```

The default model is `gemini-2.5-flash`. `GEMINI_MODEL` may override the model name. If the key or SDK is unavailable, Gemini returns no text, or the provider request fails, the existing local rule-based response runs automatically so Try Demo and offline demonstrations continue working.

The deployed Cloud Run service uses Vertex AI with Application Default
Credentials instead of consuming the AI Studio API key:

```text
GEMINI_USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=gen-lang-client-0491696796
GOOGLE_CLOUD_LOCATION=global
```

The Cloud Run runtime service account has `roles/aiplatform.user`. Local
development can continue using `GEMINI_API_KEY`; both provider paths share the
same safety prompts and scripted fallback.

### Optional email delivery

Calendar storage and `.ics` downloads work without any email service. To enable
the **Email My Week** button, configure SMTP through environment variables:

```text
SMTP_HOST
SMTP_PORT=587
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM_EMAIL
SMTP_USE_TLS=true
```

Credentials are read from the environment only. If SMTP is missing or
unavailable, the plan remains saved and the app recommends downloading the
calendar file instead. The app never sends email automatically without the
user pressing **Email My Week**.

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
|-- planner_agent.py
|-- notification_service.py
|-- PERSONAL_PLANNER_FEATURE.md
|-- sentinel_qa.py
|-- runcoach_agent.py
|-- templates/
|   |-- auth.html
|   |-- import.html
|   |-- planner.html
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

This project is deployed on Google Cloud Run:

<https://runcoach-ai-212640849356.us-central1.run.app>

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

## Final Submission Polish

- The dashboard now emphasizes six core actions and a single **Up next** card instead of competing schedule/data tiles.
- **My Plan** stores a timezone per user and exports timezone-aware calendar events.
- Planner SQL and calendar shaping live in `planner_store.py`, reducing route-level responsibilities in `app.py`.
- `RUNCOACH_DATABASE` can override the SQLite file path for an explicitly mounted persistent volume.
- Agent contracts can be checked without Gemini credentials:

```bash
python agent_eval.py
```

The deterministic evaluation dataset covers Rico, Iggy, Luna, Data Analyst, planner structure, safety concepts, and a secret-leak marker. Gemini remains the preferred response provider; these evaluations deliberately exercise the outage fallback.

See `PRODUCTION_READINESS.md` before treating the Cloud Run demo as a permanent multi-user production service.
