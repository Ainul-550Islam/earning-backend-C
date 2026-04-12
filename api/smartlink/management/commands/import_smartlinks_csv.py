"""
Management command: Bulk import SmartLinks from CSV.
CSV format: name,slug,type,fallback_url,rotation_method,targeting_countries
"""
import csv
import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Bulk import SmartLinks from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file',  type=str, help='Path to CSV file')
        parser.add_argument('--publisher', type=str, required=True, help='Publisher username')
        parser.add_argument('--dry-run',  action='store_true', help='Preview without saving')
        parser.add_argument('--skip-errors', action='store_true', help='Skip rows with errors')

    def handle(self, *args, **options):
        from ...services.core.SmartLinkBuilderService import SmartLinkBuilderService

        try:
            publisher = User.objects.get(username=options['publisher'])
        except User.DoesNotExist:
            raise CommandError(f"Publisher '{options['publisher']}' not found.")

        builder  = SmartLinkBuilderService()
        dry_run  = options['dry_run']
        skip_err = options['skip_errors']

        created = failed = skipped = 0

        try:
            with open(options['csv_file'], newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows   = list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['csv_file']}")
        except Exception as e:
            raise CommandError(f"CSV read error: {e}")

        self.stdout.write(f"Processing {len(rows)} rows...\n")

        for i, row in enumerate(rows, 1):
            name      = row.get('name', '').strip()
            slug      = row.get('slug', '').strip() or None
            sl_type   = row.get('type', 'general').strip()
            fallback  = row.get('fallback_url', '').strip()
            rotation  = row.get('rotation_method', 'weighted').strip()
            countries = [c.strip() for c in row.get('targeting_countries', '').split(',') if c.strip()]

            if not name:
                self.stdout.write(self.style.WARNING(f"  Row {i}: missing name — skipping"))
                skipped += 1
                continue

            config = {
                'name':            name,
                'type':            sl_type,
                'rotation_method': rotation,
            }
            if slug:
                config['slug'] = slug
            if fallback:
                config['fallback_url'] = fallback
            if countries:
                config['targeting'] = {
                    'geo': {'mode': 'whitelist', 'countries': countries}
                }

            if dry_run:
                self.stdout.write(f"  [DRY RUN] Row {i}: Would create '{name}' (slug={slug or 'auto'})")
                created += 1
                continue

            try:
                sl = builder.build(publisher, config)
                self.stdout.write(self.style.SUCCESS(f"  ✅ Row {i}: Created [{sl.slug}] '{name}'"))
                created += 1
            except Exception as e:
                msg = f"  ❌ Row {i}: Failed '{name}' — {e}"
                if skip_err:
                    self.stdout.write(self.style.ERROR(msg))
                    failed += 1
                else:
                    raise CommandError(msg)

        self.stdout.write(f"\n{'[DRY RUN] ' if dry_run else ''}Done!")
        self.stdout.write(self.style.SUCCESS(f"  Created:  {created}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed:   {failed}"))
        if skipped:
            self.stdout.write(self.style.WARNING(f"  Skipped:  {skipped}"))
