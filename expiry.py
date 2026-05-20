"""Periodically close polls whose expiry has passed."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import poll_store as store

log = logging.getLogger(__name__)


def start_expiry_scheduler(slack_client, refresh_fn, interval_seconds: int = 30) -> BackgroundScheduler:
    sched = BackgroundScheduler(daemon=True)

    def sweep():
        for poll in store.expired_open_polls():
            log.info("Auto-closing expired poll %s", poll.id)
            store.close_poll(poll.id)
            try:
                refresh_fn(slack_client, poll.id)
            except Exception:
                log.exception("Failed to refresh expired poll %s", poll.id)

    sched.add_job(sweep, "interval", seconds=interval_seconds, id="poll_expiry_sweep")
    sched.start()
    return sched