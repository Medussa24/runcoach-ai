from agent_eval import run_evaluation


def test_agent_contract_evaluation_passes():
    report = run_evaluation()

    assert report["total"] >= 5
    assert report["passed"] == report["total"], report["results"]
