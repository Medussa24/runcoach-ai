# RunCoach AI Defensive Security Tests

Flask-WTF CSRF protection is enabled for production requests. Defensive tests confirm tokenless POST requests are rejected and rendered form tokens are accepted.

These tests are defensive regression checks for the local Flask + SQLite capstone app. They use fake data only and do not perform destructive attacks.

## Scope

The pytest suite in `tests/test_security_defensive.py` checks:

- Prompt injection attempts against Rico, Iggy, and Luna.
- SQL injection strings in login, run notes, route notes, and chat input.
- XSS strings in run notes, route notes, and chat input.
- Malformed Apple Health XML.
- Apple Health workout records missing distance or duration.
- Attempts to access another user's data.

## Expected Results

- The app does not crash.
- SQL injection strings do not bypass login.
- SQL injection strings do not damage SQLite tables.
- XSS payloads are rendered as escaped text, not executable browser markup.
- Agents do not reveal secret keys, password hashes, system prompts, or another user's workout data.
- Malformed XML returns a safe import error.
- XML workout records missing required distance or duration are skipped.
- User data remains separated by `user_id`.

## Test Data

The tests use temporary SQLite databases created by pytest. They do not touch the local `runs.db` file and do not use real Apple Health exports.

Fake inputs include:

- SQL-like strings such as `' OR '1'='1'; DROP TABLE runs; --`
- XSS-like strings such as `<script>window.__RUNCOACH_XSS=true</script>`
- Prompt-injection style text asking agents to reveal secrets or other users' data
- Fake Apple Health XML snippets

## Running Tests

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the test suite:

```bash
pytest
```

On Windows, if `python` is not on PATH, use:

```powershell
py -m pytest
```

## Remaining Security Notes

RunCoach AI is a capstone demo, not a production security system. Before production use, add CSRF protection, stricter session configuration, rate limiting, more formal content safety handling, and production-grade secret management.
