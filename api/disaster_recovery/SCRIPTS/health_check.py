#!/usr/bin/env python3
"""Script: Comprehensive DR system health check. Usage: python health_check.py [--output json]"""
import sys, os, argparse, logging, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="DR System health check")
    parser.add_argument("--output", choices=["text","json"], default="text")
    parser.add_argument("--fail-on-degraded", action="store_true")
    parser.add_argument("--component", type=str, default=None)
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    from disaster_recovery.config import settings
    from disaster_recovery.FAILOVER_MANAGEMENT.health_checker import HealthChecker
    from disaster_recovery.MONITORING_ALERTING.system_monitor import SystemMonitor
    from disaster_recovery.dependencies import SessionLocal

    checker = HealthChecker()
    sys_monitor = SystemMonitor()
    db = SessionLocal()

    COMPONENTS = [
        {"name": "api-server", "type": "http", "url": f"http://localhost:{settings.port}/health", "timeout": args.timeout},
        {"name": "database-primary", "type": "database", "url": settings.database_url},
        {"name": "redis", "type": "tcp", "host": "localhost", "port": 6379, "timeout": args.timeout},
        {"name": "backup-storage", "type": "disk", "path": "/var/backups/dr"},
        {"name": "system", "type": "system"},
    ]
    if args.component:
        COMPONENTS = [c for c in COMPONENTS if c["name"] == args.component]

    results = {}
    overall_status = "healthy"
    failed_components = []
    degraded_components = []

    logger.info(f"Running health check on {len(COMPONENTS)} components...")

    for comp in COMPONENTS:
        name = comp["name"]
        try:
            if comp["type"] == "http": result = checker.check_http(comp["url"], timeout=comp.get("timeout",10))
            elif comp["type"] == "database": result = checker.check_database(comp["url"])
            elif comp["type"] == "tcp": result = checker.check_tcp(comp["host"], comp["port"], timeout=comp.get("timeout",10))
            elif comp["type"] == "disk": result = checker.check_disk(comp.get("path","/"))
            elif comp["type"] == "system":
                m = sys_monitor.collect_minimal()
                cpu = m.get("cpu_percent",0) or 0
                result = {"status": "critical" if cpu >= 90 else "degraded" if cpu >= 80 else "healthy", **m}
            else: result = {"status": "unknown"}

            status = result.get("status","")
            if hasattr(status, "value"): status = status.value
            status = str(status).lower()
            results[name] = {"status": status, "details": result, "checked_at": datetime.utcnow().isoformat()}

            if status in ("down","critical"):
                overall_status = "critical"; failed_components.append(name)
                logger.error(f"  ❌ {name}: {status.upper()}")
            elif status == "degraded":
                if overall_status == "healthy": overall_status = "degraded"
                degraded_components.append(name); logger.warning(f"  ⚠️  {name}: DEGRADED")
            else:
                rt = result.get("response_time_ms","")
                logger.info(f"  ✅ {name}: {status.upper()}{f' ({rt:.0f}ms)' if isinstance(rt,(int,float)) else ''}")
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}
            failed_components.append(name); logger.error(f"  ❌ {name}: ERROR — {e}")

    final = {"overall_status": overall_status, "checked_at": datetime.utcnow().isoformat(),
             "failed_components": failed_components, "degraded_components": degraded_components,
             "components": results}

    if args.output == "json":
        print(json.dumps(final, indent=2, default=str))
    else:
        logger.info(f"\n=== HEALTH CHECK: {overall_status.upper()} ===")
        if failed_components: logger.error(f"Failed: {failed_components}")
        if degraded_components: logger.warning(f"Degraded: {degraded_components}")

    db.close()
    if overall_status == "critical" or failed_components: sys.exit(2)
    if args.fail_on_degraded and degraded_components: sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
