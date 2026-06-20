"""Structured workout summaries and safe screenshot intake."""

from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename


ALLOWED_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
OCR_PLACEHOLDER = (
    "Screenshot stored safely. OCR is not enabled in this lightweight demo, "
    "so Rico, Iggy, and Luna will use imported CSV/XML and saved workout data."
)


def build_analyst_summary(runs, uploads=None):
    """Turn saved workout data into a small structured summary."""
    uploads = uploads or []
    imported_runs = [run for run in runs if run.get("imported_from")]
    sources = sorted({run.get("source") or "Unknown" for run in imported_runs})
    workout_types = {}

    for run in runs:
        workout_type = run.get("workout_type") or "Running"
        workout_types[workout_type] = workout_types.get(workout_type, 0) + 1

    return {
        "total_workouts": len(runs),
        "imported_workouts": len(imported_runs),
        "total_distance": round(sum(run["distance"] for run in runs), 2),
        "average_pace": (
            round(sum(run["pace"] for run in runs) / len(runs), 2)
            if runs
            else None
        ),
        "sources": sources,
        "workout_types": workout_types,
        "screenshots": len(uploads),
        "latest_screenshot_message": (
            uploads[0]["analysis_message"] if uploads else None
        ),
    }


def save_demo_screenshot(file_storage, upload_directory):
    """Validate and store a screenshot without attempting OCR."""
    original_name = secure_filename(file_storage.filename or "")
    extension = Path(original_name).suffix.lower()

    if not original_name or extension not in ALLOWED_SCREENSHOT_EXTENSIONS:
        raise ValueError("Choose a PNG, JPG, JPEG, or WebP screenshot.")

    data = file_storage.stream.read(MAX_SCREENSHOT_BYTES + 1)
    if not data:
        raise ValueError("The screenshot file is empty.")
    if len(data) > MAX_SCREENSHOT_BYTES:
        raise ValueError("The screenshot must be 5 MB or smaller.")

    upload_directory = Path(upload_directory)
    upload_directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    (upload_directory / stored_name).write_bytes(data)

    return {
        "original_name": original_name,
        "stored_name": stored_name,
        "status": "stored_pending_ocr",
        "analysis_message": OCR_PLACEHOLDER,
    }
