#!/usr/bin/env python
"""scripts/generate_report.py — Generate a performance report for a date range."""
import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse, json

def main():
    parser = argparse.ArgumentParser(description="Generate PostbackEngine report")
    parser.add_argument("--type", choices=["daily","weekly","monthly"], default="daily")
    parser.add_argument("--network", default=None)
    parser.add_argument("--output", default="-", help="Output file (- for stdout)")
    args = parser.parse_args()

    if args.type == "daily":
        from api.postback_engine.analytics_reporting.daily_report import daily_report
        data = daily_report.generate()
    elif args.type == "weekly":
        from api.postback_engine.analytics_reporting.weekly_report import weekly_report
        data = weekly_report.generate()
    elif args.type == "monthly":
        from api.postback_engine.analytics_reporting.monthly_report import monthly_report
        data = monthly_report.generate()

    output = json.dumps(data, indent=2, default=str)
    if args.output == "-":
        print(output)
    else:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to {args.output}")

if __name__ == "__main__":
    main()
