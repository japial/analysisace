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
from app.core.trading_calendar import get_trading_calendar
from app.models import JobRun
from app.seed.reference import seed_reference
from app.services import alerts, costs, income, macro_notes, market_data, portfolio, ratelimit
from app.services.config_registry import sync_config_versions
from app.services.email import check_email_settings, get_email_sender, send_safely
from app.services.email_templates import job_failed_email
from app.services.market_pipeline import run_market_analytics
from app.services.valuation import today_dhaka

logger = logging.getLogger("analysisace.worker")

JobFn = Callable[[Session], dict[str, Any]]


def _recurring_expenses(session: Session) -> dict[str, Any]:
    """FR12.2: write the cost entries that recurring rules have fallen due for."""
    return {"added": costs.generate_recurring(session, today_dhaka())}


def _recurring_income(session: Session) -> dict[str, Any]:
    """FR27.2: write the income entries that recurring rules have fallen due for."""
    return {"added": income.generate_recurring(session, today_dhaka())}


def _rate_limit_cleanup(session: Session) -> dict[str, Any]:
    """D28: delete rate-limit attempts past every window."""
    return {"deleted": ratelimit.purge(session)}


def _net_worth_snapshots(session: Session) -> dict[str, Any]:
    """FR14.4: store today's net worth for every household."""
    return {"households": portfolio.store_all_net_worth(session)}


def _personal_alerts(session: Session) -> dict[str, Any]:
    """FR20.1: drift, volatility, goals, maturities, revaluations and Zakat dates."""
    return {"created": alerts.run_personal_alerts(session, get_email_sender())}


def _alert_digest(session: Session) -> dict[str, Any]:
    """FR7.3: one email or push a day for alerts set to arrive once a day."""
    return {"people": alerts.send_digests(session, get_email_sender())}


def _monthly_report(session: Session) -> dict[str, Any]:
    """FR20.2: last month's spending, net worth, Zakat estimate and FIRE progress."""
    sent = alerts.send_monthly_reports(session, get_email_sender(), get_settings().web_base_url)
    return {"sent": sent}


def _adjusted_prices(session: Session) -> dict[str, Any]:
    """PRD 7.2: write adjusted closes wherever they are missing."""
    return {"changed": market_data.recompute_adjusted_closes(session)}


def _data_quality(session: Session) -> dict[str, Any]:
    """PRD section 8: checks that span days; failures go to the review queue."""
    calendar = get_trading_calendar()
    today = today_dhaka()
    if not calendar.is_trading_day(today):
        return {"skipped": "not a trading day"}
    return market_data.run_quality_checks(session, calendar, today)


def _market_analytics(session: Session) -> dict[str, Any]:
    """F1 screen, F3 scores, F5 event metrics, F2 basket, F8 regime, F7 alerts."""
    return run_market_analytics(session, get_email_sender())


def _macro_note_draft(session: Session) -> dict[str, Any]:
    """FR4.1: draft this week's note in both languages for an editor to publish."""
    notes = macro_notes.generate_draft(session, today_dhaka())
    return {"notes": [f"{n.week_start}:{n.locale}:{n.status}" for n in notes]}


# name in schedules.yaml -> implementation. Live ingestion jobs are added as each source
# adapter is written (they need outside services).
JOBS: dict[str, JobFn] = {
    "recurring_expenses": _recurring_expenses,
    "recurring_income": _recurring_income,
    "rate_limit_cleanup": _rate_limit_cleanup,
    "net_worth_snapshots": _net_worth_snapshots,
    "personal_alerts": _personal_alerts,
    "alert_digest": _alert_digest,
    "monthly_report": _monthly_report,
    "adjusted_prices": _adjusted_prices,
    "data_quality": _data_quality,
    "market_analytics": _market_analytics,
    "macro_note_draft": _macro_note_draft,
}


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
    if status == "FAILED":
        notify_operators(name, str(detail.get("error", "")))


def notify_operators(job: str, error: str) -> int:
    """Email OPS_ALERT_EMAILS that a job failed (M1: alert on failed jobs). Returns how
    many were sent; the failure is also on /admin/audit whatever happens here."""
    settings = get_settings()
    sender = get_email_sender()
    return sum(
        send_safely(
            sender,
            job_failed_email(to, job, error, settings.environment, settings.web_base_url),
        )
        for to in settings.ops_alert_email_list
    )


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
    check_email_settings(get_settings())
    run_job("config_sync", _config_sync)
    run_job("reference_seed", lambda session: {"added": seed_reference(session)})
    scheduler = build_scheduler()
    logger.info("Worker started with %d scheduled jobs", len(scheduler.get_jobs()))
    scheduler.start()


if __name__ == "__main__":
    main()
