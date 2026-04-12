#!/usr/bin/env python3
"""Script: Verify integrity of recent backups. Usage: python verify_backups.py [--days 7] [--fix]"""
import sys, os, argparse, logging, json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Verify recent backup integrity")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--policy-id", type=str, default=None)
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--min-verified-pct", type=float, default=90.0)
    args = parser.parse_args()

    from disaster_recovery.dependencies import SessionLocal
    from disaster_recovery.services import BackupService
    from disaster_recovery.enums import BackupStatus
    from disaster_recovery.BACKUP_MANAGEMENT.backup_verifier import BackupVerifier

    db = SessionLocal()
    svc = BackupService(db)
    verifier = BackupVerifier()

    try:
        cutoff = datetime.utcnow() - timedelta(days=args.days)
        logger.info(f"Verifying backups from last {args.days} days")

        query_params = {"status": BackupStatus.COMPLETED, "page": 1, "page_size": 500}
        if args.policy_id: query_params["policy_id"] = args.policy_id
        result = svc.repo.list_jobs(**query_params)
        jobs = [j for j in result["items"] if j.created_at and j.created_at >= cutoff]

        logger.info(f"Found {len(jobs)} completed backups to verify")
        verified_count = 0
        failed_count = 0
        already_verified = 0
        verification_results = []

        for job in jobs:
            if job.is_verified:
                already_verified += 1
                verification_results.append({"job_id": job.id, "status": "already_verified"})
                continue

            logger.info(f"Verifying: {job.id[:8]}...")
            if not job.storage_path or not job.checksum:
                verification_results.append({"job_id": job.id, "status": "skipped", "reason": "no checksum"})
                continue

            verify_result = verifier.verify(job.storage_path, job.checksum)
            is_valid = verify_result.get("checksum_valid", False)

            if is_valid:
                svc.repo.mark_verified(job.id)
                verified_count += 1
                logger.info(f"  ✅ Verified: {job.id[:8]}...")
            else:
                failed_count += 1
                logger.error(f"  ❌ FAILED: {job.id[:8]}...")
                if args.fix:
                    try:
                        svc.trigger_backup(policy_id=job.policy_id, backup_type=job.backup_type, actor_id="verify_backups_script")
                        logger.info(f"  Replacement backup triggered")
                    except Exception as e:
                        logger.error(f"  Could not re-trigger: {e}")

            verification_results.append({"job_id": job.id, "status": "verified" if is_valid else "failed",
                                          "checksum_valid": is_valid})

        total = len(jobs)
        verified_total = verified_count + already_verified
        verified_pct = round(verified_total / max(total, 1) * 100, 2)

        logger.info(f"\n=== VERIFICATION SUMMARY ===")
        logger.info(f"Total: {total} | Already verified: {already_verified} | Newly verified: {verified_count} | Failed: {failed_count}")
        logger.info(f"Verification rate: {verified_pct}%")

        if args.output:
            report = {"verified_at": datetime.utcnow().isoformat(), "period_days": args.days,
                      "total": total, "verified": verified_total, "failed": failed_count,
                      "verified_percent": verified_pct, "results": verification_results}
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Results saved: {args.output}")

        sys.exit(1 if verified_pct < args.min_verified_pct or failed_count > 0 else 0)
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
