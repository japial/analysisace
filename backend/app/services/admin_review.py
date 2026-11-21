"""Admin review queue for failed data checks (PRD section 8) and the audit log viewer."""

import datetime as dt
import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import AuditLog, DataIssue, JobRun, User
from app.services.auth import AuthError, audit

ISSUE_STATUSES = ("OPEN", "RESOLVED", "IGNORED")


def list_issues(
    db: Session,
    *,
    status: str | None,
    dataset: str | None,
    limit: int,
    offset: int,
) -> tuple[list[DataIssue], int, dict[str, int]]:
    """A page of issues plus the count of open issues per dataset."""
    filters: list[ColumnElement[bool]] = []
    if status:
        filters.append(DataIssue.status == status)
    if dataset:
        filters.append(DataIssue.dataset == dataset)
    total = db.scalar(select(func.count()).select_from(DataIssue).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(DataIssue)
            .where(*filters)
            .order_by(DataIssue.created_at.desc(), DataIssue.date.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    open_counts = dict(
        db.execute(
            select(DataIssue.dataset, func.count())
            .where(DataIssue.status == "OPEN")
            .group_by(DataIssue.dataset)
        ).all()
    )
    return rows, total, {k: int(v) for k, v in open_counts.items()}


def set_issue_status(
    db: Session, actor: User, issue_id: uuid.UUID, status: str, note: str | None
) -> DataIssue:
    if status not in ISSUE_STATUSES:
        raise AuthError("VALIDATION", 422)
    issue = db.get(DataIssue, issue_id)
    if issue is None:
        raise AuthError("NOT_FOUND", 404)
    before = {"status": issue.status}
    issue.status = status
    if status == "OPEN":
        issue.resolved_by, issue.resolved_at = None, None
    else:
        issue.resolved_by, issue.resolved_at = str(actor.id), utcnow()
    db.flush()
    audit(
        db,
        str(actor.id),
        "data_issue.status",
        "data_issue",
        str(issue.id),
        before=before,
        after={"status": status, "note": note},
    )
    return issue


def list_audit(
    db: Session,
    *,
    action: str | None,
    entity: str | None,
    actor: str | None,
    since: dt.date | None,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    filters: list[ColumnElement[bool]] = []
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if entity:
        filters.append(AuditLog.entity == entity)
    if actor:
        filters.append(AuditLog.actor == actor)
    if since:
        filters.append(AuditLog.at >= dt.datetime.combine(since, dt.time(), tzinfo=dt.UTC))
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return rows, total


def recent_jobs(db: Session, limit: int = 50) -> list[JobRun]:
    """Latest job runs, newest first, so failed jobs are visible to admins."""
    return list(db.scalars(select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)))
