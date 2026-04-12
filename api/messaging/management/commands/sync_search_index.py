"""
Management command: sync_search_index
Sync messages to Elasticsearch that are missing from the index.
Usage: python manage.py sync_search_index --days 7 --chat-id <uuid>
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync missing messages to Elasticsearch search index."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--chat-id", type=str, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from django.utils import timezone
        from datetime import timedelta
        from messaging.models import ChatMessage, MessageStatus
        from messaging.utils.search_engine import index_message, get_es_client

        es = get_es_client()
        cutoff = timezone.now() - timedelta(days=options["days"])
        qs = ChatMessage.objects.filter(
            created_at__gte=cutoff,
            status__in=[MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ],
        ).only("id", "chat_id", "sender_id", "content", "message_type", "created_at", "tenant_id")

        if options["chat_id"]:
            qs = qs.filter(chat_id=options["chat_id"])

        total = qs.count()
        self.stdout.write(f"Found {total} messages to sync...")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"DRY RUN — would index {total} messages."))
            return

        indexed = 0
        errors = 0
        for msg in qs.iterator(chunk_size=500):
            try:
                index_message(
                    message_id=str(msg.id),
                    chat_id=str(msg.chat_id),
                    sender_id=str(msg.sender_id) if msg.sender_id else "",
                    content=msg.content or "",
                    message_type=msg.message_type,
                    created_at=msg.created_at.isoformat(),
                    tenant_id=msg.tenant_id,
                )
                indexed += 1
                if indexed % 500 == 0:
                    self.stdout.write(f"  Indexed {indexed}/{total}...")
            except Exception as exc:
                errors += 1
                self.stderr.write(f"  Error msg={msg.id}: {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"Sync complete: indexed={indexed} errors={errors}"
        ))
