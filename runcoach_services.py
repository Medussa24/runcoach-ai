"""Pure coaching and dashboard helpers for RunCoach AI."""

from urllib.parse import quote_plus


RUNNERS_WORLD_BEGINNER_URL = (
    "https://www.runnersworld.com/beginner/a71605580/beginner-runner-faqs/"
)
RUNNERS_WORLD_FORM_URL = (
    "https://www.runnersworld.com/health-injuries/a71202281/"
    "guide-to-running-form-program-new-runner/"
)
WORLD_ATHLETICS_ROAD_RACES_URL = (
    "https://worldathletics.org/competitions/world-athletics-label-road-races"
)
CDC_WATER_URL = (
    "https://www.cdc.gov/healthy-weight-growth/water-healthy-drinks/index.html"
)


def calculate_pace(distance, duration):
    """Return minutes per mile."""
    if distance <= 0:
        return 0
    return duration / distance


def format_pace(pace):
    """Turn a decimal pace into a mm:ss string."""
    minutes = int(pace)
    seconds = round((pace - minutes) * 60)

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}"


def youtube_search_url(query):
    """Create a safe YouTube search URL for coaching resources."""
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def coach_resource_links(category, title):
    """Return compact external resources for one coaching card."""
    category_links = {
        "Breathing Exercise": [
            ("Videos", youtube_search_url("running breathing exercises for beginners")),
            ("Beginner Tips", RUNNERS_WORLD_BEGINNER_URL),
        ],
        "Stretch": [
            ("Videos", youtube_search_url("runner stretching routine")),
            ("Form Guide", RUNNERS_WORLD_FORM_URL),
        ],
        "Running Style": [
            ("Form Guide", RUNNERS_WORLD_FORM_URL),
            ("Athlete Videos", youtube_search_url("elite runner form tips")),
        ],
        "Run Type": [
            ("World Athletics", "https://worldathletics.org/"),
            ("Olympics", "https://olympics.com/en/sports/athletics/"),
        ],
        "Timed Run": [
            ("Guided Runs", youtube_search_url("20 minute guided easy run")),
            ("Nike Running", "https://www.nike.com/nrc-app"),
        ],
        "Distance Run": [
            ("Road Races", WORLD_ATHLETICS_ROAD_RACES_URL),
            ("Running Shoes", "https://www.nike.com/w/running-shoes-37v7jzy7ok"),
        ],
        "Hydration": [
            ("Hydration Videos", youtube_search_url("runner hydration tips beginners")),
            ("CDC Water", CDC_WATER_URL),
        ],
        "Rest": [
            ("Recovery Videos", youtube_search_url("runner rest day recovery tips")),
            ("Sleep Foundation", "https://www.sleepfoundation.org/physical-activity"),
        ],
        "Recovery": [
            ("Recovery Videos", youtube_search_url("easy recovery run tips beginners")),
            ("Runner Recovery", "https://www.runnersworld.com/training/a20860803/recovery-run/"),
        ],
        "Stretching": [
            ("Stretch Videos", youtube_search_url("post run stretches beginners")),
            ("Form Guide", RUNNERS_WORLD_FORM_URL),
        ],
        "Warmups": [
            ("Warmup Videos", youtube_search_url("beginner running warmup drills")),
            ("Nike Running", "https://www.nike.com/nrc-app"),
        ],
        "Cooldowns": [
            ("Cooldown Videos", youtube_search_url("runner cooldown routine beginners")),
            ("World Athletics", "https://worldathletics.org/"),
        ],
        "Meditation": [
            ("Meditation Videos", youtube_search_url("guided meditation for athletes short")),
            ("UCLA Mindful", "https://www.uclahealth.org/programs/marc/free-guided-meditations"),
        ],
        "Gratitude": [
            ("Gratitude Videos", youtube_search_url("gratitude practice athletes motivation")),
            ("Greater Good", "https://greatergood.berkeley.edu/topic/gratitude"),
        ],
        "Breathing": [
            ("Breathing Videos", youtube_search_url("breathing exercises for running beginners")),
            ("Beginner Tips", RUNNERS_WORLD_BEGINNER_URL),
        ],
        "Beginner Walking": [
            ("Walking Videos", youtube_search_url("beginner walk run routine")),
            ("Beginner Tips", RUNNERS_WORLD_BEGINNER_URL),
        ],
        "Easy Runs": [
            ("Easy Run Videos", youtube_search_url("easy run pace tips beginner")),
            ("World Athletics", "https://worldathletics.org/"),
        ],
        "Motivation": [
            ("Motivation Shorts", youtube_search_url("running motivation shorts")),
            ("Olympics", "https://olympics.com/en/sports/athletics/"),
        ],
        "Bad Day Reset": [
            ("Walk Reset Videos", youtube_search_url("10 minute walking motivation reset")),
            ("Mindful Videos", youtube_search_url("one minute breathing reset")),
        ],
        "Sleep": [
            ("Sleep Videos", youtube_search_url("sleep recovery for runners")),
            ("Sleep Foundation", "https://www.sleepfoundation.org/physical-activity"),
        ],
        "Consistency": [
            ("Habit Videos", youtube_search_url("running consistency tips beginners")),
            ("Nike Running", "https://www.nike.com/nrc-app"),
        ],
        "Pace Awareness": [
            ("Pace Videos", youtube_search_url("running pace awareness tips beginners")),
            ("Running Shoes", "https://www.nike.com/w/running-shoes-37v7jzy7ok"),
        ],
    }

    links = list(category_links.get(category, []))
    links.append(("Search", youtube_search_url(f"{title} running coaching tips")))
    return links[:3]


def video_tip_links():
    """Return beginner-friendly coaching video searches."""
    queries = [
        ("Running form tips", "beginner running form tips shorts"),
        ("Warmup drills", "beginner running warmup drills shorts"),
        ("Post-run stretches", "post run stretches for beginners shorts"),
        ("Breathing while running", "breathing tips for running beginners shorts"),
        ("Recovery run tips", "recovery run tips beginners shorts"),
    ]
    return [{"title": title, "url": youtube_search_url(query)} for title, query in queries]


def build_dashboard_visuals(runs):
    """Prepare chart and map data for the dashboard."""
    if not runs:
        return {
            "total_distance": 0,
            "average_pace": None,
            "longest_run": 0,
            "recent_runs": [],
            "distance_points": "",
            "pace_points": "",
            "cumulative_points": "",
            "distance_growth": 0,
            "pace_change_seconds": 0,
            "total_duration": 0,
            "latest_route": None,
            "video_tips": video_tip_links(),
        }

    total_distance = sum(run["distance"] for run in runs)
    average_pace = sum(run["pace"] for run in runs) / len(runs)
    recent_runs = list(reversed(runs[:10]))
    max_distance = max(run["distance"] for run in recent_runs) or 1
    max_pace = max(run["pace"] for run in recent_runs) or 1
    min_distance = min(run["distance"] for run in recent_runs)
    min_pace = min(run["pace"] for run in recent_runs)
    distance_range = max_distance - min_distance
    pace_range = max_pace - min_pace
    cumulative_distance = 0
    latest_route = next(
        (
            run
            for run in runs
            if run.get("route_type") or run.get("route_notes") or run.get("weather_summary")
        ),
        None,
    )
    chart_runs = []
    for index, run in enumerate(recent_runs):
        cumulative_distance += run["distance"]
        x_position = 8 if len(recent_runs) == 1 else 8 + (84 * index / (len(recent_runs) - 1))
        distance_score = 0.5 if not distance_range else (run["distance"] - min_distance) / distance_range
        pace_score = 0.5 if not pace_range else (max_pace - run["pace"]) / pace_range
        cumulative_score = cumulative_distance / total_distance if total_distance else 0
        chart_runs.append({
            "date": run["run_date"],
            "short_date": run["run_date"][-5:],
            "distance": run["distance"],
            "pace": run["pace"],
            "pace_label": format_pace(run["pace"]),
            "distance_width": max(8, round((run["distance"] / max_distance) * 100)),
            "pace_width": max(8, round((run["pace"] / max_pace) * 100)),
            "x": round(x_position, 2),
            "distance_y": round(88 - distance_score * 70, 2),
            "pace_y": round(88 - pace_score * 70, 2),
            "cumulative_y": round(88 - cumulative_score * 70, 2),
        })

    oldest_run = recent_runs[0]
    latest_run = recent_runs[-1]
    distance_growth = (
        ((latest_run["distance"] - oldest_run["distance"]) / oldest_run["distance"]) * 100
        if oldest_run["distance"]
        else 0
    )
    pace_change_seconds = (latest_run["pace"] - oldest_run["pace"]) * 60
    return {
        "total_distance": total_distance,
        "average_pace": average_pace,
        "longest_run": max(run["distance"] for run in runs),
        "recent_runs": chart_runs,
        "distance_points": " ".join(f'{run["x"]},{run["distance_y"]}' for run in chart_runs),
        "pace_points": " ".join(f'{run["x"]},{run["pace_y"]}' for run in chart_runs),
        "cumulative_points": " ".join(f'{run["x"]},{run["cumulative_y"]}' for run in chart_runs),
        "distance_growth": distance_growth,
        "pace_change_seconds": pace_change_seconds,
        "total_duration": sum(run["duration"] for run in runs),
        "latest_route": latest_route,
        "video_tips": video_tip_links(),
    }


def motivation_videos():
    """Return playable motivation resources for the dashboard."""
    videos = [
        ("Eddie Pinero", "Keep Showing Up", "Short motivation for consistency and discipline.", "GGaOQvkGsho"),
        ("Maya Angelou", "Courage First", "Resilience and courage for hard training days.", "wbbtRnLIb4s"),
        ("Athlete Mindset", "Super Athletes", "A quick energy boost before a walk, run, or reset.", "h9TddIAkfoY"),
        ("Athlete Mindset", "Comeback Energy", "A short reminder that progress can restart today.", "sj4ri474vD0"),
        ("MotivaShian", "Just Do It", "A playful push to stop waiting and begin.", "ZXsQAXx_ao0"),
        ("Mateusz M", "Why Do We Fall", "Turn setbacks into the energy to stand up again.", "mgmVOuLgFB0"),
        ("Ben Lionel Scott", "No Excuses", "Focused motivation for the days discipline feels difficult.", "wnHW6o8WMas"),
    ]
    return [
        {
            "speaker": speaker,
            "title": title,
            "subtitle": subtitle,
            "video_id": video_id,
            "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0",
            "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        }
        for speaker, title, subtitle, video_id in videos
    ]


def motivation_posts():
    """Return original social-style quote cards for the motivation feed."""
    return [
        {
            "coach": "Rico Runner",
            "quote": "One mile at a time. One promise kept at a time.",
            "caption": "Consistency builds the runner you are becoming.",
            "theme": "rico",
            "symbol": "🏃",
        },
        {
            "coach": "Iggy",
            "quote": "Small steps still move you forward.",
            "caption": "A gentle walk is a real win. Let today be simple.",
            "theme": "iggy",
            "symbol": "🌿",
        },
        {
            "coach": "Luna Recovery",
            "quote": "Rest is part of the plan, not a break from it.",
            "caption": "Hydrate, stretch gently, and protect tonight's sleep.",
            "theme": "luna",
            "symbol": "💧",
        },
        {
            "coach": "RunCoach AI",
            "quote": "Consistency beats intensity you cannot repeat.",
            "caption": "Choose the effort that lets you return tomorrow.",
            "theme": "sunrise",
            "symbol": "☀️",
        },
        {
            "coach": "Iggy",
            "quote": "Breathe. Move. Notice. Begin again.",
            "caption": "Turn your next walk into a quiet outdoor reset.",
            "theme": "ocean",
            "symbol": "🌊",
        },
        {
            "coach": "Rico Runner",
            "quote": "You do not have to be fast to be fearless.",
            "caption": "Wepa! Start where you are and finish proud.",
            "theme": "night",
            "symbol": "⭐",
        },
    ]
def weekly_workout_schedule():
    """Return a simple three-workout week for Rico and Iggy."""
    return {
        "rico": [
            {
                "day": "Monday",
                "title": "Easy Run and Form",
                "duration": "25 minutes",
                "steps": "Walk 5 minutes, run easy for 15 minutes, then walk 5 minutes.",
            },
            {
                "day": "Wednesday",
                "title": "Run-Walk Builder",
                "duration": "24 minutes",
                "steps": "Repeat 2 minutes easy running and 1 minute walking for 8 rounds.",
            },
            {
                "day": "Saturday",
                "title": "Easy Endurance Run",
                "duration": "30 minutes",
                "steps": "Keep a conversational pace and finish with 5 minutes of easy walking.",
            },
        ],
        "iggy": [
            {
                "day": "Tuesday",
                "title": "Nature Walk",
                "duration": "20 minutes",
                "steps": "Walk gently, count 3 trees and 2 birds, then stretch calves.",
            },
            {
                "day": "Thursday",
                "title": "Breathing Walk",
                "duration": "20 minutes",
                "steps": "Walk easy and breathe in for 4 steps and out for 4 steps for 5 minutes.",
            },
            {
                "day": "Sunday",
                "title": "Recovery Walk and Stretch",
                "duration": "15 minutes",
                "steps": "Take a no-pressure walk, then complete gentle hip and calf stretches.",
            },
        ],
    }


def create_feedback(distance, pace, mood, notes, previous_run):
    """Build simple coaching feedback from a run and its predecessor."""
    feedback = []
    if previous_run:
        if pace < previous_run["pace"]:
            feedback.append("Your pace improved. Nice progress!")
        if distance > previous_run["distance"]:
            feedback.append("You increased your distance, which is great endurance work.")
    else:
        feedback.append("Great job logging your first run.")

    difficult_words = ["hard", "tired", "sore", "difficult", "rough", "exhausted"]
    low_moods = ["tired", "sore", "stressed", "bad", "low"]
    if any(word in notes.lower() for word in difficult_words) or mood.lower() in low_moods:
        feedback.append("This run sounded tough, so consider an easier recovery run next.")

    if pace > 11:
        next_workout = "Next workout: 25 to 30 minutes easy, keeping the effort relaxed."
    elif distance < 3:
        next_workout = "Next workout: add a short 5 minute easy jog after your warmup."
    else:
        next_workout = "Next workout: try 4 x 2 minutes a little faster, with easy jogging between."
    feedback.append(next_workout)
    return " ".join(feedback)
