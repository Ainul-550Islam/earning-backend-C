# engagement/management/commands/seed_battle_pass.py
"""
Usage:
    python manage.py seed_battle_pass
    python manage.py seed_battle_pass --season 2 --tiers 50 --premium_price 500
    python manage.py seed_battle_pass --clear
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from engagement.models.battle_pass import BattlePass, BattlePassTier, BattlePassXPSource


class Command(BaseCommand):
    help = "Seed a new Battle Pass season with default tiers and XP sources."

    def add_arguments(self, parser):
        parser.add_argument("--season",        type=int,            default=1)
        parser.add_argument("--tiers",         type=int,            default=50)
        parser.add_argument("--premium_price", type=int,            default=500)
        parser.add_argument("--days",          type=int,            default=30)
        parser.add_argument("--clear",         action="store_true", help="Delete existing active pass first")

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = BattlePass.objects.filter(is_active=True).delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing active passes."))

        now      = timezone.now()
        bp, created = BattlePass.objects.get_or_create(
            season_num=options["season"],
            defaults={
                "name":               f"Season {options['season']}",
                "starts_at":          now,
                "ends_at":            now + timedelta(days=options["days"]),
                "is_active":          True,
                "premium_price_coins": Decimal(str(options["premium_price"])),
                "total_tiers":        options["tiers"],
            }
        )

        if created:
            self.stdout.write(f"Created Season {bp.season_num}. Building {options['tiers']} tiers…")
            for i in range(1, options["tiers"] + 1):
                is_milestone = i in (7, 14, 21, 28, 35, 42, 50)
                BattlePassTier.objects.create(
                    battle_pass      = bp,
                    tier_number      = i,
                    xp_required      = i * 100,
                    free_coins       = Decimal("5") if not is_milestone else Decimal("25"),
                    free_xp          = 10 if not is_milestone else 50,
                    premium_coins    = Decimal("15") if not is_milestone else Decimal("75"),
                    premium_xp       = 25 if not is_milestone else 150,
                    is_milestone     = is_milestone,
                )

            # Default XP sources
            xp_sources = [
                ("checkin",        150, 0),
                ("spin",           50,  0),
                ("quest_complete", 200, 1),
                ("achievement",    300, 0),
                ("shop_purchase",  100, 3),
                ("referral",       500, 0),
            ]
            for action, xp, cap in xp_sources:
                BattlePassXPSource.objects.get_or_create(
                    battle_pass=bp, action=action,
                    defaults={"xp_amount": xp, "daily_cap": cap},
                )

            self.stdout.write(self.style.SUCCESS(
                f"✅ Season {bp.season_num} created: {options['tiers']} tiers, 6 XP sources."
            ))
        else:
            self.stdout.write(self.style.WARNING(f"Season {bp.season_num} already exists. Use --clear to recreate."))
