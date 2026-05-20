"""SQLite-backed poll + vote store with multi-choice, anonymity, and expiry."""
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import create_engine, String, Integer, Boolean, JSON, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///polls.db"), echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Poll(Base):
    __tablename__ = "polls"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String)
    message_ts: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    creator_id: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(String)
    options: Mapped[list] = mapped_column(JSON)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    multi_choice: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Vote(Base):
    __tablename__ = "votes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String)
    option_index: Mapped[int] = mapped_column(Integer)


Base.metadata.create_all(engine)


def create_poll(
    channel_id: str,
    creator_id: str,
    question: str,
    options: List[str],
    *,
    anonymous: bool = False,
    multi_choice: bool = False,
    expires_at: Optional[datetime] = None,
) -> Poll:
    poll = Poll(
        id=str(uuid.uuid4())[:8],
        channel_id=channel_id,
        creator_id=creator_id,
        question=question,
        options=options,
        anonymous=anonymous,
        multi_choice=multi_choice,
        expires_at=expires_at,
    )
    with SessionLocal() as s:
        s.add(poll)
        s.commit()
        s.refresh(poll)
    return poll


def set_message_ts(poll_id: str, ts: str) -> None:
    with SessionLocal() as s:
        poll = s.get(Poll, poll_id)
        poll.message_ts = ts
        s.commit()


def toggle_vote(poll_id: str, user_id: str, option_index: int) -> None:
    """Toggle behavior:
       - Single-choice: replace any prior vote, or remove if clicking same option.
       - Multi-choice: add if not present, remove if already voted for this option.
    """
    with SessionLocal() as s:
        poll = s.get(Poll, poll_id)
        existing = s.query(Vote).filter_by(poll_id=poll_id, user_id=user_id).all()

        if poll.multi_choice:
            match = next((v for v in existing if v.option_index == option_index), None)
            if match:
                s.delete(match)
            else:
                s.add(Vote(poll_id=poll_id, user_id=user_id, option_index=option_index))
        else:
            if len(existing) == 1 and existing[0].option_index == option_index:
                s.delete(existing[0])  # toggle off
            else:
                for v in existing:
                    s.delete(v)
                s.add(Vote(poll_id=poll_id, user_id=user_id, option_index=option_index))
        s.commit()


def get_poll(poll_id: str) -> Optional[Poll]:
    with SessionLocal() as s:
        return s.get(Poll, poll_id)


def tally(poll_id: str) -> tuple[list[int], int]:
    with SessionLocal() as s:
        poll = s.get(Poll, poll_id)
        counts = [0] * len(poll.options)
        unique_voters = set()
        for v in s.query(Vote).filter_by(poll_id=poll_id).all():
            counts[v.option_index] += 1
            unique_voters.add(v.user_id)
        return counts, len(unique_voters)


def voters_by_option(poll_id: str) -> list[list[str]]:
    with SessionLocal() as s:
        poll = s.get(Poll, poll_id)
        buckets: list[list[str]] = [[] for _ in poll.options]
        for v in s.query(Vote).filter_by(poll_id=poll_id).all():
            buckets[v.option_index].append(v.user_id)
        return buckets


def close_poll(poll_id: str) -> None:
    with SessionLocal() as s:
        s.get(Poll, poll_id).closed = True
        s.commit()


def expired_open_polls() -> list[Poll]:
    """Polls past their expiry that haven't been closed yet."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        return (
            s.query(Poll)
            .filter(Poll.closed == False, Poll.expires_at != None, Poll.expires_at <= now)
            .all()
        )