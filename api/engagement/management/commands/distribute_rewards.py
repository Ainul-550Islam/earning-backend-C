# engagement/management/commands/distribute_rewards.py
"""
Usage:
    python manage.py distribute_rewards
    python manage.py distribute_rewards --date 2024-12-01
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from engagement.services.leaderboard_service import LeaderboardService


class Command(BaseCommand):
    help = "Distribute leaderboard coin rewards for the given date (default: yesterday)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default=None,
            help="Target date YYYY-MM-DD (default: yesterday).",
        )
        parser.add_argument(
            "--tenant_id",
            type=int,
            default=None,
            help="Tenant PK to scope the distribution.",
        )

    def handle(self, *args, **options):
        target_date = (
            date.fromisoformat(options["date"])
            if options["date"]
            else date.today() - timedelta(days=1)
        )
        tenant = None
        if options["tenant_id"]:
            from tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(pk=options["tenant_id"])
            except Tenant.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Tenant {options['tenant_id']} not found."))
                return

        self.stdout.write(f"Distributing leaderboard rewards for {target_date}…")
        count = LeaderboardService.distribute_rewards(target_date, tenant)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Rewards distributed to {count} users for {target_date}.")
        )
