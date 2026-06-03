"""Renders a poll as Slack Block Kit blocks."""
from typing import List, Dict, Any


def render_poll_blocks(
    poll_id,
    question,
    options,
    vote_counts,
    total_voters,
    creator_id,
    *,
    anonymous=False,
    multi_choice=False,
    expires_at=None,
    closed=False,
):
    header_emoji = "🔒" if closed else "📊"
    blocks: List[Dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{header_emoji} {question}",
                "emoji": True,
            },
        }
    ]

    badges = []
    if multi_choice:
        badges.append("☑️ Multi-select")
    if anonymous:
        badges.append("🕶️ Anonymous")
    if expires_at and not closed:
        badges.append(
            f"⏰ Closes <!date^{int(expires_at.timestamp())}^"
            f"{{date_short_pretty}} at {{time}}|{expires_at.isoformat()}>"
        )

    if badges:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " · ".join(badges)}],
            }
        )

    for idx, (label, count) in enumerate(zip(options, vote_counts)):
        total_votes_cast = sum(vote_counts) or 1
        pct = count / total_votes_cast * 100
        bar = _bar(pct)

        section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{label}*\n{bar} `{count}` ({pct:.0f}%)",
            },
        }

        if not closed:
            section["accessory"] = {
                "type": "button",
                "text": {"type": "plain_text", "text": "Vote", "emoji": True},
                "value": f"{poll_id}:{idx}",
                "action_id": f"vote_{idx}",
            }

        blocks.append(section)

    footer = f"_{total_voters} voter{'s' if total_voters != 1 else ''}_ · Created by <@{creator_id}>"
    if closed:
        footer += " · *Poll closed*"

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": footer}],
        }
    )

    action_elements = []

    if not closed:
        if not anonymous:
            action_elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View voters", "emoji": True},
                    "action_id": "view_voters",
                    "value": poll_id,
                }
            )

        action_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Close poll", "emoji": True},
                "style": "danger",
                "action_id": "close_poll",
                "value": poll_id,
                "confirm": {
                    "title": {"type": "plain_text", "text": "Close this poll?"},
                    "text": {"type": "mrkdwn", "text": "No more votes will be accepted."},
                    "confirm": {"type": "plain_text", "text": "Close"},
                    "deny": {"type": "plain_text", "text": "Cancel"},
                },
            }
        )

    action_elements.append(
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Delete poll", "emoji": True},
            "style": "danger",
            "action_id": "delete_poll",
            "value": poll_id,
            "confirm": {
                "title": {"type": "plain_text", "text": "Delete this poll?"},
                "text": {
                    "type": "mrkdwn",
                    "text": "This will remove the poll message from Slack. This cannot be undone.",
                },
                "confirm": {"type": "plain_text", "text": "Delete"},
                "deny": {"type": "plain_text", "text": "Cancel"},
            },
        }
    )

    blocks.append({"type": "actions", "elements": action_elements})

    return blocks


def _bar(pct: float, width: int = 12) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)