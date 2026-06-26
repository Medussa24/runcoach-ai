"""User-scoped persistence and calendar shaping for the personal planner."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "America/New_York"
SUPPORTED_TIMEZONES = (
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
)


class PlannerStore:
    """Keep planner SQL and display shaping outside the Flask route module."""

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def get_events(self, user_id, start_date=None, end_date=None):
        query = "SELECT * FROM planner_events WHERE user_id = ?"
        parameters = [user_id]
        if start_date:
            query += " AND event_date >= ?"
            parameters.append(str(start_date))
        if end_date:
            query += " AND event_date <= ?"
            parameters.append(str(end_date))
        query += " ORDER BY event_date, start_time, id"

        connection = self.connection_factory()
        try:
            return [
                dict(row)
                for row in connection.execute(query, parameters).fetchall()
            ]
        finally:
            connection.close()

    def save_generated_plan(self, user_id, events, week_start, source):
        week_end = week_start + timedelta(days=6)
        connection = self.connection_factory()
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

    def add_personal_event(self, user_id, form):
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

        connection = self.connection_factory()
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

    def toggle_event(self, event_id, user_id):
        connection = self.connection_factory()
        try:
            connection.execute(
                """
                UPDATE planner_events
                SET is_completed = CASE is_completed WHEN 1 THEN 0 ELSE 1 END
                WHERE id = ? AND user_id = ?
                """,
                (event_id, user_id),
            )
            connection.commit()
        finally:
            connection.close()

    def calendar_days(self, user_id, week_start, timezone_name=DEFAULT_TIMEZONE):
        events = self.get_events(
            user_id,
            week_start,
            week_start + timedelta(days=6),
        )
        by_date = {}
        for event in events:
            by_date.setdefault(event["event_date"], []).append(event)
        today = datetime.now(safe_zoneinfo(timezone_name)).date()
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


def parse_week_start(value=None, timezone_name=DEFAULT_TIMEZONE):
    """Use the requested date or Monday in the user's timezone."""
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    today = datetime.now(safe_zoneinfo(timezone_name)).date()
    return today - timedelta(days=today.weekday())


def normalize_timezone(value):
    return value if value in SUPPORTED_TIMEZONES else DEFAULT_TIMEZONE


def safe_zoneinfo(value):
    try:
        return ZoneInfo(normalize_timezone(value))
    except ZoneInfoNotFoundError:
        return timezone.utc
