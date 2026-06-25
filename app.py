import csv
import io
import math
import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from agent_memory import extract_memory_facts, pace_improvement_memory
from coach_data import STARTER_COACH_ITEMS
from data_analyst import build_analyst_summary, save_demo_screenshot
from notification_service import PlanEmailService, build_calendar_ics
from planner_agent import WeeklyPlannerAgent
from runcoach_agent import (
    DataAnalystAgent,
    IggyWalkAgent,
    LunaRecoveryAgent,
    MemoryAwareAgent,
    RicoRunnerAgent,
    RunCoachAgent,
)
from runcoach_services import (
    build_dashboard_visuals,
    calculate_pace,
    coach_resource_links,
    create_feedback,
    format_pace,
    motivation_posts,
    motivation_videos,
    weekly_workout_schedule,
)
from sentinel_qa import SentinelQA


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "runcoach-ai-local-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["SENTINEL_INTERVAL_SECONDS"] = 15 * 60
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("K_SERVICE"))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
csrf = CSRFProtect(app)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "runs.db"
SCREENSHOT_UPLOAD_DIR = BASE_DIR / "uploads" / "screenshots"
sentinel_qa = SentinelQA(
    app,
    BASE_DIR,
    interval_seconds=app.config["SENTINEL_INTERVAL_SECONDS"],
)
DEMO_EMAIL = "demo@runcoach.test"
DEMO_PASSWORD = "demo123"
AGENT_RICO = "rico"
AGENT_IGGY = "iggy"
AGENT_LUNA = "luna"
VALID_AGENTS = {AGENT_RICO, AGENT_IGGY, AGENT_LUNA}
VALID_MOODS = {"Great", "Good", "Okay", "Tired", "Bad", "Sore", "Stressed", "Low"}


@app.errorhandler(413)
def upload_too_large(_error):
    """Reject oversized uploads before Flask reads them into memory."""
    return "Upload too large. The maximum request size is 10 MB.", 413


def get_database_connection():
    """Open a connection to the SQLite database."""
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.row_factory = sqlite3.Row
    return connection


def setup_database():
    """Create the app tables if they do not already exist."""
    connection = get_database_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                distance REAL NOT NULL,
                duration REAL NOT NULL,
                pace REAL NOT NULL,
                mood TEXT NOT NULL,
                notes TEXT,
                feedback TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_run_context_columns(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS coach_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                instructions TEXT NOT NULL,
                recommended_when TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                agent_name TEXT DEFAULT 'rico',
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_agent_message_columns(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS walk_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                is_done INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyst_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                status TEXT NOT NULL,
                analysis_message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL DEFAULT 'shared',
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, agent_name, memory_key)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS planner_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'workout',
                event_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                title TEXT NOT NULL,
                coach TEXT,
                hydration TEXT,
                warmup TEXT,
                main_workout TEXT,
                cooldown TEXT,
                details TEXT,
                notes TEXT,
                source TEXT NOT NULL DEFAULT 'Personal',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def ensure_run_context_columns(connection):
    """Add optional context columns to older runs tables."""
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(runs)").fetchall()
    }
    context_columns = {
        "weather_summary": "TEXT",
        "temperature_f": "REAL",
        "wind_mph": "REAL",
        "route_type": "TEXT",
        "route_notes": "TEXT",
        "avg_heart_rate": "INTEGER",
        "max_heart_rate": "INTEGER",
        "calories": "INTEGER",
        "steps": "INTEGER",
        "cadence": "INTEGER",
        "source": "TEXT",
        "workout_type": "TEXT",
        "imported_from": "TEXT",
        "end_date": "TEXT",
        "device": "TEXT",
        "user_id": "INTEGER",
    }

    for column_name, column_type in context_columns.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE runs ADD COLUMN {column_name} {column_type}"
            )


def ensure_agent_message_columns(connection):
    """Add agent tracking to older chat tables."""
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_messages)").fetchall()
    }

    if "agent_name" not in existing_columns:
        connection.execute(
            "ALTER TABLE agent_messages ADD COLUMN agent_name TEXT DEFAULT 'rico'"
        )


def get_user_by_email(email):
    """Find one user by email address."""
    connection = get_database_connection()
    try:
        return connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    finally:
        connection.close()


def get_user_by_id(user_id):
    """Find one user by id."""
    connection = get_database_connection()
    try:
        return connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        connection.close()


def create_user(email, password):
    """Create a user with a hashed password."""
    connection = get_database_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO users (email, password_hash)
            VALUES (?, ?)
            """,
            (email.lower().strip(), generate_password_hash(password)),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def get_or_create_demo_user(connection):
    """Create the capstone demo user when it does not exist."""
    user = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (DEMO_EMAIL,),
    ).fetchone()

    if user:
        return user["id"]

    cursor = connection.execute(
        """
        INSERT INTO users (email, password_hash)
        VALUES (?, ?)
        """,
        (DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD)),
    )
    return cursor.lastrowid


def seed_demo_user():
    """Ensure the demo login exists for capstone testing."""
    connection = get_database_connection()
    try:
        get_or_create_demo_user(connection)
        connection.commit()
    finally:
        connection.close()


def insert_demo_run(connection, demo_user_id):
    """Insert the privacy-safe sample run used for evaluator demos."""
    distance = 1.0
    duration = 7.67
    pace = calculate_pace(distance, duration)
    feedback = create_feedback(
        distance=distance,
        pace=pace,
        mood="Great",
        notes="First demo run based on a 7:40 mile.",
        previous_run=None,
    )

    connection.execute(
        """
        INSERT INTO runs (
            run_date, distance, duration, pace, mood, notes, feedback,
            weather_summary, temperature_f, wind_mph, route_type,
            route_notes, avg_heart_rate, max_heart_rate, calories,
            steps, cadence, source, workout_type, imported_from, user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-06-16",
            distance,
            duration,
            pace,
            "Great",
            "First demo run based on a 7:40 mile.",
            feedback,
            "Clear",
            68,
            4,
            "Road",
            "Flat neighborhood route.",
            148,
            165,
            110,
            1500,
            170,
            "Demo",
            "Running",
            None,
            demo_user_id,
        ),
    )


def reset_demo_account():
    """Reset the demo account to fake seeded data for privacy-safe testing."""
    connection = get_database_connection()
    try:
        demo_user_id = get_or_create_demo_user(connection)
        connection.execute("DELETE FROM runs WHERE user_id = ?", (demo_user_id,))
        connection.execute(
            "DELETE FROM agent_messages WHERE user_id = ?",
            (demo_user_id,),
        )
        connection.execute("DELETE FROM walk_tasks WHERE user_id = ?", (demo_user_id,))
        connection.execute(
            "DELETE FROM analyst_uploads WHERE user_id = ?",
            (demo_user_id,),
        )
        connection.execute(
            "DELETE FROM user_memories WHERE user_id = ?",
            (demo_user_id,),
        )
        connection.execute(
            "DELETE FROM planner_events WHERE user_id = ?",
            (demo_user_id,),
        )
        insert_demo_run(connection, demo_user_id)
        connection.commit()
        return demo_user_id
    finally:
        connection.close()


def current_user_id():
    return session.get("user_id")


def current_user():
    user_id = current_user_id()
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    return dict(user) if user else None


def establish_user_session(user_id, is_demo=False):
    """Create one explicit authenticated browser session."""
    session.clear()
    session["user_id"] = int(user_id)
    session["is_demo"] = bool(is_demo)
    session.permanent = True
    session.modified = True


def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        user_id = current_user_id()
        user_exists = get_user_by_id(user_id) if user_id else None

        if not user_exists:
            session.clear()
            if request.method != "GET" or request.path == "/agent":
                return jsonify({"error": "Login required"}), 401
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper


def seed_demo_data():
    """Add one demo run only when the database has no runs."""
    connection = get_database_connection()
    try:
        demo_user_id = get_or_create_demo_user(connection)
        connection.execute(
            "UPDATE runs SET user_id = ? WHERE user_id IS NULL",
            (demo_user_id,),
        )
        run_count = connection.execute(
            "SELECT COUNT(*) FROM runs WHERE user_id = ?",
            (demo_user_id,),
        ).fetchone()[0]

        if run_count > 0:
            connection.commit()
            return

        insert_demo_run(connection, demo_user_id)
        connection.commit()
    finally:
        connection.close()


def seed_coach_library():
    """Add starter coaching knowledge without duplicating existing cards."""
    connection = get_database_connection()
    try:
        existing_items = {
            (row["category"], row["title"])
            for row in connection.execute(
                "SELECT category, title FROM coach_library"
            ).fetchall()
        }
        missing_items = [
            item
            for item in STARTER_COACH_ITEMS
            if (item[0], item[1]) not in existing_items
        ]

        if not missing_items:
            return

        connection.executemany(
            """
            INSERT INTO coach_library (
                category, title, description, instructions, recommended_when
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            missing_items,
        )
        connection.commit()
    finally:
        connection.close()


@app.before_request
def initialize_app_once():
    """Initialize shared data without touching the browser session."""
    if not hasattr(app, "_db_setup_done"):
        setup_database()
        seed_coach_library()
        app._db_setup_done = True



@app.after_request
def schedule_sentinel_after_safe_request(response):
    """Run Sentinel in a separate thread, never inside auth/session handling."""
    safe_endpoints = {"health", "index", "agent_api", "import_workouts"}
    if (
        not app.config.get("TESTING")
        and request.endpoint in safe_endpoints
        and response.status_code < 400
        and not sentinel_qa.is_running
        and sentinel_qa.is_due()
    ):
        seed_demo_data()
        demo_user = get_user_by_email(DEMO_EMAIL)
        if demo_user:
            sentinel_qa.start_periodic_if_due(
                demo_user["id"],
                on_complete=log_sentinel_report,
            )
    return response


def log_sentinel_report(report):
    """Write one backend-only Sentinel summary after an asynchronous check."""
    log_method = app.logger.info if report["status"] == "Healthy" else app.logger.warning
    log_method(
        "Sentinel QA backend check: status=%s checks=%s/%s warnings=%s",
        report["status"],
        report["checks_passed"],
        report["checks_total"],
        report["warnings_count"],
    )


def get_previous_run(user_id):
    """Return the most recent run before a new run is saved."""
    connection = get_database_connection()
    try:
        return connection.execute(
            """
            SELECT * FROM runs
            WHERE user_id = ?
            ORDER BY run_date DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        connection.close()


def get_all_runs(user_id):
    """Return all saved runs, newest first."""
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM runs
            WHERE user_id = ?
            ORDER BY run_date DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_analyst_uploads(user_id, limit=10):
    """Return screenshot-analysis records for one user."""
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT original_name, status, analysis_message, created_at
            FROM analyst_uploads
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def save_analyst_upload(user_id, upload):
    """Save screenshot metadata for the logged-in user."""
    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO analyst_uploads (
                user_id, original_name, stored_name, status, analysis_message
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                upload["original_name"],
                upload["stored_name"],
                upload["status"],
                upload["analysis_message"],
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_coach_library():
    """Return coaching library items grouped by category."""
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM coach_library
            ORDER BY category, title
            """
        ).fetchall()
    finally:
        connection.close()

    grouped_items = {}
    for row in rows:
        item = dict(row)
        item["resource_links"] = coach_resource_links(item["category"], item["title"])
        grouped_items.setdefault(item["category"], []).append(item)

    return grouped_items


def get_coach_library_items():
    """Return all coaching library rows as dictionaries."""
    connection = get_database_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM coach_library ORDER BY category, title"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_agent_messages(user_id, agent_name=AGENT_RICO, limit=30):
    """Return recent chat messages for one user and one coach."""
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT sender, message, created_at
            FROM agent_messages
            WHERE user_id = ?
              AND (agent_name = ? OR (? = 'rico' AND agent_name IS NULL))
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, agent_name, agent_name, limit),
        ).fetchall()
    finally:
        connection.close()

    return [dict(row) for row in reversed(rows)]


def save_agent_message(user_id, sender, message, agent_name=AGENT_RICO):
    """Save one chat message for the logged-in user."""
    message = (message or "").strip()

    if not message:
        return

    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO agent_messages (user_id, agent_name, sender, message)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, agent_name, sender, message),
        )
        connection.commit()
    finally:
        connection.close()


def upsert_user_memory(user_id, memory_key, memory_value, agent_name="shared"):
    """Store one user-scoped memory without creating duplicate keys."""
    if not memory_value:
        return

    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO user_memories (
                user_id, agent_name, memory_key, memory_value
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, agent_name, memory_key)
            DO UPDATE SET
                memory_value = excluded.memory_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, agent_name, memory_key, memory_value),
        )
        connection.commit()
    finally:
        connection.close()


def remember_user_message(user_id, message):
    """Extract and save stable facts from a user message."""
    for memory_key, memory_value in extract_memory_facts(message).items():
        upsert_user_memory(user_id, memory_key, memory_value)


def get_user_memories(user_id, agent_name):
    """Return shared and agent-specific memory for one user only."""
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT memory_key, memory_value
            FROM user_memories
            WHERE user_id = ? AND agent_name IN ('shared', ?)
            ORDER BY updated_at, id
            """,
            (user_id, agent_name),
        ).fetchall()
    finally:
        connection.close()

    return {row["memory_key"]: row["memory_value"] for row in rows}


def remember_pace_improvement(user_id, runs):
    """Save the latest measurable pace improvement as shared memory."""
    improvement = pace_improvement_memory(runs, format_pace)
    if improvement:
        upsert_user_memory(user_id, "pace_improvement", improvement)


def normalize_agent_name(agent_name):
    """Return a known coach id for chat routing."""
    agent_name = (agent_name or "").strip().lower()
    if agent_name in VALID_AGENTS:
        return agent_name
    return AGENT_RICO


DEFAULT_WALK_TASKS = [
    ("Warm up with 3 shoulder rolls and 3 ankle circles", "Warmup"),
    ("Walk 5 minutes at an easy talking pace", "Walk"),
    ("Spot and count 3 trees", "Nature"),
    ("Spot and count 2 birds", "Nature"),
    ("Breathe in for 4 steps and out for 4 steps for 2 minutes", "Breathing"),
    ("Do a 20 second calf stretch on each side", "Stretch"),
    ("Write one note about how the walk felt", "Reflect"),
]


def seed_walk_tasks(user_id):
    """Create Iggy's default walking checklist for a user if it is empty."""
    connection = get_database_connection()
    try:
        existing_count = connection.execute(
            "SELECT COUNT(*) AS count FROM walk_tasks WHERE user_id = ?",
            (user_id,),
        ).fetchone()["count"]

        if existing_count == 0:
            connection.executemany(
                """
                INSERT INTO walk_tasks (user_id, title, category)
                VALUES (?, ?, ?)
                """,
                [(user_id, title, category) for title, category in DEFAULT_WALK_TASKS],
            )
            connection.commit()
    finally:
        connection.close()


def get_walk_tasks(user_id):
    """Return Iggy's walking checklist for one user."""
    seed_walk_tasks(user_id)
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, title, category, is_done
            FROM walk_tasks
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def toggle_walk_task(task_id, user_id):
    """Mark one walking checklist item done or not done for the current user."""
    connection = get_database_connection()
    try:
        task = connection.execute(
            """
            SELECT is_done
            FROM walk_tasks
            WHERE id = ? AND user_id = ?
            """,
            (task_id, user_id),
        ).fetchone()

        if task:
            connection.execute(
                """
                UPDATE walk_tasks
                SET is_done = ?
                WHERE id = ? AND user_id = ?
                """,
                (0 if task["is_done"] else 1, task_id, user_id),
            )
            connection.commit()
    finally:
        connection.close()


def reset_walk_tasks(user_id):
    """Reset Iggy's checklist for one user."""
    connection = get_database_connection()
    try:
        connection.execute(
            "UPDATE walk_tasks SET is_done = 0 WHERE user_id = ?",
            (user_id,),
        )
        connection.commit()
    finally:
        connection.close()


def empty_to_none(value):
    """Store blank optional form fields as None."""
    if value is None or value == "":
        return None
    return value


def optional_float(value):
    value = empty_to_none(value)
    if value is None:
        return None
    return float(value)


def optional_int(value):
    value = empty_to_none(value)
    if value is None:
        return None
    return int(value)


def parse_run_form(form):
    """Validate and normalize a manually entered run."""
    run_date = (form.get("run_date") or "").strip()
    mood = (form.get("mood") or "").strip()

    try:
        date.fromisoformat(run_date)
    except ValueError as error:
        raise ValueError("Choose a valid run date.") from error

    try:
        distance = float(form.get("distance", ""))
        duration = float(form.get("duration", ""))
        temperature_f = optional_float(form.get("temperature_f"))
        wind_mph = optional_float(form.get("wind_mph"))
        avg_heart_rate = optional_int(form.get("avg_heart_rate"))
        steps = optional_int(form.get("steps"))
        cadence = optional_int(form.get("cadence"))
    except (TypeError, ValueError) as error:
        raise ValueError("Use valid numbers for the run details.") from error

    numeric_values = [distance, duration, temperature_f, wind_mph]
    if any(value is not None and not math.isfinite(value) for value in numeric_values):
        raise ValueError("Run details must use finite numbers.")

    if distance <= 0 or duration <= 0:
        raise ValueError("Distance and duration must be greater than zero.")

    if any(value is not None and value <= 0 for value in (avg_heart_rate, steps, cadence)):
        raise ValueError("Heart rate, steps, and cadence must be greater than zero.")

    if mood not in VALID_MOODS:
        raise ValueError("Choose a valid mood.")

    return {
        "run_date": run_date,
        "distance": distance,
        "duration": duration,
        "mood": mood,
        "notes": form.get("notes", ""),
        "weather_summary": empty_to_none(form.get("weather_summary")),
        "temperature_f": temperature_f,
        "wind_mph": wind_mph,
        "route_type": empty_to_none(form.get("route_type")),
        "route_notes": empty_to_none(form.get("route_notes")),
        "avg_heart_rate": avg_heart_rate,
        "steps": steps,
        "cadence": cadence,
    }


def normalize_apple_workout_type(workout_type):
    """Return a friendly workout type for supported Apple Health workouts."""
    cleaned = (workout_type or "").replace("HKWorkoutActivityType", "").strip()
    normalized = cleaned.lower().replace(" ", "")

    if normalized in {"running", "run"}:
        return "Running"

    if normalized in {"walking", "walk"}:
        return "Walking"

    if normalized in {"outdoorrun", "outdoorrunning"}:
        return "Outdoor Run"

    return None


def convert_distance_to_miles(value, unit):
    """Convert Apple Health distance values into miles."""
    distance = float(value)
    normalized_unit = (unit or "mi").lower()

    if normalized_unit in {"mi", "mile", "miles"}:
        return distance

    if normalized_unit in {"km", "kilometer", "kilometers"}:
        return distance * 0.621371

    if normalized_unit in {"m", "meter", "meters"}:
        return distance * 0.000621371

    if normalized_unit in {"ft", "foot", "feet"}:
        return distance / 5280

    return distance


def convert_duration_to_minutes(value, unit):
    """Convert Apple Health duration values into minutes."""
    duration = float(value)
    normalized_unit = (unit or "min").lower()

    if normalized_unit in {"min", "mins", "minute", "minutes"}:
        return duration

    if normalized_unit in {"sec", "secs", "s", "second", "seconds"}:
        return duration / 60

    if normalized_unit in {"hr", "hrs", "h", "hour", "hours"}:
        return duration * 60

    return duration


def apple_health_date_to_run_date(start_date):
    """Use the date portion of an Apple Health timestamp for the run list."""
    if not start_date:
        return ""
    return start_date[:10]


def optional_rounded_int(value):
    if value in (None, ""):
        return None
    return int(round(float(value)))


def import_workouts_from_csv(file_storage, user_id):
    """Import supported Apple Health-style workout CSV rows."""
    allowed_workout_types = {"running", "run", "walking", "outdoor run"}
    required_columns = {
        "date",
        "workout_type",
        "distance_miles",
        "duration_minutes",
        "avg_heart_rate",
        "max_heart_rate",
        "calories",
        "source",
    }
    imported_count = 0
    skipped_count = 0
    duplicate_count = 0
    errors = []

    text_stream = io.TextIOWrapper(file_storage.stream, encoding="utf-8-sig")
    reader = csv.DictReader(text_stream)

    if not reader.fieldnames:
        return {
            "imported": 0,
            "skipped": 0,
            "duplicates": 0,
            "errors": ["The CSV file is empty or missing headers."],
        }

    missing_columns = required_columns - set(reader.fieldnames)
    if missing_columns:
        return {
            "imported": 0,
            "skipped": 0,
            "duplicates": 0,
            "errors": [f"Missing columns: {', '.join(sorted(missing_columns))}"],
        }

    connection = get_database_connection()
    try:
        for row_number, row in enumerate(reader, start=2):
            workout_type = row["workout_type"].strip()
            normalized_type = workout_type.lower()

            if normalized_type not in allowed_workout_types:
                skipped_count += 1
                continue

            try:
                run_date = row["date"].strip()
                distance = round(float(row["distance_miles"]), 4)
                duration = round(float(row["duration_minutes"]), 2)
                avg_heart_rate = optional_int(row.get("avg_heart_rate"))
                max_heart_rate = optional_int(row.get("max_heart_rate"))
                calories = optional_int(row.get("calories"))
                source = row["source"].strip() or "Apple Health CSV"
            except ValueError:
                skipped_count += 1
                errors.append(f"Row {row_number} has invalid number values.")
                continue

            if distance <= 0 or duration <= 0:
                skipped_count += 1
                errors.append(f"Row {row_number} needs positive distance and duration.")
                continue

            duplicate = connection.execute(
                """
                SELECT id FROM runs
                WHERE user_id = ? AND run_date = ? AND distance = ? AND duration = ? AND source = ?
                LIMIT 1
                """,
                (user_id, run_date, distance, duration, source),
            ).fetchone()

            if duplicate:
                duplicate_count += 1
                continue

            pace = calculate_pace(distance, duration)
            notes = f"Imported {workout_type} workout from {source}."
            previous_run = connection.execute(
                """
                SELECT * FROM runs
                WHERE user_id = ?
                ORDER BY run_date DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            feedback = create_feedback(distance, pace, "Good", notes, previous_run)

            connection.execute(
                """
                INSERT INTO runs (
                    run_date, distance, duration, pace, mood, notes, feedback,
                    avg_heart_rate, max_heart_rate, calories, source,
                    workout_type, imported_from, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date,
                    distance,
                    duration,
                    pace,
                    "Good",
                    notes,
                    feedback,
                    avg_heart_rate,
                    max_heart_rate,
                    calories,
                    source,
                    workout_type,
                    "Apple Health CSV",
                    user_id,
                ),
            )
            imported_count += 1

        connection.commit()
    finally:
        connection.close()

    return {
        "imported": imported_count,
        "skipped": skipped_count,
        "duplicates": duplicate_count,
        "errors": errors,
    }


def import_workouts_from_apple_health_xml(file_storage, user_id):
    """Import running and walking workouts from Apple Health export.xml."""
    imported_count = 0
    skipped_count = 0
    duplicate_count = 0
    errors = []

    try:
        tree = ET.parse(file_storage.stream)
    except ET.ParseError:
        return {
            "imported": 0,
            "skipped": 0,
            "duplicates": 0,
            "errors": [
                "The XML file could not be parsed. Choose Apple Health "
                "export.xml or the sample file."
            ],
        }

    root = tree.getroot()
    workouts = root.findall("Workout")

    connection = get_database_connection()
    try:
        for row_number, workout in enumerate(workouts, start=1):
            workout_type = normalize_apple_workout_type(
                workout.attrib.get("workoutActivityType")
            )

            if not workout_type:
                skipped_count += 1
                continue

            try:
                start_date = workout.attrib.get("startDate", "").strip()
                end_date = workout.attrib.get("endDate", "").strip()
                run_date = apple_health_date_to_run_date(start_date)
                distance = convert_distance_to_miles(
                    workout.attrib.get("totalDistance"),
                    workout.attrib.get("totalDistanceUnit"),
                )
                duration = convert_duration_to_minutes(
                    workout.attrib.get("duration"),
                    workout.attrib.get("durationUnit"),
                )
                calories = optional_rounded_int(workout.attrib.get("totalEnergyBurned"))
                source = workout.attrib.get("sourceName", "").strip() or "Apple Health Export"
                device = workout.attrib.get("device", "").strip() or None
            except (TypeError, ValueError):
                skipped_count += 1
                errors.append(f"Workout {row_number} is missing valid distance or duration values.")
                continue

            if not run_date:
                skipped_count += 1
                errors.append(f"Workout {row_number} is missing a start date.")
                continue

            if distance <= 0 or duration <= 0:
                skipped_count += 1
                errors.append(f"Workout {row_number} needs positive distance and duration.")
                continue

            duplicate = connection.execute(
                """
                SELECT id FROM runs
                WHERE user_id = ? AND run_date = ? AND distance = ? AND duration = ? AND source = ?
                LIMIT 1
                """,
                (user_id, run_date, round(distance, 4), round(duration, 2), source),
            ).fetchone()

            if duplicate:
                duplicate_count += 1
                continue

            pace = calculate_pace(distance, duration)
            notes = f"Imported {workout_type} workout from Apple Health export.xml."
            previous_run = connection.execute(
                """
                SELECT * FROM runs
                WHERE user_id = ?
                ORDER BY run_date DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            feedback = create_feedback(distance, pace, "Good", notes, previous_run)

            connection.execute(
                """
                INSERT INTO runs (
                    run_date, distance, duration, pace, mood, notes, feedback,
                    calories, source, workout_type, imported_from, end_date, device,
                    user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date,
                    round(distance, 4),
                    round(duration, 2),
                    pace,
                    "Good",
                    notes,
                    feedback,
                    calories,
                    source,
                    workout_type,
                    "Apple Health export.xml",
                    end_date,
                    device,
                    user_id,
                ),
            )
            imported_count += 1

        connection.commit()
    finally:
        connection.close()

    return {
        "imported": imported_count,
        "skipped": skipped_count,
        "duplicates": duplicate_count,
        "errors": errors,
    }


def build_data_analyst(user_id, runs=None):
    """Create the internal, non-chatting Data Analyst."""
    return DataAnalystAgent(
        runs or get_all_runs(user_id),
        format_pace,
        get_walk_tasks(user_id),
    )


def build_private_agent_summary(user_id, runs):
    """Build imported and training summaries for one logged-in user only."""
    summary = build_analyst_summary(runs, get_analyst_uploads(user_id))
    summary.update(build_data_analyst(user_id, runs).summary())
    return summary


def get_planner_events(user_id, start_date=None, end_date=None):
    """Return calendar events for one authenticated user."""
    query = "SELECT * FROM planner_events WHERE user_id = ?"
    parameters = [user_id]
    if start_date:
        query += " AND event_date >= ?"
        parameters.append(str(start_date))
    if end_date:
        query += " AND event_date <= ?"
        parameters.append(str(end_date))
    query += " ORDER BY event_date, start_time, id"

    connection = get_database_connection()
    try:
        return [
            dict(row)
            for row in connection.execute(query, parameters).fetchall()
        ]
    finally:
        connection.close()


def save_generated_plan(user_id, events, week_start, source):
    """Replace generated workouts for one user's selected week."""
    week_end = week_start + timedelta(days=6)
    connection = get_database_connection()
    try:
        connection.execute(
            """
            DELETE FROM planner_events
            WHERE user_id = ? AND event_type = 'workout'
              AND source IN ('Gemini', 'Scripted fallback')
              AND event_date BETWEEN ? AND ?
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        )
        for event in events:
            connection.execute(
                """
                INSERT INTO planner_events (
                    user_id, event_type, event_date, start_time,
                    duration_minutes, title, coach, hydration, warmup,
                    main_workout, cooldown, notes, source
                )
                VALUES (?, 'workout', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    event["date"],
                    event["start_time"],
                    event["duration_minutes"],
                    event["title"],
                    event["coach"],
                    event["hydration"],
                    event["warmup"],
                    event["main_workout"],
                    event["cooldown"],
                    event.get("notes", ""),
                    source,
                ),
            )
        connection.commit()
    finally:
        connection.close()


def add_personal_planner_event(user_id, form):
    """Validate and store one personal calendar event."""
    title = (form.get("title") or "").strip()
    details = (form.get("details") or "").strip()
    try:
        event_date = date.fromisoformat(form.get("event_date", ""))
        start_time = datetime.strptime(
            form.get("start_time", ""),
            "%H:%M",
        ).strftime("%H:%M")
        duration = int(form.get("duration_minutes", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("Choose a valid date, time, and duration.") from error
    if not title:
        raise ValueError("Add a title for the event.")
    if not 5 <= duration <= 720:
        raise ValueError("Event duration must be between 5 minutes and 12 hours.")

    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO planner_events (
                user_id, event_type, event_date, start_time,
                duration_minutes, title, details, source
            )
            VALUES (?, 'personal', ?, ?, ?, ?, ?, 'Personal')
            """,
            (
                user_id,
                event_date.isoformat(),
                start_time,
                duration,
                title[:120],
                details[:1000],
            ),
        )
        connection.commit()
    finally:
        connection.close()


def planner_calendar_days(user_id, week_start):
    """Build seven display-ready calendar columns."""
    events = get_planner_events(
        user_id,
        week_start,
        week_start + timedelta(days=6),
    )
    by_date = {}
    for event in events:
        by_date.setdefault(event["event_date"], []).append(event)
    today = date.today()
    return [
        {
            "date": day.isoformat(),
            "weekday": day.strftime("%A"),
            "day_number": day.day,
            "month": day.strftime("%b"),
            "is_today": day == today,
            "events": by_date.get(day.isoformat(), []),
        }
        for day in (week_start + timedelta(days=offset) for offset in range(7))
    ]


def parse_planner_week_start(value=None):
    """Use the requested date or the current week's Monday."""
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    today = date.today()
    return today - timedelta(days=today.weekday())


def build_user_scoped_agent_tools(user_id, agent_name):
    """Create safe Gemini tools with account scope captured by the server.

    The model never receives a SQL tool or a user_id parameter. These closures
    call existing parameterized data-access functions for the authenticated user.
    """

    def get_user_profile_for_logged_in_user() -> dict:
        """Return remembered profile facts for the logged-in user."""
        return get_user_memories(user_id, agent_name)

    def get_recent_chat_for_this_agent(limit: int = 10) -> list[dict]:
        """Return recent messages for this coach and the logged-in user."""
        safe_limit = max(1, min(int(limit), 10))
        return get_agent_messages(user_id, agent_name, limit=safe_limit)

    def get_recent_workouts_for_logged_in_user(limit: int = 10) -> list[dict]:
        """Return recent workouts for the logged-in user."""
        safe_limit = max(1, min(int(limit), 12))
        return get_all_runs(user_id)[:safe_limit]

    def get_walk_context_for_logged_in_user() -> dict:
        """Return walking workouts and checklist tasks for the logged-in user."""
        runs = get_all_runs(user_id)
        return {
            "walk_workouts": [
                run
                for run in runs[:12]
                if "walk" in (run.get("workout_type") or "").lower()
            ],
            "walking_checklist": get_walk_tasks(user_id),
        }

    def get_recovery_context_for_logged_in_user() -> dict:
        """Return mood and recovery signals for the logged-in user."""
        runs = get_all_runs(user_id)[:12]
        return {
            "mood_entries": [
                {"run_date": run.get("run_date"), "mood": run.get("mood")}
                for run in runs
            ],
            "recovery_logs": [
                run
                for run in runs
                if (run.get("mood") or "").lower()
                in {"tired", "sore", "stressed", "low"}
                or any(
                    word in (run.get("notes") or "").lower()
                    for word in ("hard", "tired", "sore", "recovery")
                )
            ],
        }

    def get_import_summary_for_logged_in_user() -> dict:
        """Return imported-workout summaries for the logged-in user."""
        runs = get_all_runs(user_id)
        return build_private_agent_summary(user_id, runs)

    def get_upcoming_plan_for_logged_in_user() -> list[dict]:
        """Return upcoming calendar events for the logged-in user."""
        today = date.today()
        return get_planner_events(
            user_id,
            today,
            today + timedelta(days=14),
        )[:20]

    return [
        get_user_profile_for_logged_in_user,
        get_recent_chat_for_this_agent,
        get_recent_workouts_for_logged_in_user,
        get_walk_context_for_logged_in_user,
        get_recovery_context_for_logged_in_user,
        get_import_summary_for_logged_in_user,
        get_upcoming_plan_for_logged_in_user,
    ]


def build_agent(user_id, runs=None):
    """Create Rico with private memory and recent conversation context."""
    runs = runs or get_all_runs(user_id)
    base_agent = RicoRunnerAgent(
        runs,
        format_pace,
        get_coach_library_items(),
        tools=build_user_scoped_agent_tools(user_id, AGENT_RICO),
    )
    return MemoryAwareAgent(
        base_agent,
        get_agent_messages(user_id, AGENT_RICO, limit=10),
        get_user_memories(user_id, AGENT_RICO),
        build_private_agent_summary(user_id, runs),
    )


def build_iggy_agent(user_id, runs=None):
    """Create Iggy with private memory and recent conversation context."""
    runs = runs or get_all_runs(user_id)
    base_agent = IggyWalkAgent(
        runs,
        get_walk_tasks(user_id),
        format_pace,
        tools=build_user_scoped_agent_tools(user_id, AGENT_IGGY),
    )
    return MemoryAwareAgent(
        base_agent,
        get_agent_messages(user_id, AGENT_IGGY, limit=10),
        get_user_memories(user_id, AGENT_IGGY),
        build_private_agent_summary(user_id, runs),
    )


def build_luna_agent(user_id, runs=None):
    """Create Luna with private memory and Data Analyst summaries."""
    runs = runs or get_all_runs(user_id)
    return LunaRecoveryAgent(
        runs,
        get_walk_tasks(user_id),
        format_pace,
        get_user_memories(user_id, AGENT_LUNA),
        build_private_agent_summary(user_id, runs),
        get_agent_messages(user_id, AGENT_LUNA, limit=10),
        tools=build_user_scoped_agent_tools(user_id, AGENT_LUNA),
    )


def build_agent_for_name(user_id, agent_name):
    """Create the requested coach agent."""
    agent_name = normalize_agent_name(agent_name)
    if agent_name == AGENT_IGGY:
        return build_iggy_agent(user_id)
    if agent_name == AGENT_LUNA:
        return build_luna_agent(user_id)
    return build_agent(user_id)


def respond_with_memory(user_id, agent_name, question):
    """Save context, answer, and remember private facts and prior advice."""
    agent_name = normalize_agent_name(agent_name)
    save_agent_message(user_id, "user", question, agent_name)
    remember_user_message(user_id, question)
    runs = get_all_runs(user_id)
    remember_pace_improvement(user_id, runs)

    if agent_name == AGENT_IGGY:
        agent = build_iggy_agent(user_id, runs)
    elif agent_name == AGENT_LUNA:
        agent = build_luna_agent(user_id, runs)
    else:
        agent = build_agent(user_id, runs)

    answer = agent.answer(question)
    save_agent_message(user_id, agent_name, answer, agent_name)
    upsert_user_memory(
        user_id,
        "previous_advice",
        answer[:500],
        agent_name=agent_name,
    )
    return answer


def dashboard_context(user, agent_question=""):
    """Collect the shared context needed by the main dashboard template."""
    user_id = user["id"]
    runs = get_all_runs(user_id)
    analyst_uploads = get_analyst_uploads(user_id)
    data_summary = build_data_analyst(user_id, runs).summary()
    chart_data = data_summary["chart_summary"]
    luna_agent = build_luna_agent(user_id, runs)
    analyst_summary = build_analyst_summary(runs, analyst_uploads)
    analyst_summary.update(data_summary)

    return {
        "runs": runs,
        "format_pace": format_pace,
        "coach_library": get_coach_library(),
        "agent_question": agent_question,
        "current_user": user,
        "chat_messages": get_agent_messages(user_id, AGENT_RICO),
        "iggy_chat_messages": get_agent_messages(user_id, AGENT_IGGY),
        "walk_tasks": get_walk_tasks(user_id),
        "visuals": build_dashboard_visuals(runs),
        "chart_data": chart_data,
        "analyst_summary": analyst_summary,
        "analyst_uploads": analyst_uploads,
        "analyst_notice": request.args.get("analyst"),
        "motivation_videos": motivation_videos(),
        "motivation_posts": motivation_posts(),
        "weekly_schedule": weekly_workout_schedule(),
        "luna_summary": luna_agent.summary(),
        "luna_cards": luna_agent.cards(),
        "wellness_disclaimer": LunaRecoveryAgent.disclaimer,
    }


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user = current_user()
    user_id = user["id"]

    if request.method == "POST":
        try:
            run = parse_run_form(request.form)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(f"{url_for('index')}#log-run")

        run_date = run["run_date"]
        distance = run["distance"]
        duration = run["duration"]
        mood = run["mood"]
        notes = run["notes"]
        weather_summary = run["weather_summary"]
        temperature_f = run["temperature_f"]
        wind_mph = run["wind_mph"]
        route_type = run["route_type"]
        route_notes = run["route_notes"]
        avg_heart_rate = run["avg_heart_rate"]
        steps = run["steps"]
        cadence = run["cadence"]

        pace = calculate_pace(distance, duration)
        previous_run = get_previous_run(user_id)
        feedback = create_feedback(distance, pace, mood, notes, previous_run)

        connection = get_database_connection()
        try:
            connection.execute(
                """
                INSERT INTO runs (
                    run_date, distance, duration, pace, mood, notes, feedback,
                    weather_summary, temperature_f, wind_mph, route_type,
                    route_notes, avg_heart_rate, steps, cadence, source,
                    workout_type, imported_from, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date,
                    distance,
                    duration,
                    pace,
                    mood,
                    notes,
                    feedback,
                    weather_summary,
                    temperature_f,
                    wind_mph,
                    route_type,
                    route_notes,
                    avg_heart_rate,
                    steps,
                    cadence,
                    "Manual",
                    "Running",
                    None,
                    user_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return redirect(url_for("index", saved=1))

    return render_template("index.html", **dashboard_context(user))


@app.route("/analyze-screenshot", methods=["POST"])
@login_required
def analyze_screenshot():
    """Store a demo screenshot and record an OCR placeholder analysis."""
    screenshot = request.files.get("screenshot")
    if not screenshot or not screenshot.filename:
        return redirect(url_for("index", analyst="missing"))

    try:
        upload = save_demo_screenshot(screenshot, SCREENSHOT_UPLOAD_DIR)
    except ValueError:
        return redirect(url_for("index", analyst="invalid"))

    save_analyst_upload(current_user_id(), upload)
    return redirect(url_for("index", analyst="stored"))


@app.route("/import", methods=["GET", "POST"])
@login_required
def import_workouts():
    user = current_user()
    user_id = user["id"]

    result = None

    if request.method == "POST":
        csv_file = request.files.get("workouts_csv")
        xml_file = request.files.get("health_xml")

        if csv_file and csv_file.filename:
            result = import_workouts_from_csv(csv_file, user_id)
        elif xml_file and xml_file.filename:
            result = import_workouts_from_apple_health_xml(xml_file, user_id)
        else:
            result = {
                "imported": 0,
                "skipped": 0,
                "duplicates": 0,
                "errors": ["Choose a CSV or Apple Health export.xml file before importing."],
            }

    return render_template("import.html", result=result, current_user=user)


@app.route("/ask", methods=["POST"])
@login_required
def ask_agent():
    user = current_user()
    user_id = user["id"]

    question = request.form.get("question", "")
    agent_name = normalize_agent_name(request.form.get("agent"))
    answer = respond_with_memory(user_id, agent_name, question)

    return render_template("index.html", **dashboard_context(user, question))


@app.route("/agent", methods=["GET", "POST"])
@login_required
def agent_api():
    user_id = current_user_id()

    if request.method == "GET":
        return jsonify(
            {
                "name": "RunCoach AI Agent",
                "agents": {
                    AGENT_RICO: (
                        "Rico Runner coaches saved runs, pace trends, "
                        "context, and next workouts."
                    ),
                    AGENT_IGGY: (
                        "Iggy coaches beginner walking routines, breathing, "
                        "stretches, and nature-count tasks."
                    ),
                    AGENT_LUNA: (
                        "Luna Recovery is a passive rooster agent for hydration, "
                        "stretching, rest, gratitude, and gentle wellness reminders."
                    ),
                },
                "internal_data_analyst": (
                    "DataAnalystAgent creates structured summaries for Rico, "
                    "Iggy, and Luna. It does not chat with users."
                ),
                "example": {"question": "Give me a breathing exercise before my run."},
            }
        )

    data = request.get_json(silent=True) or {}
    question = data.get("question", "")
    agent_name = normalize_agent_name(data.get("agent"))
    answer = respond_with_memory(user_id, agent_name, question)

    return jsonify({"answer": answer, "agent": agent_name})


@app.route("/planner")
@login_required
def planner():
    user = current_user()
    week_start = parse_planner_week_start(request.args.get("week_start"))
    week_end = week_start + timedelta(days=6)
    return render_template(
        "planner.html",
        current_user=user,
        week_start=week_start.isoformat(),
        week_label=(
            f"{week_start.strftime('%b %d')} – "
            f"{week_end.strftime('%b %d, %Y')}"
        ),
        previous_week=(week_start - timedelta(days=7)).isoformat(),
        next_week=(week_start + timedelta(days=7)).isoformat(),
        calendar_days=planner_calendar_days(user["id"], week_start),
    )


@app.route("/planner/generate", methods=["POST"])
@login_required
def generate_weekly_plan():
    user_id = current_user_id()
    week_start = parse_planner_week_start(request.form.get("week_start"))
    preferred_time = request.form.get("preferred_time", "07:00")
    goal = request.form.get("goal", "")
    summary = build_private_agent_summary(user_id, get_all_runs(user_id))
    events, source = WeeklyPlannerAgent().generate(
        week_start,
        preferred_time,
        goal,
        summary,
    )
    save_generated_plan(user_id, events, week_start, source)
    flash(
        f"{len(events)} workouts added using {source}.",
        "success",
    )
    return redirect(url_for("planner", week_start=week_start.isoformat()))


@app.route("/planner/event", methods=["POST"])
@login_required
def add_planner_event():
    event_day = parse_planner_week_start(request.form.get("event_date"))
    week_start = event_day - timedelta(days=event_day.weekday())
    try:
        add_personal_planner_event(current_user_id(), request.form)
    except ValueError as error:
        flash(str(error), "error")
    else:
        flash("Personal event added.", "success")
    return redirect(url_for("planner", week_start=week_start.isoformat()))


@app.route("/planner/event/<int:event_id>/toggle", methods=["POST"])
@login_required
def toggle_planner_event(event_id):
    connection = get_database_connection()
    try:
        connection.execute(
            """
            UPDATE planner_events
            SET is_completed = CASE is_completed WHEN 1 THEN 0 ELSE 1 END
            WHERE id = ? AND user_id = ?
            """,
            (event_id, current_user_id()),
        )
        connection.commit()
    finally:
        connection.close()
    return redirect(request.referrer or url_for("planner"))


@app.route("/planner/calendar.ics")
@login_required
def planner_calendar():
    start = parse_planner_week_start(request.args.get("week_start"))
    events = get_planner_events(
        current_user_id(),
        start,
        start + timedelta(days=6),
    )
    return Response(
        build_calendar_ics(events),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=runcoach-week.ics"
        },
    )


@app.route("/planner/email", methods=["POST"])
@login_required
def email_weekly_plan():
    user = current_user()
    start = parse_planner_week_start(request.form.get("week_start"))
    events = get_planner_events(
        user["id"],
        start,
        start + timedelta(days=6),
    )
    if not events:
        flash("Add or generate events before emailing your week.", "error")
        return redirect(url_for("planner", week_start=start.isoformat()))
    sent, message = PlanEmailService().send_week(
        user["email"],
        events,
        build_calendar_ics(events),
    )
    flash(message, "success" if sent else "warning")
    return redirect(url_for("planner", week_start=start.isoformat()))


@app.route("/walk-task/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_walk_task_route(task_id):
    toggle_walk_task(task_id, current_user_id())
    return redirect(url_for("index", walk_task=1))


@app.route("/walk-task/reset", methods=["POST"])
@login_required
def reset_walk_tasks_route():
    reset_walk_tasks(current_user_id())
    return redirect(url_for("index", walk_task=1))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    seed_demo_user()

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Enter an email and password."
        elif len(password) < 6:
            error = "Use at least 6 characters for the password."
        else:
            try:
                user_id = create_user(email, password)
            except sqlite3.IntegrityError:
                error = "An account with that email already exists."
            else:
                establish_user_session(user_id)
                return redirect(url_for("index", welcome=1))

    return render_template(
        "auth.html",
        mode="signup",
        error=error,
        demo_email=DEMO_EMAIL,
        demo_password=DEMO_PASSWORD,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    seed_demo_data()

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = get_user_by_email(email)

        if user and check_password_hash(user["password_hash"], password):
            establish_user_session(user["id"], is_demo=user["email"] == DEMO_EMAIL)
            return redirect(url_for("index", welcome=1))

        error = "Email or password was not correct."

    return render_template(
        "auth.html",
        mode="login",
        error=error,
        demo_email=DEMO_EMAIL,
        demo_password=DEMO_PASSWORD,
    )


@app.route("/demo-login", methods=["POST"])
def demo_login():
    """Log evaluators into the privacy-safe demo account in one click."""
    demo_user_id = reset_demo_account()
    establish_user_session(demo_user_id, is_demo=True)
    return redirect(url_for("index", welcome=1))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/coach-library")
def coach_library_api():
    return jsonify({"items": get_coach_library_items()})


if __name__ == "__main__":
    setup_database()
    seed_demo_data()
    seed_coach_library()
    app._db_setup_done = True
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
