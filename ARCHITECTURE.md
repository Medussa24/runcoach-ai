# RunCoach AI Architecture

## Overview

RunCoach AI is a small Flask application with a local SQLite database, three Gemini-backed coach agents, and deterministic local fallbacks. The design keeps the capstone easy to demo even when no API key or network is available.

## Layers

### 1. Core Run Logging

User input is collected in `templates/index.html` and submitted to small Flask routes in `app.py`. Pure coaching, media, and dashboard calculations live in `runcoach_services.py`; structured workout summaries and safe screenshot storage live in `data_analyst.py`.

Core fields:

- date
- distance in miles
- duration in minutes
- mood
- notes

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
- `DataAnalystAgent`: internal, non-chatting analysis for the six structured training metrics.
- `SentinelQA`: internal, non-chatting quality agent for bounded local route, rendering, Try Demo, and pytest checks.
- `MemoryAwareAgent`: gives Rico and Iggy recent conversation, private memory, and Data Analyst context.

The coach prompts define separate personas: Rico is a warm Puerto Rican coquí focused on pace and consistency; Iggy is a curious green iguana focused on beginner walks, breathing, and nature; Luna is a gentle Caribbean wellness bird. Data Analyst remains neutral and emits structured `emotional_support_signals` so the coaches can lower pressure when saved moods or notes indicate stress, sadness, burnout, or frustration.

`gemini_service.py` is the only provider boundary. It reads `GEMINI_API_KEY` from the process environment, calls `gemini-2.5-flash` through the Google GenAI SDK, applies shared privacy and medical-safety instructions, and returns `None` on missing configuration or provider failure. Returning `None` activates the existing deterministic coach response.

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

Sentinel QA is implemented in `sentinel_qa.py` and intentionally remains deterministic. The dashboard reads only its in-memory cached report. A logged-in user can manually POST to `/sentinel/health-check`; Sentinel then uses Flask's test client for bounded read-only route/render checks and runs pytest in a separate local subprocess. `/sentinel/health` returns the cached report without starting work. A lock prevents overlapping runs, and there is no timer, polling loop, LLM call, or external service.

### 4. Context Layer

Context is optional and beginner-friendly.

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
