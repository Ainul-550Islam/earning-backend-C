"""
Management command: retry_failed
Usage: python manage.py retry_failed [--dry-run] [--limit N] [--network KEY]

Re-queues FAILED postback logs that are eligible for retry
(retry_count < MAX and next_retry_at <= now).
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-queue eligible FAILED postback logs for async reprocessing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print eligible logs without queuing them.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Maximum number of logs to re-queue in one run (default: 500).",
        )
        parser.add_argument(
            "--network",
            type=str,
            default=None,
            help="Filter by network_key (e.g. --network my_cpa_network).",
        )
        parser.add_argument(
            "--include-rejected",
            action="store_true",
            default=False,
            help="Also re-queue REJECTED (not just FAILED) logs.",
        )

    def handle(self, *args, **options):
        from postback.models import PostbackLog
        from postback.choices import PostbackStatus
        from postback.constants import MAX_POSTBACK_PROCESSING_RETRIES

        dry_run = options["dry_run"]
        limit = options["limit"]
        network_key = options.get("network")
        include_rejected = options["include_rejected"]

        now = timezone.now()
        statuses = [PostbackStatus.FAILED]
        if include_rejected:
            statuses.append(PostbackStatus.REJECTED)

        qs = PostbackLog.objects.filter(
            status__in=statuses,
            retry_count__lt=MAX_POSTBACK_PROCESSING_RETRIES,
        ).filter(
            # Either no next_retry_at scheduled, or it has passed
            next_retry_at__isnull=True
        ) | PostbackLog.objects.filter(
            status__in=statuses,
            retry_count__lt=MAX_POSTBACK_PROCESSING_RETRIES,
            next_retry_at__lte=now,
        )

        if network_key:
            qs = qs.filter(network__network_key=network_key)

        qs = qs.select_related("network").order_by("received_at")[:limit]

        total = qs.count()
        self.stdout.write(
            f"Found {total} eligible log(s) to retry "
            f"(limit={limit}, network={network_key or 'all'})."
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN – nothing queued --"))
            for log in qs[:20]:
                self.stdout.write(
                    f"  [{log.status}] {log.pk} | network={log.network.network_key} "
                    f"| retries={log.retry_count} | received={log.received_at:%Y-%m-%d %H:%M}"
                )
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more.")
            return

        from postback.tasks import process_postback
        queued = 0
        errors = 0
        for log in qs.iterator():
            try:
                process_postback.delay(
                    str(log.pk),
                    signature="",
                    timestamp_str="",
                    nonce="",
                    body_bytes_hex="",
                    path="",
                    query_params={},
                )
                queued += 1
            except Exception as exc:
                errors += 1
                logger.exception("Failed to queue log %s: %s", log.pk, exc)
                self.stderr.write(self.style.ERROR(f"  Error queuing {log.pk}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(f"Done. Queued: {queued}  |  Errors: {errors}")
        )
        logger.info("retry_failed: queued %d, errors %d", queued, errors)
