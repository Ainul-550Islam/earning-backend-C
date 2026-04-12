#!/usr/bin/env python3
"""Monitor Status Script — Real-time DR system status monitoring."""
import sys, os, argparse, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    parser = argparse.ArgumentParser(description="Monitor DR system status")
    parser.add_argument("--interval", type=int, default=30, help="Refresh interval seconds")
    parser.add_argument("--output", choices=["text","json"], default="text")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    from disaster_recovery.FAILOVER_MANAGEMENT.health_checker import HealthChecker
    from disaster_recovery.MONITORING_ALERTING.system_monitor import SystemMonitor

    checker = HealthChecker()
    sys_monitor = SystemMonitor()

    def check():
        health = checker.check_all([
            {"name":"api","type":"http","url":"http://localhost:8000/health"},
            {"name":"redis","type":"tcp","host":"localhost","port":6379},
        ])
        metrics = sys_monitor.collect_minimal()
        overall = str(health.get("overall","unknown")).lower()
        icons = {"healthy":"OK","degraded":"DEGRADED","down":"DOWN","unknown":"?"}
        status = {"overall": overall, "health": health, "metrics": metrics}
        if args.output == "json":
            print(json.dumps(status, default=str))
        else:
            icon = icons.get(overall, "?")
            print(f"  Status: [{icon}] {overall.upper()}")
            print(f"  CPU: {metrics.get('cpu_percent','?')}%  MEM: {metrics.get('memory_percent','?')}%  DISK: {metrics.get('disk_percent','?')}%")
        return overall

    if args.once:
        check(); return
    try:
        while True:
            check()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Monitoring stopped.")

if __name__ == "__main__":
    main()
