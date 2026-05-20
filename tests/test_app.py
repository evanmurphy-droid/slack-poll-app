"""End-to-end Flask + Bolt tests with a mocked Slack client."""
import json
from datetime import datetime, timezone


def test_healthz(flask_client):
    r = flask_client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_api_requires_auth(flask_client):
    r = flask_client.post("/api/polls", json={"channel": "C1", "question": "Q?", "options": ["A", "B"]})
    assert r.status_code == 401


def test_api_creates_poll(flask_client, slack_client):
    r = flask_client.post(
        "/api/polls",
        headers={"Authorization": "Bearer test-token"},
        json={"channel": "C1", "question": "Q?", "options": ["A", "B"]},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["poll_id"]
    assert body["channel"] == "C1"
    slack_client.chat_postMessage.assert_called_once()
    call_kwargs = slack_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C1"
    assert any(b["type"] == "header" for b in call_kwargs["blocks"])


def test_api_validates_options(flask_client):
    r = flask_client.post(
        "/api/polls",
        headers={"Authorization": "Bearer test-token"},
        json={"channel": "C1", "question": "Q?", "options": ["only one"]},
    )
    assert r.status_code == 400


def test_api_with_flags(flask_client, slack_client):
    r = flask_client.post(
        "/api/polls",
        headers={"Authorization": "Bearer test-token"},
        json={
            "channel": "C1", "question": "Q?", "options": ["A", "B"],
            "anonymous": True, "multi_choice": True, "expires_in": "1h",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["expires_at"] is not None


def test_parse_duration():
    from app import _parse_duration
    assert _parse_duration("30m") > datetime.now(timezone.utc)
    assert _parse_duration("garbage") is None
    assert _parse_duration("2h") is not None