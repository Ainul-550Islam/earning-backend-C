# =============================================================================
# behavior_analytics/management/commands/calculate_engagement.py
# =============================================================================
"""
Management command: calculate_engagement

Triggers engagement score calculation for all active users (or a single user)
for a given date.  Can run synchronously or fan out via Celery.

Examples::

    # Recalculate everyone for today (synchronous)
    python manage.py calculate_engagement

    # Recalculate for a specific date
    python manage.py calculate_engagement --date 2024-03-15

    # Fan out to Celery instead of blocking
    python manage.py calculate_engagement --async

    # Single user only
    python manage.py calculate_engagement --user-id <uuid>
"""

from __future__ import annotations

import logging
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Calculate engagement scores for active users."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Target date in YYYY-MM-DD format (default: today).",
        )
        parser.add_argument(
            "--user-id",
            type=str,
            default=None,
            dest="user_id",
            help="Restrict calculation to a single user by primary key.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            default=False,
            dest="use_async",
            help="Fan out to Celery workers instead of running synchronously.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            dest="dry_run",
            help="Print what would be done without writing anything.",
        )

    def handle(self, *args, **options) -> None:
        target_date = self._parse_date(options["date"])
        use_async   = options["use_async"]
        dry_run     = options["dry_run"]
        user_id     = options.get("user_id")

        self.stdout.write(
            self.style.NOTICE(
                f"calculate_engagement: date={target_date} "
                f"async={use_async} dry_run={dry_run}"
            )
        )

        users = self._get_users(user_id)
        self.stdout.write(f"  → {users.count()} user(s) to process.")

        if dry_run:
            for u in users:
                self.stdout.write(f"  [DRY RUN] Would calculate for {u.pk} ({u})")
            return

        if use_async:
            self._dispatch_async(users, target_date)
        else:
            self._run_sync(users, target_date)

        self.stdout.write(self.style.SUCCESS("Done."))

    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(raw: str | None) -> date:
        if raw is None:
            return timezone.localdate()
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError(f"Invalid date format '{raw}'. Use YYYY-MM-DD.") from exc

    @staticmethod
    def _get_users(user_id: str | None):
        if user_id:
            qs = User.objects.filter(pk=user_id)
            if not qs.exists():
                raise CommandError(f"No user found with pk='{user_id}'.")
            return qs
        return User.objects.filter(is_active=True)

    def _dispatch_async(self, users, target_date: date) -> None:
        from behavior_analytics.tasks import calculate_engagement_score
        dispatched = 0
        for user in users.iterator(chunk_size=100):
            calculate_engagement_score.delay(
                str(user.pk), target_date.isoformat()
            )
            dispatched += 1
        self.stdout.write(f"  → {dispatched} task(s) queued.")

    def _run_sync(self, users, target_date: date) -> None:
        from behavior_analytics.services import EngagementScoreService
        success = error = 0
        for user in users.iterator(chunk_size=100):
            try:
                result = EngagementScoreService.calculate_for_user(
                    user=user, target_date=target_date
                )
                self.stdout.write(
                    f"  ✓ user={user.pk} score={result.score} tier={result.tier}"
                )
                success += 1
            except Exception as exc:
                logger.exception(
                    "calculate_engagement.cmd_error user_id=%s", user.pk
                )
                self.stderr.write(
                    self.style.ERROR(f"  ✗ user={user.pk} error={exc}")
                )
                error += 1

        self.stdout.write(
            f"  Summary: {success} succeeded, {error} failed."
        )
