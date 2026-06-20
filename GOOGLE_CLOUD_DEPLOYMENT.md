# Publish RunCoach AI on Google Cloud

This app is prepared for Google Cloud Run. Cloud Run is a good first deployment target because it can publish a Flask web app from source and provide a public URL.

## What Was Added

- `runcoach_agent.py`: the small RunCoach Agent.
- `/ask`: lets the web page ask the agent.
- `/agent`: JSON API endpoint for agent questions.
- `/health`: simple health check endpoint.
- `Procfile`: tells Cloud Run how to start the app with Gunicorn.
- `.gcloudignore`: keeps local-only files, including `runs.db`, out of deployment.

## Important Database Note

The current app uses local SQLite. That is fine for local demos, but Cloud Run instances are temporary. For a real public app, move saved runs to a managed database such as Cloud SQL or Firestore.

For a course/demo submission, this version is still useful because the app starts, seeds one demo run, logs runs during the running container session, and demonstrates the agent.

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
