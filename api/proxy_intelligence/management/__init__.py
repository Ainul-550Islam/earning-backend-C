"""
Management Command: sync_threat_feeds
Usage: python manage.py sync_threat_feeds
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync all active threat feeds and update the malicious IP database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--feed', type=str, default='all',
            help='Specific feed to sync (default: all)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be synced without saving'
        )

    def handle(self, *args, **options):
        from api.proxy_intelligence.threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator

        self.stdout.write(self.style.NOTICE('Syncing threat feeds...'))

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes will be saved.'))

        integrator = ThreatFeedIntegrator()
        results = integrator.sync_all_feeds()

        for feed, status in results.items():
            if 'error' in status:
                self.stdout.write(self.style.ERROR(f'  ✗ {feed}: {status}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {feed}: {status}'))

        self.stdout.write(self.style.SUCCESS('Done.'))
