"""
Management Command: reset_contest — Reset a ContestCycle back to DRAFT (dev/staging only).

WARNING: This command is destructive. It is intended for development and staging
environments ONLY and must NEVER be run in production without explicit safeguards.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Reset a ContestCycle and all related data back to DRAFT status. "
        "DEV/STAGING ONLY — never run in production."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "cycle_id",
            type=str,
            help="UUID of the ContestCycle to reset.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip the production environment safety check.",
        )
        parser.add_argument(
            "--delete-achievements",
            action="store_true",
            help="Also delete all UserAchievement records for this cycle.",
        )
        parser.add_argument(
            "--delete-snapshots",
            action="store_true",
            help="Also delete all LeaderboardSnapshot records for this cycle.",
        )

    def handle(self, *args, **options):
        # Safety check: block execution in production unless --force is supplied
        env = getattr(settings, "ENVIRONMENT", "production").lower()
        if env == "production" and not options["force"]:
            raise CommandError(
                "reset_contest is blocked in the PRODUCTION environment. "
                "Use --force to override (extremely dangerous)."
            )

        cycle_id = options["cycle_id"]
        if not cycle_id or not cycle_id.strip():
            raise CommandError("cycle_id must not be empty.")

        from api.gamification.models import ContestCycle, UserAchievement, LeaderboardSnapshot
        from api.gamification.choices import ContestCycleStatus

        try:
            cycle = ContestCycle.objects.get(pk=cycle_id)
        except ContestCycle.DoesNotExist:
            raise CommandError(f"ContestCycle with pk={cycle_id!r} does not exist.")
        except (ValueError, TypeError) as exc:
            raise CommandError(f"Invalid cycle_id '{cycle_id}': {exc}")

        self.stdout.write(
            self.style.WARNING(
                f"About to reset ContestCycle '{cycle.name}' (id={cycle.id}) "
                f"from '{cycle.status}' to 'DRAFT'."
            )
        )

        with transaction.atomic():
            if options["delete_achievements"]:
                deleted, _ = UserAchievement.objects.filter(contest_cycle=cycle).delete()
                self.stdout.write(f"  Deleted {deleted} UserAchievement record(s).")

            if options["delete_snapshots"]:
                deleted, _ = LeaderboardSnapshot.objects.filter(contest_cycle=cycle).delete()
                self.stdout.write(f"  Deleted {deleted} LeaderboardSnapshot record(s).")

            cycle.status = ContestCycleStatus.DRAFT
            # Bypass the state machine for management command reset
            ContestCycle.objects.filter(pk=cycle.pk).update(status=ContestCycleStatus.DRAFT)

        self.stdout.write(
            self.style.SUCCESS(
                f"ContestCycle '{cycle.name}' successfully reset to DRAFT."
            )
        )
        logger.warning(
            "reset_contest executed on cycle %s in environment=%s by management command.",
            cycle.id,
            env,
        )
