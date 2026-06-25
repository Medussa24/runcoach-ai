"""Gemini-first weekly workout planning with a deterministic fallback."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

from gemini_service import GeminiService


PLANNER_SYSTEM_PROMPT = """
You are the RunCoach AI Weekly Planner. Create a safe, beginner-friendly weekly
movement plan from the supplied user-scoped training summary.

Return JSON only, as an array of 3 or 4 workout objects. Each object must contain:
date (YYYY-MM-DD), start_time (HH:MM, 24-hour), duration_minutes (integer),
title, coach (Rico, Iggy, or Luna), hydration, warmup, main_workout, cooldown,
and notes.

Requirements:
- Keep every workout within the requested seven-day window.
- Use the requested preferred time when practical.
- Include hydration, warm-up, main workout, and cool-down in every workout.
- Prefer repeatable effort over aggressive progression.
- If mood or recovery signals show stress, soreness, fatigue, or burnout,
  lower intensity and include more walking or recovery.
- Do not diagnose, prescribe treatment, or invent user measurements.
""".strip()


class WeeklyPlannerAgent:
    """Generate normalized calendar workouts with Gemini or local rules."""

    def __init__(self, llm_service=None):
        self.llm_service = llm_service or GeminiService()

    def generate(
        self,
        week_start,
        preferred_time,
        goal,
        training_summary,
    ):
        week_start = self._parse_date(week_start)
        preferred_time = self._normalize_time(preferred_time)
        context = {
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            "preferred_time": preferred_time,
            "user_goal": (goal or "build consistent movement").strip()[:300],
            "training_summary": training_summary,
        }
        response = self.llm_service.generate(
            PLANNER_SYSTEM_PROMPT,
            "Create this user's organized weekly workout calendar.",
            context,
            max_output_tokens=3000,
            response_mime_type="application/json",
            thinking_budget=0,
        )
        parsed = self._parse_response(response, week_start, preferred_time)
        if parsed:
            return parsed, "Gemini"
        return self.fallback_plan(
            week_start,
            preferred_time,
            goal,
            training_summary,
        ), "Scripted fallback"

    def fallback_plan(
        self,
        week_start,
        preferred_time="07:00",
        goal="build consistent movement",
        training_summary=None,
    ):
        """Return a complete, safe three-session week without an LLM."""
        week_start = self._parse_date(week_start)
        preferred_time = self._normalize_time(preferred_time)
        summary = training_summary or {}
        recovery_signals = int(summary.get("recovery_frequency") or 0)
        easy_duration = 25 if recovery_signals else 30
        long_duration = 35 if recovery_signals else 45
        goal_text = (goal or "build consistency").strip()[:120]
        return [
            {
                "date": (week_start + timedelta(days=1)).isoformat(),
                "start_time": preferred_time,
                "duration_minutes": easy_duration,
                "title": "Easy Run-Walk Foundation",
                "coach": "Rico",
                "hydration": "Drink a glass of water 30–60 minutes before starting and sip afterward.",
                "warmup": "5 minutes brisk walking, ankle circles, and gentle leg swings.",
                "main_workout": (
                    "Alternate 3 minutes easy running with 2 minutes walking. "
                    "Keep the effort conversational."
                ),
                "cooldown": "5 minutes easy walking, then gentle calf and hip stretches.",
                "notes": f"Purpose: {goal_text}. Finish with energy left.",
            },
            {
                "date": (week_start + timedelta(days=3)).isoformat(),
                "start_time": preferred_time,
                "duration_minutes": 25,
                "title": "Nature Reset Walk",
                "coach": "Iggy",
                "hydration": "Bring water in warm weather and take a few sips before leaving.",
                "warmup": "3 minutes easy walking with relaxed shoulders and slow breathing.",
                "main_workout": (
                    "Walk comfortably. Notice 3 colors, 2 sounds, and 1 landmark. "
                    "Use 4-step inhales and 4-step exhales for two minutes."
                ),
                "cooldown": "3 minutes slower walking and a gentle calf stretch on each side.",
                "notes": "A low-pressure movement day that still counts toward consistency.",
            },
            {
                "date": (week_start + timedelta(days=5)).isoformat(),
                "start_time": preferred_time,
                "duration_minutes": long_duration,
                "title": "Steady Endurance Session",
                "coach": "Rico",
                "hydration": "Hydrate before the session and drink again during recovery.",
                "warmup": "7 minutes walking, mobility, and two short relaxed jogging pickups.",
                "main_workout": (
                    "Move at an easy, sustainable effort. Use planned walk breaks "
                    "whenever breathing stops feeling conversational."
                ),
                "cooldown": "5–8 minutes walking, then light calf, hamstring, and hip mobility.",
                "notes": "Consistency matters more than pace. Reduce duration if fatigue is elevated.",
            },
        ]

    def _parse_response(self, response, week_start, preferred_time):
        if not response:
            return None
        text = response.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            raw_items = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(raw_items, list) or not 3 <= len(raw_items) <= 4:
            return None

        normalized = []
        week_end = week_start + timedelta(days=6)
        for item in raw_items:
            if not isinstance(item, dict):
                return None
            try:
                event_date = date.fromisoformat(str(item.get("date", "")))
                duration = int(item.get("duration_minutes", 0))
            except (TypeError, ValueError):
                return None
            required_text = [
                "title",
                "hydration",
                "warmup",
                "main_workout",
                "cooldown",
            ]
            if not week_start <= event_date <= week_end:
                return None
            if not 10 <= duration <= 120:
                return None
            if any(not str(item.get(key, "")).strip() for key in required_text):
                return None
            normalized.append(
                {
                    "date": event_date.isoformat(),
                    "start_time": self._normalize_time(
                        item.get("start_time") or preferred_time
                    ),
                    "duration_minutes": duration,
                    "title": str(item["title"]).strip()[:120],
                    "coach": self._normalize_coach(item.get("coach")),
                    "hydration": str(item["hydration"]).strip()[:600],
                    "warmup": str(item["warmup"]).strip()[:600],
                    "main_workout": str(item["main_workout"]).strip()[:1200],
                    "cooldown": str(item["cooldown"]).strip()[:600],
                    "notes": str(item.get("notes", "")).strip()[:600],
                }
            )
        return sorted(normalized, key=lambda item: (item["date"], item["start_time"]))

    @staticmethod
    def _parse_date(value):
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return date.today()

    @staticmethod
    def _normalize_time(value):
        try:
            return datetime.strptime(str(value), "%H:%M").strftime("%H:%M")
        except ValueError:
            return "07:00"

    @staticmethod
    def _normalize_coach(value):
        coach = str(value or "").strip().title()
        return coach if coach in {"Rico", "Iggy", "Luna"} else "Rico"
