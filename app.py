"""Slack Poll App — Bolt for Python, with multi-select/anon/expiry."""
import os
import re
import shlex
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk.errors import SlackApiError

import poll_store as store
from blocks import render_poll_blocks
from expiry import start_expiry_scheduler

load_dotenv()

bolt_app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    token_verification_enabled=False,
)
POLL_API_TOKEN = os.environ["POLL_API_TOKEN"]


def _blocks_for(poll, counts, voters):
    return render_poll_blocks(
        poll.id,
        poll.question,
        poll.options,
        counts,
        voters,
        poll.creator_id,
        anonymous=poll.anonymous,
        multi_choice=poll.multi_choice,
        expires_at=poll.expires_at,
        closed=poll.closed,
    )


def _post_poll(client, channel_id, creator_id, question, options, **kwargs):
    poll = store.create_poll(channel_id, creator_id, question, options, **kwargs)
    counts, voters = store.tally(poll.id)

    resp = client.chat_postMessage(
        channel=channel_id,
        blocks=_blocks_for(poll, counts, voters),
        text=f"Poll: {question}",
    )

    store.set_message_ts(poll.id, resp["ts"])
    return poll, resp["ts"]


def _refresh_poll_message(client, poll_id):
    poll = store.get_poll(poll_id)
    counts, voters = store.tally(poll_id)

    client.chat_update(
        channel=poll.channel_id,
        ts=poll.message_ts,
        blocks=_blocks_for(poll, counts, voters),
        text=f"Poll: {poll.question}",
    )


def _normalize_command_text(text: str) -> str:
    """Normalize common smart punctuation that breaks slash command parsing."""
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u2014", "--")
        .replace("\u2013", "--")
    )


def _parse_flags(tokens):
    flags = {"multi_choice": False, "anonymous": False, "expires_at": None}
    rest = []

    for tok in tokens:
        if tok == "--multi":
            flags["multi_choice"] = True
        elif tok == "--anon":
            flags["anonymous"] = True
        elif tok.startswith("--expires="):
            flags["expires_at"] = _parse_duration(tok.split("=", 1)[1])
        else:
            rest.append(tok)

    return flags, rest


def _parse_duration(s: str) -> Optional[datetime]:
    m = re.fullmatch(r"(\d+)([mhd])", s.strip())
    if not m:
        return None

    n, unit = int(m.group(1)), m.group(2)
    delta = {
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }[unit]

    return datetime.now(timezone.utc) + delta


# ---------- /poll ----------
@bolt_app.command("/poll")
def handle_poll_command(ack, command, client, respond):
    ack()

    try:
        normalized_text = _normalize_command_text(command["text"])
        tokens = shlex.split(normalized_text)
    except ValueError:
        return respond(
            '⚠️ Parse error. Try `/poll "Q?" "A" "B" [--multi] [--anon] [--expires=30m]`'
        )

    flags, parts = _parse_flags(tokens)

    if len(parts) < 3:
        return respond(
            'Need a question and ≥2 options.\n'
            '`/poll "Lunch?" "🍜 Ramen" "🥢 Pho" --multi --expires=1h`'
        )

    question, *options = parts
    _post_poll(client, command["channel_id"], command["user_id"], question, options, **flags)


# ---------- vote ----------
@bolt_app.action(re.compile(r"^vote_\d+$"))
def handle_vote(ack, body, client):
    ack()

    poll_id, idx_str = body["actions"][0]["value"].split(":")
    poll = store.get_poll(poll_id)

    if not poll:
        return client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=body["user"]["id"],
            text="This poll no longer exists.",
        )

    if poll.closed:
        return

    store.toggle_vote(poll_id, body["user"]["id"], int(idx_str))
    _refresh_poll_message(client, poll_id)


# ---------- view voters ----------
@bolt_app.action("view_voters")
def handle_view_voters(ack, body, client):
    ack()

    poll_id = body["actions"][0]["value"]
    poll = store.get_poll(poll_id)

    if not poll:
        return client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=body["user"]["id"],
            text="This poll no longer exists.",
        )

    if poll.anonymous:
        return

    buckets = store.voters_by_option(poll_id)
    lines = [
        f"*{opt}*\n" + (", ".join(f"<@{u}>" for u in users) or "_no votes_")
        for opt, users in zip(poll.options, buckets)
    ]

    client.chat_postEphemeral(
        channel=poll.channel_id,
        user=body["user"]["id"],
        text="Voters:\n\n" + "\n\n".join(lines),
    )


# ---------- close ----------
@bolt_app.action("close_poll")
def handle_close(ack, body, client):
    ack()

    poll_id = body["actions"][0]["value"]
    poll = store.get_poll(poll_id)

    if not poll:
        return client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=body["user"]["id"],
            text="This poll no longer exists.",
        )

    if body["user"]["id"] != poll.creator_id:
        return client.chat_postEphemeral(
            channel=poll.channel_id,
            user=body["user"]["id"],
            text="Only the poll creator can close it.",
        )

    store.close_poll(poll_id)
    _refresh_poll_message(client, poll_id)


# ---------- delete ----------
@bolt_app.action("delete_poll")
def handle_delete(ack, body, client):
    ack()

    poll_id = body["actions"][0]["value"]
    poll = store.get_poll(poll_id)

    if not poll:
        return client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=body["user"]["id"],
            text="This poll no longer exists.",
        )

    if body["user"]["id"] != poll.creator_id:
        return client.chat_postEphemeral(
            channel=poll.channel_id,
            user=body["user"]["id"],
            text="Only the poll creator can delete it.",
        )

    try:
        client.chat_delete(channel=poll.channel_id, ts=poll.message_ts)
        store.delete_poll(poll_id)
    except SlackApiError as e:
        slack_error = e.response.get("error", "unknown_error")
        client.chat_postEphemeral(
            channel=poll.channel_id,
            user=body["user"]["id"],
            text=f"Could not delete this poll. Slack returned: `{slack_error}`",
        )


# ---------- Flask wiring ----------
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@flask_app.route("/healthz")
def healthz():
    return {"ok": True}


# ---------- HTTP API for AI agent ----------
@flask_app.route("/api/polls", methods=["POST"])
def create_poll_api():
    if request.headers.get("Authorization") != f"Bearer {POLL_API_TOKEN}":
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    channel = data.get("channel")
    question = data.get("question")
    options = data.get("options") or []
    creator = data.get("creator_user_id", "USYSTEM")

    if not channel or not question or len(options) < 2:
        return jsonify({"error": "channel, question, and >=2 options required"}), 400

    kwargs = {
        "anonymous": bool(data.get("anonymous", False)),
        "multi_choice": bool(data.get("multi_choice", False)),
        "expires_at": _parse_duration(data["expires_in"]) if data.get("expires_in") else None,
    }

    poll, ts = _post_poll(bolt_app.client, channel, creator, question, options, **kwargs)

    return jsonify(
        {
            "poll_id": poll.id,
            "channel": channel,
            "message_ts": ts,
            "expires_at": poll.expires_at.isoformat() if poll.expires_at else None,
        }
    )


if os.environ.get("RUN_SCHEDULER", "1") == "1" and not os.environ.get("PYTEST_CURRENT_TEST"):
    start_expiry_scheduler(bolt_app.client, _refresh_poll_message)


if __name__ == "__main__":
    flask_app.run(port=3000)