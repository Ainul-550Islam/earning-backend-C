#!/usr/bin/env python
"""scripts/monitor_queue.py — Live queue monitoring dashboard."""
import os, sys, django, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse

def get_queue_stats():
    from api.postback_engine.queue_management.queue_manager import queue_manager
    from api.postback_engine.analytics_reporting.real_time_dashboard import realtime_dashboard
    return {
        "queue": queue_manager.get_stats(),
        "realtime": realtime_dashboard.get_live_stats(),
    }

def main():
    parser = argparse.ArgumentParser(description="Monitor PostbackEngine queue")
    parser.add_argument("--interval", type=int, default=5, help="Refresh interval in seconds")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    while True:
        stats = get_queue_stats()
        if args.json:
            print(json.dumps(stats, default=str))
        else:
            rt = stats.get("realtime", {})
            q = stats.get("queue", {})
            print(f"\r[Queue Monitor] "
                  f"Conversions: {rt.get('conversions',0)} | "
                  f"Fraud: {rt.get('fraud_attempts',0)} | "
                  f"Errors: {rt.get('errors',0)} | "
                  f"Queue depth: {sum(q.values()) if isinstance(q, dict) else q}   ", end="")
            sys.stdout.flush()
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
