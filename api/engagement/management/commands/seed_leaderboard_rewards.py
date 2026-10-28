# engagement/management/commands/seed_leaderboard_rewards.py
"""
Usage:
    python manage.py seed_leaderboard_rewards
    python manage.py seed_leaderboard_rewards --season_type weekly
    python manage.py seed_leaderboard_rewards --clear
"""
from django.core.management.base import BaseCommand
from engagement.models.leaderboard import LeaderboardReward

DAILY_REWARDS = [
    {"rank": 1,  "reward_coins": 100, "reward_xp": 200, "reward_badge": "streak-100"},
    {"rank": 2,  "reward_coins": 75,  "reward_xp": 150, "reward_badge": ""},
    {"rank": 3,  "reward_coins": 50,  "reward_xp": 100, "reward_badge": ""},
    {"rank": 4,  "reward_coins": 40,  "reward_xp": 80,  "reward_badge": ""},
    {"rank": 5,  "reward_coins": 30,  "reward_xp": 60,  "reward_badge": ""},
    {"rank": 6,  "reward_coins": 25,  "reward_xp": 50,  "reward_badge": ""},
    {"rank": 7,  "reward_coins": 20,  "reward_xp": 40,  "reward_badge": ""},
    {"rank": 8,  "reward_coins": 15,  "reward_xp": 30,  "reward_badge": ""},
    {"rank": 9,  "reward_coins": 10,  "reward_xp": 20,  "reward_badge": ""},
    {"rank": 10, "reward_coins": 10,  "reward_xp": 20,  "reward_badge": ""},
]

WEEKLY_REWARDS = [
    {"rank": 1,  "reward_coins": 500, "reward_xp": 1000, "reward_badge": "level-50"},
    {"rank": 2,  "reward_coins": 300, "reward_xp": 600,  "reward_badge": ""},
    {"rank": 3,  "reward_coins": 200, "reward_xp": 400,  "reward_badge": ""},
    {"rank": 4,  "reward_coins": 150, "reward_xp": 300,  "reward_badge": ""},
    {"rank": 5,  "reward_coins": 100, "reward_xp": 200,  "reward_badge": ""},
]

MONTHLY_REWARDS = [
    {"rank": 1,  "reward_coins": 2000, "reward_xp": 5000, "reward_badge": "level-50"},
    {"rank": 2,  "reward_coins": 1000, "reward_xp": 2500, "reward_badge": ""},
    {"rank": 3,  "reward_coins": 500,  "reward_xp": 1000, "reward_badge": ""},
]


class Command(BaseCommand):
    help = "Seed the database with default leaderboard reward tiers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season_type",
            choices=["daily", "weekly", "monthly", "all"],
            default="all",
            help="Which season type to seed (default: all).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing rewards for the chosen season type before seeding.",
        )

    def handle(self, *args, **options):
        season_type = options["season_type"]

        seasons_to_seed = {
            "daily":   DAILY_REWARDS,
            "weekly":  WEEKLY_REWARDS,
            "monthly": MONTHLY_REWARDS,
        }

        if season_type != "all":
            seasons_to_seed = {season_type: seasons_to_seed[season_type]}

        for stype, rewards in seasons_to_seed.items():
            if options["clear"]:
                deleted, _ = LeaderboardReward.objects.filter(season_type=stype).delete()
                self.stdout.write(self.style.WARNING(
                    f"Deleted {deleted} existing {stype} rewards."
                ))

            created = updated = 0
            for row in rewards:
                obj, was_created = LeaderboardReward.objects.update_or_create(
                    rank=row["rank"],
                    season_type=stype,
                    defaults={
                        "reward_coins": row["reward_coins"],
                        "reward_xp":   row["reward_xp"],
                        "reward_badge": row["reward_badge"],
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ [{stype}] {created} created + {updated} updated reward tiers."
                )
            )
