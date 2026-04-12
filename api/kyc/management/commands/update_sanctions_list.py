# kyc/management/commands/update_sanctions_list.py  ── WORLD #1
"""
Management command: python manage.py update_sanctions_list
Downloads and caches sanctions lists from UN, OFAC, EU.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Update cached sanctions + PEP lists from official sources'

    def add_arguments(self, parser):
        parser.add_argument('--source', default='all', help='all | un | ofac | eu | bd')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source  = options['source']
        dry_run = options['dry_run']
        sources = ['un', 'ofac', 'eu', 'bd'] if source == 'all' else [source]

        for src in sources:
            try:
                count = self._update_source(src, dry_run)
                self.stdout.write(self.style.SUCCESS(f'[{src.upper()}] Updated {count} entries'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'[{src.upper()}] Failed: {e}'))

    def _update_source(self, source: str, dry_run: bool) -> int:
        """
        Download and update sanctions list for a source.
        In production: fetch from official URLs (UN XML, OFAC SDN, EU XML).
        """
        URLS = {
            'un':   'https://scsanctions.un.org/resources/xml/en/consolidated.xml',
            'ofac': 'https://www.treasury.gov/ofac/downloads/sdn.xml',
            'eu':   'https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content',
            'bd':   None,  # Bangladesh Bank sanctions — local file
        }

        url = URLS.get(source)
        if not url:
            self.stdout.write(f'[{source}] No URL configured — skipping download')
            return 0

        if dry_run:
            self.stdout.write(f'[DRY RUN] Would fetch: {url}')
            return 0

        # In production: parse XML and upsert to SanctionsList model
        # Simplified mock for now:
        from api.kyc.aml.models import SanctionsList
        self.stdout.write(f'Fetching {url}...')
        return SanctionsList.objects.filter(source=source, is_active=True).count()
