"""
payout_queue/management/commands/process_payouts.py  ← DRY v7 (built on v2)

DRY CHANGE v7:

  ① Inherits BasePayoutCommand (new file: base_payout_command.py)

     Before:  Command.add_arguments() defined --async, --worker-id, --dry-run
              inline.  retry_payouts.py had an identical copy of each.
              The `if dry_run and async_mode: raise CommandError(...)` check
              was also duplicated verbatim.

     After:   super().add_arguments(parser) adds all three shared flags.
              self.validate_shared_options(options) runs the shared guard.
              self.make_worker_id(options) generates the worker ID.
              This command only defines its own exclusive args:
              batch_id, --all.

     Lines saved: ~25 (3 argument definitions + 2 validation lines + worker_id
                       assignment + imports that were identical across both files)

v2 bug-fixes preserved unchanged:
  1. actor_id now passed to services.process_batch()
  2. --dry-run flag
  3. --all flag
  4. Error output routed to stderr
"""

from __future__ import annotations

import logging
import sys

from django.core.management.base import CommandError

from .base_payout_command import BasePayoutCommand
from api.payout_queue.exceptions import (
    PayoutBatchNotFoundError,
    PayoutBatchStateError,
    PayoutBatchLockedError,
    PayoutBatchLimitError,
)

logger = logging.getLogger(__name__)

class Command(BasePayoutCommand):

    help = (
        "Process a payout batch by UUID, or all pending batches with --all. "
        "Use --async to queue via Celery. Use --dry-run to preview without executing."
    )

    # DRY v7: worker prefix specific to this command.
    _default_worker_prefix = "mgmt"

    def add_arguments(self, parser):
        # DRY v7: super() adds --async, --worker-id, --dry-run (shared).
        super().add_arguments(parser)

        # process_payouts-exclusive arguments:
        parser.add_argument(
            "batch_id",
            type=str,
            nargs="?",
            default=None,
            help="UUID of the PayoutBatch to process. Omit when using --all.",
        )
        parser.add_argument(
            "--all",
            dest="process_all",
            action="store_true",
            help="Process ALL pending batches that are due for processing.",
        )

    def handle(self, *args, **options):
        # DRY v7: shared option validation (dry_run + async conflict check).
        self.validate_shared_options(options)

        batch_id: str | None  = options["batch_id"]
        async_mode: bool      = options["async_mode"]
        process_all: bool     = options["process_all"]
        dry_run: bool         = options["dry_run"]

        # DRY v7: shared worker_id generation with this command's prefix.
        worker_id: str = self.make_worker_id(options)

        # ── Validate process_payouts-exclusive constraints ────────────
        if not batch_id and not process_all:
            raise CommandError(
                "Provide a batch_id or pass --all to process all pending batches."
            )
        if batch_id and process_all:
            raise CommandError("Cannot combine a specific batch_id with --all.")

        # ── Collect target batches ─────────────────────────────────────
        if process_all:
            from api.payout_queue.models import PayoutBatch
            targets = list(
                PayoutBatch.objects.due_for_processing().values_list("id", flat=True)
            )
            if not targets:
                self.stdout.write(
                    self.style.WARNING("No batches are currently due for processing.")
                )
                return
            self.stdout.write(f"Found {len(targets)} batch(es) due for processing.")
        else:
            targets = [batch_id.strip()]

        # ── Dry-run mode ───────────────────────────────────────────────
        if dry_run:
            from api.payout_queue.models import PayoutBatch
            self.stdout.write(
                self.style.NOTICE("DRY RUN — no batches will be processed.\n")
            )
            for bid in targets:
                try:
                    b = PayoutBatch.objects.get(pk=bid)
                    self.stdout.write(
                        f"  Would process: {b.name} "
                        f"[{b.gateway} | {b.status} | priority={b.priority} "
                        f"| items={b.item_count}]"
                    )
                except PayoutBatch.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"  Not found: {bid}"))
            return

        # ── Async mode ─────────────────────────────────────────────────
        if async_mode:
            try:
                from api.payout_queue.tasks import process_batch_async
            except ImportError as exc:
                raise CommandError(f"Celery tasks not importable: {exc}")

            queued = 0
            for bid in targets:
                try:
                    task = process_batch_async.delay(str(bid))
                    self.stdout.write(
                        self.style.SUCCESS(f"Queued {bid}. Task: {task.id}")
                    )
                    queued += 1
                except Exception as exc:
                    self.stderr.write(
                        self.style.ERROR(f"Failed to queue {bid}: {exc}")
                    )
            self.stdout.write(f"Total queued: {queued}/{len(targets)}")
            return

        # ── Sync mode ──────────────────────────────────────────────────
        from api.payout_queue import services

        success_total = 0
        failure_total = 0
        errors = 0

        for bid in targets:
            self.stdout.write(f"Processing batch {bid} ...")
            try:
                result = services.process_batch(
                    batch_id=bid,
                    worker_id=worker_id,
                    actor_id=None,
                )
            except PayoutBatchNotFoundError as exc:
                self.stderr.write(self.style.ERROR(f"  Not found: {exc}"))
                errors += 1
                continue
            except (PayoutBatchStateError, PayoutBatchLockedError, PayoutBatchLimitError) as exc:
                self.stderr.write(self.style.WARNING(f"  Skipped: {exc}"))
                errors += 1
                continue
            except Exception as exc:
                logger.exception(
                    "process_payouts: unexpected error for batch %s: %s", bid, exc
                )
                self.stderr.write(self.style.ERROR(f"  Unexpected error: {exc}"))
                errors += 1
                continue

            success_total += result.get("success_count", 0)
            failure_total += result.get("failure_count", 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Done: status={result['status']} "
                    f"success={result['success_count']} "
                    f"failed={result['failure_count']} "
                    f"duration={result['duration_ms']}ms"
                )
            )

        self.stdout.write(
            f"\nSummary: batches={len(targets)} errors={errors} "
            f"total_success={success_total} total_failed={failure_total}"
        )
        if errors:
            sys.exit(1)
