# RunCoach AI Changelog

This file records user-visible features, architecture decisions, reliability fixes, and validation evidence so reviewers can understand how the project evolved.

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
