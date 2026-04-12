#!/usr/bin/env python3
"""
Script: Force sync all database replicas with primary.
Usage: python sync_replicas.py [--primary HOST] [--check-only]
"""
import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Sync database replicas with primary")
    parser.add_argument("--primary", default="localhost", help="Primary DB host")
    parser.add_argument("--replicas", nargs="+", default=[], help="Replica hosts")
    parser.add_argument("--check-only", action="store_true",
                         help="Only check lag, do not force sync")
    parser.add_argument("--max-lag", type=float, default=60.0,
                         help="Maximum acceptable lag in seconds")
    args = parser.parse_args()

    from disaster_recovery.REPLICATION_MANAGEMENT.replication_monitor import ReplicationMonitor
    from disaster_recovery.REPLICATION_MANAGEMENT.replication_sync import ReplicationSync
    from disaster_recovery.dependencies import SessionLocal

    db = SessionLocal()
    monitor = ReplicationMonitor(db_session=db)
    syncer = ReplicationSync()

    replicas = args.replicas or ["replica-1", "replica-2"]
    replica_configs = [{"host": r, "max_lag_seconds": args.max_lag} for r in replicas]

    logger.info(f"Checking replication status: primary={args.primary}")
    results = monitor.check_all_replicas(args.primary, replica_configs)

    all_healthy = True
    for result in results:
        lag = result.get("lag_seconds", 0)
        healthy = result.get("healthy", False)
        status = "✅ OK" if healthy else f"❌ HIGH LAG"
        logger.info(f"  {result['replica']}: {status} (lag={lag:.1f}s)")
        if not healthy:
            all_healthy = False
            if not args.check_only:
                logger.warning(f"  Initiating resync for {result['replica']}...")
                sync_result = syncer.resync_replica(args.primary, result["replica"])
                logger.info(f"  Resync: {sync_result}")

    if all_healthy:
        logger.info("All replicas healthy ✅")
        sys.exit(0)
    else:
        logger.warning("Some replicas have high lag ⚠️")
        sys.exit(1 if args.check_only else 0)

    db.close()


if __name__ == "__main__":
    main()
