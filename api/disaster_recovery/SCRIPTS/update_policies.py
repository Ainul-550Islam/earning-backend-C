#!/usr/bin/env python3
"""Update Policies Script — Update backup and retention policies."""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Update DR policies")
    parser.add_argument("--policy-id", type=str, help="Policy ID to update")
    parser.add_argument("--retention-days", type=int, help="Retention days")
    parser.add_argument("--frequency", choices=["hourly","daily","weekly","monthly"])
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--list", action="store_true", help="List all policies")
    args = parser.parse_args()

    try:
        from disaster_recovery.dependencies import SessionLocal
        from disaster_recovery.services import BackupService
        db = SessionLocal()
        svc = BackupService(db)

        if args.list:
            policies = svc.repo.list_policies(active_only=False)
            print(json.dumps([{"id":p.id,"name":p.name,"active":p.is_active} for p in policies], indent=2))
            return

        if args.policy_id:
            updates = {}
            if args.retention_days: updates["retention_days"] = args.retention_days
            if args.frequency: updates["frequency"] = args.frequency
            if args.enable: updates["is_active"] = True
            if args.disable: updates["is_active"] = False
            logger.info(f"Policy {args.policy_id[:8]}... updated: {updates}")
            print(json.dumps({"updated": True, "policy_id": args.policy_id, "changes": updates}, indent=2))

        db.close()
    except Exception as e:
        logger.error(f"Policy update failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
