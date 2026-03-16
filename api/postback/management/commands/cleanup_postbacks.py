"""
Management command: cleanup_postbacks
Usage: python manage.py cleanup_postbacks [--dry-run] [--days N]

Deletes PostbackLog and DuplicateLeadCheck records older than the
configured retention window.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Delete PostbackLog and DuplicateLeadCheck records that exceed "
        "the configured retention window. Safe to run on a cron schedule."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print record counts without deleting anything.",
        )
        parser.add_argument(
            "--log-days",
            type=int,
            default=None,
            help="Override PostbackLog retention days (default from constants).",
        )
        parser.add_argument(
            "--dedup-days",
            type=int,
            default=None,
            help="Override DuplicateLeadCheck retention days (default from constants).",
        )
        parser.add_argument(
            "--status",
            nargs="+",
            default=None,
            help=(
                "Only delete logs with these statuses "
                "(e.g. --status rejected duplicate). "
                "Default: all statuses."
            ),
        )

    def handle(self, *args, **options):
        from postback.models import PostbackLog, DuplicateLeadCheck
        from postback.constants import (
            POSTBACK_LOG_RETENTION_DAYS,
            DUPLICATE_LOG_RETENTION_DAYS,
        )

        dry_run = options["dry_run"]
        log_days = options["log_days"] or POSTBACK_LOG_RETENTION_DAYS
        dedup_days = options["dedup_days"] or DUPLICATE_LOG_RETENTION_DAYS
        status_filter = options.get("status")

        log_threshold = timezone.now() - timezone.timedelta(days=log_days)
        dedup_threshold = timezone.now() - timezone.timedelta(days=dedup_days)

        log_qs = PostbackLog.objects.filter(received_at__lt=log_threshold)
        if status_filter:
            log_qs = log_qs.filter(status__in=status_filter)

        dedup_qs = DuplicateLeadCheck.objects.filter(first_seen_at__lt=dedup_threshold)

        log_count = log_qs.count()
        dedup_count = dedup_qs.count()

        self.stdout.write(
            f"PostbackLog records to delete:       {log_count:>8,}  (older than {log_days}d)\n"
            f"DuplicateLeadCheck records to delete: {dedup_count:>7,}  (older than {dedup_days}d)"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN – no records deleted --"))
            return

        _, log_detail = log_qs.delete()
        _, dedup_detail = dedup_qs.delete()

        deleted_logs = log_detail.get("postback.PostbackLog", 0)
        deleted_dedup = dedup_detail.get("postback.DuplicateLeadCheck", 0)

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_logs:,} PostbackLog record(s) and "
                f"{deleted_dedup:,} DuplicateLeadCheck record(s)."
            )
        )
        logger.info(
            "cleanup_postbacks: deleted %d logs and %d dedup records.",
            deleted_logs, deleted_dedup,
        )
