#!/usr/bin/env python
"""scripts/restore_data.py — Restore PostbackEngine data from JSON backup."""
import os, sys, django, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse
from django.core import serializers

def main():
    parser = argparse.ArgumentParser(description="Restore PostbackEngine backup")
    parser.add_argument("files", nargs="+", help="Backup JSON files to restore")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue

        with open(filepath, "r") as f:
            data = f.read()

        objects = list(serializers.deserialize("json", data))
        print(f"\n{filepath}: {len(objects)} objects")

        if not args.dry_run:
            restored = 0
            for obj in objects:
                try:
                    obj.save()
                    restored += 1
                except Exception as exc:
                    print(f"  Failed to restore {obj}: {exc}")
            print(f"  Restored {restored}/{len(objects)} objects")
        else:
            print(f"  DRY RUN: would restore {len(objects)} objects")

if __name__ == "__main__":
    main()
