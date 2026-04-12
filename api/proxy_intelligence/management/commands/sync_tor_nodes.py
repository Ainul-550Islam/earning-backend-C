"""Management Command: sync_tor_nodes — syncs Tor exit node list from Tor Project."""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync the Tor exit node list from the Tor Project official source'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Count nodes without saving to DB'
        )
        parser.add_argument(
            '--show-new', action='store_true',
            help='Print newly added nodes'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            f'Syncing Tor exit nodes from Tor Project... ({timezone.now().strftime("%Y-%m-%d %H:%M")})'
        ))

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes will be saved.'))

        try:
            from api.proxy_intelligence.detection_engines.tor_detector import TorDetector

            if options['dry_run']:
                import requests
                from api.proxy_intelligence.constants import TOR_EXIT_NODE_LIST_URL
                resp = requests.get(TOR_EXIT_NODE_LIST_URL, timeout=15)
                resp.raise_for_status()
                nodes = [l.strip() for l in resp.text.splitlines()
                         if l.strip() and not l.startswith('#')]
                self.stdout.write(self.style.SUCCESS(
                    f'[DRY RUN] Would sync {len(nodes)} Tor exit nodes.'
                ))
                return

            count = TorDetector.sync_exit_nodes()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Successfully synced {count} Tor exit nodes.'
            ))

            # Show stats
            from api.proxy_intelligence.models import TorExitNode
            active = TorExitNode.objects.filter(is_active=True).count()
            total  = TorExitNode.objects.count()
            self.stdout.write(f'  Active nodes: {active} / Total in DB: {total}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Sync failed: {e}'))
            logger.error(f'Tor sync management command failed: {e}')
            raise
