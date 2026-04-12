#!/usr/bin/env python3
"""Run Drill Script — Execute DR drills from command line."""
import sys, os, argparse, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging_import = "import logging"
exec(logging_import)
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Run a DR drill")
    parser.add_argument("--scenario", required=True,
        choices=["database_failover","backup_restore","region_failover","chaos"],
        help="Drill scenario type")
    parser.add_argument("--name", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    drill_name = args.name or f"{args.scenario}_drill"
    logger.info(f"Starting DR drill: {drill_name} ({args.scenario})")

    if args.dry_run:
        result = {"success": True, "drill_id": "dry-run", "dry_run": True,
                  "scenario": args.scenario, "name": drill_name}
    else:
        try:
            from disaster_recovery.dependencies import SessionLocal
            from disaster_recovery.DR_DRILL_MANAGEMENT.drill_executor import DrillExecutor
            import uuid
            drill_id = str(uuid.uuid4())[:8]
            executor = DrillExecutor(drill_id, args.scenario, dry_run=False)
            result = executor.execute()
        except Exception as e:
            logger.error(f"Drill failed: {e}")
            result = {"success": False, "error": str(e)}

    passed = result.get("success", False)
    logger.info(f"Drill {'PASSED' if passed else 'FAILED'}: {drill_name}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
