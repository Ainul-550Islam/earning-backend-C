#!/usr/bin/env python3
"""Script: Trigger all active backup policies. Usage: python backup_all.py [--type incremental] [--dry-run]"""
import sys, os, argparse, logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Trigger all active backup policies")
    parser.add_argument("--type", choices=["full","incremental","differential"], default="incremental")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--policy-id", type=str, default=None)
    parser.add_argument("--notify", action="store_true", default=False)
    args = parser.parse_args()

    from disaster_recovery.dependencies import SessionLocal
    from disaster_recovery.services import BackupService
    from disaster_recovery.enums import BackupType

    type_map = {"full": BackupType.FULL, "incremental": BackupType.INCREMENTAL, "differential": BackupType.DIFFERENTIAL}
    backup_type = type_map[args.type]
    db = SessionLocal()
    svc = BackupService(db)

    try:
        if args.policy_id:
            policies = [svc.repo.get_policy(args.policy_id)]
        else:
            policies = svc.repo.list_policies(active_only=True)

        logger.info(f"Backup run: {len(policies)} policies, type={args.type}, dry_run={args.dry_run}")
        success_count = 0
        failed_count = 0

        for policy in policies:
            logger.info(f"Processing policy: {policy.name} ({policy.id[:8]}...)")
            if args.dry_run:
                logger.info(f"  [DRY RUN] Would trigger {args.type} backup for: {policy.name}")
                continue
            try:
                job = svc.trigger_backup(policy_id=policy.id, backup_type=backup_type, actor_id="backup_all_script")
                logger.info(f"  ✅ Triggered: job={job.id[:8]}... status={job.status.value}")
                success_count += 1
            except Exception as e:
                logger.error(f"  ❌ Failed for {policy.name}: {e}")
                failed_count += 1

        if not args.dry_run:
            logger.info(f"Backup run complete: {success_count} triggered, {failed_count} failed")

        sys.exit(1 if failed_count > 0 else 0)
    except Exception as e:
        logger.error(f"Backup run failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
