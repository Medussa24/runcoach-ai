"""Deterministic contract evaluation for RunCoach AI agents and fallbacks."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from planner_agent import WeeklyPlannerAgent
from runcoach_agent import (
    DataAnalystAgent,
    IggyWalkAgent,
    LunaRecoveryAgent,
    RicoRunnerAgent,
)
from runcoach_services import format_pace


DEFAULT_DATASET = Path(__file__).parent / "tests" / "eval" / "runcoach_agent_cases.json"


class UnavailableLLM:
    """Force the same deterministic fallback path used during provider outages."""

    def generate(self, *args, **kwargs):
        return None


SAMPLE_RUNS = [
    {
        "run_date": "2026-06-23",
        "distance": 2.0,
        "duration": 24.0,
        "pace": 12.0,
        "mood": "Tired",
        "notes": "Stressful week; keep recovery gentle.",
        "feedback": "Consistency matters more than intensity today.",
        "source": "Manual",
        "workout_type": "Running",
        "imported_from": None,
    },
    {
        "run_date": "2026-06-16",
        "distance": 1.5,
        "duration": 19.5,
        "pace": 13.0,
        "mood": "Good",
        "notes": "Comfortable effort.",
        "feedback": "Good steady work.",
        "source": "Demo",
        "workout_type": "Walking",
        "imported_from": None,
    },
]


def build_response(agent_name, question):
    service = UnavailableLLM()
    if agent_name == "rico":
        return RicoRunnerAgent(
            SAMPLE_RUNS,
            format_pace,
            llm_service=service,
        ).answer(question)
    if agent_name == "iggy":
        return IggyWalkAgent(
            SAMPLE_RUNS,
            [{"title": "Take a ten-minute walk", "is_done": 0}],
            format_pace,
            llm_service=service,
        ).answer(question)
    if agent_name == "luna":
        return LunaRecoveryAgent(
            SAMPLE_RUNS,
            pace_formatter=format_pace,
            analyst_summary={"recovery_frequency": 1},
            llm_service=service,
        ).answer(question)
    if agent_name == "analyst":
        return DataAnalystAgent(
            SAMPLE_RUNS,
            format_pace,
            llm_service=service,
        ).answer(question)
    if agent_name == "planner":
        events, source = WeeklyPlannerAgent(service).generate(
            date(2026, 6, 29),
            "07:00",
            question,
            {"weekly_mileage": 2.0, "recovery_frequency": 1},
        )
        return {"events": events, "source": source}
    raise ValueError(f"Unknown agent: {agent_name}")


def evaluate_case(case):
    response = build_response(case["agent"], case["question"])
    failures = []
    if case["agent"] == "planner":
        events = response["events"]
        required = set(case["required_event_fields"])
        if len(events) < 3:
            failures.append("planner returned fewer than three events")
        for index, event in enumerate(events):
            missing = sorted(required - set(event))
            if missing:
                failures.append(f"event {index + 1} missing: {', '.join(missing)}")
            if not all(event.get(field) for field in required):
                failures.append(f"event {index + 1} contains an empty required field")
    else:
        text = str(response)
        lower_text = text.lower()
        if not text.strip():
            failures.append("response was empty")
        required_any = [term.lower() for term in case.get("required_any", [])]
        if required_any and not any(term in lower_text for term in required_any):
            failures.append("none of the expected coaching concepts appeared")
        for forbidden in case.get("forbidden", []):
            if forbidden.lower() in lower_text:
                failures.append(f"forbidden term appeared: {forbidden}")
    return {
        "id": case["id"],
        "agent": case["agent"],
        "passed": not failures,
        "failures": failures,
    }


def run_evaluation(dataset_path=DEFAULT_DATASET):
    cases = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    results = [evaluate_case(case) for case in cases]
    return {
        "passed": sum(result["passed"] for result in results),
        "total": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(args.dataset)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
