# engagement/management/commands/rebuild_leaderboard.py
"""
Usage:
    python manage.py rebuild_leaderboard
    python manage.py rebuild_leaderboard --date 2024-12-01
    python manage.py rebuild_leaderboard --tenant_id 3
"""
from datetime import date
from django.core.management.base import BaseCommand
from engagement.services.leaderboard_service import LeaderboardService


class Command(BaseCommand):
    help = "Rebuild the daily leaderboard snapshot for the given date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default=None,
            help="Target date in YYYY-MM-DD format (default: today).",
        )
        parser.add_argument(
            "--tenant_id",
            type=int,
            default=None,
            help="Tenant PK to scope the rebuild (default: all tenants).",
        )

    def handle(self, *args, **options):
        target_date = (
            date.fromisoformat(options["date"]) if options["date"] else date.today()
        )
        tenant = None
        if options["tenant_id"]:
            from tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(pk=options["tenant_id"])
            except Tenant.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Tenant {options['tenant_id']} not found."))
                return

        self.stdout.write(f"Rebuilding leaderboard for {target_date}…")
        count = LeaderboardService.rebuild_daily(target_date, tenant)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Done. {count} entries written for {target_date}.")
        )
