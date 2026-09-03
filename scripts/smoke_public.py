"""Run the Tier 1 journey against a public RunCoach AI deployment."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from datetime import date, timedelta
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener


CSRF_INPUT = re.compile(r'name="csrf_token"\s+value="([^"]+)"')
CSRF_META = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"')
WEEK_START = re.compile(r'name="week_start"\s+value="([0-9]{4}-[0-9]{2}-[0-9]{2})"')


class SmokeFailure(RuntimeError):
    """Raised when a live smoke assertion fails."""


class PublicClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = build_opener(
            HTTPCookieProcessor(CookieJar()),
            HTTPSHandler(context=ssl.create_default_context()),
        )

    def request(
        self,
        path: str,
        *,
        data: dict[str, str] | None = None,
        json_data: dict[str, str] | None = None,
        csrf: str | None = None,
    ) -> tuple[int, str, str]:
        headers = {"User-Agent": "RunCoach-Tier1-Smoke/1.0"}
        payload = None
        if data is not None:
            payload = urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if json_data is not None:
            payload = json.dumps(json_data).encode()
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRFToken"] = csrf
        response = self.opener.open(
            Request(f"{self.base_url}{path}", data=payload, headers=headers),
            timeout=self.timeout,
        )
        return response.status, response.geturl(), response.read().decode("utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def extract(pattern: re.Pattern[str], html: str, label: str) -> str:
    match = pattern.search(html)
    if not match:
        raise SmokeFailure(f"Could not find {label} in the live page.")
    return match.group(1)


def run(base_url: str, timeout: float, include_plan: bool) -> None:
    client = PublicClient(base_url, timeout)

    status, _, body = client.request("/health")
    require(status == 200 and json.loads(body).get("status") == "ok", "Health check failed.")
    print("PASS health")

    status, _, login = client.request("/login")
    require(status == 200 and "Explore Demo" in login, "Demo entry is unavailable.")
    csrf = extract(CSRF_INPUT, login, "login CSRF token")
    status, url, dashboard = client.request("/demo-login", data={"csrf_token": csrf})
    require(status == 200 and url.endswith("/?welcome=1"), "Demo login did not reach Today.")
    require("Welcome back" in dashboard, "Today page did not render after demo login.")
    print("PASS demo login")

    status, _, log_page = client.request("/log-workout")
    require(status == 200, "Workout form did not load.")
    csrf = extract(CSRF_INPUT, log_page, "workout CSRF token")
    status, url, saved = client.request(
        "/log-workout",
        data={
            "csrf_token": csrf,
            "run_date": date.today().isoformat(),
            "duration_hours": "0",
            "duration_minutes": "30",
            "duration_seconds": "0",
            "distance": "3",
            "distance_unit": "mi",
            "avg_heart_rate": "145",
        },
    )
    require(status == 200 and "saved=1" in url, "Workout save did not complete.")
    require("3.0 miles" in saved and "10:00" in saved, "Saved pace evidence is missing.")
    print("PASS workout save and 10:00 pace")

    csrf = extract(CSRF_META, saved, "agent CSRF token")
    status, _, response = client.request(
        "/agent",
        json_data={"agent": "rico", "question": "What should my next workout be?"},
        csrf=csrf,
    )
    answer = json.loads(response).get("answer", "")
    require(status == 200 and len(answer.strip()) >= 20, "Rico did not return a useful response.")
    print("PASS Rico recommendation")

    status, _, progress = client.request("/progress")
    require(status == 200 and "3.00 mi" in progress and "30.0 min" in progress, "Workout history is missing the saved run.")
    print("PASS persisted workout history")

    status, _, planner = client.request("/planner")
    require(status == 200 and "Planner synced with 2 saved workouts" in planner, "My Plan did not sync workout history.")
    if include_plan:
        csrf = extract(CSRF_INPUT, planner, "planner CSRF token")
        week_start = extract(WEEK_START, planner, "planner week start")
        status, _, planner = client.request(
            "/planner/generate",
            data={
                "csrf_token": csrf,
                "week_start": week_start,
                "preferred_time": "07:00",
                "goal": "Build consistency safely",
            },
        )
        require(status == 200 and "workouts added using" in planner, "Weekly plan generation failed.")
        require(planner.count("planner-week-card") >= 3, "Generated plan has fewer than three workouts.")
        print("PASS My Plan generation")
    else:
        print("PASS My Plan sync")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Public RunCoach base URL")
    parser.add_argument("--timeout", type=float, default=60, help="Per-request timeout in seconds")
    parser.add_argument("--include-plan", action="store_true", help="Generate and validate a weekly plan")
    args = parser.parse_args()
    try:
        run(args.url, args.timeout, args.include_plan)
    except (SmokeFailure, HTTPError, URLError, json.JSONDecodeError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    print("Tier 1 public smoke flow passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
