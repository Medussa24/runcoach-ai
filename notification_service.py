"""Optional SMTP email and calendar export helpers for personal plans."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage


class PlanEmailService:
    """Send a weekly plan only when SMTP is explicitly configured."""

    def __init__(self):
        self.host = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.username = os.environ.get("SMTP_USERNAME")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.sender = os.environ.get("SMTP_FROM_EMAIL") or self.username
        self.use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in {
            "1",
            "true",
            "yes",
        }

    @property
    def is_configured(self):
        return bool(self.host and self.sender)

    def send_week(self, recipient, events, calendar_bytes):
        if not self.is_configured:
            return False, (
                "Email reminders are not configured on this server. "
                "Download the calendar file instead."
            )
        message = EmailMessage()
        message["Subject"] = "Your RunCoach AI weekly plan"
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(self._plain_text(events))
        message.add_attachment(
            calendar_bytes,
            maintype="text",
            subtype="calendar",
            filename="runcoach-week.ics",
            params={"method": "PUBLISH"},
        )
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            return False, "The email provider was unavailable. Your calendar is still saved."
        return True, f"Weekly plan sent to {recipient}."

    @staticmethod
    def _plain_text(events):
        lines = ["Your RunCoach AI weekly plan", ""]
        for event in events:
            lines.extend(
                [
                    f"{event['event_date']} at {event['start_time']} — {event['title']}",
                    f"Duration: {event['duration_minutes']} minutes",
                    f"Hydration: {event.get('hydration') or 'Hydrate before and after.'}",
                    f"Warm-up: {event.get('warmup') or 'Begin gently.'}",
                    f"Workout: {event.get('main_workout') or event.get('details') or ''}",
                    f"Cool-down: {event.get('cooldown') or 'Finish with easy movement.'}",
                    "",
                ]
            )
        return "\n".join(lines)


def build_calendar_ics(events):
    """Create a standards-friendly calendar file without external packages."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RunCoach AI//Personal Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for event in events:
        start = datetime.fromisoformat(
            f"{event['event_date']}T{event['start_time']}"
        )
        end = start + timedelta(minutes=int(event["duration_minutes"]))
        description = "\\n".join(
            filter(
                None,
                [
                    f"Hydration: {event.get('hydration') or ''}",
                    f"Warm-up: {event.get('warmup') or ''}",
                    f"Workout: {event.get('main_workout') or event.get('details') or ''}",
                    f"Cool-down: {event.get('cooldown') or ''}",
                    f"Notes: {event.get('notes') or ''}",
                ],
            )
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:runcoach-{event['id']}@runcoach.ai",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{_escape_ics(event['title'])}",
                f"DESCRIPTION:{_escape_ics(description)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _escape_ics(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
