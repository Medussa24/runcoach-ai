"""Deterministic, local quality checks for RunCoach AI.

Sentinel QA is an internal agent. It never chats with users or calls an LLM.
It verifies application contracts and caches the latest report for the dashboard.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


class SentinelQA:
    """Run bounded health checks without polling or external services."""

    def __init__(self, flask_app, project_root: Path, temp_root: Path | None = None):
        self.flask_app = flask_app
        self.project_root = Path(project_root)
        self.temp_root = Path(temp_root or tempfile.gettempdir())
        self._lock = threading.Lock()
        self._last_report = self._not_checked_report()

    @staticmethod
    def _not_checked_report():
        return {
            "agent": "Sentinel QA",
            "app_status": "Not checked yet",
            "last_check_time": "Never",
            "tests_passed": 0,
            "checks_passed": 0,
            "checks_total": 0,
            "warnings_count": 1,
            "status": "Needs Review",
            "warnings": ["Run the first manual health check."],
            "test_summary": "Defensive tests have not run in this process.",
        }

    def get_report(self):
        """Return a copy so templates cannot mutate shared state."""
        return dict(self._last_report)

    def run_health_check(self, demo_user_id: int, include_test_suite: bool = True):
        """Run one bounded check and cache its result.

        A non-blocking lock prevents repeated clicks from starting overlapping
        pytest processes. No background timer or polling loop is used.
        """
        if not self._lock.acquire(blocking=False):
            report = self.get_report()
            report["warnings"] = ["A Sentinel QA check is already running."]
            report["warnings_count"] = 1
            report["status"] = "Warning"
            return report

        try:
            checks = self._run_route_checks(demo_user_id)
            test_result = self._run_pytest() if include_test_suite else {
                "passed": 0,
                "warning": None,
                "summary": "Pytest skipped for this lightweight check.",
            }

            warnings = [check["message"] for check in checks if not check["passed"]]
            if test_result["warning"]:
                warnings.append(test_result["warning"])

            passed_checks = sum(check["passed"] for check in checks)
            health_route_ok = any(
                check["name"] == "health route" and check["passed"] for check in checks
            )

            if not health_route_ok or len(warnings) >= 3:
                status = "Needs Review"
            elif warnings:
                status = "Warning"
            else:
                status = "Healthy"

            report = {
                "agent": "Sentinel QA",
                "app_status": "Online" if health_route_ok else "Issues found",
                "last_check_time": datetime.now(timezone.utc).astimezone().strftime(
                    "%Y-%m-%d %I:%M:%S %p %Z"
                ),
                "tests_passed": test_result["passed"],
                "checks_passed": passed_checks,
                "checks_total": len(checks),
                "warnings_count": len(warnings),
                "status": status,
                "warnings": warnings,
                "test_summary": test_result["summary"],
            }
            self._last_report = report
            return self.get_report()
        finally:
            self._lock.release()

    def _run_route_checks(self, demo_user_id: int):
        checks = []

        def record(name, passed, message):
            checks.append({"name": name, "passed": bool(passed), "message": message})

        with self.flask_app.test_client() as client:
            login = client.get("/login")
            login_html = login.get_data(as_text=True)
            record("login route", login.status_code == 200, "/login did not render.")
            record(
                "Try Demo",
                'action="/demo-login"' in login_html and "Try Demo" in login_html,
                "Try Demo form is missing from the login page.",
            )

            health = client.get("/health")
            record(
                "health route",
                health.status_code == 200 and health.get_json() == {"status": "ok"},
                "/health did not return the expected response.",
            )

            with client.session_transaction() as session:
                session["user_id"] = demo_user_id

            dashboard = client.get("/")
            dashboard_html = dashboard.get_data(as_text=True)
            record("dashboard route", dashboard.status_code == 200, "/ did not render.")
            record(
                "coach rendering",
                all(
                    name in dashboard_html
                    for name in ("Rico Runner", "Iggy", "Luna Recovery")
                ),
                "One or more coach panels did not render.",
            )
            record(
                "previous runs",
                "Previous Runs" in dashboard_html and "run-card" in dashboard_html,
                "Previous Runs did not render demo workout content.",
            )

            imports = client.get("/import")
            record(
                "imports page",
                imports.status_code == 200 and "Import" in imports.get_data(as_text=True),
                "/import did not render.",
            )

            agent = client.get("/agent")
            agent_routes = {
                rule.rule: rule.methods for rule in self.flask_app.url_map.iter_rules()
            }
            record(
                "agent API",
                agent.status_code == 200 and "agents" in (agent.get_json() or {}),
                "The agent API did not return its agent registry.",
            )
            record(
                "chat endpoints",
                "POST" in agent_routes.get("/agent", set())
                and "POST" in agent_routes.get("/ask", set()),
                "One or more chat POST endpoints are unavailable.",
            )

        return checks

    def _run_pytest(self):
        self.temp_root.mkdir(parents=True, exist_ok=True)
        temp_directory = Path(
            tempfile.mkdtemp(prefix="runcoach-sentinel-", dir=self.temp_root)
        )
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp={temp_directory / 'pytest'}",
        ]
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return {
                "passed": 0,
                "warning": f"Defensive test suite could not finish: {error}",
                "summary": "Pytest did not complete.",
            }
        finally:
            shutil.rmtree(temp_directory, ignore_errors=True)

        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        passed_match = re.search(r"(\d+) passed", output)
        passed = int(passed_match.group(1)) if passed_match else 0
        summary = output.splitlines()[-1] if output else "Pytest returned no output."
        warning = None if result.returncode == 0 else f"Defensive tests failed: {summary}"
        return {"passed": passed, "warning": warning, "summary": summary}
