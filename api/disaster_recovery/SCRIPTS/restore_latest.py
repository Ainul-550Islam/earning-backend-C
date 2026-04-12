#!/usr/bin/env python3
"""Script: Restore from the latest successful backup."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from disaster_recovery.dependencies import SessionLocal
from disaster_recovery.services import RestoreService, BackupService

def main():
    parser = argparse.ArgumentParser(description="Restore from latest backup")
    parser.add_argument("--database", required=True, help="Target database name")
    parser.add_argument("--approver", default="script", help="Approver ID")
    args = parser.parse_args()
    db = SessionLocal()
    backup_svc = BackupService(db)
    latest = backup_svc.repo.get_latest_successful_job(args.database)
    if not latest:
        print(f"ERROR: No backup found for database: {args.database}")
        sys.exit(1)
    print(f"Found backup: {latest.id} (completed: {latest.completed_at})")
    restore_svc = RestoreService(db)
    req = restore_svc.request_restore(
        {"backup_job_id": latest.id, "restore_type": "full", "target_database": args.database},
        requested_by=args.approver
    )
    restore_svc.approve_restore(req.id, approver=args.approver)
    restore_svc.execute_restore(req.id)
    print(f"Restore initiated: {req.id}")
    db.close()

if __name__ == "__main__":
    main()
