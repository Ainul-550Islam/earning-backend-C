"""Management command: process_payouts — Trigger batch processing from CLI."""
from __future__ import annotations
import logging
from django.core.management.base import BaseCommand, CommandError
from api.payout_queue.exceptions import PayoutBatchNotFoundError, PayoutBatchStateError, PayoutBatchLockedError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process a payout batch by UUID. Use --async to queue via Celery."

    def add_arguments(self, parser):
        parser.add_argument("batch_id", type=str, help="UUID of the PayoutBatch.")
        parser.add_argument("--async", dest="async_mode", action="store_true",
                            help="Queue via Celery instead of processing inline.")
        parser.add_argument("--worker-id", type=str, default="management-cmd",
                            help="Worker ID for advisory lock.")

    def handle(self, *args, **options):
        batch_id = options["batch_id"].strip()
        async_mode = options["async_mode"]
        worker_id = options.get("worker_id", "management-cmd")

        if not batch_id:
            raise CommandError("batch_id must not be empty.")

        if async_mode:
            try:
                from api.payout_queue.tasks import process_batch_async
                task = process_batch_async.delay(batch_id)
                self.stdout.write(
                    self.style.SUCCESS(f"Batch {batch_id} queued. Task: {task.id}")
                )
            except Exception as exc:
                raise CommandError(f"Failed to queue: {exc}")
            return

        self.stdout.write(f"Processing batch {batch_id} ...")
        try:
            from api.payout_queue import services
            result = services.process_batch(batch_id=batch_id, worker_id=worker_id)
        except PayoutBatchNotFoundError as exc:
            raise CommandError(f"Not found: {exc}")
        except (PayoutBatchStateError, PayoutBatchLockedError) as exc:
            raise CommandError(f"State/lock error: {exc}")
        except Exception as exc:
            logger.exception("process_payouts: unexpected error: %s", exc)
            raise CommandError(f"Unexpected: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: status={result['status']} "
                f"success={result['success_count']} failed={result['failure_count']} "
                f"duration={result['duration_ms']}ms"
            )
        )
