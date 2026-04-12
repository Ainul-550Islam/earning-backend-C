#!/usr/bin/env python3
"""
Script: Sync Threat Feeds
==========================
Pulls latest threat intelligence data from all active feed providers
and updates the MaliciousIPDatabase.

Usage:
    python scripts/sync_threat_feeds.py
    python scripts/sync_threat_feeds.py --feed abuseipdb
    python scripts/sync_threat_feeds.py --check-ip 1.2.3.4
    python scripts/sync_threat_feeds.py --reset-quota

Requires Django to be configured before running.
"""
import os
import sys
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))))

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s %(levelname)s %(message)s')

from api.proxy_intelligence.threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator
from api.proxy_intelligence.models import ThreatFeedProvider


def print_table_header():
    print(f"\n{'Feed':<20} {'Status':<15} {'Entries':<12} {'Last Sync':<25}")
    print('-' * 75)


def sync_all(feed_name: str = 'all', dry_run: bool = False):
    """Sync all active threat feeds."""
    providers = ThreatFeedProvider.objects.filter(is_active=True)
    if feed_name != 'all':
        providers = providers.filter(name=feed_name)

    if not providers.exists():
        print(f"❌ No active feed found matching: {feed_name}")
        return

    print(f"\n🔄 Syncing {providers.count()} threat feed(s)...")
    if dry_run:
        print("⚠️  [DRY RUN] No changes will be made.\n")

    print_table_header()

    if dry_run:
        for p in providers:
            print(f"  ~ {p.display_name:<18} [would sync] "
                  f"{p.total_entries:<12} "
                  f"{str(p.last_sync or 'never'):<25}")
        return

    integrator = ThreatFeedIntegrator()
    results = integrator.sync_all_feeds()

    for feed, status in results.items():
        is_error = 'error' in str(status).lower()
        icon = '✗' if is_error else '✓'
        provider = providers.filter(name=feed).first()
        entries = provider.total_entries if provider else '-'
        print(f"  {icon} {feed:<18} {str(status):<15} {str(entries):<12}")

    print(f"\n✅ Sync complete at {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def check_single_ip(ip_address: str):
    """Check a single IP against all threat feeds."""
    print(f"\n🔍 Checking IP: {ip_address}")
    print('-' * 50)

    integrator = ThreatFeedIntegrator()
    result = integrator.check_ip(ip_address)

    print(f"  Malicious:      {'YES ⚠️' if result['is_malicious'] else 'No ✓'}")
    print(f"  Max Confidence: {result['max_confidence']:.1%}")
    print(f"  Threat Types:   {', '.join(result['threat_types']) or 'none'}")
    print(f"  Feeds Checked:  {result['feeds_checked']}")

    if result.get('feed_results'):
        print("\n  Feed Results:")
        for fr in result['feed_results']:
            print(f"    [{fr.get('feed','?')}] confidence={fr.get('confidence',0):.2f}")


def reset_quota():
    """Reset daily API usage counters."""
    count = ThreatFeedProvider.objects.all().update(used_today=0)
    print(f"✓ Reset daily quota for {count} feed providers.")


def list_feeds():
    """List all configured threat feed providers."""
    providers = ThreatFeedProvider.objects.all().order_by('priority')
    if not providers.exists():
        print("No threat feeds configured.")
        return

    print(f"\n{'#':<4} {'Name':<20} {'Display':<25} {'Active':<8} "
          f"{'Quota':<12} {'Used':<8} {'Last Sync'}")
    print('-' * 90)
    for p in providers:
        active = '✓' if p.is_active else '✗'
        print(f"  {p.priority:<4} {p.name:<20} {p.display_name:<25} "
              f"{active:<8} {p.daily_quota:<12} {p.used_today:<8} "
              f"{str(p.last_sync or 'never')[:19]}")


def main():
    parser = argparse.ArgumentParser(
        description='Proxy Intelligence — Threat Feed Sync Tool'
    )
    parser.add_argument('--feed', default='all',
                        help='Feed name to sync (default: all)')
    parser.add_argument('--check-ip', metavar='IP',
                        help='Check a single IP against all feeds')
    parser.add_argument('--list-feeds', action='store_true',
                        help='List all configured feeds')
    parser.add_argument('--reset-quota', action='store_true',
                        help='Reset daily API usage counters')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')

    args = parser.parse_args()

    if args.list_feeds:
        list_feeds()
    elif args.reset_quota:
        reset_quota()
    elif args.check_ip:
        check_single_ip(args.check_ip)
    else:
        sync_all(feed_name=args.feed, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
