# engagement/management/commands/seed_quests.py
"""
Usage:
    python manage.py seed_quests
    python manage.py seed_quests --clear
"""
from django.core.management.base import BaseCommand
from engagement.models.quest import Quest

DEFAULT_QUESTS = [
    # ── Daily ────────────────────────────────────────────────────────────────
    {
        "slug": "daily-checkin",
        "title": "Daily Check-In",
        "description": "Check in today to earn your streak bonus.",
        "type": "daily",
        "icon": "📅",
        "target": 1,
        "action": "checkin",
        "coin_reward": 5,
        "xp_reward": 20,
        "order": 1,
    },
    {
        "slug": "daily-spin-3",
        "title": "Spin 3 Times",
        "description": "Use the spin wheel 3 times today.",
        "type": "daily",
        "icon": "🎡",
        "target": 3,
        "action": "spin",
        "coin_reward": 10,
        "xp_reward": 30,
        "order": 2,
    },
    {
        "slug": "daily-spin-all",
        "title": "Max Spins",
        "description": "Use all 5 spin wheel spins today.",
        "type": "daily",
        "icon": "🎰",
        "target": 5,
        "action": "spin",
        "coin_reward": 25,
        "xp_reward": 50,
        "order": 3,
    },
    {
        "slug": "daily-buy-item",
        "title": "Visit the Shop",
        "description": "Purchase any item from the coin shop.",
        "type": "daily",
        "icon": "🛍️",
        "target": 1,
        "action": "buy_item",
        "coin_reward": 15,
        "xp_reward": 25,
        "order": 4,
    },

    # ── Weekly ───────────────────────────────────────────────────────────────
    {
        "slug": "weekly-checkin-5",
        "title": "5-Day Check-In",
        "description": "Check in at least 5 days this week.",
        "type": "weekly",
        "icon": "🗓️",
        "target": 5,
        "action": "checkin",
        "coin_reward": 50,
        "xp_reward": 100,
        "order": 1,
    },
    {
        "slug": "weekly-checkin-7",
        "title": "Perfect Week",
        "description": "Check in every single day this week.",
        "type": "weekly",
        "icon": "🏆",
        "target": 7,
        "action": "checkin",
        "coin_reward": 100,
        "xp_reward": 200,
        "order": 2,
    },
    {
        "slug": "weekly-spin-20",
        "title": "Spin Frenzy",
        "description": "Complete 20 spins this week.",
        "type": "weekly",
        "icon": "🌀",
        "target": 20,
        "action": "spin",
        "coin_reward": 75,
        "xp_reward": 150,
        "order": 3,
    },
    {
        "slug": "weekly-buy-3",
        "title": "Shop Spree",
        "description": "Purchase 3 items from the shop this week.",
        "type": "weekly",
        "icon": "💳",
        "target": 3,
        "action": "buy_item",
        "coin_reward": 60,
        "xp_reward": 120,
        "order": 4,
    },
]


class Command(BaseCommand):
    help = "Seed the database with default daily and weekly quest definitions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing quests before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Quest.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing quests."))

        created = updated = 0
        for data in DEFAULT_QUESTS:
            obj, was_created = Quest.objects.update_or_create(
                slug=data["slug"],
                defaults={**data, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"✅ Quests seeded: {created} created + {updated} updated.")
        )
