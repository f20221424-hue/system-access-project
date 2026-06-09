"""Audit logging for access lifecycle events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from database import AccessRequest, AuditLog, Exception, User

EVENT_ACCESS_GRANTED = "Access Granted"
EVENT_ACCESS_REVOKED = "Access Revoked"
EVENT_REQUEST_CREATED = "Access Request Created"
EVENT_EXCEPTION_GENERATED = "Exception Generated"


def log_event(
    session: Session,
    event_type: str,
    description: str,
    user_id: str | None = None,
    timestamp: datetime | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        event_type=event_type,
        timestamp=timestamp or datetime.utcnow(),
        description=description,
    )
    session.add(entry)
    return entry


def generate_audit_trail(session: Session) -> list[AuditLog]:
    """Rebuild audit trail from source data and governance outputs."""
    session.query(AuditLog).delete()
    session.commit()

    entries: list[AuditLog] = []

    for req in session.query(AccessRequest).order_by(AccessRequest.request_date).all():
        ts = datetime.combine(req.request_date, datetime.min.time())
        entries.append(
            log_event(
                session,
                EVENT_REQUEST_CREATED,
                f"Access request {req.request_id} created for system '{req.requested_system}' "
                f"(status: {req.approval_status})",
                user_id=req.user_id,
                timestamp=ts,
            )
        )

        if req.approval_status == "Approved" and req.closure_status == "Open":
            entries.append(
                log_event(
                    session,
                    EVENT_ACCESS_GRANTED,
                    f"Access granted to '{req.requested_system}' via request {req.request_id}",
                    user_id=req.user_id,
                    timestamp=ts,
                )
            )
        elif req.closure_status == "Closed" and req.approval_status in {"Approved", "Rejected"}:
            entries.append(
                log_event(
                    session,
                    EVENT_ACCESS_REVOKED,
                    f"Access request {req.request_id} closed ({req.approval_status})",
                    user_id=req.user_id,
                    timestamp=ts,
                )
            )

    for exc in session.query(Exception).all():
        entries.append(
            log_event(
                session,
                EVENT_EXCEPTION_GENERATED,
                f"[{exc.severity}] {exc.issue_type}: {exc.description}",
                user_id=exc.user_id,
            )
        )

    session.commit()
    return entries


def audit_logs_to_dataframe(session: Session):
    import pandas as pd

    rows = session.query(AuditLog).order_by(AuditLog.timestamp).all()
    return pd.DataFrame(
        [
            {
                "event_id": r.event_id,
                "user_id": r.user_id or "",
                "event_type": r.event_type,
                "timestamp": r.timestamp,
                "description": r.description,
            }
            for r in rows
        ]
    )
