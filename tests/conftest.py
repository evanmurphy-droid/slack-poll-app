"""Shared fixtures for poll app tests."""
import os
import tempfile
import pytest
from unittest.mock import MagicMock, PropertyMock


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    """Give each test its own SQLite file so tests don't share state."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp.name}")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
    monkeypatch.setenv("POLL_API_TOKEN", "test-token")
    monkeypatch.setenv("RUN_SCHEDULER", "0")

    import importlib
    import poll_store
    importlib.reload(poll_store)
    yield
    os.unlink(tmp.name)


@pytest.fixture
def slack_client():
    """Mock Slack WebClient that records all calls."""
    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1234567890.000100", "channel": "C123"}
    client.chat_update.return_value = {"ok": True}
    client.chat_postEphemeral.return_value = {"ok": True}
    return client


@pytest.fixture
def flask_client(slack_client, monkeypatch):
    """Flask test client with bolt_app.client patched out.

    `App.client` is a read-only property in slack-bolt, so we patch the
    *type* with a PropertyMock that returns our mock client.
    """
    import importlib
    import app as app_module
    importlib.reload(app_module)

    # Replace the read-only `client` property on the App class with a
    # PropertyMock that returns our fake Slack client.
    from slack_bolt import App
    monkeypatch.setattr(
        App, "client", PropertyMock(return_value=slack_client), raising=False
    )

    app_module.flask_app.config["TESTING"] = True
    with app_module.flask_app.test_client() as c:
        yield c