"""Generate realistic sample CSV datasets for the access governance platform."""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
random.seed(42)

DEPARTMENTS = ["Treasury", "Finance", "Risk", "Operations", "Compliance"]
LOCATIONS = ["Zurich", "London", "New York", "Singapore", "Hong Kong"]

ROLE_MATRIX = {
    "Treasury Analyst": ["Treasury Portal", "Funding Dashboard"],
    "Treasury Manager": ["Treasury Portal", "Funding Dashboard", "SWIFT Gateway"],
    "Finance Analyst": ["GL System", "Reporting Platform"],
    "Finance Manager": ["GL System", "Reporting Platform", "Treasury Portal"],
    "Risk Analyst": ["Risk Engine", "Stress Testing Tool"],
    "Risk Manager": ["Risk Engine", "Stress Testing Tool", "Trading System"],
    "Operations Analyst": ["Operations Hub", "Settlement System"],
    "Operations Manager": ["Operations Hub", "Settlement System", "SWIFT Gateway"],
    "Compliance Analyst": ["Compliance Portal", "AML Monitoring"],
    "Compliance Manager": ["Compliance Portal", "AML Monitoring", "Reporting Platform"],
}

SENSITIVE_SYSTEMS = {"SWIFT Gateway", "Trading System", "Risk Engine", "AML Monitoring"}

FIRST_NAMES = [
    "Anna", "Marco", "Sophie", "James", "Priya", "Liam", "Elena", "David",
    "Yuki", "Olivia", "Raj", "Emma", "Thomas", "Nina", "Carlos", "Fatima",
    "Michael", "Laura", "Wei", "Sarah", "Daniel", "Aisha", "Robert", "Claire",
    "Hassan", "Julia", "Kevin", "Mei", "Patrick", "Isabella", "Ahmed", "Grace",
    "Stefan", "Leila", "Brian", "Chloe", "Vikram", "Hannah", "Felix", "Zara",
]

LAST_NAMES = [
    "Mueller", "Rossi", "Chen", "Williams", "Patel", "O'Brien", "Kowalski",
    "Nakamura", "Schmidt", "Dubois", "Singh", "Anderson", "Garcia", "Kim",
    "Hoffman", "Ali", "Taylor", "Bernard", "Zhang", "Johnson", "Khan", "Lee",
    "Fischer", "Martin", "Okonkwo", "Santos", "Nguyen", "Brown", "Ivanov",
    "Murphy", "Hassan", "Wright", "Moreau", "Sharma", "Clark", "Weber", "Park",
    "Evans", "Rahman", "Cohen",
]

MANAGERS = [
    "Dr. Helena Vogel", "James Whitfield", "Sarah Nakamura", "Michael Torres",
    "Dr. Anika Sharma", "Robert Klein", "Elena Petrov", "David Okonkwo",
]


def _build_users(n: int = 40) -> pd.DataFrame:
    roles = list(ROLE_MATRIX.keys())
    users = []
    used_ids: set[str] = set()

    for i in range(n):
        user_id = f"EMP{1001 + i:04d}"
        while user_id in used_ids:
            user_id = f"EMP{random.randint(1001, 9999):04d}"
        used_ids.add(user_id)

        role = roles[i % len(roles)]
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[i % len(LAST_NAMES)]}"
        status = "Terminated" if i in {5, 12, 23, 31} else "Active"

        users.append(
            {
                "user_id": user_id,
                "employee_name": name,
                "department": dept,
                "location": LOCATIONS[i % len(LOCATIONS)],
                "manager": MANAGERS[i % len(MANAGERS)],
                "current_role": role,
                "employment_status": status,
            }
        )
    return pd.DataFrame(users)


def _build_role_matrix() -> pd.DataFrame:
    rows = []
    for role, systems in ROLE_MATRIX.items():
        rows.append({"role": role, "allowed_systems": "|".join(systems)})
    return pd.DataFrame(rows)


def _build_access_requests(users: pd.DataFrame, n: int = 120) -> pd.DataFrame:
    today = date.today()
    requests = []
    user_records = users.to_dict("records")

    for i in range(n):
        user = user_records[i % len(user_records)]
        role = user["current_role"]
        allowed = ROLE_MATRIX[role]
        all_systems = sorted({s for systems in ROLE_MATRIX.values() for s in systems})

        scenario = i % 10
        if scenario == 0:
            system = random.choice([s for s in all_systems if s not in allowed])
            approval = "Approved"
            closure = "Open"
        elif scenario == 1:
            system = random.choice(allowed)
            approval = "Pending"
            closure = "Open"
            req_date = today - timedelta(days=random.randint(16, 45))
        elif scenario == 2:
            system = random.choice(allowed)
            approval = "Rejected"
            closure = "Closed"
            req_date = today - timedelta(days=random.randint(1, 30))
        elif scenario == 3 and user["employment_status"] == "Terminated":
            system = random.choice(allowed)
            approval = "Approved"
            closure = "Open"
            req_date = today - timedelta(days=random.randint(30, 180))
        else:
            system = random.choice(allowed)
            approval = random.choice(["Approved", "Approved", "Pending", "Rejected"])
            closure = "Open" if approval == "Approved" else "Closed"
            req_date = today - timedelta(days=random.randint(1, 60))

        if scenario != 1:
            req_date = today - timedelta(days=random.randint(1, 90))

        if approval != "Approved":
            closure = "Closed" if approval == "Rejected" else "Open"

        requests.append(
            {
                "request_id": f"REQ{2024001 + i:05d}",
                "user_id": user["user_id"],
                "requested_system": system,
                "request_date": req_date.isoformat(),
                "approval_status": approval,
                "closure_status": closure,
            }
        )

    # Duplicate requests for Rule 5 (Low severity)
    for dup_idx in range(5):
        base = requests[dup_idx * 3]
        requests.append(
            {
                "request_id": f"REQ{2024200 + dup_idx:05d}",
                "user_id": base["user_id"],
                "requested_system": base["requested_system"],
                "request_date": base["request_date"],
                "approval_status": "Pending",
                "closure_status": "Open",
            }
        )

    # Users with >5 active systems
    power_user = user_records[0]
    for j, system in enumerate(
        ["Treasury Portal", "Funding Dashboard", "GL System", "Reporting Platform",
         "Risk Engine", "Operations Hub", "Compliance Portal"]
    ):
        requests.append(
            {
                "request_id": f"REQ{2024300 + j:05d}",
                "user_id": power_user["user_id"],
                "requested_system": system,
                "request_date": (today - timedelta(days=10 + j)).isoformat(),
                "approval_status": "Approved",
                "closure_status": "Open",
            }
        )

    return pd.DataFrame(requests)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    users = _build_users()
    role_matrix = _build_role_matrix()
    requests = _build_access_requests(users)

    users.to_csv(DATA_DIR / "users.csv", index=False)
    role_matrix.to_csv(DATA_DIR / "approved_role_matrix.csv", index=False)
    requests.to_csv(DATA_DIR / "access_requests.csv", index=False)

    print(f"Generated {len(users)} users, {len(requests)} access requests.")
    print(f"Files written to {DATA_DIR}")


if __name__ == "__main__":
    main()
