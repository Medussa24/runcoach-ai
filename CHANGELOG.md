# RunCoach AI Changelog

This file records user-visible features, architecture decisions, reliability fixes, and validation evidence so reviewers can understand how the project evolved.

## 2026-06-25 - Personal calendar and weekly workout planner

### Added

- A private **My Plan** tab with seven-day calendar navigation.
- Gemini-generated weekly workouts using the logged-in user's structured training summary.
- A deterministic three-workout fallback when Gemini is unavailable, malformed, or incomplete.
- Required date, time, duration, hydration, warm-up, main workout, cool-down, coach, and notes fields.
- Personal calendar events and user-scoped completion tracking.
- `.ics` calendar downloads.
- Optional, user-triggered weekly email delivery through environment-configured SMTP.
- Sentinel coverage for the authenticated planner route.

### Safety and privacy

- Every planner row is scoped by `user_id`.
- Gemini receives no email credentials and no selectable `user_id`.
- Model output is parsed and validated before database storage.
- Email is never sent automatically; the user must press **Email My Week**.

### Validation

- Python syntax check: passed.
- JavaScript syntax check: passed.
- Pytest: **60 passed**.
- Added `PERSONAL_PLANNER_FEATURE.md` as a reviewer-facing explanation of the feature's purpose, architecture, fallback behavior, privacy model, routes, validation, and limitations.

## 2026-06-25 - Intro copy cleanup

- Removed the visible note announcing the completion chime and coquí sound.
- Kept the sound behavior unchanged so it remains a subtle tutorial surprise rather than instructional copy.

## 2026-06-25 - Production Vertex AI activation

### Fixed

- Identified that Cloud Run had no `GEMINI_API_KEY`, causing Rico and Iggy to use scripted fallback responses.
- Attached the key through Secret Manager, then discovered its AI Studio prepayment credits were depleted.
- Verified the same Google Cloud project can call Gemini 2.5 Flash successfully through Vertex AI.
- Added a Vertex AI production provider path using Cloud Run Application Default Credentials, while preserving API-key support for local development.
- Added safe provider-failure logging that records only the exception type before falling back.

### Why

The previous agent orchestration was Gemini-first in code, but production lacked a usable provider configuration. Repeated answers were therefore expected scripted fallback behavior. Vertex AI now supplies the production model connection without hardcoded credentials.

## 2026-06-25 - All-agent Gemini fallback alignment

### Changed

- Made Data Analyst Gemini-capable through an internal `answer()` method that sends only its precomputed structured training summary.
- Made Sentinel QA Gemini-capable through an internal `answer()` method that sends only its completed deterministic health report.
- Preserved deterministic Python calculations, security checks, status decisions, and scripted responses as the authoritative fallback.
- Kept Gemini out of Sentinel's periodic scheduler so routine health checks do not create model cost or depend on provider availability.

### Validation

- Confirmed Rico, Iggy, Luna, Data Analyst, and Sentinel each attempt Gemini through the shared `GeminiService`.
- Confirmed all five return scripted output when Gemini is unavailable or returns no text.
- Python syntax check: passed.
- JavaScript syntax check: passed.
- Pytest: **52 passed**.

## 2026-06-25 - Agentic coaching, visual progress, and demo hardening

### Added

- Gemini 2.5 Flash integration for Rico Runner, Iggy Walk Agent, and Luna Recovery, with separate personalities and safety prompts.
- Deterministic local fallbacks when `GEMINI_API_KEY` or the Google GenAI SDK is unavailable.
- User-scoped agent context for recent runs, coach-specific chat history, walking tasks, mood/recovery signals, memories, and imported workout summaries.
- A neutral internal `DataAnalystAgent` that prepares chart-ready summaries for the coaches.
- A backend-only `SentinelQA` agent that periodically checks routes, authentication boundaries, CSRF behavior, injection defenses, demo behavior, and key rendering contracts.
- Responsive canvas charts for distance, pace, weekly miles, mood, walking activity, and recovery activity.
- Growth summary metrics and a collapsible full run history.
- A richer motivation feed with videos and visual quote cards.
- Clickable Rico, Iggy, and Luna coach surfaces that open advice bubbles.
- A short visual demo introduction for all three coaches, ending with a chime and synthesized coquí calls.
- A lightweight tutorial and return-to-top control.

### Changed

- Try Demo now creates a real authenticated session for `demo@runcoach.test` instead of displaying an unauthenticated dashboard.
- Sentinel runs asynchronously after safe requests and no longer appears on the dashboard.
- Coach Library is positioned above the motivation feed with clearer spacing.
- Previous Runs and Progress are chart-first while preserving detailed run cards.
- CSV duplicate matching uses the same rounded values stored in SQLite.
- Static assets use versioned URLs so deployed browsers receive the current JavaScript and CSS.

### Fixed

- Prevented Sentinel's periodic checks from interfering with login cookies and CSRF state.
- Removed obsolete open-page controls and the visible manual health-check panel.
- Fixed coach advice interactions when the dashboard is served by Flask.
- Rejected malformed, missing, zero, negative, non-finite, invalid-date, and invalid-mood run submissions without a server error or corrupt database row.

### Security and privacy

- Every agent receives data only after server-side `user_id` filtering.
- Database access follows approved Python tool calling rather than Text-to-SQL.
- Agent prompts forbid diagnosis, treatment prescriptions, secret disclosure, and cross-user data disclosure.
- CSRF protection remains active for demo login, forms, imports, and JSON agent requests.
- Defensive tests cover SQL injection, prompt injection, XSS, upload handling, user separation, and protected routes.

### Validation

- Python syntax check: passed.
- JavaScript syntax check: passed.
- Pytest: **49 passed**.
- Flask demo flow: demo login, dashboard, run logging, Rico chat, and Iggy chat passed.
- Browser runtime: no broken images and no console warnings or errors.
- Cloud Run logs: no severity-ERROR entries found during the production audit.

### Known limitation

SQLite storage inside Cloud Run is ephemeral and instance-local. It is appropriate for the privacy-safe capstone demo, but a production multi-user release should migrate persistence to Cloud SQL or Firestore.
