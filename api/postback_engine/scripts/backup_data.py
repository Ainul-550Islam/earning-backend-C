#!/usr/bin/env python
"""scripts/backup_data.py — Export PostbackEngine data to JSON backup."""
import os, sys, django, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse
from datetime import timedelta
from django.utils import timezone
from django.core import serializers

def main():
    parser = argparse.ArgumentParser(description="Backup PostbackEngine data")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--days", type=int, default=30, help="Export last N days of data")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    cutoff = timezone.now() - timedelta(days=args.days)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

    from api.postback_engine.models import Conversion, ClickLog, FraudAttemptLog

    exports = {
        "conversions": Conversion.objects.filter(converted_at__gte=cutoff),
        "clicks": ClickLog.objects.filter(clicked_at__gte=cutoff),
        "fraud_attempts": FraudAttemptLog.objects.filter(detected_at__gte=cutoff),
    }

    for name, qs in exports.items():
        filepath = os.path.join(args.output, f"{timestamp}_{name}.json")
        with open(filepath, "w") as f:
            f.write(serializers.serialize("json", qs))
        print(f"Exported {qs.count()} {name} to {filepath}")

if __name__ == "__main__":
    main()
