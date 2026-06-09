"""Governance rules engine for access control exception detection."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from database import AccessRequest, ApprovedRole, Exception, User

SENSITIVE_SYSTEMS = {"SWIFT Gateway", "Trading System", "Risk Engine", "AML Monitoring"}
PENDING_AGE_THRESHOLD_DAYS = 15
MAX_ACTIVE_SYSTEMS = 5

SEVERITY_MAP = {
    "Unauthorized System Access": "High",
    "Terminated User Active Access": "High",
    "Excessive Active Systems": "Medium",
    "Aged Pending Request": "Medium",
    "Duplicate Access Request": "Low",
}


def _role_matrix(session: Session) -> dict[str, set[str]]:
    matrix: dict[str, set[str]] = {}
    for row in session.query(ApprovedRole).all():
        matrix[row.role] = set(row.allowed_systems.split("|"))
    return matrix


def _active_access_df(session: Session) -> pd.DataFrame:
    rows = (
        session.query(
            AccessRequest.user_id,
            AccessRequest.requested_system,
            AccessRequest.request_id,
            AccessRequest.request_date,
            AccessRequest.approval_status,
            AccessRequest.closure_status,
            User.employee_name,
            User.current_role,
            User.department,
            User.employment_status,
        )
        .join(User, User.user_id == AccessRequest.user_id)
        .filter(
            AccessRequest.approval_status == "Approved",
            AccessRequest.closure_status == "Open",
        )
        .all()
    )
    return pd.DataFrame(
        rows,
        columns=[
            "user_id", "requested_system", "request_id", "request_date",
            "approval_status", "closure_status", "employee_name",
            "current_role", "department", "employment_status",
        ],
    )


def rule_unauthorized_access(session: Session, matrix: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Rule 1: Flag users with systems outside approved role matrix."""
    findings: list[dict[str, Any]] = []
    active = _active_access_df(session)

    for _, row in active.iterrows():
        allowed = matrix.get(row["current_role"], set())
        if row["requested_system"] not in allowed:
            severity = "High"
            if row["requested_system"] in SENSITIVE_SYSTEMS:
                desc = (
                    f"Unauthorized access to sensitive system '{row['requested_system']}' "
                    f"(role '{row['current_role']}' permits: {', '.join(sorted(allowed)) or 'none'})"
                )
            else:
                desc = (
                    f"System '{row['requested_system']}' not in approved matrix for "
                    f"role '{row['current_role']}'"
                )
            findings.append(
                {
                    "user_id": row["user_id"],
                    "user_name": row["employee_name"],
                    "issue_type": "Unauthorized System Access",
                    "severity": severity,
                    "description": desc,
                }
            )
    return findings


def rule_excessive_systems(session: Session) -> list[dict[str, Any]]:
    """Rule 2: Flag users with more than 5 active systems."""
    active = _active_access_df(session)
    if active.empty:
        return []

    counts = active.groupby(["user_id", "employee_name"]).size().reset_index(name="system_count")
    findings: list[dict[str, Any]] = []

    for _, row in counts[counts["system_count"] > MAX_ACTIVE_SYSTEMS].iterrows():
        systems = active.loc[active["user_id"] == row["user_id"], "requested_system"].tolist()
        findings.append(
            {
                "user_id": row["user_id"],
                "user_name": row["employee_name"],
                "issue_type": "Excessive Active Systems",
                "severity": SEVERITY_MAP["Excessive Active Systems"],
                "description": (
                    f"User has {row['system_count']} active systems (limit: {MAX_ACTIVE_SYSTEMS}): "
                    f"{', '.join(systems)}"
                ),
            }
        )
    return findings


def rule_aged_pending_requests(session: Session) -> list[dict[str, Any]]:
    """Rule 3: Flag pending requests older than 15 days."""
    cutoff = date.today() - timedelta(days=PENDING_AGE_THRESHOLD_DAYS)
    pending = (
        session.query(AccessRequest, User)
        .join(User, User.user_id == AccessRequest.user_id)
        .filter(
            AccessRequest.approval_status == "Pending",
            AccessRequest.closure_status == "Open",
            AccessRequest.request_date <= cutoff,
        )
        .all()
    )

    findings: list[dict[str, Any]] = []
    for req, user in pending:
        age = (date.today() - req.request_date).days
        findings.append(
            {
                "user_id": user.user_id,
                "user_name": user.employee_name,
                "issue_type": "Aged Pending Request",
                "severity": SEVERITY_MAP["Aged Pending Request"],
                "description": (
                    f"Request {req.request_id} for '{req.requested_system}' pending "
                    f"{age} days (threshold: {PENDING_AGE_THRESHOLD_DAYS} days)"
                ),
            }
        )
    return findings


def rule_terminated_active_access(session: Session) -> list[dict[str, Any]]:
    """Rule 4: Flag terminated users with active access."""
    active = _active_access_df(session)
    terminated = active[active["employment_status"] == "Terminated"]
    findings: list[dict[str, Any]] = []

    for user_id, group in terminated.groupby("user_id"):
        systems = group["requested_system"].tolist()
        findings.append(
            {
                "user_id": user_id,
                "user_name": group.iloc[0]["employee_name"],
                "issue_type": "Terminated User Active Access",
                "severity": SEVERITY_MAP["Terminated User Active Access"],
                "description": (
                    f"Terminated employee retains active access to: {', '.join(systems)}"
                ),
            }
        )
    return findings


def rule_duplicate_requests(session: Session) -> list[dict[str, Any]]:
    """Rule 5 (Low): Flag duplicate pending access requests."""
    pending = (
        session.query(AccessRequest, User)
        .join(User, User.user_id == AccessRequest.user_id)
        .filter(
            AccessRequest.approval_status == "Pending",
            AccessRequest.closure_status == "Open",
        )
        .all()
    )

    key_counts: Counter[tuple[str, str]] = Counter()
    key_users: dict[tuple[str, str], tuple[str, str]] = {}

    for req, user in pending:
        key = (req.user_id, req.requested_system)
        key_counts[key] += 1
        key_users[key] = (user.user_id, user.employee_name)

    findings: list[dict[str, Any]] = []
    for key, count in key_counts.items():
        if count > 1:
            user_id, name = key_users[key]
            findings.append(
                {
                    "user_id": user_id,
                    "user_name": name,
                    "issue_type": "Duplicate Access Request",
                    "severity": SEVERITY_MAP["Duplicate Access Request"],
                    "description": (
                        f"{count} duplicate pending requests for system '{key[1]}'"
                    ),
                }
            )
    return findings


def run_governance_rules(session: Session) -> list[dict[str, Any]]:
    """Execute all governance rules and persist exceptions."""
    session.query(Exception).delete()
    session.commit()

    matrix = _role_matrix(session)
    all_findings: list[dict[str, Any]] = []
    all_findings.extend(rule_unauthorized_access(session, matrix))
    all_findings.extend(rule_excessive_systems(session))
    all_findings.extend(rule_aged_pending_requests(session))
    all_findings.extend(rule_terminated_active_access(session))
    all_findings.extend(rule_duplicate_requests(session))

    for finding in all_findings:
        session.add(Exception(**finding))

    session.commit()
    return all_findings


def get_exception_summary(session: Session) -> dict[str, Any]:
    """Aggregate exception metrics for MIS reporting."""
    exceptions = session.query(Exception).all()
    by_severity = Counter(e.severity for e in exceptions)
    by_type = Counter(e.issue_type for e in exceptions)

    dept_breaches: dict[str, int] = defaultdict(int)
    for exc in exceptions:
        user = session.query(User).filter(User.user_id == exc.user_id).first()
        if user:
            dept_breaches[user.department] += 1

    return {
        "total": len(exceptions),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "by_department": dict(dept_breaches),
    }
