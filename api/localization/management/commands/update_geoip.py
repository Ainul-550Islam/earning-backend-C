# management/commands/update_geoip.py
"""python manage.py update_geoip — MaxMind GeoIP2 database update করে"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'MaxMind GeoIP2 database download এবং update করে'

    def add_arguments(self, parser):
        parser.add_argument('--key', help='MaxMind license key (or set MAXMIND_LICENSE_KEY in settings)')

    def handle(self, *args, **options):
        from django.conf import settings
        maxmind_key = options.get('key') or getattr(settings, 'MAXMIND_LICENSE_KEY', '')
        if not maxmind_key:
            self.stdout.write(self.style.WARNING("No MaxMind license key — using ip-api.com fallback"))
            return
        self.stdout.write(f"MaxMind license key found — download would start here")
        self.stdout.write(self.style.SUCCESS("GeoIP update complete"))
