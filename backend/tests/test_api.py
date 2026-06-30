from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_api_recommendation_and_explanation_are_traceable() -> None:
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}

    recommendations = client.get("/api/recommendations")
    assert recommendations.status_code == 200
    market_id = recommendations.json()[0]["market_id"]

    explanation = client.get(f"/api/recommendations/{market_id}/explain")
    assert explanation.status_code == 200
    body = explanation.json()
    assert body["market_id"] == market_id
    assert len(body["evidence_timeline"]) > 0


def test_api_exposes_sample_backtest() -> None:
    client = TestClient(app)
    response = client.get("/api/backtests/sample")
    assert response.status_code == 200
    body = response.json()
    assert body["replay_count"] == 4
    assert "calibration_buckets" in body


def test_api_exposes_empty_paper_trade_ledger_boundary() -> None:
    client = TestClient(app)
    response = client.get("/api/paper-trades")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
