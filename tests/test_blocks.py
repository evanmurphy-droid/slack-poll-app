from datetime import datetime, timezone

from blocks import render_poll_blocks, _bar


def test_bar_zero_and_full():
    assert _bar(0) == "░" * 12
    assert _bar(100) == "█" * 12


def test_basic_render():
    blocks = render_poll_blocks("p1", "Q?", ["A", "B"], [1, 2], 3, "U1")

    assert blocks[0]["type"] == "header"
    assert "Q?" in blocks[0]["text"]["text"]

    option_sections = [b for b in blocks if b["type"] == "section"]
    assert len(option_sections) == 2

    for section in option_sections:
        assert section["accessory"]["action_id"].startswith("vote_")


def test_closed_strips_vote_buttons_but_keeps_delete_button():
    blocks = render_poll_blocks("p1", "Q?", ["A", "B"], [1, 0], 1, "U1", closed=True)

    for block in blocks:
        if block["type"] == "section":
            assert "accessory" not in block

    actions = [b for b in blocks if b["type"] == "actions"][0]
    action_ids = [el["action_id"] for el in actions["elements"]]

    assert action_ids == ["delete_poll"]
    assert "🔒" in blocks[0]["text"]["text"]


def test_anonymous_hides_view_voters():
    blocks = render_poll_blocks("p1", "Q?", ["A", "B"], [1, 0], 1, "U1", anonymous=True)

    actions = [b for b in blocks if b["type"] == "actions"][0]
    action_ids = [el["action_id"] for el in actions["elements"]]

    assert "view_voters" not in action_ids
    assert "close_poll" in action_ids
    assert "delete_poll" in action_ids


def test_delete_button_renders():
    blocks = render_poll_blocks("p1", "Q?", ["A", "B"], [0, 0], 0, "U1")

    actions = [b for b in blocks if b["type"] == "actions"][0]
    action_ids = [el["action_id"] for el in actions["elements"]]

    assert "delete_poll" in action_ids


def test_delete_button_renders_when_closed():
    blocks = render_poll_blocks("p1", "Q?", ["A", "B"], [1, 0], 1, "U1", closed=True)

    actions = [b for b in blocks if b["type"] == "actions"][0]
    action_ids = [el["action_id"] for el in actions["elements"]]

    assert action_ids == ["delete_poll"]


def test_badges():
    expires = datetime.now(timezone.utc)
    blocks = render_poll_blocks(
        "p1",
        "Q?",
        ["A", "B"],
        [0, 0],
        0,
        "U1",
        anonymous=True,
        multi_choice=True,
        expires_at=expires,
    )

    badge_row = blocks[1]
    text = badge_row["elements"][0]["text"]

    assert "Multi-select" in text
    assert "Anonymous" in text
    assert "Closes" in text