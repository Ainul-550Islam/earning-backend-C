"""
payout_queue/management/commands/base_payout_command.py  ← DRY v7 (NEW FILE)

PURPOSE:

  Before v7:  process_payouts.py and retry_payouts.py each contained
              identical boilerplate:

              add_arguments():
                - --async, --worker-id, --dry-run argument definitions
                  (same argparse code, same help text, same defaults)

              handle():
                - `if dry_run and async_mode: raise CommandError(...)` check
                - `worker_id = options.get("worker_id") or f"<prefix>-<uuid8>"`
                - Error output routing: self.stderr vs self.stdout

              Any change to these shared patterns (e.g. renaming a flag,
              changing a default, changing the error message text) had to be
              applied in two files.

  After v7:   BasePayoutCommand owns these shared elements once.
              Subcommands call super().add_arguments(parser) from their own
              add_arguments(), and call self.validate_shared_options(options)
              + self.make_worker_id(options) from their handle().

USAGE:

    class Command(BasePayoutCommand):
        help   = "My payout management command."
        _default_worker_prefix = "my-prefix"

        def add_arguments(self, parser):
            super().add_arguments(parser)          # adds --async, --worker-id, --dry-run
            parser.add_argument("--my-flag", ...)  # command-specific args

        def handle(self, *args, **options):
            self.validate_shared_options(options)  # raises CommandError for invalid combos
            worker_id = self.make_worker_id(options)
            dry_run   = options["dry_run"]
            async_mode = options["async_mode"]
            ...
"""

from __future__ import annotations

import logging
import uuid as _uuid

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

class BasePayoutCommand(BaseCommand):
    """
    DRY v7: Abstract base for payout management commands.

    Provides:
      - Shared --async, --worker-id, --dry-run argument definitions.
      - validate_shared_options(): dry-run + async conflict check.
      - make_worker_id(): generates a default worker ID if not supplied.
    """

    # Subclasses override this to get their specific worker-id prefix.
    # process_payouts → "mgmt", retry_payouts → "retry-mgmt"
    _default_worker_prefix: str = "mgmt"

    def add_arguments(self, parser) -> None:
        """
        Registers the three arguments shared by every payout command.

        Subclasses MUST call super().add_arguments(parser) before adding
        their own command-specific arguments.
        """
        parser.add_argument(
            "--async",
            dest="async_mode",
            action="store_true",
            default=False,
            help="Queue via Celery instead of running inline.",
        )
        parser.add_argument(
            "--worker-id",
            type=str,
            default=None,
            help=(
                "Worker ID used for advisory lock and logging. "
                f"Defaults to '{self._default_worker_prefix}-<random>' if not provided."
            ),
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help=(
                "Preview what would happen without executing anything. "
                "Incompatible with --async."
            ),
        )

    def validate_shared_options(self, options: dict) -> None:
        """
        Validate option combinations that are invalid for ALL payout commands.
        Call this at the start of every subclass handle() before any work.

        Currently guards:
          --dry-run + --async  →  CommandError
        """
        if options.get("dry_run") and options.get("async_mode"):
            raise CommandError(
                "--dry-run is incompatible with --async. "
                "Use one or the other."
            )

    def make_worker_id(self, options: dict) -> str:
        """
        Return the worker ID for this invocation.

        Uses the value of --worker-id if supplied; otherwise generates a
        short random ID with the command's _default_worker_prefix.

        Example outputs:
          mgmt-a3f2b1c4          (process_payouts, no --worker-id)
          retry-mgmt-d9e8f7a6    (retry_payouts,   no --worker-id)
          my-custom-worker       (any command,      --worker-id my-custom-worker)
        """
        provided = (options.get("worker_id") or "").strip()
        if provided:
            return provided
        short_uuid = str(_uuid.uuid4())[:8]
        return f"{self._default_worker_prefix}-{short_uuid}"
