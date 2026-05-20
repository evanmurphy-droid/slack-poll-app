"""Vote logic + persistence tests."""
from datetime import datetime, timedelta, timezone
import poll_store as store


def test_create_and_tally():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B"])
    counts, voters = store.tally(poll.id)
    assert counts == [0, 0]
    assert voters == 0


def test_single_choice_replace():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B"])
    store.toggle_vote(poll.id, "U2", 0)
    store.toggle_vote(poll.id, "U2", 1)  # should move, not add
    counts, voters = store.tally(poll.id)
    assert counts == [0, 1]
    assert voters == 1


def test_single_choice_toggle_off():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B"])
    store.toggle_vote(poll.id, "U2", 0)
    store.toggle_vote(poll.id, "U2", 0)  # same option again → removes
    counts, voters = store.tally(poll.id)
    assert counts == [0, 0]
    assert voters == 0


def test_multi_choice():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B", "C"], multi_choice=True)
    store.toggle_vote(poll.id, "U2", 0)
    store.toggle_vote(poll.id, "U2", 2)
    counts, voters = store.tally(poll.id)
    assert counts == [1, 0, 1]
    assert voters == 1  # one unique voter, two votes


def test_multi_choice_toggle_off_one():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B"], multi_choice=True)
    store.toggle_vote(poll.id, "U2", 0)
    store.toggle_vote(poll.id, "U2", 1)
    store.toggle_vote(poll.id, "U2", 0)  # removes A only
    counts, _ = store.tally(poll.id)
    assert counts == [0, 1]


def test_voters_by_option_not_anonymous():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B"])
    store.toggle_vote(poll.id, "U2", 0)
    store.toggle_vote(poll.id, "U3", 0)
    store.toggle_vote(poll.id, "U4", 1)
    buckets = store.voters_by_option(poll.id)
    assert sorted(buckets[0]) == ["U2", "U3"]
    assert buckets[1] == ["U4"]


def test_close_poll():
    poll = store.create_poll("C1", "U1", "Q?", ["A", "B"])
    store.close_poll(poll.id)
    assert store.get_poll(poll.id).closed is True


def test_expired_open_polls():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    expired = store.create_poll("C1", "U1", "Old", ["A", "B"], expires_at=past)
    store.create_poll("C1", "U1", "New", ["A", "B"], expires_at=future)
    store.create_poll("C1", "U1", "No expiry", ["A", "B"])
    ids = {p.id for p in store.expired_open_polls()}
    assert ids == {expired.id}