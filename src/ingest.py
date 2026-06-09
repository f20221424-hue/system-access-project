"""CSV ingestion and database population."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from database import (
    PROJECT_ROOT,
    AccessRequest,
    ApprovedRole,
    User,
    get_engine,
    init_database,
)

DATA_DIR = PROJECT_ROOT / "data"


def load_csv_data(data_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    data_dir = data_dir or DATA_DIR
    return {
        "users": pd.read_csv(data_dir / "users.csv"),
        "access_requests": pd.read_csv(data_dir / "access_requests.csv", parse_dates=["request_date"]),
        "approved_roles": pd.read_csv(data_dir / "approved_role_matrix.csv"),
    }


def populate_database(session: Session, data: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Load CSV data into SQLite. Returns row counts per table."""
    session.query(AccessRequest).delete()
    session.query(ApprovedRole).delete()
    session.query(User).delete()
    session.commit()

    for _, row in data["users"].iterrows():
        session.add(
            User(
                user_id=row["user_id"],
                employee_name=row["employee_name"],
                department=row["department"],
                location=row["location"],
                manager=row["manager"],
                current_role=row["current_role"],
                employment_status=row.get("employment_status", "Active"),
            )
        )

    for _, row in data["approved_roles"].iterrows():
        session.add(ApprovedRole(role=row["role"], allowed_systems=row["allowed_systems"]))

    for _, row in data["access_requests"].iterrows():
        session.add(
            AccessRequest(
                request_id=row["request_id"],
                user_id=row["user_id"],
                requested_system=row["requested_system"],
                request_date=row["request_date"].date() if hasattr(row["request_date"], "date") else row["request_date"],
                approval_status=row["approval_status"],
                closure_status=row["closure_status"],
            )
        )

    session.commit()
    return {
        "users": len(data["users"]),
        "access_requests": len(data["access_requests"]),
        "approved_roles": len(data["approved_roles"]),
    }


def run_ingest(session: Session | None = None, data_dir: Path | None = None) -> dict[str, int]:
    data = load_csv_data(data_dir)
    if session is None:
        engine = get_engine()
        init_database(engine)
        session = Session(bind=engine)
        try:
            return populate_database(session, data)
        finally:
            session.close()
    return populate_database(session, data)
