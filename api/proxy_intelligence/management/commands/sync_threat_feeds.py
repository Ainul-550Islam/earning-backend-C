"""
Management Command: sync_threat_feeds
Usage: python manage.py sync_threat_feeds [--feed <name>] [--ip <ip>] [--dry-run]
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync all active threat feeds and update the malicious IP database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--feed', type=str, default='all',
            help='Specific feed name to sync (e.g. abuseipdb, virustotal). Default: all'
        )
        parser.add_argument(
            '--ip', type=str, default=None,
            help='Check a single IP against all feeds (for testing)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be synced without making any changes'
        )
        parser.add_argument(
            '--reset-quota', action='store_true',
            help='Reset daily API usage counters for all feeds'
        )

    def handle(self, *args, **options):
        from api.proxy_intelligence.threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator
        from api.proxy_intelligence.models import ThreatFeedProvider

        # ── Reset quota ────────────────────────────────────────────────────
        if options['reset_quota']:
            count = ThreatFeedProvider.objects.all().update(used_today=0)
            self.stdout.write(self.style.SUCCESS(
                f'✓ Reset daily quota for {count} feed providers.'
            ))
            return

        # ── Single IP check mode ───────────────────────────────────────────
        if options['ip']:
            self.stdout.write(self.style.NOTICE(
                f'Checking IP {options["ip"]} against all threat feeds...'
            ))
            integrator = ThreatFeedIntegrator()
            result = integrator.check_ip(options['ip'])
            self.stdout.write(f"  IP:             {result['ip_address']}")
            self.stdout.write(f"  Is Malicious:   {result['is_malicious']}")
            self.stdout.write(f"  Max Confidence: {result['max_confidence']}")
            self.stdout.write(f"  Threat Types:   {', '.join(result['threat_types']) or 'none'}")
            self.stdout.write(f"  Feeds Checked:  {result['feeds_checked']}")
            return

        # ── Sync mode ──────────────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE(
            f'[{timezone.now().strftime("%Y-%m-%d %H:%M")}] Syncing threat feeds...'
        ))

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes will be saved.'))

        # Show available feeds
        providers = ThreatFeedProvider.objects.filter(is_active=True)
        if options['feed'] != 'all':
            providers = providers.filter(name=options['feed'])

        if not providers.exists():
            self.stdout.write(self.style.WARNING(
                f'No active providers found. Feed: {options["feed"]}'
            ))
            return

        self.stdout.write(f'  Feeds to sync: {providers.count()}')
        self.stdout.write('')

        if not options['dry_run']:
            integrator = ThreatFeedIntegrator()
            results = integrator.sync_all_feeds()

            for feed, status in results.items():
                has_error = 'error' in str(status).lower()
                style = self.style.ERROR if has_error else self.style.SUCCESS
                icon  = '✗' if has_error else '✓'
                self.stdout.write(style(f'  {icon} {feed}: {status}'))
        else:
            for provider in providers:
                self.stdout.write(self.style.WARNING(
                    f'  ~ [DRY RUN] Would sync: {provider.display_name}'
                    f' (last sync: {provider.last_sync or "never"},'
                    f' quota: {provider.used_today}/{provider.daily_quota})'
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{"[DRY RUN] " if options["dry_run"] else ""}Threat feed sync complete.'
        ))
