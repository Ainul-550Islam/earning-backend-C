# management/commands/cleanup_translation_cache.py
"""python manage.py cleanup_translation_cache"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Expired translation cache entries delete করে'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Delete entries older than N days')

    def handle(self, *args, **options):
        from localization.models.translation import TranslationCache
        days = options.get('days', 7)
        deleted, _ = TranslationCache.bulk_clean_expired(days=days)
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired cache entries (older than {days} days)"))
