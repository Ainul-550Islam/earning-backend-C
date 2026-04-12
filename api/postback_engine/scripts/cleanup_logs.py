#!/usr/bin/env python
"""scripts/cleanup_logs.py — Delete old postback logs per retention policy."""
import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse
from datetime import timedelta
from django.utils import timezone

def main():
    parser = argparse.ArgumentParser(description="Clean up old postback logs")
    parser.add_argument("--days", type=int, default=90, help="Delete logs older than N days")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.postback_engine.models import PostbackRawLog, ClickLog, FraudAttemptLog
    cutoff = timezone.now() - timedelta(days=args.days)

    qs_pb = PostbackRawLog.objects.filter(received_at__lt=cutoff)
    qs_cl = ClickLog.objects.filter(clicked_at__lt=cutoff)
    qs_fr = FraudAttemptLog.objects.filter(detected_at__lt=cutoff)

    if args.dry_run:
        print(f"DRY RUN (>{args.days}d old):")
        print(f"  PostbackRawLogs: {qs_pb.count()}")
        print(f"  ClickLogs: {qs_cl.count()}")
        print(f"  FraudAttemptLogs: {qs_fr.count()}")
    else:
        pb_deleted, _ = qs_pb.delete()
        cl_deleted, _ = qs_cl.delete()
        fr_deleted, _ = qs_fr.delete()
        print(f"Deleted: {pb_deleted} postbacks, {cl_deleted} clicks, {fr_deleted} fraud logs")

if __name__ == "__main__":
    main()
