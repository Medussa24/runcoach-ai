"""Select truthful post-run story context without generative decisions."""


def build_story(workout, insights=(), xp_awards=(), reflection=None, profile=None):
    top = next(iter(insights), None)
    story_type = "standard"
    if top and top["type"] in {"longest_run", "comeback", "pace_improvement"}:
        story_type = {"longest_run": "milestone", "pace_improvement": "breakthrough"}.get(top["type"], top["type"])
    return {
        "story_type": story_type,
        "workout": {key: workout.get(key) for key in ("id", "run_date", "distance", "duration", "pace", "avg_heart_rate")},
        "insight": top,
        "xp_awards": list(xp_awards),
        "xp_total": sum(int(item["xp"]) for item in xp_awards),
        "reflection": reflection,
        "profile": profile or {},
    }
