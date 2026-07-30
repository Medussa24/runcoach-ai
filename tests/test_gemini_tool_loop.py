from types import SimpleNamespace

import pytest
from google.genai import types

import app as runcoach
from gemini_service import GeminiService, approve_user_scoped_tool


def response_with_text(text):
    return SimpleNamespace(text=text, function_calls=None, candidates=[])


def response_with_calls(*calls):
    content = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(
                    id=f"call-{index}",
                    name=name,
                    args=args,
                )
            )
            for index, (name, args) in enumerate(calls)
        ],
    )
    return SimpleNamespace(
        text=None,
        function_calls=[part.function_call for part in content.parts],
        candidates=[SimpleNamespace(content=content)],
    )


class ScriptedModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def service_for(*responses):
    models = ScriptedModels(responses)
    client = SimpleNamespace(models=models)
    return GeminiService(client=client), models


def tool_results(models):
    results = []
    for call in models.calls[1:]:
        for content in call["contents"]:
            for part in getattr(content, "parts", None) or []:
                if part.function_response:
                    results.append(part.function_response)
    return results


def test_no_tool_response_returns_text_without_another_turn():
    service, models = service_for(response_with_text("Direct answer"))

    assert service.generate("System", "Question", {}) == "Direct answer"
    assert len(models.calls) == 1


def test_one_successful_tool_call_is_returned_to_gemini():
    calls = []

    @approve_user_scoped_tool
    def recent_workouts(limit: int = 10):
        calls.append(limit)
        return [{"distance": 2.0}]

    service, models = service_for(
        response_with_calls(("recent_workouts", {"limit": 2})),
        response_with_text("Use the two-mile run."),
    )

    answer = service.generate("System", "Question", {}, tools=[recent_workouts])

    assert answer == "Use the two-mile run."
    assert calls == [2]
    assert tool_results(models)[0].response == {
        "result": [{"distance": 2.0}]
    }
    assert models.calls[0]["config"].automatic_function_calling.disable is True


def test_multiple_tool_calls_execute_across_model_turns():
    calls = []

    @approve_user_scoped_tool
    def profile():
        calls.append("profile")
        return {"goal": "5K"}

    @approve_user_scoped_tool
    def workouts():
        calls.append("workouts")
        return [{"distance": 3.0}]

    service, models = service_for(
        response_with_calls(("profile", {})),
        response_with_calls(("workouts", {})),
        response_with_text("Final coaching answer"),
    )

    assert service.generate(
        "System",
        "Question",
        {},
        tools=[profile, workouts],
    ) == "Final coaching answer"
    assert calls == ["profile", "workouts"]
    assert len(models.calls) == 3


@pytest.mark.parametrize(
    ("requested_name", "arguments", "expected_code"),
    [
        ("delete_database", {}, "unknown_tool"),
        ("recent_workouts", {"limit": "all"}, "invalid_arguments"),
        ("recent_workouts", {"user_id": 99}, "invalid_arguments"),
    ],
)
def test_invalid_tool_names_and_arguments_are_not_executed(
    requested_name,
    arguments,
    expected_code,
):
    calls = []

    @approve_user_scoped_tool
    def recent_workouts(limit: int = 10):
        calls.append(limit)
        return []

    service, models = service_for(
        response_with_calls((requested_name, arguments)),
        response_with_text("Handled safely"),
    )

    assert service.generate(
        "System",
        "Question",
        {},
        tools=[recent_workouts],
    ) == "Handled safely"
    assert calls == []
    assert tool_results(models)[0].response["error"]["code"] == expected_code


def test_tool_failure_is_returned_without_crashing_agent_flow():
    @approve_user_scoped_tool
    def workouts():
        raise RuntimeError("private database details")

    service, models = service_for(
        response_with_calls(("workouts", {})),
        response_with_text("I could not load that context."),
    )

    assert service.generate(
        "System",
        "Question",
        {},
        tools=[workouts],
    ) == "I could not load that context."
    error = tool_results(models)[0].response["error"]
    assert error == {
        "code": "tool_failure",
        "message": "The approved tool could not complete.",
    }


def test_iteration_limit_returns_none_for_deterministic_fallback():
    @approve_user_scoped_tool
    def profile():
        return {"goal": "5K"}

    service, models = service_for(
        response_with_calls(("profile", {})),
        response_with_calls(("profile", {})),
        response_with_calls(("profile", {})),
    )

    assert service.generate(
        "System",
        "Question",
        {},
        tools=[profile],
        max_tool_iterations=2,
    ) is None
    assert len(models.calls) == 3


def test_gemini_unavailable_keeps_offline_fallback_signal(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert GeminiService().generate("System", "Question", {}) is None


def test_only_explicitly_approved_tools_are_exposed_or_executed():
    calls = []

    def unsafe_tool():
        calls.append("unsafe")
        return "secret"

    service, models = service_for(
        response_with_calls(("unsafe_tool", {})),
        response_with_text("Safe response"),
    )

    assert service.generate(
        "System",
        "Question",
        {},
        tools=[unsafe_tool],
    ) == "Safe response"
    assert calls == []
    assert models.calls[0]["config"].tools == []
    assert tool_results(models)[0].response["error"]["code"] == "unknown_tool"


def test_tool_execution_preserves_authenticated_user_data_isolation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(runcoach, "DATABASE", tmp_path / "tool-isolation.db")
    runcoach.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    runcoach.setup_database()
    user_one = runcoach.create_user("tool-one@example.test", "safe-password")
    user_two = runcoach.create_user("tool-two@example.test", "safe-password")
    runcoach.save_manual_workout(
        user_one,
        {
            "run_date": "2026-07-29",
            "distance": "2",
            "duration": "20",
            "mood": "Good",
            "notes": "USER_ONE_PRIVATE",
        },
    )
    runcoach.save_manual_workout(
        user_two,
        {
            "run_date": "2026-07-29",
            "distance": "4",
            "duration": "40",
            "mood": "Good",
            "notes": "USER_TWO_PRIVATE",
        },
    )
    tools = runcoach.build_user_scoped_agent_tools(user_one, runcoach.AGENT_RICO)
    service, models = service_for(
        response_with_calls(
            ("get_recent_workouts_for_logged_in_user", {"limit": 10})
        ),
        response_with_text("User-scoped answer"),
    )

    assert service.generate(
        "System",
        "Question",
        {},
        tools=tools,
    ) == "User-scoped answer"
    result = tool_results(models)[0].response["result"]
    serialized = str(result)
    assert "USER_ONE_PRIVATE" in serialized
    assert "USER_TWO_PRIVATE" not in serialized
