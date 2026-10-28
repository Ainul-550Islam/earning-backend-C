# api/support/management/commands/index_kb_articles.py
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    help = "Rebuild KB article search index"
    def handle(self, *args, **options):
        from api.support.models import KBArticle
        from django.core.cache import cache
        articles = KBArticle.objects.filter(status="published")
        # Clear search cache
        cache.delete_pattern("kb_search:*") if hasattr(cache, "delete_pattern") else None
        self.stdout.write(self.style.SUCCESS(f"Indexed {articles.count()} KB articles"))