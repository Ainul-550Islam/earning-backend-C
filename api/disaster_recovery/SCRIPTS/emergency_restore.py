#!/usr/bin/env python3
"""Script: Emergency restore from latest backup. Usage: python emergency_restore.py --database DB --confirm"""
import sys, os, argparse, logging, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Emergency restore from latest backup")
    parser.add_argument("--database", required=True, help="Target database to restore")
    parser.add_argument("--confirm", action="store_true", required=True, help="WILL OVERWRITE CURRENT DATA")
    parser.add_argument("--backup-id", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-snapshot", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    if not args.confirm:
        print("ERROR: --confirm is required. This will OVERWRITE current database data!")
        sys.exit(1)

    print(f"""
╔════════════════════════════════════════════════╗
║        EMERGENCY RESTORE INITIATED              ║
╠════════════════════════════════════════════════╣
║  Database: {args.database:<36}║
║  Dry Run:  {str(args.dry_run):<36}║
║  Time:     {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'):<36}║
╚════════════════════════════════════════════════╝
    """)

    from disaster_recovery.dependencies import SessionLocal
    from disaster_recovery.AUTOMATION_ENGINES.auto_restore import AutoRestore
    from disaster_recovery.config import settings

    db = SessionLocal()
    try:
        restore_engine = AutoRestore(db_session=db, config={
            "db_host": "localhost", "db_port": 5432, "db_user": "postgres"})

        backup = restore_engine._find_best_backup(args.database, "full") if not args.backup_id else {"id": args.backup_id}
        if not backup:
            logger.critical(f"ERROR: No backup found for: {args.database}")
            sys.exit(1)

        logger.critical(f"Using backup: {backup.get('id','')}")

        if args.dry_run:
            result = {"success": True, "dry_run": True, "database": args.database,
                      "backup_id": backup.get("id",""), "timestamp": datetime.utcnow().isoformat()}
        else:
            result = restore_engine.restore_from_latest(
                target_database=args.database, requested_by="emergency_restore_script",
                restore_type="full", create_pre_restore_snapshot=not args.skip_snapshot)

        success = result.get("success", False)
        print(f"\nEMERGENCY RESTORE: {'SUCCESS ✅' if success else 'FAILED ❌'}")
        if not success: print(f"Error: {result.get('error','Unknown error')}")

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            logger.critical(f"Report saved: {args.output}")

        sys.exit(0 if success or args.dry_run else 1)
    except Exception as e:
        logger.critical(f"EMERGENCY RESTORE FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
