"""Scheduled jobs process. Run with `python -m app.jobs.worker`.

Schedules come from config/schedules.yaml. A job listed there runs only once it has an
implementation registered in `JOBS`; the others are logged as pending so the gap is visible.
Every run is recorded in `job_run` (PRD section 12).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.app_config import get_config
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import JobRun
from app.seed.reference import seed_reference
from app.services.config_registry import sync_config_versions

logger = logging.getLogger("analysisace.worker")

JobFn = Callable[[Session], dict[str, Any]]

# name in schedules.yaml -> implementation. Ingestion jobs are added in M1 as each source
# adapter is written.
JOBS: dict[str, JobFn] = {}


def run_job(name: str, fn: JobFn) -> None:
    """Run one job in its own transaction and record the outcome."""
    started = datetime.now(UTC)
    status, detail = "SUCCESS", {}
    with get_sessionmaker()() as session:
        try:
            detail = fn(session)
            session.commit()
        except Exception as exc:
            session.rollback()
            status, detail = "FAILED", {"error": repr(exc)}
            logger.exception("Job %s failed", name)
        session.add(
            JobRun(
                job=name,
                started_at=started,
                finished_at=datetime.now(UTC),
                status=status,
                detail=detail,
            )
        )
        session.commit()
    logger.info("Job %s finished: %s", name, status)


def _config_sync(session: Session) -> dict[str, Any]:
    added = sync_config_versions(session, get_settings().config_dir)
    return {"added": [f"{domain}@{version}" for domain, version in added]}


def cron_trigger(spec: dict[str, Any], timezone: str) -> CronTrigger:
    """Translate one schedules.yaml entry into a cron trigger.

    `days: trading` fires Sunday to Thursday; the job itself must skip market holidays by
    asking the trading calendar.
    """
    hour, minute = (int(part) for part in str(spec["at"]).split(":"))
    days = spec.get("days", "daily")
    fields: dict[str, Any] = {"hour": hour, "minute": minute}
    if days == "trading":
        fields["day_of_week"] = "sun,mon,tue,wed,thu"
    elif days == "weekly":
        fields["day_of_week"] = str(spec["weekday"]).lower()
    elif days == "monthly":
        fields["day"] = int(spec["day"])
    elif days != "daily":
        raise ValueError(f"Unknown schedule `days` value: {days}")
    return CronTrigger(timezone=timezone, **fields)


def build_scheduler() -> BlockingScheduler:
    schedules = get_config("schedules").data
    timezone = schedules["timezone"]
    scheduler = BlockingScheduler(timezone=timezone)
    for name, spec in schedules["jobs"].items():
        fn = JOBS.get(name)
        if fn is None:
            logger.warning("Job %s is scheduled in config but not implemented yet", name)
            continue
        scheduler.add_job(run_job, cron_trigger(spec, timezone), args=[name, fn], id=name)
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_job("config_sync", _config_sync)
    run_job("reference_seed", lambda session: {"added": seed_reference(session)})
    scheduler = build_scheduler()
    logger.info("Worker started with %d scheduled jobs", len(scheduler.get_jobs()))
    scheduler.start()


if __name__ == "__main__":
    main()
