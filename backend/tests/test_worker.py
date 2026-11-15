"""Worker schedule parsing (PRD section 8 schedules, Asia/Dhaka)."""

import pytest

from app.core.app_config import get_config
from app.jobs.worker import cron_trigger


def _fields(spec: dict[str, object]) -> dict[str, str]:
    trigger = cron_trigger(spec, "Asia/Dhaka")
    return {f.name: str(f) for f in trigger.fields}


def test_trading_day_job_runs_sunday_to_thursday() -> None:
    fields = _fields({"days": "trading", "at": "16:30"})
    assert (fields["hour"], fields["minute"]) == ("16", "30")
    assert fields["day_of_week"] == "sun,mon,tue,wed,thu"


def test_weekly_and_monthly_jobs() -> None:
    assert _fields({"days": "weekly", "weekday": "FRI", "at": "09:00"})["day_of_week"] == "fri"
    assert _fields({"days": "monthly", "day": 10, "at": "10:00"})["day"] == "10"


def test_unknown_days_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown schedule"):
        cron_trigger({"days": "sometimes", "at": "10:00"}, "Asia/Dhaka")


def test_every_job_in_schedules_yaml_parses() -> None:
    schedules = get_config("schedules").data
    for spec in schedules["jobs"].values():
        cron_trigger(spec, schedules["timezone"])
