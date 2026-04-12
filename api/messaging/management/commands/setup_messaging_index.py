"""
Management command: setup_messaging_index
Sets up Elasticsearch index for messaging.
Usage: python manage.py setup_messaging_index [--recreate]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create/verify Elasticsearch index for messaging search."

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate", action="store_true",
            help="Delete existing index and recreate from scratch.",
        )
        parser.add_argument(
            "--bulk-index", action="store_true",
            help="Bulk index all existing messages after creating index.",
        )
        parser.add_argument(
            "--days", type=int, default=90,
            help="Number of days of messages to bulk index (default: 90).",
        )

    def handle(self, *args, **options):
        from messaging.utils.search_engine import get_es_client, ensure_index_exists, ES_INDEX_MESSAGES

        es = get_es_client()
        if not es:
            self.stderr.write(self.style.ERROR(
                "Elasticsearch not configured. Set ELASTICSEARCH_URL in settings."
            ))
            return

        if not es.ping():
            self.stderr.write(self.style.ERROR("Cannot connect to Elasticsearch."))
            return

        self.stdout.write("Connected to Elasticsearch ✓")

        if options["recreate"]:
            if es.indices.exists(index=ES_INDEX_MESSAGES):
                es.indices.delete(index=ES_INDEX_MESSAGES)
                self.stdout.write(self.style.WARNING(f"Deleted existing index '{ES_INDEX_MESSAGES}'"))

        ok = ensure_index_exists()
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Index '{ES_INDEX_MESSAGES}' is ready ✓"))
        else:
            self.stderr.write(self.style.ERROR("Failed to create index."))
            return

        if options["bulk_index"]:
            self.stdout.write(f"Starting bulk index (last {options['days']} days)...")
            from messaging.tasks import bulk_reindex_task
            result = bulk_reindex_task(days=options["days"])
            self.stdout.write(self.style.SUCCESS(
                f"Bulk index complete: indexed={result['indexed']} errors={result['errors']}"
            ))
