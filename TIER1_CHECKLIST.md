# RunCoach AI Tier 1 Checklist

These are the must-work features for the Kaggle Capstone foundation.

| Feature | Why it matters | Status |
| --- | --- | --- |
| Log a run | Main user action | Verified live on Cloud Run (Sep 2, 2026) |
| Save run to database | Shows persistence | Verified live with demo SQLite storage |
| Calculate pace | Shows useful app logic | Verified live: 3.0 miles in 30.0 minutes = 10:00/mile |
| Show previous runs | Shows history | Verified live: Progress showed both the new manual run and seeded demo run |
| RunCoach Agent response | Makes it an agent project | Verified live: Rico recommended a 20-minute easy run |
| README + screenshots | Makes it understandable | README complete; Tier 1 submission screenshots captured |
| Public deployed URL | Makes it real | Revision `runcoach-ai-00025-v4k` serving 100% of traffic |

## Screenshot Checklist

Capture these before submitting:

- [x] Public login page and demo entry on the Cloud Run URL.
- [x] A saved run showing calculated pace.
- [x] Rico answering a next-workout question.
- [x] My Plan showing three generated workouts.
- [x] Previous Runs showing the saved workout after navigation.

Captured files are tracked in `docs/screenshots/`.

## Final Capstone Gate

Before submission, verify:

```text
Can log a run
Can refresh and still see saved runs
Can see pace calculated correctly
Can ask the RunCoach Agent a question
Can explain the architecture in one minute
Can open the public deployed URL
Can generate and view My Plan
```
