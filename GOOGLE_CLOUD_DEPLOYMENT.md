# Publish RunCoach AI on Google Cloud

This app is prepared for Google Cloud Run. Cloud Run is a good first deployment target because it can publish a Flask web app from source and provide a public URL.

## What Was Added

- `runcoach_agent.py`: the small RunCoach Agent.
- `/ask`: lets the web page ask the agent.
- `/agent`: JSON API endpoint for agent questions.
- `/health`: simple health check endpoint.
- `/planner`: authenticated personal calendar, agent-generated weekly workouts, event completion, and `.ics` export.
- `planner_agent.py`: Gemini-first structured weekly planning with a deterministic fallback.
- `notification_service.py`: optional SMTP weekly-plan delivery and calendar generation.
- `Procfile`: tells Cloud Run how to start the app with Gunicorn.
- `.gcloudignore`: keeps local-only files, including `runs.db`, out of deployment.

## Important Database Note

The current app uses local SQLite. That is fine for local demos, but Cloud Run instances are temporary. For a real public app, move saved runs to a managed database such as Cloud SQL or Firestore.

For a course/demo submission, this version is still useful because the app starts, seeds one demo run, logs runs during the running container session, and demonstrates the agent.

The same limitation applies to personal calendar events: SQLite planner rows are
instance-local in Cloud Run. Move `runs`, `planner_events`, conversations, and
memories to Cloud SQL or Firestore for durable production use.

## Production Gemini Configuration

The deployed service uses Vertex AI with the Cloud Run service account:

```bash
gcloud run services update runcoach-ai \
  --region us-central1 \
  --update-env-vars \
GEMINI_USE_VERTEX=true,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-2.5-flash
```

Grant the runtime service account `roles/aiplatform.user`. Local development may
use `GEMINI_API_KEY` instead.

## Optional Planner Email

The calendar and `.ics` downloads require no email provider. To enable
user-triggered email delivery, store SMTP credentials in Secret Manager and map
these environment variables to Cloud Run:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM_EMAIL
SMTP_USE_TLS
```

Do not place SMTP passwords in source code or plain deployment commands.

## Deploy from Google Cloud Shell

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Open Cloud Shell.
4. Upload this project folder or push it to a Git repository and clone it in Cloud Shell.
5. From the project folder, run:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud run deploy runcoach-ai --source . --region us-central1 --allow-unauthenticated
```

6. When prompted to enable APIs or create an Artifact Registry repository, answer `Y`.
7. Copy the Cloud Run service URL when deployment finishes.

## Test the Agent API

Replace `YOUR_SERVICE_URL` with the Cloud Run URL:

```bash
curl -X POST YOUR_SERVICE_URL/agent \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What should my next workout be?\"}"
```

## Google Console Checklist

- Cloud Run service is deployed.
- Service URL opens in the browser.
- `/health` returns `{"status":"ok"}`.
- The homepage shows RunCoach AI.
- The RunCoach Agent panel answers a training question.
- `/agent` accepts a JSON question and returns an answer.
- `/planner` renders after Try Demo.
- Generate Weekly Workouts creates three or four dated workout cards.
- Every generated workout includes hydration, warm-up, main workout, and cool-down.
- Calendar download returns a `.ics` file.
