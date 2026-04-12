#!/usr/bin/env python
"""scripts/replay_failed.py — Replay all failed postbacks."""
import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse

def main():
    parser = argparse.ArgumentParser(description="Replay failed postbacks")
    parser.add_argument("--network", default=None, help="Filter by network_key")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.postback_engine.queue_management.batch_processor import batch_processor
    if args.dry_run:
        from api.postback_engine.models import PostbackRawLog
        from api.postback_engine.enums import PostbackStatus
        qs = PostbackRawLog.objects.filter(status=PostbackStatus.FAILED)
        if args.network: qs = qs.filter(network__network_key=args.network)
        print(f"DRY RUN: would replay {qs.count()} failed postbacks")
    else:
        result = batch_processor.replay_failed(network_key=args.network, limit=args.limit)
        print(f"Replayed: {result}")

if __name__ == "__main__":
    main()
