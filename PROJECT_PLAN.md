# RunCoach AI Project Plan

## Submission Framing

- Track: Concierge Agents
- Project: RunCoach AI
- Problem: Many beginner runners track workouts but do not know how to interpret pace, distance, mood, and progress.
- Solution: RunCoach AI stores running history, calculates pace, reviews previous runs, and gives simple personalized coaching suggestions.
- Agent workflow: User logs a run -> app saves it -> RunCoach Agent reads run history -> agent provides feedback and next-workout guidance -> user continues training with clearer direction.

## v0.1 Features

Keep v0.1 intentionally small and stable. The goal is a local app that helps a runner log runs, add optional context, and receive simple coaching guidance.

- Log a run with date, distance, duration, mood, and notes.
- Import historical Apple Health-style workout CSV files.
- Calculate pace in minutes per mile.
- Save runs locally with SQLite.
- Show a list of previous runs.
- Include a small RunCoach Agent that answers training questions from saved runs.
- Agent summarizes progress, compares recent runs, mentions pace trends, and suggests a safe next workout.
- Expose a simple `/agent` JSON endpoint.
- Add a starter coaching library for breathing, stretching, running styles, run types, timed runs, and distance runs.
- Add optional context fields for weather, route/map notes, and wearable-style data.
- Generate simple coach feedback:
  - Encourage the user if pace improved.
  - Suggest recovery if mood is low or the run felt difficult.
  - Mention endurance progress if distance increased.
  - Suggest one next workout.

## Tier 1 Must Work

| Feature | Why it matters |
| --- | --- |
| Log a run | Main user action |
| Save run to database | Shows persistence |
| Calculate pace | Shows useful logic |
| Show previous runs | Shows history |
| RunCoach Agent response | Makes it an agent project |
| README + screenshots | Makes it understandable |
| Public deployed URL | Makes it real |

## Capstone Layers

1. Core run logging
2. Training metrics
3. RunCoach Agent
4. Context layer: weather, maps/routes, wearable-style data, Apple Health-style CSV import
5. Capstone documentation

## Database Schema

SQLite database file: `runs.db`

Table: `runs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key, auto-incrementing |
| `run_date` | TEXT | Date of the run |
| `distance` | REAL | Distance in miles |
| `duration` | REAL | Duration in minutes |
| `pace` | REAL | Calculated minutes per mile |
| `mood` | TEXT | User-selected mood |
| `notes` | TEXT | Optional run notes |
| `feedback` | TEXT | Generated coach feedback |
| `created_at` | TIMESTAMP | Automatically set when the row is created |
| `weather_summary` | TEXT | Optional weather context |
| `route_type` | TEXT | Optional route/map context |
| `avg_heart_rate` | INTEGER | Optional wearable-style average heart rate |
| `max_heart_rate` | INTEGER | Optional imported max heart rate |
| `calories` | INTEGER | Optional imported calories |
| `source` | TEXT | Manual, demo, or CSV source |
| `workout_type` | TEXT | Running, Walking, Outdoor Run, etc. |
| `imported_from` | TEXT | Import source such as Apple Health CSV |

Table: `coach_library`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key, auto-incrementing |
| `category` | TEXT | Coaching category, such as Stretch or Timed Run |
| `title` | TEXT | Name of the exercise, style, or workout |
| `description` | TEXT | Short explanation |
| `instructions` | TEXT | How to do it |
| `recommended_when` | TEXT | When the agent should suggest it |

## Agent v0.1

The first RunCoach Agent is intentionally small. It does not need an external model yet.

- Reads saved runs from SQLite.
- Reads imported historical workouts from SQLite.
- Reads starter coaching knowledge from SQLite.
- Answers questions about progress, recent-run comparisons, pace trends, recovery, and next workouts.
- Powers a web chat panel and a JSON API endpoint.

## Folder Structure

```text
RunCoach AI/
|-- app.py
|-- CAPSTONE_SUMMARY.md
|-- PROJECT_PLAN.md
|-- GOOGLE_CLOUD_DEPLOYMENT.md
|-- Procfile
|-- README.md
|-- requirements.txt
|-- runcoach_agent.py
|-- SUBMISSION_BRIEF.md
|-- TIER1_CHECKLIST.md
|-- runs.db
|-- static/
|   `-- style.css
`-- templates/
    `-- index.html
```

## Future Roadmap

These ideas are intentionally out of scope for v0.1.

- Weather: Save weather conditions with each run and adjust feedback for heat, cold, wind, or rain.
- Maps: Let users view or import routes and compare effort across different courses.
- Health: Replace wearable-style mock fields with Apple Health or Apple Watch import later.
- Apple HealthKit: Add real native sync later; current version supports CSV import first.
- Calendar: Plan upcoming workouts and show weekly training volume.
