"""Small, deterministic memory helpers for RunCoach AI agents."""

import re


MEMORY_PATTERNS = {
    "name": [
        r"\bmy name is\s+([a-z][a-z' -]{0,39})",
        r"\bcall me\s+([a-z][a-z' -]{0,39})",
    ],
    "goal": [
        r"\bmy goal is\s+(.{3,120})",
        r"\bi want to\s+(.{3,120})",
        r"\bi(?:'m| am) training for\s+(.{3,120})",
    ],
    "favorite_activity": [
        r"\bmy favorite activit(?:y|ies) (?:is|are)\s+(.{2,100})",
        r"\bi (?:really )?(?:like|love|enjoy)\s+(.{2,100})",
    ],
    "struggle": [
        r"\bi struggle with\s+(.{3,120})",
        r"\bmy biggest struggle is\s+(.{3,120})",
        r"\b(.{3,80}) is hard for me\b",
    ],
}


def extract_memory_facts(message):
    """Extract supported personal facts from one user message."""
    text = " ".join((message or "").strip().split())
    lowered = text.lower()
    facts = {}

    for memory_key, patterns in MEMORY_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                value = _clean_value(match.group(1))
                if value:
                    facts[memory_key] = value
                break

    return facts


def pace_improvement_memory(runs, pace_formatter):
    """Describe the latest measurable pace improvement, if one exists."""
    if len(runs) < 2:
        return None

    latest, previous = runs[0], runs[1]
    if latest["pace"] >= previous["pace"]:
        return None

    return (
        f"Improved from {pace_formatter(previous['pace'])} to "
        f"{pace_formatter(latest['pace'])} per mile on the latest run."
    )


def _clean_value(value):
    value = (value or "").strip(" .,!?:;\"'")
    value = re.split(r"[.!?]", value, maxsplit=1)[0].strip()
    return value[:120]
