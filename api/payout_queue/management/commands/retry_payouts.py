"""Management command: retry_payouts — Retry failed payout items."""
from __future__ import annotations
import logging
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Retry RETRYING payout items that are due. Optionally filter by batch."

    def add_arguments(self, parser):
        parser.add_argument("--batch-id", type=str, default=None,
                            help="Only retry items from this batch UUID.")
        parser.add_argument("--async", dest="async_mode", action="store_true",
                            help="Queue via Celery instead of running inline.")
        parser.add_argument("--worker-id", type=str, default="retry-cmd")

    def handle(self, *args, **options):
        batch_id = options.get("batch_id")
        async_mode = options["async_mode"]
        worker_id = options.get("worker_id", "retry-cmd")

        if async_mode:
            try:
                from api.payout_queue.tasks import retry_due_items
                task = retry_due_items.delay(batch_id=batch_id)
                self.stdout.write(
                    self.style.SUCCESS(f"Retry task queued. Task: {task.id}")
                )
            except Exception as exc:
                raise CommandError(f"Failed to queue retry: {exc}")
            return

        self.stdout.write("Retrying due payout items ...")
        try:
            from api.payout_queue import services
            result = services.retry_failed_items(
                batch_id=batch_id,
                worker_id=worker_id,
            )
        except Exception as exc:
            logger.exception("retry_payouts: unexpected error: %s", exc)
            raise CommandError(f"Unexpected: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Retried={result['retried_count']} "
                f"success={result['success_count']} failed={result['failure_count']}"
            )
        )
