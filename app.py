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
from planner_store import (
    DEFAULT_TIMEZONE,
    SUPPORTED_TIMEZONES,
    PlannerStore,
    normalize_timezone,
    parse_week_start,
    safe_zoneinfo,
)
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
DATABASE = Path(os.environ.get("RUNCOACH_DATABASE", BASE_DIR / "runs.db"))
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


planner_store = PlannerStore(get_database_connection)
get_planner_events = planner_store.get_events
save_generated_plan = planner_store.save_generated_plan
add_personal_planner_event = planner_store.add_personal_event
planner_calendar_days = planner_store.calendar_days


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
                timezone TEXT NOT NULL DEFAULT 'America/New_York',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_user_columns(connection)
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS community_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                location TEXT NOT NULL,
                pace_group TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS health_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_user_id TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_expires_at TEXT,
                sync_enabled INTEGER DEFAULT 1,
                last_synced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, provider)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS imported_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                external_activity_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                distance REAL NOT NULL,
                duration REAL NOT NULL,
                pace REAL NOT NULL,
                avg_heart_rate INTEGER,
                max_heart_rate INTEGER,
                calories INTEGER,
                steps INTEGER,
                source_name TEXT,
                raw_summary TEXT,
                is_approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, external_activity_id)
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


def ensure_user_columns(connection):
    """Add profile preferences to older users tables."""
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "timezone" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN timezone TEXT "
            "NOT NULL DEFAULT 'America/New_York'"
        )
    if "language" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN language TEXT "
            "NOT NULL DEFAULT 'en'"
        )
    if "accessibility_mode" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN accessibility_mode TEXT "
            "NOT NULL DEFAULT 'standard'"
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


def get_user_timezone(user_id):
    """Return a supported display timezone for one user."""
    user = get_user_by_id(user_id)
    return normalize_timezone(user["timezone"] if user else DEFAULT_TIMEZONE)


def update_user_timezone(user_id, timezone_name):
    """Persist one user's planner timezone."""
    timezone_name = normalize_timezone(timezone_name)
    connection = get_database_connection()
    try:
        connection.execute(
            "UPDATE users SET timezone = ? WHERE id = ?",
            (timezone_name, user_id),
        )
        connection.commit()
    finally:
        connection.close()
    return timezone_name


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
    timezone_name = get_user_timezone(user_id)
    today = datetime.now(safe_zoneinfo(timezone_name)).date()
    upcoming_events = get_planner_events(
        user_id,
        today,
        today + timedelta(days=14),
    )
    next_plan_event = next(
        (event for event in upcoming_events if not event["is_completed"]),
        None,
    )

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
        "next_plan_event": next_plan_event,
        "planner_timezone": timezone_name,
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
    timezone_name = get_user_timezone(user["id"])
    week_start = parse_week_start(request.args.get("week_start"), timezone_name)
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
        calendar_days=planner_calendar_days(
            user["id"],
            week_start,
            timezone_name,
        ),
        timezone_name=timezone_name,
        supported_timezones=SUPPORTED_TIMEZONES,
    )


@app.route("/planner/generate", methods=["POST"])
@login_required
def generate_weekly_plan():
    user_id = current_user_id()
    week_start = parse_week_start(
        request.form.get("week_start"),
        get_user_timezone(user_id),
    )
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
    event_day = parse_week_start(
        request.form.get("event_date"),
        get_user_timezone(current_user_id()),
    )
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
    planner_store.toggle_event(event_id, current_user_id())
    return redirect(request.referrer or url_for("planner"))


@app.route("/planner/timezone", methods=["POST"])
@login_required
def update_planner_timezone():
    timezone_name = update_user_timezone(
        current_user_id(),
        request.form.get("timezone"),
    )
    flash(f"Planner timezone updated to {timezone_name}.", "success")
    return redirect(
        url_for(
            "planner",
            week_start=request.form.get("week_start") or None,
        )
    )


@app.route("/planner/calendar.ics")
@login_required
def planner_calendar():
    user_id = current_user_id()
    timezone_name = get_user_timezone(user_id)
    start = parse_week_start(request.args.get("week_start"), timezone_name)
    events = get_planner_events(
        user_id,
        start,
        start + timedelta(days=6),
    )
    return Response(
        build_calendar_ics(events, timezone_name),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=runcoach-week.ics"
        },
    )


@app.route("/planner/email", methods=["POST"])
@login_required
def email_weekly_plan():
    user = current_user()
    timezone_name = get_user_timezone(user["id"])
    start = parse_week_start(request.form.get("week_start"), timezone_name)
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
        build_calendar_ics(events, timezone_name),
        timezone_name,
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


# ----------------------------------------------------
# BILINGUAL & ACCESSIBILITY-FIRST COMMUNITY FEATURES
# ----------------------------------------------------

TRANSLATIONS = {
    "en": {
        "dashboard": "Dashboard",
        "rico_runner": "Rico Runner",
        "iggy_walk_agent": "Iggy Walk Agent",
        "luna_recovery": "Luna Recovery",
        "progress": "Progress",
        "history": "History",
        "my_plan": "My Plan",
        "import_data": "Import Data",
        "coach_library": "Coach Library",
        "log_out": "Log Out",
        "log_a_run": "Log a Run",
        "beginner_path": "Beginner Path",
        "import_workouts": "Import Workouts",
        "ready_to_move": "Ready to move?",
        "save_run": "Save Run",
        "distance_miles": "Distance (miles)",
        "duration_minutes": "Duration (minutes)",
        "run_date": "Run Date",
        "mood": "Mood",
        "notes": "Notes",
        "weather_summary": "Weather Summary",
        "temperature_f": "Temperature (°F)",
        "wind_mph": "Wind (mph)",
        "route_type": "Route Type",
        "route_notes": "Route Notes",
        "avg_heart_rate": "Avg Heart Rate",
        "steps": "Steps",
        "cadence": "Cadence",
        "wearable_style_data": "Wearable-style data",
        "context": "Context",
        "previous_runs": "Previous Runs",
        "progress_visuals": "Progress visuals",
        "inspiration_feed": "Your movement inspiration feed",
        "video_tips": "Video tips",
        "events_community": "Events & Community",
        "shop": "Shop",
        "accessibility_settings": "Accessibility Settings",
        "standard_mode": "Standard Mode",
        "deaf_hoh_mode": "Deaf / Hard-of-hearing Mode",
        "visual_coaching_mode": "Visual Coaching Mode",
        "language": "Language",
        "save_settings": "Save Settings",
        "english": "English",
        "spanish": "Spanish",
        "create_event": "Create an Event",
        "upcoming_events": "Upcoming Events",
        "event_title": "Event Title",
        "description": "Description",
        "event_type": "Event Type",
        "date": "Date",
        "time": "Time",
        "location": "Location",
        "pace_group": "Pace Group",
        "buy_now": "Buy Now",
        "share_facebook": "Share to Facebook"
    },
    "es": {
        "dashboard": "Tablero",
        "rico_runner": "Corredor Rico",
        "iggy_walk_agent": "Agente de Caminata Iggy",
        "luna_recovery": "Recuperación Luna",
        "progress": "Progreso",
        "history": "Historial",
        "my_plan": "Mi Plan",
        "import_data": "Importar Datos",
        "coach_library": "Biblioteca de Entrenadores",
        "log_out": "Cerrar Sesión",
        "log_a_run": "Registrar Carrera",
        "beginner_path": "Ruta de Principiantes",
        "import_workouts": "Importar Entrenamientos",
        "ready_to_move": "¿Listo para moverte?",
        "save_run": "Guardar Carrera",
        "distance_miles": "Distancia (millas)",
        "duration_minutes": "Duración (minutos)",
        "run_date": "Fecha de la Carrera",
        "mood": "Estado de ánimo",
        "notes": "Notas",
        "weather_summary": "Resumen del Clima",
        "temperature_f": "Temperatura (°F)",
        "wind_mph": "Viento (mph)",
        "route_type": "Tipo de Ruta",
        "route_notes": "Notas de la Ruta",
        "avg_heart_rate": "Frecuencia Cardíaca Promedio",
        "steps": "Pasos",
        "cadence": "Cadencia",
        "wearable_style_data": "Datos estilo Wearable",
        "context": "Contexto",
        "previous_runs": "Carreras Anteriores",
        "progress_visuals": "Visualizaciones de Progreso",
        "inspiration_feed": "Tu feed de inspiración de movimiento",
        "video_tips": "Consejos en video",
        "events_community": "Eventos y Comunidad",
        "shop": "Tienda",
        "accessibility_settings": "Ajustes de Accesibilidad",
        "standard_mode": "Modo Estándar",
        "deaf_hoh_mode": "Modo Sordo / Dificultad Auditiva",
        "visual_coaching_mode": "Modo de Entrenamiento Visual",
        "language": "Idioma",
        "save_settings": "Guardar Ajustes",
        "english": "Inglés",
        "spanish": "Español",
        "create_event": "Crear un Evento",
        "upcoming_events": "Próximos Eventos",
        "event_title": "Título del Evento",
        "description": "Descripción",
        "event_type": "Tipo de Evento",
        "date": "Fecha",
        "time": "Hora",
        "location": "Ubicación",
        "pace_group": "Grupo de Ritmo",
        "buy_now": "Comprar ahora",
        "share_facebook": "Compartir en Facebook"
    }
}

@app.context_processor
def inject_translations():
    user_id = session.get("user_id")
    lang = "en"
    if user_id:
        user = get_user_by_id(user_id)
        if user and "language" in dict(user):
            lang = user["language"] or "en"
        else:
            lang = session.get("language", "en")
    else:
        lang = session.get("language", "en")
    
    if lang not in ("en", "es"):
        lang = "en"
        
    def translate(key):
        return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)
    
    accessibility_mode = "standard"
    if user_id:
        user = get_user_by_id(user_id)
        if user and "accessibility_mode" in dict(user):
            accessibility_mode = user["accessibility_mode"] or "standard"
        else:
            accessibility_mode = session.get("accessibility_mode", "standard")
    else:
        accessibility_mode = session.get("accessibility_mode", "standard")
        
    if accessibility_mode not in ("standard", "deaf_hoh", "visual_coaching"):
        accessibility_mode = "standard"

    return dict(_=translate, current_lang=lang, current_accessibility_mode=accessibility_mode)


def create_community_event(creator_id, title, description, event_type, event_date, event_time, location, pace_group, language):
    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO community_events (creator_id, title, description, event_type, event_date, event_time, location, pace_group, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (creator_id, title.strip(), description.strip(), event_type.strip(), event_date.strip(), event_time.strip(), location.strip(), pace_group.strip(), language.strip())
        )
        connection.commit()
    finally:
        connection.close()

def get_display_name(user_row):
    user_dict = dict(user_row)
    if user_dict.get("display_name"):
        return user_dict["display_name"]
    if user_dict.get("username"):
        return user_dict["username"]
    return f"Runner #{user_dict['id']}"

def get_upcoming_events():
    connection = get_database_connection()
    try:
        events = connection.execute(
            """
            SELECT *
            FROM community_events
            ORDER BY event_date ASC, event_time ASC
            """
        ).fetchall()
        result = []
        for e in events:
            evt = dict(e)
            creator = get_user_by_id(evt["creator_id"])
            if creator:
                evt["creator_name"] = get_display_name(creator)
            else:
                evt["creator_name"] = "Runner"
            result.append(evt)
        return result
    finally:
        connection.close()

def get_event_by_id(event_id):
    connection = get_database_connection()
    try:
        event = connection.execute(
            "SELECT * FROM community_events WHERE id = ?",
            (event_id,)
        ).fetchone()
        if event:
            evt = dict(event)
            creator = get_user_by_id(evt["creator_id"])
            if creator:
                evt["creator_name"] = get_display_name(creator)
            else:
                evt["creator_name"] = "Runner"
            return evt
        return None
    finally:
        connection.close()

def is_user_rsvped(user_id, event_id):
    connection = get_database_connection()
    try:
        r = connection.execute(
            "SELECT 1 FROM event_rsvps WHERE user_id = ? AND event_id = ?",
            (user_id, event_id)
        ).fetchone()
        return r is not None
    finally:
        connection.close()

def get_event_rsvps_count(event_id):
    connection = get_database_connection()
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM event_rsvps WHERE event_id = ?",
            (event_id,)
        ).fetchone()[0]
    finally:
        connection.close()

def get_event_rsvp_users(event_id):
    connection = get_database_connection()
    try:
        rows = connection.execute(
            """
            SELECT u.*
            FROM event_rsvps r
            JOIN users u ON r.user_id = u.id
            WHERE r.event_id = ?
            """,
            (event_id,)
        ).fetchall()
        result = []
        for r in rows:
            user_data = dict(r)
            clean_user = {
                "id": user_data["id"],
                "display_name": get_display_name(r)
            }
            result.append(clean_user)
        return result
    finally:
        connection.close()

def toggle_event_rsvp(user_id, event_id):
    connection = get_database_connection()
    try:
        r = connection.execute(
            "SELECT id FROM event_rsvps WHERE user_id = ? AND event_id = ?",
            (user_id, event_id)
        ).fetchone()
        if r:
            connection.execute(
                "DELETE FROM event_rsvps WHERE id = ?",
                (r["id"],)
            )
            action = "removed"
        else:
            connection.execute(
                "INSERT INTO event_rsvps (user_id, event_id) VALUES (?, ?)",
                (user_id, event_id)
            )
            action = "added"
        connection.commit()
        return action
    finally:
        connection.close()

def update_user_settings(user_id, language, accessibility_mode):
    connection = get_database_connection()
    try:
        connection.execute(
            "UPDATE users SET language = ?, accessibility_mode = ? WHERE id = ?",
            (language, accessibility_mode, user_id)
        )
        connection.commit()
    finally:
        connection.close()


@app.route("/set-language", methods=["POST"])
def set_language():
    lang = request.form.get("language", "en")
    if lang not in ("en", "es"):
        lang = "en"
    session["language"] = lang
    
    user_id = current_user_id()
    if user_id:
        connection = get_database_connection()
        try:
            connection.execute("UPDATE users SET language = ? WHERE id = ?", (lang, user_id))
            connection.commit()
        finally:
            connection.close()
            
    return redirect(request.referrer or url_for("index"))


@app.route("/update-settings", methods=["POST"])
@login_required
def update_settings():
    user_id = current_user_id()
    language = request.form.get("language", "en")
    accessibility_mode = request.form.get("accessibility_mode", "standard")
    
    if language not in ("en", "es"):
        language = "en"
    if accessibility_mode not in ("standard", "deaf_hoh", "visual_coaching"):
        accessibility_mode = "standard"
        
    update_user_settings(user_id, language, accessibility_mode)
    session["language"] = language
    session["accessibility_mode"] = accessibility_mode
    flash("Settings updated successfully!", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/events", methods=["GET", "POST"])
@login_required
def events_list():
    user = current_user()
    user_id = user["id"]
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_type = request.form.get("event_type", "").strip()
        event_date = request.form.get("event_date", "").strip()
        event_time = request.form.get("event_time", "").strip()
        location = request.form.get("location", "").strip()
        pace_group = request.form.get("pace_group", "").strip()
        language = request.form.get("language", "").strip()
        
        errors = []
        if not title or len(title) > 120:
            errors.append("Title is required and must be under 120 characters.")
        if not description or len(description) > 1000:
            errors.append("Description is required and must be under 1000 characters.")
        if event_type not in ("run", "walk", "walkathon", "marathon", "practice"):
            errors.append("Invalid event type.")
        if not event_date or not event_time:
            errors.append("Date and time are required.")
        if not location or len(location) > 200:
            errors.append("Location is required and must be under 200 characters.")
        if not pace_group or len(pace_group) > 100:
            errors.append("Pace group is required and must be under 100 characters.")
        if not language or len(language) > 50:
            errors.append("Language is required.")
            
        if errors:
            for err in errors:
                flash(err, "error")
        else:
            create_community_event(user_id, title, description, event_type, event_date, event_time, location, pace_group, language)
            flash("Event created successfully!", "success")
            return redirect(url_for("events_list"))
            
    events = get_upcoming_events()
    for e in events:
        e["rsvped"] = is_user_rsvped(user_id, e["id"])
        e["rsvp_count"] = get_event_rsvps_count(e["id"])
        
    return render_template("events.html", events=events, current_user=user)


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    event = get_event_by_id(event_id)
    if not event:
        return "Event not found", 404
        
    user_id = current_user_id()
    rsvped = False
    if user_id:
        rsvped = is_user_rsvped(user_id, event_id)
        
    rsvp_count = get_event_rsvps_count(event_id)
    rsvp_users = get_event_rsvp_users(event_id)
    
    user = current_user()
    return render_template("event_detail.html", event=event, rsvped=rsvped, rsvp_count=rsvp_count, rsvp_users=rsvp_users, current_user=user)


@app.route("/event/<int:event_id>/rsvp", methods=["POST"])
@login_required
def event_rsvp(event_id):
    user_id = current_user_id()
    event = get_event_by_id(event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events_list"))
        
    action = toggle_event_rsvp(user_id, event_id)
    if action == "added":
        flash("Successfully RSVPed to the event!", "success")
    else:
        flash("Cancelled your RSVP.", "success")
    return redirect(request.referrer or url_for("event_detail", event_id=event_id))


@app.route("/shop")
@login_required
def shop_page():
    user = current_user()
    products = [
        {
            "id": "tshirt",
            "title": "RunCoach AI T-shirt",
            "description": "High-quality, breathable running T-shirt with the RunCoach AI logo.",
            "price": "$25.00",
            "image": "tshirt.png"
        },
        {
            "id": "hoodie",
            "title": "Rico Runner hoodie",
            "description": "Warm and stylish hoodie featuring Rico Runner, perfect for warmups.",
            "price": "$45.00",
            "image": "hoodie.png"
        },
        {
            "id": "walker_shirt",
            "title": "Walker-friendly shirt",
            "description": "Relaxed fit, moisture-wicking shirt designed for comfort during long walks.",
            "price": "$22.00",
            "image": "walker_shirt.png"
        },
        {
            "id": "stickers",
            "title": "Sticker pack",
            "description": "Show your love with custom stickers of Rico Runner, Iggy, and Luna.",
            "price": "$5.00",
            "image": "stickers.png"
        }
    ]
    return render_template("shop.html", products=products, current_user=user)


# ----------------------------------------------------
# HEALTH INTEGRATIONS FOUNDATION
# ----------------------------------------------------

def create_health_connection(user_id, provider, provider_user_id=None, access_token=None, refresh_token=None, token_expires_at=None, sync_enabled=1):
    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO health_connections (user_id, provider, provider_user_id, access_token, refresh_token, token_expires_at, sync_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                provider_user_id=excluded.provider_user_id,
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                token_expires_at=excluded.token_expires_at,
                sync_enabled=excluded.sync_enabled
            """,
            (user_id, provider, provider_user_id, access_token, refresh_token, token_expires_at, sync_enabled)
        )
        connection.commit()
    finally:
        connection.close()

def get_health_connections(user_id):
    connection = get_database_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM health_connections WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        connection.close()

def toggle_health_sync(user_id, provider):
    connection = get_database_connection()
    try:
        conn = connection.execute(
            "SELECT sync_enabled FROM health_connections WHERE user_id = ? AND provider = ?",
            (user_id, provider)
        ).fetchone()
        if conn:
            new_val = 0 if conn["sync_enabled"] else 1
            connection.execute(
                "UPDATE health_connections SET sync_enabled = ? WHERE user_id = ? AND provider = ?",
                (new_val, user_id, provider)
            )
            connection.commit()
            return new_val
        return None
    finally:
        connection.close()

def save_imported_activity(user_id, provider, external_activity_id, activity_type, start_time, end_time, distance, duration, pace, avg_heart_rate=None, max_heart_rate=None, calories=None, steps=None, source_name=None, raw_summary=None):
    connection = get_database_connection()
    try:
        connection.execute(
            """
            INSERT INTO imported_activities (
                user_id, provider, external_activity_id, activity_type, start_time, end_time,
                distance, duration, pace, avg_heart_rate, max_heart_rate, calories, steps,
                source_name, raw_summary, is_approved
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                user_id, provider, external_activity_id, activity_type, start_time, end_time,
                distance, duration, pace, avg_heart_rate, max_heart_rate, calories, steps,
                source_name, raw_summary
            )
        )
        connection.commit()
    finally:
        connection.close()

def get_imported_activities(user_id):
    connection = get_database_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM imported_activities WHERE user_id = ? ORDER BY start_time DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        connection.close()

def convert_imported_activity_to_run(user_id, activity_id):
    connection = get_database_connection()
    try:
        activity = connection.execute(
            "SELECT * FROM imported_activities WHERE id = ? AND user_id = ? AND is_approved = 0",
            (activity_id, user_id)
        ).fetchone()
        if not activity:
            return False
            
        act = dict(activity)
        pace = act["pace"]
        feedback = f"Imported activity from {act['provider'].capitalize()}. Excellent {act['activity_type']}!"
        
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
                act["start_time"][:10],
                act["distance"],
                act["duration"],
                pace,
                "Okay",
                act["raw_summary"] or f"Imported {act['activity_type']} via {act['provider'].capitalize()}.",
                feedback,
                "Not tracked",
                None,
                None,
                "Road",
                None,
                act["avg_heart_rate"],
                act["steps"],
                None,
                act["provider"].capitalize(),
                act["activity_type"].capitalize(),
                act["provider"].capitalize(),
                user_id
            )
        )
        
        connection.execute(
            "UPDATE imported_activities SET is_approved = 1 WHERE id = ?",
            (activity_id,)
        )
        connection.commit()
        return True
    finally:
        connection.close()


@app.route("/integrations")
@login_required
def integrations_page():
    user = current_user()
    user_id = user["id"]
    
    connections = get_health_connections(user_id)
    connections_map = {conn["provider"]: conn for conn in connections}
    
    imported_activities = get_imported_activities(user_id)
    
    for conn in connections_map.values():
        conn["access_token"] = "•" * 12 if conn["access_token"] else None
        conn["refresh_token"] = "•" * 12 if conn["refresh_token"] else None
        
    return render_template(
        "integrations.html",
        current_user=user,
        connections=connections_map,
        imported_activities=imported_activities
    )


@app.route("/integrations/connect/<provider>", methods=["POST"])
@login_required
def connect_mock_provider(provider):
    if provider not in ("strava", "fitbit", "garmin"):
        flash("Invalid provider.", "error")
        return redirect(url_for("integrations_page"))
        
    user_id = current_user_id()
    create_health_connection(
        user_id=user_id,
        provider=provider,
        provider_user_id=f"mock-user-{user_id}",
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
        token_expires_at="2027-01-01 00:00:00",
        sync_enabled=1
    )
    flash(f"Successfully connected to mock {provider.capitalize()}!", "success")
    return redirect(url_for("integrations_page"))


@app.route("/integrations/disconnect/<provider>", methods=["POST"])
@login_required
def disconnect_provider(provider):
    if provider not in ("strava", "fitbit", "garmin"):
        flash("Invalid provider.", "error")
        return redirect(url_for("integrations_page"))
        
    user_id = current_user_id()
    connection = get_database_connection()
    try:
        connection.execute(
            "DELETE FROM health_connections WHERE user_id = ? AND provider = ?",
            (user_id, provider)
        )
        connection.commit()
    finally:
        connection.close()
        
    flash(f"Disconnected from {provider.capitalize()}.", "success")
    return redirect(url_for("integrations_page"))


@app.route("/integrations/toggle/<provider>", methods=["POST"])
@login_required
def toggle_provider_sync(provider):
    user_id = current_user_id()
    res = toggle_health_sync(user_id, provider)
    if res is not None:
        status = "enabled" if res else "disabled"
        flash(f"Syncing {status} for {provider.capitalize()}.", "success")
    else:
        flash("Connection not found.", "error")
    return redirect(url_for("integrations_page"))


@app.route("/integrations/sync", methods=["POST"])
@login_required
def sync_activities():
    user_id = current_user_id()
    connections = get_health_connections(user_id)
    active_providers = [c["provider"] for c in connections if c["sync_enabled"]]
    
    if not active_providers:
        flash("No active connected services with sync enabled.", "error")
        return redirect(url_for("integrations_page"))
        
    import random
    from datetime import datetime, timedelta
    
    imported_count = 0
    errors_count = 0
    
    for provider in active_providers:
        external_id = f"act-{random.randint(100000, 999999)}"
        dist = round(random.uniform(2.0, 6.0), 2)
        dur = round(dist * random.uniform(8.0, 11.0), 2)
        pace_val = dur / dist
        start = (datetime.now() - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            save_imported_activity(
                user_id=user_id,
                provider=provider,
                external_activity_id=external_id,
                activity_type="run",
                start_time=start,
                end_time=None,
                distance=dist,
                duration=dur,
                pace=pace_val,
                avg_heart_rate=random.randint(130, 165),
                max_heart_rate=random.randint(170, 185),
                calories=random.randint(200, 600),
                steps=random.randint(4000, 12000),
                source_name=f"{provider.capitalize()} Wearable",
                raw_summary=f"Afternoon run synced via mock {provider.capitalize()} webhook."
            )
            imported_count += 1
        except Exception:
            errors_count += 1
            
    if imported_count > 0:
        flash(f"Sync complete! Imported {imported_count} new activity/activities.", "success")
    elif errors_count > 0:
        flash("Sync complete. No new workouts found (duplicates skipped).", "success")
    else:
        flash("No workouts found on remote servers.", "success")
        
    return redirect(url_for("integrations_page"))


@app.route("/integrations/activity/<int:activity_id>/approve", methods=["POST"])
@login_required
def approve_imported_activity(activity_id):
    user_id = current_user_id()
    res = convert_imported_activity_to_run(user_id, activity_id)
    if res:
        flash("Activity approved and saved to your run history!", "success")
    else:
        flash("Unable to approve activity (already approved or not found).", "error")
    return redirect(url_for("integrations_page"))


if __name__ == "__main__":
    setup_database()
    seed_demo_data()
    seed_coach_library()
    app._db_setup_done = True
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
