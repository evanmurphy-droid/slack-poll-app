"""Renders a poll as Slack Block Kit blocks."""
from typing import List, Dict, Any, Optional
from datetime import datetime


def render_poll_blocks(
    poll_id: str,
    question: str,
    options: List[str],
    vote_counts: List[int],
    total_voters: int,
    creator_id: str,
    *,
    anonymous: bool = False,
    multi_choice: bool = False,
    expires_at: Optional[datetime] = None,
    closed: bool = False,
) -> List[Dict[str, Any]]:
    header_emoji = "🔒" if closed else "📊"
    blocks: List[Dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{header_emoji} {question}", "emoji": True},
        }
    ]

    # Subtitle row: mode badges
    badges = []
    if multi_choice:
        badges.append("☑️ Multi-select")
    if anonymous:
        badges.append("🕶️ Anonymous")
    if expires_at and not closed:
        badges.append(f"⏰ Closes <!date^{int(expires_at.timestamp())}^{{date_short_pretty}} at {{time}}|{expires_at.isoformat()}>")
    if badges:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": " · ".join(badges)}],
        })

    for idx, (label, count) in enumerate(zip(options, vote_counts)):
        total_votes_cast = sum(vote_counts) or 1  # avoid div-by-zero; pct of all votes
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
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]})

    if not closed:
        action_elements = []
        if not anonymous:
            action_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "View voters", "emoji": True},
                "action_id": "view_voters",
                "value": poll_id,
            })
        action_elements.append({
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
        })
        if action_elements:
            blocks.append({"type": "actions", "elements": action_elements})

    return blocks


def _bar(pct: float, width: int = 12) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)