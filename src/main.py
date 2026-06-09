"""
System Access Governance & MIS Reporting Tool
-----------------------------------------------
End-to-end pipeline for access governance, exception detection,
audit logging, and management reporting.

Usage:
    python main.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure src is on path when run directly
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from audit import generate_audit_trail
from database import get_engine, get_session_factory, init_database
from ingest import run_ingest
from reporting import export_all_reports
from rules_engine import get_exception_summary, run_governance_rules


def print_banner() -> None:
    print("=" * 72)
    print("  SYSTEM ACCESS GOVERNANCE & MIS REPORTING TOOL")
    print("  Group Access Management | Governance & Controls | MIS Reporting")
    print("=" * 72)


def run_pipeline() -> dict:
    start = time.perf_counter()
    print_banner()

    engine = get_engine()
    init_database(engine)
    Session = get_session_factory(engine)
    session = Session()

    try:
        print("\n[Step 1/7] Loading CSV data...")
        counts = run_ingest(session=session)
        print(f"  -> Loaded {counts['users']} users, "
              f"{counts['access_requests']} requests, "
              f"{counts['approved_roles']} role definitions")

        print("\n[Step 2/7] Database populated (SQLite).")

        print("\n[Step 3/7] Running governance rules engine...")
        findings = run_governance_rules(session)
        summary = get_exception_summary(session)
        print(f"  -> {len(findings)} exceptions detected")
        for sev in ["High", "Medium", "Low"]:
            print(f"     {sev}: {summary['by_severity'].get(sev, 0)}")

        print("\n[Step 4/7] Exceptions persisted to database.")

        print("\n[Step 5/7] Generating audit trail...")
        audit_entries = generate_audit_trail(session)
        print(f"  -> {len(audit_entries)} audit events recorded")

        print("\n[Step 6/7] Building MIS dashboard...")
        reports = export_all_reports(session)

        print("\n[Step 7/7] Reports exported:")
        for name, path in reports.items():
            if isinstance(path, list):
                for p in path:
                    print(f"  -> {p}")
            else:
                print(f"  -> {path}")

        elapsed = time.perf_counter() - start
        print(f"\nPipeline completed in {elapsed:.2f}s")
        print("=" * 72)

        return {
            "counts": counts,
            "exceptions": len(findings),
            "audit_events": len(audit_entries),
            "reports": reports,
        }
    finally:
        session.close()


if __name__ == "__main__":
    run_pipeline()
