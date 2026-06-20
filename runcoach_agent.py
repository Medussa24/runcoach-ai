from collections import Counter
from datetime import date, timedelta


class MemoryAwareAgent:
    """Add private conversation, memory, and analyst context to a coach."""

    def __init__(self, agent, conversation=None, memories=None, analyst_summary=None):
        self.agent = agent
        self.conversation = list(conversation or [])[-10:]
        self.memories = memories or {}
        self.analyst_summary = analyst_summary or {}

    def answer(self, question):
        """Answer with remembered facts and recent conversation context."""
        question_text = (question or "").strip()
        lower_question = question_text.lower()

        if any(word in lower_question for word in ["remember", "my name", "my goal", "previous advice"]):
            memory_answer = self._memory_answer()
            if memory_answer:
                return memory_answer

        answer = self.agent.answer(question_text)
        name = self.memories.get("name")
        if name:
            answer = f"{name.title()}, {answer[0].lower() + answer[1:]}"

        analyst_note = self._analyst_note(lower_question)
        if analyst_note:
            answer = f"{answer} {analyst_note}"
        return answer

    def _memory_answer(self):
        labels = {
            "name": "name",
            "goal": "goal",
            "favorite_activity": "favorite activity",
            "struggle": "previous struggle",
            "pace_improvement": "pace improvement",
            "previous_advice": "previous advice",
        }
        facts = [
            f"Your {labels[key]}: {value}"
            for key, value in self.memories.items()
            if key in labels and value
        ]

        recent_user_messages = [
            message["message"]
            for message in self.conversation
            if message.get("sender") == "user"
        ][-2:]
        if recent_user_messages:
            facts.append("Recent conversation: " + " | ".join(recent_user_messages))

        if not facts:
            return "I do not have a saved personal detail yet. Tell me your name, goal, favorite activity, or current struggle."
        return "I remember this for your account only. " + ". ".join(facts) + "."

    def _analyst_note(self, question):
        summary = self.analyst_summary
        if not summary:
            return ""
        if any(word in question for word in ["progress", "week", "mileage", "summary"]):
            return (
                f"Your private Data Analyst summary shows {summary['weekly_mileage']:.2f} "
                f"miles in the latest training week and a longest run of "
                f"{summary['longest_run']:.2f} miles."
            )
        if "pace" in question and summary.get("average_pace_label"):
            return f"Your overall average pace is {summary['average_pace_label']} per mile."
        if any(word in question for word in ["walk", "beginner"]):
            return f"Your saved history includes {summary['walk_frequency']} walking workouts."
        if any(word in question for word in ["recovery", "tired", "rest", "sore"]):
            return f"Your history includes {summary['recovery_frequency']} recovery-need signals."
        return ""


class DataAnalystAgent:
    """Create internal structured training summaries; this agent does not chat."""

    def __init__(self, runs=None, pace_formatter=None):
        self.runs = runs or []
        self.format_pace = pace_formatter

    def summary(self):
        if not self.runs:
            return {
                "weekly_mileage": 0,
                "longest_run": 0,
                "average_pace": None,
                "average_pace_label": None,
                "mood_trends": {},
                "walk_frequency": 0,
                "recovery_frequency": 0,
            }

        dated_runs = []
        for run in self.runs:
            try:
                run_day = date.fromisoformat(run["run_date"][:10])
            except (TypeError, ValueError):
                continue
            dated_runs.append((run_day, run))

        latest_day = max((item[0] for item in dated_runs), default=date.today())
        week_start = latest_day - timedelta(days=6)
        weekly_mileage = sum(
            run["distance"]
            for run_day, run in dated_runs
            if week_start <= run_day <= latest_day
        )
        average_pace = sum(run["pace"] for run in self.runs) / len(self.runs)
        mood_trends = dict(Counter((run.get("mood") or "Unknown") for run in self.runs))
        walk_frequency = sum(
            1
            for run in self.runs
            if "walk" in (run.get("workout_type") or "").lower()
        )
        recovery_words = {"tired", "sore", "stressed", "low"}
        recovery_frequency = sum(
            1
            for run in self.runs
            if (run.get("mood") or "").lower() in recovery_words
            or any(
                word in (run.get("notes") or "").lower()
                for word in ["hard", "tired", "sore", "rough", "recovery"]
            )
        )
        return {
            "weekly_mileage": round(weekly_mileage, 2),
            "longest_run": max(run["distance"] for run in self.runs),
            "average_pace": average_pace,
            "average_pace_label": (
                self.format_pace(average_pace) if self.format_pace else None
            ),
            "mood_trends": mood_trends,
            "walk_frequency": walk_frequency,
            "recovery_frequency": recovery_frequency,
        }


class RunCoachAgent:
    """A small coaching agent that answers questions using saved run data."""

    def __init__(self, runs, pace_formatter, coach_library=None):
        self.runs = runs
        self.format_pace = pace_formatter
        self.coach_library = coach_library or []

    def answer(self, question):
        """Return a helpful coaching answer for the user's question."""
        question_text = (question or "").strip()

        if not question_text:
            return "Ask me about your recent runs, pace, recovery, or next workout."

        if not self.runs:
            return "Log your first run, then I can use your history to coach you."

        lower_question = question_text.lower()

        if self._question_has(lower_question, ["progress", "summary", "summarize"]):
            return self._progress_answer()

        if self._question_has(lower_question, ["compare", "recent"]):
            return self._comparison_answer()

        if self._question_has(lower_question, ["trend", "trending"]):
            return self._pace_trend_answer()

        if self._question_has(
            lower_question,
            ["import", "historical", "history", "apple health"],
        ):
            return self._history_answer()

        if self._question_has(
            lower_question,
            ["weather", "route", "map", "watch", "heart", "cadence"],
        ):
            return self._context_answer()

        if self._question_has(
            lower_question,
            ["bad day", "rough day", "stressed", "sad", "overwhelmed", "walk and talk"],
        ):
            return self._bad_day_answer()

        if self._question_has(lower_question, ["hydrate", "hydration", "water", "drink"]):
            return self._library_answer("Hydration")

        if self._question_has(lower_question, ["sleep", "rest"]):
            return self._library_answer("Rest")

        if self._question_has(lower_question, ["meditate", "meditation", "mindful"]):
            return self._library_answer("Meditation")

        if self._question_has(lower_question, ["gratitude", "thankful"]):
            return self._library_answer("Gratitude")

        if "pace" in lower_question or "fast" in lower_question:
            return self._pace_answer()

        if "distance" in lower_question or "endurance" in lower_question:
            return self._distance_answer()

        if "recovery" in lower_question or "tired" in lower_question or "sore" in lower_question:
            return self._recovery_answer()

        if "breath" in lower_question:
            return self._library_answer("Breathing Exercise")

        if "stretch" in lower_question or "tight" in lower_question:
            return self._library_answer("Stretch")

        if "style" in lower_question or "form" in lower_question or "cadence" in lower_question:
            return self._library_answer("Running Style")

        if "timed" in lower_question or "time" in lower_question:
            return self._library_answer("Timed Run")

        if "mile" in lower_question or "distance run" in lower_question:
            return self._library_answer("Distance Run")

        if "type" in lower_question or "tempo" in lower_question:
            return self._library_answer("Run Type")

        if "next" in lower_question or "workout" in lower_question or "recommend" in lower_question:
            return self._next_workout_answer()

        return self._summary_answer()

    def _question_has(self, question, keywords):
        return any(keyword in question for keyword in keywords)

    def _latest_run(self):
        return self.runs[0]

    def _previous_run(self):
        if len(self.runs) < 2:
            return None
        return self.runs[1]

    def _recent_runs(self, limit=3):
        return self.runs[:limit]

    def _progress_answer(self):
        recent_runs = self._recent_runs()
        latest = self._latest_run()
        total_distance = sum(run["distance"] for run in self.runs)
        average_pace = sum(run["pace"] for run in self.runs) / len(self.runs)

        if len(recent_runs) == 1:
            return (
                f"You have logged 1 run: {latest['distance']:.2f} miles at "
                f"{self.format_pace(latest['pace'])} per mile. Keep logging runs "
                "so I can spot progress trends."
            )

        return (
            f"You have logged {len(self.runs)} runs for {total_distance:.2f} total miles. "
            f"Your average pace is {self.format_pace(average_pace)} per mile. "
            f"Your latest run was {latest['distance']:.2f} miles at "
            f"{self.format_pace(latest['pace'])} per mile. "
            f"{self._pace_trend_sentence()}"
        )

    def _comparison_answer(self):
        latest = self._latest_run()
        previous = self._previous_run()

        if not previous:
            return (
                "You only have one saved run so far. Add another run and I can "
                "compare pace, distance, and effort."
            )

        pace_change = latest["pace"] - previous["pace"]
        distance_change = latest["distance"] - previous["distance"]

        pace_text = (
            "faster"
            if pace_change < 0
            else "slower"
            if pace_change > 0
            else "the same pace"
        )
        distance_text = (
            "longer"
            if distance_change > 0
            else "shorter"
            if distance_change < 0
            else "the same distance"
        )

        return (
            f"Compared with your previous run, your latest run was {distance_text} "
            f"and {pace_text}. Latest: {latest['distance']:.2f} miles at "
            f"{self.format_pace(latest['pace'])} per mile. Previous: "
            f"{previous['distance']:.2f} miles at "
            f"{self.format_pace(previous['pace'])} per mile."
        )

    def _history_answer(self):
        imported_runs = [run for run in self.runs if run.get("imported_from")]

        if not imported_runs:
            return (
                "I do not see imported historical workouts yet. Use Import "
                "Workouts to upload Apple Health export.xml or a workout CSV first."
            )

        total_distance = sum(run["distance"] for run in imported_runs)
        average_pace = sum(run["pace"] for run in imported_runs) / len(imported_runs)
        sources = sorted({run.get("source") or "Unknown" for run in imported_runs})

        return (
            f"I found {len(imported_runs)} imported historical workouts from {', '.join(sources)}. "
            f"Imported distance totals {total_distance:.2f} miles with an average pace of "
            f"{self.format_pace(average_pace)} per mile. I include these workouts "
            "when summarizing progress, "
            f"pace trends, and next-workout guidance."
        )

    def _pace_trend_answer(self):
        return self._pace_trend_sentence()

    def _pace_trend_sentence(self):
        if len(self.runs) < 2:
            return "I need at least two saved runs to describe a pace trend."

        recent_runs = self._recent_runs()
        newest_pace = recent_runs[0]["pace"]
        oldest_pace = recent_runs[-1]["pace"]

        if newest_pace < oldest_pace:
            return (
                "Your recent pace trend is improving. Keep the next workout "
                "controlled so progress stays sustainable."
            )

        if newest_pace > oldest_pace:
            return (
                "Your recent pace trend is slower. That can happen from fatigue, "
                "harder conditions, or building distance, so choose an easier next run."
            )

        return "Your recent pace trend is steady. That is useful base-building consistency."

    def _context_answer(self):
        latest = self._latest_run()
        context = self._context_notes(latest)

        if not context:
            return (
                "I do not see weather, route, or wearable-style data for your "
                "latest run yet. Add optional context fields when logging a run "
                "and I can use them."
            )

        return "For your latest run, I noticed: " + " ".join(context)

    def _pace_answer(self):
        latest = self._latest_run()
        previous = self._previous_run()
        latest_pace = self.format_pace(latest["pace"])

        if previous and latest["pace"] < previous["pace"]:
            return (
                f"Your latest pace was {latest_pace} per mile, faster than your "
                "previous run. That is real progress."
            )

        if previous:
            return (
                f"Your latest pace was {latest_pace} per mile. Keep the next run "
                "relaxed and build consistency."
            )

        return (
            f"Your first saved pace is {latest_pace} per mile. Add more runs so "
            "I can compare your progress."
        )

    def _distance_answer(self):
        latest = self._latest_run()
        previous = self._previous_run()

        if previous and latest["distance"] > previous["distance"]:
            return (
                f"Your latest run was {latest['distance']:.2f} miles, which is "
                "longer than your previous run. Nice endurance progress."
            )

        return (
            f"Your latest run was {latest['distance']:.2f} miles. A small distance "
            "increase next week would be a smart endurance goal."
        )

    def _recovery_answer(self):
        latest = self._latest_run()
        mood = latest["mood"].lower()
        notes = (latest["notes"] or "").lower()
        difficult_words = ["hard", "tired", "sore", "difficult", "rough", "exhausted"]

        if mood in ["tired", "sore", "stressed", "low"] or any(
            word in notes for word in difficult_words
        ):
            return (
                "Your latest run sounds demanding. Make the next run an easy "
                "recovery run for 20 to 30 minutes."
            )

        return (
            "You do not have a strong recovery warning in your latest run. Still, "
            "keep one easy day between harder efforts."
        )

    def _bad_day_answer(self):
        return (
            "Rico says: rough days get low-pressure goals. Try a 10-minute "
            "walk and talk reset, breathe slowly, notice three things around "
            "you, and let that count as today's win. If you feel unsafe or in "
            "immediate danger, contact emergency help or a crisis hotline right away."
        )

    def _next_workout_answer(self):
        latest = self._latest_run()

        if self._needs_recovery(latest):
            return (
                "Next workout: keep it safe with a 20 to 30 minute recovery run "
                "or brisk walk. Stay relaxed and finish feeling fresh."
            )

        if self._hard_context(latest):
            return (
                "Next workout: choose an easy 20 to 30 minute run. Your context "
                "data suggests the last run may have had extra stress, so keep "
                "effort relaxed."
            )

        if latest["pace"] > 11:
            return (
                "Next workout: run 25 to 30 minutes easy and keep the effort comfortable."
            )

        if latest["distance"] < 3:
            return (
                "Next workout: warm up, then add a short 5 minute easy jog "
                "before cooling down."
            )

        return (
            "Next workout: try 4 x 2 minutes slightly faster than normal, "
            "with easy jogging between each repeat."
        )

    def _needs_recovery(self, run):
        mood = run["mood"].lower()
        notes = (run["notes"] or "").lower()
        difficult_words = ["hard", "tired", "sore", "difficult", "rough", "exhausted"]
        return mood in ["tired", "sore", "stressed", "low"] or any(
            word in notes for word in difficult_words
        )

    def _hard_context(self, run):
        temperature = run.get("temperature_f")
        wind = run.get("wind_mph")
        route = (run.get("route_type") or "").lower()
        heart_rate = run.get("avg_heart_rate")
        max_heart_rate = run.get("max_heart_rate")

        return (
            (temperature is not None and temperature >= 80)
            or (wind is not None and wind >= 15)
            or route == "hilly"
            or (heart_rate is not None and heart_rate >= 170)
            or (max_heart_rate is not None and max_heart_rate >= 185)
        )

    def _context_notes(self, run):
        notes = []
        weather = run.get("weather_summary")
        temperature = run.get("temperature_f")
        wind = run.get("wind_mph")
        route = run.get("route_type")
        route_notes = run.get("route_notes")
        heart_rate = run.get("avg_heart_rate")
        max_heart_rate = run.get("max_heart_rate")
        calories = run.get("calories")
        steps = run.get("steps")
        cadence = run.get("cadence")
        source = run.get("source")
        workout_type = run.get("workout_type")
        imported_from = run.get("imported_from")
        end_date = run.get("end_date")
        device = run.get("device")

        if imported_from:
            source_text = f"Imported workout from {source or imported_from}"
            if workout_type:
                source_text += f" ({workout_type})"
            source_text += "."
            notes.append(source_text)

        if end_date:
            notes.append(f"Apple Health end time was {end_date}.")

        if device:
            notes.append(f"Device detail was {device}.")

        if weather:
            weather_text = f"Weather was {weather}"
            if temperature is not None:
                weather_text += f" at {temperature:.0f} F"
            if wind is not None:
                weather_text += f" with {wind:.0f} mph wind"
            weather_text += "."
            notes.append(weather_text)

        if route:
            route_text = f"Route context was {route}"
            if route_notes:
                route_text += f" ({route_notes})"
            route_text += "."
            notes.append(route_text)

        if heart_rate is not None:
            notes.append(f"Average heart rate was {heart_rate} bpm.")

        if max_heart_rate is not None:
            notes.append(f"Max heart rate was {max_heart_rate} bpm.")

        if calories is not None:
            notes.append(f"Calories were {calories}.")

        if cadence is not None:
            notes.append(f"Cadence was {cadence} steps per minute.")

        if steps is not None:
            notes.append(f"Wearable-style step count was {steps}.")

        if self._hard_context(run):
            notes.append(
                "Because the context looks demanding, keep the next workout easy "
                "and avoid stacking hard days."
            )

        return notes

    def _library_answer(self, category):
        items = [item for item in self.coach_library if item["category"] == category]

        if not items:
            return f"I do not have any {category.lower()} items in the coaching library yet."

        item = items[0]
        return (
            f"{item['title']}: {item['description']} "
            f"How to do it: {item['instructions']} "
            f"Best for: {item['recommended_when']}"
        )

    def _summary_answer(self):
        latest = self._latest_run()
        pace = self.format_pace(latest["pace"])
        return (
            f"Your latest run was {latest['distance']:.2f} miles in "
            f"{latest['duration']:.1f} minutes at {pace} per mile. "
            f"Mood was {latest['mood']}. {_sentence_case(latest['feedback'])} "
            f"{' '.join(self._context_notes(latest))}"
        )


def _sentence_case(text):
    if not text:
        return ""
    return text[0].upper() + text[1:]


class IggyWalkAgent:
    """A simple walking coach for beginners who are learning to run."""

    def __init__(self, runs=None, walk_tasks=None, pace_formatter=None):
        self.runs = runs or []
        self.walk_tasks = walk_tasks or []
        self.format_pace = pace_formatter

    def answer(self, question):
        """Return a gentle walking-focused answer."""
        question_text = (question or "").strip()

        if not question_text:
            return (
                "Ask Iggy for a walking routine, breathing task, stretch, or "
                "nature-count checklist."
            )

        lower_question = question_text.lower()

        if self._question_has(
            lower_question,
            ["bad day", "rough day", "stressed", "sad", "overwhelmed", "walk and talk"],
        ):
            return self._bad_day_answer()

        if self._question_has(
            lower_question,
            ["routine", "plan", "walk", "beginner"],
        ):
            return self._routine_answer()

        if "checklist" in lower_question or "task" in lower_question or "todo" in lower_question:
            return self._checklist_answer()

        if "breath" in lower_question:
            return (
                "Iggy breathing task: walk easy, inhale for 4 steps, exhale for "
                "4 steps, and repeat for 2 minutes. Keep your shoulders loose."
            )

        if "stretch" in lower_question or "warm" in lower_question:
            return (
                "Iggy stretch break: do 5 ankle circles each way, 5 gentle leg "
                "swings per side, then a 20 second calf stretch on each leg."
            )

        if self._question_has(
            lower_question,
            ["tree", "bird", "spot", "count", "nature"],
        ):
            return (
                "Iggy nature task: during your walk, count 3 trees, 2 birds, "
                "and 1 safe landmark. This keeps the walk calm, present, and fun."
            )

        if "progress" in lower_question or "done" in lower_question or "complete" in lower_question:
            return self._progress_answer()

        return (
            "Iggy says: start easier than you think. Walk first, breathe steady, "
            "notice your surroundings, then build toward running one small step at a time."
        )

    def _routine_answer(self):
        latest_note = self._latest_training_note()
        return (
            "Iggy's beginner walk routine: 3 minutes easy warmup, 10 minutes comfortable walking, "
            "2 minutes of 4-step breathing, then 3 minutes cool down. During "
            "the walk, spot 3 trees "
            "and 2 birds. Finish with a calf stretch on both sides. "
            f"{latest_note}"
        )

    def _checklist_answer(self):
        if not self.walk_tasks:
            return (
                "Iggy checklist: warm up, walk easy, count trees, count birds, "
                "breathe steady, stretch, and write one feeling note."
            )

        total = len(self.walk_tasks)
        done = sum(1 for task in self.walk_tasks if task.get("is_done"))
        next_task = next((task for task in self.walk_tasks if not task.get("is_done")), None)

        if not next_task:
            return (
                "Iggy checklist complete. Great job. Take a sip of water and "
                "log how the walk felt."
            )

        return (
            f"You have finished {done} of {total} Iggy walk tasks. "
            f"Next task: {next_task['title']}."
        )

    def _progress_answer(self):
        if not self.walk_tasks:
            return "Iggy sees your walking plan ready. Complete one checklist item at a time."

        total = len(self.walk_tasks)
        done = sum(1 for task in self.walk_tasks if task.get("is_done"))

        if done == total:
            return (
                "Iggy sees a completed walk checklist. That is beginner-runner "
                "progress: consistent, calm, and repeatable."
            )

        return (
            f"Iggy sees {done} of {total} walking tasks complete. Keep the pace "
            "easy and finish feeling better than when you started."
        )

    def _latest_training_note(self):
        if not self.runs:
            return "No run history is needed to start this walk."

        latest = self.runs[0]
        if latest.get("workout_type") and "walk" in latest["workout_type"].lower():
            return (
                "Your latest saved workout was walking, so this routine is a "
                "good repeatable base."
            )

        if latest.get("pace") and self.format_pace:
            return (
                f"Your latest saved pace was {self.format_pace(latest['pace'])}; "
                "keep today's walk relaxed."
            )

        return "Use your saved history as context, but keep this walk conversational."

    def _question_has(self, question, keywords):
        return any(keyword in question for keyword in keywords)

    def _bad_day_answer(self):
        return (
            "Iggy says: no performance goal today. Walk gently for 10 minutes, count 3 trees "
            "or safe landmarks, breathe in for 4 steps and out for 4 steps, then write one thing "
            "you survived today. If you feel unsafe or in immediate danger, contact emergency help "
            "or a crisis hotline right away."
        )


class LunaRecoveryAgent:
    """Passive hydration, recovery, and wellness reminders for the dashboard."""

    disclaimer = "Wellness guidance is general and not medical advice."

    def __init__(
        self,
        runs=None,
        walk_tasks=None,
        pace_formatter=None,
        memories=None,
        analyst_summary=None,
    ):
        self.runs = runs or []
        self.walk_tasks = walk_tasks or []
        self.format_pace = pace_formatter
        self.memories = memories or {}
        self.analyst_summary = analyst_summary or {}

    def summary(self):
        latest = self._latest_run()
        name = self.memories.get("name")
        greeting = f"{name.title()}, " if name else ""

        if not latest:
            return (
                f"{greeting}Luna Recovery is ready with water, stretch, breathing, "
                "gratitude, and rest nudges once you begin."
            )

        if self._needs_recovery(latest):
            return (
                f"{greeting}Luna noticed your latest effort may need extra care. Keep the "
                "next move gentle, hydrate, and stretch lightly."
            )

        if self._warm_or_long(latest):
            return f"{greeting}Luna noticed extra hydration may help after that warm or longer workout."

        return (
            f"{greeting}Luna is watching the recovery basics: water, mobility, breathing, "
            f"gratitude, and rest. Your Data Analyst found "
            f"{self.analyst_summary.get('recovery_frequency', 0)} recovery-need signals."
        )

    def cards(self):
        latest = self._latest_run()
        cards = [
            {
                "type": "Hydration",
                "title": "Water Check",
                "message": (
                    "Sip water before you feel thirsty, especially after warm "
                    "or humid movement."
                ),
            },
            {
                "type": "Stretch",
                "title": "Mobility Break",
                "message": (
                    "Every few hours, stand up and do gentle calf, hip, and "
                    "shoulder movement for one minute."
                ),
            },
            {
                "type": "Mindful Reset",
                "title": "One-Minute Breath",
                "message": "Try slow breathing before deciding to skip movement completely.",
            },
            {
                "type": "Gratitude",
                "title": "Body Note",
                "message": "Write down one thing your body helped you do today.",
            },
        ]

        if latest and self._needs_recovery(latest):
            cards.insert(
                0,
                {
                    "type": "Recovery",
                    "title": "Lower The Goal",
                    "message": (
                        "Your latest notes suggest a demanding day. Choose an "
                        "easy walk or rest day and let that count."
                    ),
                },
            )
        elif latest and self._warm_or_long(latest):
            cards.insert(
                0,
                {
                    "type": "Hydration",
                    "title": "Post-Workout Refill",
                    "message": (
                        "Because the last workout had extra stress, add a calm "
                        "water break before the next session."
                    ),
                },
            )
        else:
            cards.insert(
                0,
                {
                    "type": "Bad Day Reset",
                    "title": "Walk And Talk",
                    "message": (
                        "Had a rough day? Try a 10-minute walk and talk reset "
                        "with no pace goal."
                    ),
                },
            )

        return cards[:5]

    def _latest_run(self):
        return self.runs[0] if self.runs else None

    def _needs_recovery(self, run):
        mood = (run.get("mood") or "").lower()
        notes = (run.get("notes") or "").lower()
        difficult_words = ["hard", "tired", "sore", "difficult", "rough", "exhausted", "bad day"]
        return mood in {"tired", "sore", "stressed", "low"} or any(
            word in notes for word in difficult_words
        )

    def _warm_or_long(self, run):
        temperature = run.get("temperature_f")
        duration = run.get("duration") or 0
        distance = run.get("distance") or 0
        return (
            (temperature is not None and temperature >= 80)
            or duration >= 45
            or distance >= 4
        )
