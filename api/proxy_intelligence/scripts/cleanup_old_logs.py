#!/usr/bin/env python3
"""
Script: cleanup_old_logs.py
============================
Standalone script to clean up old proxy intelligence logs.
Run directly without Django management command infrastructure.

Usage:
    python scripts/cleanup_old_logs.py
    python scripts/cleanup_old_logs.py --days 14 --dry-run
    python scripts/cleanup_old_logs.py --model APIRequestLog --days 7
    python scripts/cleanup_old_logs.py --stats

Requires Django to be configured before running.
"""
import os
import sys
import argparse
import logging
from datetime import timedelta

# ── Django setup ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s'
)

from django.utils import timezone

# ── Default retention per model (days) ────────────────────────────────────
DEFAULT_RETENTION = {
    'APIRequestLog':        30,
    'PerformanceMetric':    90,
    'VelocityMetric':        7,
    'AnomalyDetectionLog':  90,
    'VPNDetectionLog':      90,
    'ProxyDetectionLog':    90,
}

DATE_FIELDS = {
    'PerformanceMetric': 'recorded_at',
}


def get_count(model_name: str, cutoff) -> int:
    from api.proxy_intelligence import models as m
    Model = getattr(m, model_name, None)
    if not Model:
        return 0
    date_field = DATE_FIELDS.get(model_name, 'created_at')
    return Model.objects.filter(**{f'{date_field}__lt': cutoff}).count()


def delete_old(model_name: str, cutoff, batch_size: int = 5000) -> int:
    from api.proxy_intelligence import models as m
    Model = getattr(m, model_name, None)
    if not Model:
        return 0
    date_field   = DATE_FIELDS.get(model_name, 'created_at')
    total_deleted = 0
    while True:
        pks = list(
            Model.objects.filter(**{f'{date_field}__lt': cutoff})
            .values_list('pk', flat=True)[:batch_size]
        )
        if not pks:
            break
        deleted, _ = Model.objects.filter(pk__in=pks).delete()
        total_deleted += deleted
    return total_deleted


def show_stats():
    print('\n  Current database record counts:')
    print(f'  {"Model":<30} {"Records":>12}')
    print(f'  {"-"*44}')
    from api.proxy_intelligence import models as m
    total = 0
    for model_name in DEFAULT_RETENTION:
        Model = getattr(m, model_name, None)
        if Model:
            try:
                count = Model.objects.count()
                total += count
                print(f'  {model_name:<30} {count:>12,}')
            except Exception as e:
                print(f'  {model_name:<30} {"ERROR":>12}')
    print(f'  {"-"*44}')
    print(f'  {"TOTAL":<30} {total:>12,}\n')


def main():
    parser = argparse.ArgumentParser(
        description='Proxy Intelligence Log Cleanup Script'
    )
    parser.add_argument('--days', type=int, default=None,
                        help='Delete records older than N days (overrides per-model defaults)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Count records without deleting')
    parser.add_argument('--stats', action='store_true',
                        help='Show current record counts')
    parser.add_argument('--model',
                        choices=list(DEFAULT_RETENTION.keys()) + ['all'],
                        default='all',
                        help='Specific model to clean (default: all)')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Batch delete size (default: 5000)')

    args = parser.parse_args()

    print(f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M")}] Starting log cleanup...')
    if args.dry_run:
        print('[DRY RUN] No records will be deleted.\n')

    if args.stats:
        show_stats()

    # Determine models to clean
    if args.model == 'all':
        to_clean = list(DEFAULT_RETENTION.items())
    else:
        to_clean = [(args.model, DEFAULT_RETENTION[args.model])]

    total_deleted = 0
    total_would   = 0

    for model_name, default_days in to_clean:
        days   = args.days if args.days is not None else default_days
        cutoff = timezone.now() - timedelta(days=days)

        count = get_count(model_name, cutoff)
        print(f'\n  {model_name} (>{days}d old):')

        if args.dry_run:
            print(f'    ~ Would delete: {count:,} records')
            total_would += count
        else:
            deleted = delete_old(model_name, cutoff, args.batch_size)
            total_deleted += deleted
            icon = '✓' if deleted == count else '!'
            print(f'    {icon} Deleted: {deleted:,} records')

    print('')
    if args.dry_run:
        print(f'[DRY RUN] Would delete {total_would:,} total records.')
    else:
        print(f'Cleanup complete. Deleted {total_deleted:,} records.')

    if args.stats and not args.dry_run:
        show_stats()


if __name__ == '__main__':
    main()
