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

## Documentation Tests

| Test | Expected Result |
| --- | --- |
| README has local run instructions | Reviewer can run the app locally |
| README has deployment command | Reviewer can see Cloud Run path |
| CAPSTONE_SUMMARY explains track fit | Concierge Agents fit is clear |
| ARCHITECTURE explains data flow | App is easy to explain |
| Wellness note exists | Docs explain guidance is general and not medical advice |
| Screenshot checklist exists | Reviewer knows what to capture |

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

## Known Limitations

- Apple Watch / Apple Health integration is represented with wearable-style input fields.
- Apple Health `export.xml` import is local and file-based; it is not live HealthKit sync.
- Weather and route data are manually entered for stability.
- SQLite is local-first; production persistence should use Cloud SQL or Firestore.
- Luna guidance is intentionally general and non-medical.
