"""
Management command: python manage.py bulk_index_messages

Reindex all messages (or messages from a specific chat) into Elasticsearch.
Usage:
  python manage.py bulk_index_messages
  python manage.py bulk_index_messages --chat-id <uuid>
  python manage.py bulk_index_messages --days 30
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Bulk reindex messages into Elasticsearch"

    def add_arguments(self, parser):
        parser.add_argument("--chat-id", type=str, default=None, help="Only reindex this chat")
        parser.add_argument("--days", type=int, default=90, help="Only reindex messages from last N days")
        parser.add_argument("--async", dest="use_async", action="store_true", help="Run via Celery task")

    def handle(self, *args, **options):
        chat_id   = options.get("chat_id")
        days      = options.get("days", 90)
        use_async = options.get("use_async", False)

        if use_async:
            from messaging.tasks import bulk_reindex_task
            result = bulk_reindex_task.delay(chat_id=chat_id, days=days)
            self.stdout.write(f"✅ Queued bulk reindex task: {result.id}")
            return

        from messaging.tasks import bulk_reindex_task
        self.stdout.write(f"🔄 Indexing messages (days={days}, chat={chat_id or 'all'}) ...")
        result = bulk_reindex_task(chat_id=chat_id, days=days)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Indexed {result['indexed']} messages, {result['errors']} errors."
        ))
