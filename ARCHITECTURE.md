# RunCoach AI Architecture

## Overview

RunCoach AI is a small Flask application with a local SQLite database, five Gemini-capable agents, and deterministic local fallbacks. The design keeps the capstone easy to demo even when no API key or network is available.

## Layers

### 1. Core Run Logging

User input is collected in `templates/index.html` and submitted to small Flask routes in `app.py`. Pure coaching, media, and dashboard calculations live in `runcoach_services.py`; structured workout summaries and safe screenshot storage live in `data_analyst.py`.

Core fields:

- date
- distance in miles
- duration in minutes
- mood
- notes

Manual run submissions are validated again on the server rather than trusting browser `required`, `min`, or input-type checks. Invalid dates, unknown moods, malformed numbers, non-finite values, and non-positive distance/duration are rejected before pace calculation or database access. A user-facing error is flashed back to the run form instead of returning HTTP 500 or storing an invalid row.

Historical workout input is collected in `templates/import.html` and submitted to `/import`.

### 2. Training Metrics

`app.py` calculates pace as:

```text
duration / distance = minutes per mile
```

The app stores pace with the run and displays it as `mm:ss / mile`.

CSV and Apple Health XML imports calculate pace the same way so imported workouts can be compared with manually logged runs.

The AI Data Analyst summarizes user-scoped manual, CSV, and XML workouts into weekly mileage, longest run, average pace, mood trends, walk frequency, and recovery frequency for Rico, Iggy, and Luna. Demo screenshot uploads are stored locally under ignored `uploads/` and receive a clear placeholder analysis when OCR is unavailable.

`agent_messages` stores conversation history in SQLite. `user_memories` stores names, goals, favorite activities, previous struggles, pace improvements, and previous advice using a unique `user_id + agent_name + memory_key` boundary. Each response receives at most the latest 10 messages for that coach.

### 3. Coach Agents

`runcoach_agent.py` contains:

- `RicoRunnerAgent`: Rico Runner's Gemini personality and established local running-coach fallback (`RunCoachAgent` remains the compatibility base).
- `IggyWalkAgent`: Iggy, the beginner walking coach.
- `LunaRecoveryAgent`: Luna Recovery, the passive hydration, recovery, and wellness support rooster.
- `DataAnalystAgent`: internal analysis for structured training metrics, with optional Gemini interpretation and a scripted analytical fallback.
- `SentinelQA`: backend-only security and quality agent for bounded route, authentication, injection-defense, CSRF, rendering, and Try Demo checks, plus optional Gemini explanation of completed reports and a scripted fallback.
- `MemoryAwareAgent`: gives Rico and Iggy recent conversation, private memory, and Data Analyst context.

The coach prompts define separate personas: Rico is a warm Puerto Rican coquí focused on pace and consistency; Iggy is a curious green iguana focused on beginner walks, breathing, and nature; Luna is a gentle Caribbean wellness bird. Data Analyst remains neutral and emits structured `emotional_support_signals` so the coaches can lower pressure when saved moods or notes indicate stress, sadness, burnout, or frustration.

`gemini_service.py` is the only provider boundary. In Cloud Run it uses Vertex AI through Application Default Credentials when `GEMINI_USE_VERTEX=true`; local development can use `GEMINI_API_KEY`. Both paths call `gemini-2.5-flash` through the Google GenAI SDK, apply shared privacy and medical-safety instructions, and return `None` on missing configuration or provider failure. Returning `None` activates the existing deterministic coach response. Provider failures are logged by exception type without exposing prompts, user data, or secrets.

No API key is stored in SQLite, templates, chat history, or source control. Context is assembled after `user_id` filtering and is bounded to recent rows. Workout notes and chat content are labeled untrusted so they cannot override the system privacy rules.

The database integration uses tool calling, never Text-to-SQL. `build_user_scoped_agent_tools` creates approved Python closures after authentication. Each closure captures the server-selected `user_id`, exposes no `user_id` argument, clamps result limits, and calls existing parameterized access functions. Gemini cannot select tables, generate SQL, or switch account scope.

Rico reads:

- saved runs
- pace values
- mood and notes
- coaching library rows
- optional context data
- imported Apple Health XML or CSV workout rows

Rico can answer:

- progress summaries
- recent-run comparisons
- pace trend questions
- recovery questions
- next-workout questions
- breathing/stretch/run-type questions

Iggy reads the logged-in user's walking checklist and saved workout history when available. Iggy can answer beginner walking routine questions, checklist progress questions, breathing tasks, stretch tasks, and nature-count prompts such as trees and birds.

Luna reads the logged-in user's recent run context and walking checklist. Luna does not have a full chat panel, but `/agent` accepts `agent: luna` for a Gemini recovery response. The unchanged dashboard continues to render deterministic reminder cards for hydration, stretching, rest, breathing, gratitude, and bad-day walk-and-talk resets. Luna stays general and non-medical.

Sentinel QA is implemented in `sentinel_qa.py` and is deterministic and completely backend-only. During normal request activity, Flask schedules bounded route, authentication-boundary, SQL-injection rejection, CSRF, and render probes in a guarded daemon thread after safe responses when the 15-minute interval is due, then writes a status summary to server logs. Login and demo-login requests never start Sentinel, preventing nested test-client work from touching browser session or CSRF context. It has no dashboard component, agent-registry entry, or web report endpoint. Locks prevent overlapping or recursive checks. The periodic scheduler performs no browser polling, LLM call, paid service, or automatic runtime pytest process. Deeper tests use temporary databases in pytest/CI. Because Cloud Run can scale to zero, checks resume with the next request rather than waking an idle container.

Sentinel's scheduled checks never require Gemini. Its `answer()` method may use Gemini
to explain the cached deterministic report when explicitly invoked, but Gemini cannot
alter test execution, status, warning counts, or pass/fail results. Data Analyst follows
the same boundary: Python calculates the metrics first, then Gemini may interpret them;
provider failure returns the scripted brief.

### 4. Context Layer

Context is optional and beginner-friendly.

### Chart Data Flow

`DataAnalystAgent.chart_summary()` converts only the authenticated user's runs and walking checklist into bounded JSON-ready series: run dates, distance, pace, safe mood scores, weekly mileage, weekly walks, and recovery-signal counts. Flask embeds this object through Jinja's `tojson` filter. `static/app.js` parses the inert `application/json` block and draws responsive canvas charts without an external chart dependency. The same nested summary is included in Rico, Iggy, and Luna's approved user-scoped analyst context. Raw run cards remain server-rendered inside the collapsed **View run history** section.

Weather fields:

- weather summary
- temperature F
- wind mph

Map/route fields:

- route type
- route notes

Wearable-style fields:

- average heart rate
- max heart rate
- calories
- steps
- cadence

These represent Apple Watch-style data without requiring real Apple Health integration.

CSV import fields:

- date
- workout type
- distance
- duration
- average heart rate
- max heart rate
- calories
- source

Apple Health XML import fields:

- start date
- end date
- workout type
- distance
- duration
- calories
- source
- device

### 5. Capstone Documentation

Documentation explains the project for reviewers:

- `README.md`
- `CAPSTONE_SUMMARY.md`
- `ARCHITECTURE.md`
- `TEST_PLAN.md`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

## Data Flow

Demo login flow:

```text
Evaluator clicks Try Demo
-> Flask resets demo@runcoach.test to fake seeded data
-> Flask stores demo user_id in the session
-> Dashboard opens with sample runs, Rico, Iggy, and checklist data
```

```text
User logs a run
-> Flask receives form data
-> Pace is calculated
-> SQLite stores run + context
-> Homepage displays history
-> User asks agent question
-> Flask routes the request to Rico, Iggy, or Luna
-> Selected agent reads saved user data
-> Gemini 2.5 Flash receives bounded, user-scoped context when configured
-> Existing rule-based answer runs when Gemini is unavailable
-> Agent returns coaching answer
-> Luna cards refresh from the same user-scoped run context
```

Import flow:

```text
User uploads Apple Health export.xml or CSV
-> Flask reads rows
-> App filters supported workout types
-> App skips duplicates
-> Pace is calculated
-> Imported workouts are saved in runs table
-> Previous Runs and coach agents include imported history
```

## Database

Main table: `runs`

Stores core run fields, calculated pace, feedback, and optional context fields.

Identity table: `users`

Stores email, password hash, and account creation time.

Chat table: `agent_messages`

Stores visible/API chat history for Rico, Iggy, and Luna by `user_id` and `agent_name`.

Luna's dashboard cards do not write chat messages. Luna API requests use the same private message boundary as the other agents.

Walking table: `walk_tasks`

Stores Iggy's per-user beginner walking checklist.

Apple Health privacy guardrails:

- `.gitignore` excludes real `export.xml`, zip files, `apple_health_export` folders, `health-data` folders, and `workout-routes` folders.
- `sample_health_export.xml` contains fake demo data only.

Library table: `coach_library`

Stores starter coaching knowledge for hydration, rest, recovery, stretching, warmups, cooldowns, meditation, gratitude, breathing, beginner walking, easy runs, motivation, bad-day resets, sleep, consistency, pace awareness, running styles, run types, timed runs, and distance runs.

Wellness safety:

- Guidance is general and not medical advice.
- The app does not diagnose, treat, or provide therapy.
- Crisis, self-harm, or immediate danger language should direct users to emergency help or a crisis hotline.

## Deployment Shape

Cloud Run runs the Flask app with Gunicorn using the `Procfile`:

```text
web: gunicorn --bind :$PORT app:app
```

SQLite is acceptable for local demos. For a production app, persistent data should move to Cloud SQL or Firestore.
