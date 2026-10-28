"""
payout_queue/management/commands/retry_payouts.py  ← DRY v7 (built on v2)

DRY CHANGE v7:

  ① Inherits BasePayoutCommand (new file: base_payout_command.py)

     Before:  add_arguments() defined --async, --worker-id, --dry-run inline —
              the exact same argparse code as process_payouts.py.
              The `if dry_run and async_mode: raise CommandError(...)` check
              was also a verbatim copy.

     After:   super().add_arguments(parser) adds the three shared flags.
              self.validate_shared_options(options) runs the shared guard.
              self.make_worker_id(options) generates "retry-mgmt-<uuid8>".
              This command only defines its own exclusive args:
              --batch-id, --item-ids, --limit.

     Lines saved: ~25 (same as process_payouts)

v2 bug-fixes preserved unchanged:
  1. --item-ids flag exposed (was missing — services accepted it but CLI didn't)
  2. --dry-run flag
  3. --limit flag (prevents unbounded retry storms)
  4. Error output routed to stderr
  5. worker_id fallback prevents PayoutQueueError from services
"""

from __future__ import annotations

import logging
import sys

from django.core.management.base import CommandError

from .base_payout_command import BasePayoutCommand

logger = logging.getLogger(__name__)

class Command(BasePayoutCommand):

    help = (
        "Retry RETRYING payout items that are due. "
        "Filter by --batch-id or --item-ids. "
        "Use --dry-run to preview. Use --limit to cap batch size."
    )

    # DRY v7: worker prefix specific to this command.
    _default_worker_prefix = "retry-mgmt"

    def add_arguments(self, parser):
        # DRY v7: super() adds --async, --worker-id, --dry-run (shared).
        super().add_arguments(parser)

        # retry_payouts-exclusive arguments:
        parser.add_argument(
            "--batch-id",
            type=str,
            default=None,
            help="Only retry items from this batch UUID.",
        )
        parser.add_argument(
            "--item-ids",
            type=str,
            nargs="+",
            default=None,
            metavar="UUID",
            help="Retry specific payout item UUIDs (space-separated).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help=(
                "Maximum number of items to retry in one invocation (default: 100). "
                "Set 0 for unlimited."
            ),
        )

    def handle(self, *args, **options):
        # DRY v7: shared option validation (dry_run + async conflict check).
        self.validate_shared_options(options)

        batch_id: str | None       = options.get("batch_id")
        item_ids: list[str] | None = options.get("item_ids")
        async_mode: bool           = options["async_mode"]
        dry_run: bool              = options["dry_run"]
        limit: int                 = options["limit"]

        # DRY v7: shared worker_id generation with this command's prefix.
        worker_id: str = self.make_worker_id(options)

        # ── Validate retry_payouts-exclusive constraints ───────────────
        if batch_id and item_ids:
            raise CommandError("Cannot combine --batch-id with --item-ids.")

        # ── Dry-run mode ───────────────────────────────────────────────
        if dry_run:
            from api.payout_queue.models import PayoutItem

            qs = PayoutItem.objects.due_for_retry()
            if batch_id:
                qs = qs.filter(batch_id=batch_id)
            if item_ids:
                qs = qs.filter(id__in=item_ids)
            if limit:
                qs = qs[:limit]

            items = list(qs.select_related("user", "batch"))
            if not items:
                self.stdout.write(
                    self.style.WARNING("No items are due for retry.")
                )
                return

            self.stdout.write(
                self.style.NOTICE(
                    f"DRY RUN — {len(items)} item(s) would be retried:\n"
                )
            )
            for item in items:
                self.stdout.write(
                    f"  {item.id}  user={item.user_id}  "
                    f"account={item.account_number}  "
                    f"amount={item.gross_amount}  "
                    f"retry_count={item.retry_count}  "
                    f"error={item.error_code}"
                )
            return

        # ── Async mode ─────────────────────────────────────────────────
        if async_mode:
            try:
                from api.payout_queue.tasks import retry_due_items
            except ImportError as exc:
                raise CommandError(f"Celery tasks not importable: {exc}")

            try:
                task = retry_due_items.delay(
                    batch_id=batch_id,
                    item_ids=item_ids,
                    limit=limit,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Retry task queued. Task: {task.id}")
                )
            except Exception as exc:
                raise CommandError(f"Failed to queue retry: {exc}")
            return

        # ── Sync mode ──────────────────────────────────────────────────
        self.stdout.write("Retrying due payout items ...")
        try:
            from api.payout_queue import services
            result = services.retry_failed_items(
                batch_id=batch_id,
                item_ids=item_ids,
                worker_id=worker_id,
                limit=limit if limit else None,
            )
        except Exception as exc:
            logger.exception("retry_payouts: unexpected error: %s", exc)
            raise CommandError(f"Unexpected error: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Retried={result['retried_count']} "
                f"success={result['success_count']} "
                f"failed={result['failure_count']}"
            )
        )
        if result.get("failure_count", 0) > 0:
            sys.exit(1)
