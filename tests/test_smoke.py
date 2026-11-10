"""Smoke tests in mock mode: run `pytest` before every merge to main."""

import os

os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from core.documents import list_scenarios  # noqa: E402
from core.pipeline import analyze  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_scenarios_give_expected_risk_levels():
    scenarios = list_scenarios()
    assert len(scenarios) == 3
    levels = [analyze(text, name).risk_level for name, text in scenarios.items()]
    assert levels == ["low", "high", "medium"]


def test_analyze_and_decide_end_to_end():
    text = next(iter(list_scenarios().values()))
    result = client.post("/analyze", json={"text": text, "source_name": "test"}).json()
    assert result["case_id"]
    decision = client.post(
        "/decision",
        json={"case_id": result["case_id"], "decision": "approve", "reviewer": "pytest"},
    ).json()
    assert decision["event_type"] == "human_decision"
    events = client.get("/audit", params={"case_id": result["case_id"]}).json()
    assert [e["event_type"] for e in events] == ["human_decision", "ai_analysis"]
