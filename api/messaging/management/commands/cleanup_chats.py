"""
Management Command: cleanup_chats — Remove soft-deleted chats and old archived messages.
"""
from __future__ import annotations
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleanup soft-deleted chats and old archived inbox items."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30,
                            help="Delete soft-deleted chats older than N days (default: 30).")
        parser.add_argument("--inbox-days", type=int, default=90,
                            help="Delete archived inbox items older than N days (default: 90).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would be deleted without actually deleting.")

    def handle(self, *args, **options):
        days = options["days"]
        inbox_days = options["inbox_days"]
        dry_run = options["dry_run"]

        if days < 1 or inbox_days < 1:
            raise CommandError("--days and --inbox-days must be at least 1.")

        from datetime import timedelta
        from django.utils import timezone
        from api.messaging.models import InternalChat, UserInbox
        from api.messaging.choices import ChatStatus

        cutoff_chats = timezone.now() - timedelta(days=days)
        cutoff_inbox = timezone.now() - timedelta(days=inbox_days)

        deleted_chats_qs = InternalChat.objects.filter(
            status=ChatStatus.DELETED, updated_at__lt=cutoff_chats
        )
        deleted_inbox_qs = UserInbox.objects.filter(
            is_archived=True, created_at__lt=cutoff_inbox
        )

        self.stdout.write(f"Chats to delete: {deleted_chats_qs.count()}")
        self.stdout.write(f"Inbox items to delete: {deleted_inbox_qs.count()}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing deleted."))
            return

        with transaction.atomic():
            chat_count, _ = deleted_chats_qs.delete()
            inbox_count, _ = deleted_inbox_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {chat_count} chats and {inbox_count} inbox items."
            )
        )
        logger.info("cleanup_chats: deleted %d chats, %d inbox items.", chat_count, inbox_count)
