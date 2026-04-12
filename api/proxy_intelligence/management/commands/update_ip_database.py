"""
Management Command: update_ip_database
Usage: python manage.py update_ip_database [--source <name>] [--dry-run] [--stats]

Syncs datacenter IP ranges from public cloud provider sources.
Updates the DatacenterIPRange model with fresh CIDR blocks.
"""
import logging
import json
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Public IP Range Data Sources ──────────────────────────────────────────
IP_RANGE_SOURCES = {
    'aws': {
        'name':         'AWS',
        'url':          'https://ip-ranges.amazonaws.com/ip-ranges.json',
        'asn':          'AS16509',
        'parser':       'parse_aws',
        'description':  'Amazon Web Services IP ranges (S3, EC2, CloudFront, etc.)',
    },
    'cloudflare': {
        'name':         'Cloudflare',
        'url':          'https://www.cloudflare.com/ips-v4',
        'asn':          'AS13335',
        'parser':       'parse_plain_text',
        'description':  'Cloudflare CDN and proxy IP ranges',
    },
    'cloudflare_v6': {
        'name':         'Cloudflare-IPv6',
        'url':          'https://www.cloudflare.com/ips-v6',
        'asn':          'AS13335',
        'parser':       'parse_plain_text',
        'description':  'Cloudflare IPv6 ranges',
    },
    'google': {
        'name':         'Google Cloud',
        'url':          'https://www.gstatic.com/ipranges/cloud.json',
        'asn':          'AS15169',
        'parser':       'parse_google',
        'description':  'Google Cloud Platform IP ranges',
    },
    'azure': {
        'name':         'Microsoft Azure',
        'url':          'https://download.microsoft.com/download/7/1/D/71D86715-5596-4529-9B13-DA13A5DE5B63/ServiceTags_Public_20230227.json',
        'asn':          'AS8075',
        'parser':       'parse_azure',
        'description':  'Microsoft Azure public IP ranges',
    },
    'digitalocean': {
        'name':         'DigitalOcean',
        'url':          'https://digitalocean.com/geo/google.csv',
        'asn':          'AS14061',
        'parser':       'parse_digitalocean_csv',
        'description':  'DigitalOcean datacenter IP ranges',
    },
}


class Command(BaseCommand):
    help = 'Update datacenter IP range database from public cloud provider sources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            choices=list(IP_RANGE_SOURCES.keys()) + ['all'],
            default='all',
            help=f'IP range source to update (default: all). Choices: {", ".join(IP_RANGE_SOURCES.keys())}',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Count ranges without saving to database',
        )
        parser.add_argument(
            '--stats', action='store_true',
            help='Show database statistics after update',
        )
        parser.add_argument(
            '--deactivate-stale', action='store_true',
            help='Deactivate ranges not updated in 30 days',
        )
        parser.add_argument(
            '--list-sources', action='store_true',
            help='List all available sources and exit',
        )

    def handle(self, *args, **options):
        # ── List sources mode ────────────────────────────────────────────
        if options['list_sources']:
            self.stdout.write('\nAvailable IP range sources:\n')
            for key, info in IP_RANGE_SOURCES.items():
                self.stdout.write(f"  {key:<20} {info['name']:<25} ASN: {info['asn']}")
                self.stdout.write(f"               {info['description']}")
            return

        source_key = options['source']
        dry_run    = options['dry_run']

        sources = (
            IP_RANGE_SOURCES
            if source_key == 'all'
            else {source_key: IP_RANGE_SOURCES[source_key]}
        )

        self.stdout.write(self.style.NOTICE(
            f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M")}] '
            f'Updating IP database ({len(sources)} source(s))...'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes will be saved.\n'))

        total_added   = 0
        total_updated = 0
        total_errors  = 0

        for key, source in sources.items():
            self.stdout.write(f'\n  [{source["name"]}] Fetching...')
            try:
                ranges = self._fetch_ranges(source)
                if ranges is None:
                    self.stdout.write(self.style.WARNING(f'    ⚠ Skipped (fetch failed)'))
                    total_errors += 1
                    continue

                self.stdout.write(f'    Found {len(ranges)} CIDR ranges')

                if not dry_run:
                    added, updated = self._save_ranges(ranges, source)
                    total_added   += added
                    total_updated += updated
                    self.stdout.write(self.style.SUCCESS(
                        f'    ✓ Saved: +{added} new, ~{updated} updated'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'    ~ [DRY RUN] Would save {len(ranges)} ranges'
                    ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ✗ Error: {e}'))
                logger.exception(f'IP database update failed for {key}: {e}')
                total_errors += 1

        # ── Deactivate stale entries ─────────────────────────────────────
        if options['deactivate_stale'] and not dry_run:
            from api.proxy_intelligence.models import DatacenterIPRange
            cutoff  = timezone.now() - timedelta(days=30)
            stale   = DatacenterIPRange.objects.filter(
                is_active=True, last_updated__lt=cutoff
            )
            count   = stale.count()
            stale.update(is_active=False)
            self.stdout.write(self.style.WARNING(
                f'\n  Deactivated {count} stale ranges (>30 days old)'
            ))

        # ── Summary ──────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{"[DRY RUN] " if dry_run else ""}'
            f'Update complete: +{total_added} added, ~{total_updated} updated, '
            f'{total_errors} error(s)'
        ))

        # ── Stats ────────────────────────────────────────────────────────
        if options['stats']:
            self._show_stats()

    # ── Fetch Methods ──────────────────────────────────────────────────────

    def _fetch_ranges(self, source: dict) -> list:
        """Fetch and parse IP ranges from a source."""
        import requests
        try:
            resp = requests.get(source['url'], timeout=30)
            resp.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    ✗ HTTP error: {e}'))
            return None

        parser = getattr(self, f"_{source['parser']}", None)
        if not parser:
            self.stdout.write(self.style.ERROR(f"    ✗ Parser '{source['parser']}' not found"))
            return None

        try:
            return parser(resp, source)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    ✗ Parse error: {e}'))
            return None

    def _parse_aws(self, resp, source: dict) -> list:
        """Parse AWS ip-ranges.json format."""
        data   = resp.json()
        ranges = []
        for prefix in data.get('prefixes', []):
            cidr = prefix.get('ip_prefix', '')
            if cidr:
                ranges.append({
                    'cidr':          cidr,
                    'country_code':  prefix.get('region', '').split('-')[0].upper()[:2],
                    'provider_name': source['name'],
                    'asn':           source['asn'],
                })
        for prefix in data.get('ipv6_prefixes', []):
            cidr = prefix.get('ipv6_prefix', '')
            if cidr:
                ranges.append({
                    'cidr':          cidr,
                    'country_code':  '',
                    'provider_name': source['name'],
                    'asn':           source['asn'],
                })
        return ranges

    def _parse_plain_text(self, resp, source: dict) -> list:
        """Parse plain-text one-CIDR-per-line format (Cloudflare)."""
        ranges = []
        for line in resp.text.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                ranges.append({
                    'cidr':          line,
                    'country_code':  '',
                    'provider_name': source['name'],
                    'asn':           source['asn'],
                })
        return ranges

    def _parse_google(self, resp, source: dict) -> list:
        """Parse Google Cloud IP ranges JSON format."""
        data   = resp.json()
        ranges = []
        for prefix in data.get('prefixes', []):
            cidr = prefix.get('ipv4Prefix') or prefix.get('ipv6Prefix', '')
            if cidr:
                ranges.append({
                    'cidr':          cidr,
                    'country_code':  '',
                    'provider_name': source['name'],
                    'asn':           source['asn'],
                })
        return ranges

    def _parse_azure(self, resp, source: dict) -> list:
        """Parse Azure Service Tags JSON format."""
        data   = resp.json()
        ranges = []
        for value in data.get('values', []):
            for addr_prefix in value.get('properties', {}).get('addressPrefixes', []):
                if addr_prefix:
                    ranges.append({
                        'cidr':          addr_prefix,
                        'country_code':  '',
                        'provider_name': source['name'],
                        'asn':           source['asn'],
                    })
        return ranges

    def _parse_digitalocean_csv(self, resp, source: dict) -> list:
        """Parse DigitalOcean CSV format."""
        ranges = []
        for line in resp.text.splitlines():
            parts = line.split(',')
            if parts and parts[0].strip():
                ranges.append({
                    'cidr':          parts[0].strip(),
                    'country_code':  parts[1].strip().upper()[:2] if len(parts) > 1 else '',
                    'provider_name': source['name'],
                    'asn':           source['asn'],
                })
        return ranges

    # ── Save Method ────────────────────────────────────────────────────────

    def _save_ranges(self, ranges: list, source: dict) -> tuple:
        """Save IP ranges to DatacenterIPRange model. Returns (added, updated)."""
        from api.proxy_intelligence.models import DatacenterIPRange

        added   = 0
        updated = 0

        for entry in ranges:
            cidr = entry.get('cidr', '').strip()
            if not cidr:
                continue
            try:
                _, created = DatacenterIPRange.objects.update_or_create(
                    cidr=cidr,
                    defaults={
                        'provider_name': entry.get('provider_name', source['name']),
                        'asn':           entry.get('asn', source['asn']),
                        'country_code':  entry.get('country_code', ''),
                        'is_active':     True,
                        'source':        source['name'].lower().replace(' ', '_'),
                        'last_updated':  timezone.now(),
                    }
                )
                if created:
                    added += 1
                else:
                    updated += 1
            except Exception as e:
                logger.debug(f"Failed to save CIDR {cidr}: {e}")

        return added, updated

    # ── Stats Display ──────────────────────────────────────────────────────

    def _show_stats(self):
        """Display database statistics."""
        from api.proxy_intelligence.models import DatacenterIPRange
        from django.db.models import Count

        total  = DatacenterIPRange.objects.filter(is_active=True).count()
        by_provider = list(
            DatacenterIPRange.objects.filter(is_active=True)
            .values('provider_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        self.stdout.write('\n  Database Statistics:')
        self.stdout.write(f'  Total active ranges: {total}')
        self.stdout.write('  By provider:')
        for row in by_provider:
            self.stdout.write(f"    {row['provider_name']:<25} {row['count']:>6} ranges")
