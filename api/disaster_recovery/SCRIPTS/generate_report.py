#!/usr/bin/env python3
"""Generate Report Script — Generate DR status and compliance reports."""
import sys, os, argparse, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Generate DR reports")
    parser.add_argument("--type", choices=["backup","failover","drill","sla","all"],
                         default="all", dest="report_type")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", type=str, default=f"dr_report_{datetime.utcnow().strftime('%Y%m%d')}.json")
    args = parser.parse_args()

    try:
        from disaster_recovery.dependencies import SessionLocal
        from disaster_recovery.services import BackupService
        db = SessionLocal()
        svc = BackupService(db)
        stats = svc.repo.get_backup_stats(days=args.days)
        report = {
            "report_type": args.report_type,
            "period_days": args.days,
            "generated_at": datetime.utcnow().isoformat(),
            "backup_stats": stats,
        }
        db.close()
    except Exception as e:
        logger.warning(f"DB unavailable: {e}")
        report = {
            "report_type": args.report_type,
            "period_days": args.days,
            "generated_at": datetime.utcnow().isoformat(),
            "note": "Generated without DB connection",
        }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Report saved: {args.output}")
    print(f"Report generated: {args.output}")

if __name__ == "__main__":
    main()
