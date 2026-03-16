"""
Management Command: generate_leaderboard — Manually trigger leaderboard snapshot generation.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from api.gamification.choices import LeaderboardScope
from api.gamification.constants import DEFAULT_LEADERBOARD_TOP_N
from api.gamification.exceptions import (
    ContestCycleNotFoundError,
    LeaderboardGenerationError,
    GamificationServiceError,
)
from api.gamification import services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manually generate a leaderboard snapshot for a ContestCycle."

    def add_arguments(self, parser):
        parser.add_argument(
            "cycle_id",
            type=str,
            help="UUID of the ContestCycle to generate a snapshot for.",
        )
        parser.add_argument(
            "--scope",
            type=str,
            default=LeaderboardScope.GLOBAL,
            choices=LeaderboardScope.values,
            help=f"Leaderboard scope (default: {LeaderboardScope.GLOBAL}).",
        )
        parser.add_argument(
            "--scope-ref",
            type=str,
            default="",
            help="Optional scope qualifier (e.g. region code).",
        )
        parser.add_argument(
            "--top-n",
            type=int,
            default=DEFAULT_LEADERBOARD_TOP_N,
            help=f"Number of top entries to capture (default: {DEFAULT_LEADERBOARD_TOP_N}).",
        )

    def handle(self, *args, **options):
        cycle_id = options["cycle_id"]
        scope = options["scope"]
        scope_ref = options["scope_ref"]
        top_n = options["top_n"]

        if not cycle_id or not cycle_id.strip():
            raise CommandError("cycle_id must not be empty.")

        if top_n < 1 or top_n > 1000:
            raise CommandError("--top-n must be between 1 and 1000.")

        self.stdout.write(
            f"Generating leaderboard snapshot for cycle={cycle_id} "
            f"scope={scope} scope_ref={scope_ref!r} top_n={top_n} ..."
        )

        try:
            snapshot = services.generate_leaderboard_snapshot(
                cycle_id=cycle_id,
                scope=scope,
                scope_ref=scope_ref,
                top_n=top_n,
            )
        except ContestCycleNotFoundError as exc:
            raise CommandError(f"ContestCycle not found: {exc}")
        except LeaderboardGenerationError as exc:
            raise CommandError(f"Snapshot generation failed: {exc}")
        except GamificationServiceError as exc:
            raise CommandError(f"Service error: {exc}")
        except Exception as exc:
            logger.exception("Unexpected error in generate_leaderboard command: %s", exc)
            raise CommandError(f"Unexpected error: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot {snapshot.id} finalized with {snapshot.entry_count} entries. "
                f"Checksum: {snapshot.checksum}"
            )
        )
