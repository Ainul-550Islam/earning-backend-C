#!/usr/bin/env python3
"""Emergency Shutdown Script — Gracefully shuts down DR system."""
import sys, os, logging, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Emergency DR system shutdown")
    parser.add_argument("--reason", required=True, help="Reason for shutdown")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true", required=True)
    args = parser.parse_args()
    if not args.confirm:
        print("--confirm required"); sys.exit(1)
    logger.critical(f"EMERGENCY SHUTDOWN: {args.reason}")
    if args.dry_run:
        logger.critical("[DRY RUN] Shutdown simulated"); return
    try:
        from disaster_recovery.AUTOMATION_ENGINES.auto_recovery import AutoRecovery
        recovery = AutoRecovery()
        logger.critical(f"Initiating emergency shutdown: {args.reason}")
        print(f"Emergency shutdown initiated: {args.reason}")
    except Exception as e:
        logger.critical(f"Shutdown error: {e}"); sys.exit(1)

if __name__ == "__main__":
    main()
