# RunCoach AI Test Plan

## Goal

Verify that the capstone foundation works and that optional context data does not break the beginner-friendly run logging flow.

## Tier 1 Tests

| Test | Steps | Expected Result |
| --- | --- | --- |
| Homepage loads | Open `/` | Run form, Rico chat, Iggy chat, walking checklist, previous runs, and coach library appear |
| Branding loads | Open `/` or `/login` | RunCoach AI logo, Move Improve Thrive tagline, and Rico/Iggy/Luna visuals appear |
| Log basic run | Submit date, distance, duration, mood, notes | Run saves and appears in previous runs |
| Pace calculation | Log 2 miles in 20 minutes | Pace displays as `10:00 / mile` |
| Persistence | Refresh page after saving | Saved run is still visible |
| Invalid run input | Bypass browser validation and submit malformed, zero, negative, non-finite, invalid-date, or invalid-mood values | A friendly error appears, no HTTP 500 occurs, and no row is stored |
| Agent chat | Ask `What should my next workout be?` | Agent returns safe next-workout guidance |
| Agent API | POST JSON to `/agent` | JSON response includes `answer` |
| Health check | Open `/health` | Returns `{"status":"ok"}` |

## Iggy Walking Agent Tests

| Test | Steps | Expected Result |
| --- | --- | --- |
| Iggy panel loads | Open dashboard while logged in | Iggy avatar, chat box, and walking checklist appear |
| Walking routine answer | Ask Iggy `Create my beginner walking routine` | Iggy returns easy walking, breathing, counting, and stretching guidance |
| Nature task answer | Ask Iggy `What should I count outside today?` | Iggy suggests trees, birds, and a safe outdoor landmark |
| Checklist toggle | Click one walking checklist task | Task switches between open and done |
| Checklist reset | Click Reset checklist | All walking tasks return to open |
| User-scoped checklist | Log in as two users | Each user has their own checklist state |

## Luna Recovery Tests

| Test | Steps | Expected Result |
| --- | --- | --- |
| Luna card render | Open dashboard while logged in | Luna Recovery card and reminder grid appear |
| Luna disclaimer | Open dashboard | Page shows `Wellness guidance is general and not medical advice.` |
| Hydration reminder | Open dashboard with demo data | Luna shows a water or recovery reminder |
| Bad day reset layer | Ask Rico or Iggy about a rough day | Response suggests low-pressure movement and includes crisis escalation wording for danger |
| Passive behavior | Inspect dashboard | Luna does not require user input or a separate chat panel |
| Luna API response | POST `/agent` with `agent: luna` | Gemini response is returned when configured; local summary is returned otherwise |
| Weekly schedule | Expand Weekly Schedule | Three Rico workouts and three Iggy workouts appear |

## User Identity Tests

| Test | Steps | Expected Result |
| --- | --- | --- |
| Logged-out redirect | Open `/` without logging in | App redirects to `/login` |
| CSRF rejection | POST to `/login` without a CSRF token | Request is rejected with HTTP 400 |
| CSRF form success | Submit the rendered login or demo token | Request succeeds normally |
| Ten-message context | Build an agent after several exchanges | Agent receives only the latest 10 messages |
| Cross-coach memory | Tell Rico a name and goal, then ask Iggy | Iggy remembers the same user's facts |
| Cross-user isolation | Save memory for user A and ask as user B | User B never receives user A's facts |
| Internal Data Analyst | Build `DataAnalystAgent` | Six structured metrics are returned and no chat method exists |
| Signup | Create an account at `/signup` | User is logged in and sent to dashboard |
| Password storage | Inspect `users.password_hash` | Plain text password is not stored |
| Demo login | Log in with `demo@runcoach.test` / `demo123` | Demo dashboard loads |
| One-click demo | Click Try Demo on `/login` | Demo user is logged in and redirected to dashboard |
| Demo privacy note | Open `/login` | Page says demo mode uses fake workout data for privacy-safe testing |
| Demo data reset | Add demo data, log out, click Try Demo | Demo account returns to fake seeded workout data |
| Logout | Click Log Out | Session clears and login page appears |
| User data separation | Create two users and log runs under each | Each user sees only their own runs |
| User-scoped agent | Ask `/agent` as two different users | Answers use only the logged-in user's runs |
| User-scoped imports | Import Apple Health XML for one user | Other users do not see imported workouts |

## Apple Health Import Tests

| Test | Steps | Expected Result |
| --- | --- | --- |
| Import page loads | Open `/import` | Apple Health XML and CSV upload forms appear |
| Upload size ceiling | Upload a request larger than 10 MB | Flask returns HTTP 413 without parsing the file |
| Demo screenshot | Upload a small PNG/JPG/WebP | File is stored under ignored `uploads/` and a placeholder OCR message appears |
| Import sample XML | Upload `sample_health_export.xml` | Running and walking rows import into Previous Runs |
| Skip XML unsupported rows | Include Cycling in XML | Cycling workout is skipped |
| Convert XML distance | Import walking row stored in kilometers | Distance displays in miles |
| Import supported rows | Upload CSV with Running, Run, Walking, Outdoor Run | Rows import into Previous Runs |
| Skip unsupported rows | Include Cycling or Yoga | Unsupported rows are skipped |
| Calculate imported pace | Import 2 miles in 20 minutes | Pace displays as `10:00 / mile` |
| Duplicate protection | Upload the same XML or CSV twice | Second upload counts duplicates instead of importing again |
| Historical agent answer | Ask `Analyze my imported history` | Agent mentions imported workouts |
| Privacy files ignored | Check `.gitignore` | Real Apple Health export files and folders are excluded |

## Context Layer Tests

| Test | Steps | Expected Result |
| --- | --- | --- |
| Weather context | Add weather, temperature, wind | Saved run displays weather context |
| Route context | Add route type and route notes | Saved run displays route context |
| Wearable-style context | Add heart rate, steps, cadence | Saved run displays wearable-style metrics |
| Imported wearable data | Import avg HR, max HR, calories | Previous Runs shows imported effort data |
| Agent context answer | Ask `How did weather affect my run?` | Agent mentions available context |
| Safe workout with hard context | Log hot, windy, hilly, or high-heart-rate run | Agent suggests an easier next workout |

## Gemini Agent Tests

| Test | Expected Result |
| --- | --- |
| Rico Gemini adapter | Mocked provider receives Rico's prompt, profile, history, runs, moods, recovery, and import context |
| Iggy Gemini adapter | Mocked provider receives Iggy's prompt, agent-specific history, walks, and checklist |
| Luna Gemini adapter | Mocked provider receives Luna's prompt and recovery context while cards still render |
| User separation | Two users have distinct runs; mocked Gemini context contains only the logged-in user's note |
| Tool scope | Inspect/invoke registered tools | Tools expose no `user_id` parameter and return only the authenticated user's records |
| Missing key | Remove `GEMINI_API_KEY`; existing rule-based response remains available |
| Provider safety | Shared prompt forbids diagnosis, treatment, secrets, and cross-user disclosure |
| Emotional support | Stress, sadness, burnout, or frustration lowers intensity and produces coach-specific gentle suggestions |
| Data Analyst tone | Structured summary exposes neutral emotional-support signals without conversational language |
| No network in pytest | Gemini is mocked or disabled; tests consume no API quota |
| Data Analyst Gemini fallback | Gemini receives only the structured summary; provider failure returns the scripted analytical brief |
| Sentinel Gemini fallback | Gemini may explain a completed report but cannot alter checks; provider failure returns the scripted Sentinel brief |

## Documentation Tests

| Test | Expected Result |
| --- | --- |
| README has local run instructions | Reviewer can run the app locally |
| README has deployment command | Reviewer can see Cloud Run path |
| CAPSTONE_SUMMARY explains track fit | Concierge Agents fit is clear |
| ARCHITECTURE explains data flow | App is easy to explain |
| Wellness note exists | Docs explain guidance is general and not medical advice |
| Screenshot checklist exists | Reviewer knows what to capture |

## Sentinel QA Tests

| Test | Expected Result |
| --- | --- |
| Hidden report | Dashboard does not render Sentinel status or a manual health-check button |
| Backend-only access | No Sentinel report route or public agent-registry entry exists |
| Periodic cadence | Active server requests refresh the bounded report at most once every 15 minutes |
| Safe security probes | Authentication boundaries, SQL-injection rejection, and CSRF enforcement are checked without modifying user data |
| Session isolation | Sentinel never runs synchronously inside login or demo-login requests |
| Core routes | `/`, `/login`, `/import`, `/health`, and `/agent` respond as expected |
| Chat contracts | `/ask` and `/agent` retain POST support |
| Try Demo | Login page still renders the Try Demo form |
| Agent rendering | Rico, Iggy, Luna, and Data Analyst render on the dashboard |
| Previous Runs | Demo workout content renders in Previous Runs |
| Defensive suite | Full pytest suite includes user_id separation and security defenses |
| No polling | No browser timer, background loop, or automatic pytest process exists |

## Demo Session Tests

| Test | Expected Result |
| --- | --- |
| Try Demo + CSRF | Rendered token is accepted and redirects to `/?welcome=1` |
| Session identity | Session contains the real demo `user_id`, demo flag, and permanent lifetime |
| Demo run | Authenticated demo user can save a run |
| Coach chats | Authenticated demo user can message Rico and Iggy through `/agent` |
| Protected POSTs | Anonymous users receive `401` on protected writes |

## Progress Chart Tests

| Test | Expected Result |
| --- | --- |
| Distance and pace | Date labels and numeric values are generated in chronological order |
| Weekly mileage | Runs are grouped by Monday-starting week and distances are totaled |
| Mood trend | Great/Good/Okay/Tired/Bad map only to 5/4/3/2/1 |
| Activity | Walking workouts and recovery signals are counted by week |
| Growth insights | Total, average pace, longest, latest, and week-over-week change are present |
| JSON safety | Chart payload is rendered with `tojson` and parses as JSON |
| Run details | Full cards remain available under **View run history** |
| Empty state | Missing series show friendly guidance instead of fabricated points |

## Manual Commands

Local route check:

```bash
python -c "from app import app; client = app.test_client(); print(client.get('/').status_code); print(client.get('/health').json)"
```

Agent API check:

```bash
curl -X POST http://127.0.0.1:5000/agent \
  -H "Content-Type: application/json" \
  -d "{\"agent\":\"rico\",\"question\":\"Summarize my progress\"}"
```

Iggy API check:

```bash
curl -X POST http://127.0.0.1:5000/agent \
  -H "Content-Type: application/json" \
  -d "{\"agent\":\"iggy\",\"question\":\"Create my beginner walking routine\"}"
```

Luna render check:

```bash
python -c "from app import app; c = app.test_client(); c.post('/demo-login'); html = c.get('/').data.decode(); print('Luna Recovery' in html); print('Wellness guidance is general and not medical advice.' in html)"
```

Sentinel unit and integration checks:

```bash
python -m pytest -q tests/test_sentinel_qa.py
```

Full release validation:

```bash
python -m py_compile app.py runcoach_agent.py runcoach_services.py sentinel_qa.py gemini_service.py data_analyst.py
node --check static/app.js
python -m pytest -q
```

Latest verified result on June 25, 2026: **52 passed**.

## Known Limitations

- Apple Watch / Apple Health integration is represented with wearable-style input fields.
- Apple Health `export.xml` import is local and file-based; it is not live HealthKit sync.
- Weather and route data are manually entered for stability.
- SQLite is local-first; production persistence should use Cloud SQL or Firestore.
- Luna guidance is intentionally general and non-medical.
- Sentinel's cached report and cadence are process-local; multiple Gunicorn workers can briefly show different last-check timestamps.
- Cloud Run scale-to-zero pauses request-driven checks while the app is idle; the next request resumes the cadence.
- Gemini response quality and latency depend on Google's service; provider errors deliberately fall back to local responses.
- Automated pytest verifies request contracts and privacy boundaries, not nondeterministic LLM wording.
