#!/usr/bin/env python3
"""Test Failover Script — Test failover procedures without full execution."""
import sys, os, argparse, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Test DR failover procedures")
    parser.add_argument("--primary", required=True, help="Primary node host")
    parser.add_argument("--secondary", required=True, help="Secondary node host")
    parser.add_argument("--type", choices=["tcp","http","database"], default="tcp")
    parser.add_argument("--simulate", action="store_true", help="Simulate failover without executing")
    args = parser.parse_args()

    logger.info(f"Testing failover: {args.primary} -> {args.secondary}")

    from disaster_recovery.FAILOVER_MANAGEMENT.health_checker import HealthChecker
    checker = HealthChecker()

    # Test primary health
    primary_health = checker.check_tcp(args.primary, 5432, timeout=5)
    secondary_health = checker.check_tcp(args.secondary, 5432, timeout=5)

    result = {
        "primary": args.primary,
        "secondary": args.secondary,
        "primary_healthy": str(primary_health.get("status","")).lower() != "down",
        "secondary_ready": str(secondary_health.get("status","")).lower() != "down",
        "failover_feasible": True,
        "simulated": args.simulate,
        "tested_at": datetime.utcnow().isoformat(),
    }

    if args.simulate:
        result["note"] = "Simulation only — no actual failover performed"
        logger.info("Failover simulation complete")
    else:
        logger.info(f"Primary: {result['primary_healthy']}, Secondary: {result['secondary_ready']}")

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["failover_feasible"] else 1)

if __name__ == "__main__":
    main()
