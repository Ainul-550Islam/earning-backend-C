# engagement/management/commands/seed_achievements.py
"""
Usage:
    python manage.py seed_achievements
    python manage.py seed_achievements --clear
"""
from django.core.management.base import BaseCommand
from engagement.models.achievement import Achievement


ACHIEVEMENTS = [
    # ── Streak ──────────────────────────────────────────────────────────────
    {"slug": "streak-3",   "name": "3-Day Streak",    "type": "streak",   "threshold": 3,   "icon": "🔥", "xp_reward": 50,  "coin_reward": 10,  "order": 1},
    {"slug": "streak-7",   "name": "7-Day Streak",    "type": "streak",   "threshold": 7,   "icon": "🔥", "xp_reward": 100, "coin_reward": 25,  "order": 2},
    {"slug": "streak-14",  "name": "2-Week Warrior",  "type": "streak",   "threshold": 14,  "icon": "🔥", "xp_reward": 200, "coin_reward": 50,  "order": 3},
    {"slug": "streak-30",  "name": "30-Day Legend",   "type": "streak",   "threshold": 30,  "icon": "🏆", "xp_reward": 500, "coin_reward": 100, "order": 4},
    {"slug": "streak-100", "name": "100-Day Champion", "type": "streak",  "threshold": 100, "icon": "👑", "xp_reward": 2000,"coin_reward": 500, "order": 5, "is_secret": True},

    # ── Spins ────────────────────────────────────────────────────────────────
    {"slug": "spins-10",   "name": "First Spins",     "type": "spins",    "threshold": 10,  "icon": "🎡", "xp_reward": 30,  "coin_reward": 5,   "order": 1},
    {"slug": "spins-50",   "name": "Spin Addict",     "type": "spins",    "threshold": 50,  "icon": "🎡", "xp_reward": 100, "coin_reward": 20,  "order": 2},
    {"slug": "spins-200",  "name": "Spin Master",     "type": "spins",    "threshold": 200, "icon": "🎰", "xp_reward": 300, "coin_reward": 75,  "order": 3},
    {"slug": "spins-1000", "name": "Wheel Wizard",    "type": "spins",    "threshold": 1000,"icon": "🧙", "xp_reward": 1000,"coin_reward": 200, "order": 4, "is_secret": True},

    # ── Levels ───────────────────────────────────────────────────────────────
    {"slug": "level-5",    "name": "Level 5",         "type": "level",    "threshold": 5,   "icon": "⬆️", "xp_reward": 100, "coin_reward": 20,  "order": 1},
    {"slug": "level-10",   "name": "Level 10",        "type": "level",    "threshold": 10,  "icon": "⬆️", "xp_reward": 250, "coin_reward": 50,  "order": 2},
    {"slug": "level-25",   "name": "Level 25",        "type": "level",    "threshold": 25,  "icon": "🌟", "xp_reward": 750, "coin_reward": 150, "order": 3},
    {"slug": "level-50",   "name": "Level 50 Elite",  "type": "level",    "threshold": 50,  "icon": "💎", "xp_reward": 2000,"coin_reward": 400, "order": 4, "is_secret": True},

    # ── Referrals ─────────────────────────────────────────────────────────────
    {"slug": "referral-1",  "name": "First Referral",  "type": "referral", "threshold": 1,  "icon": "👥", "xp_reward": 100, "coin_reward": 25,  "order": 1},
    {"slug": "referral-5",  "name": "5 Referrals",     "type": "referral", "threshold": 5,  "icon": "👥", "xp_reward": 300, "coin_reward": 75,  "order": 2},
    {"slug": "referral-20", "name": "Referral King",   "type": "referral", "threshold": 20, "icon": "👑", "xp_reward": 1000,"coin_reward": 250, "order": 3},

    # ── Quests ────────────────────────────────────────────────────────────────
    {"slug": "quests-10",  "name": "Quest Starter",   "type": "quest",    "threshold": 10,  "icon": "📋", "xp_reward": 100, "coin_reward": 20,  "order": 1},
    {"slug": "quests-50",  "name": "Quest Hero",      "type": "quest",    "threshold": 50,  "icon": "📋", "xp_reward": 400, "coin_reward": 80,  "order": 2},
    {"slug": "quests-100", "name": "Quest Legend",    "type": "quest",    "threshold": 100, "icon": "🦸", "xp_reward": 1000,"coin_reward": 200, "order": 3},

    # ── Shop Purchases ────────────────────────────────────────────────────────
    {"slug": "purchase-1", "name": "First Purchase",  "type": "purchase", "threshold": 1,   "icon": "🛍️","xp_reward": 50,  "coin_reward": 0,   "order": 1},
    {"slug": "purchase-10","name": "Shop Regular",    "type": "purchase", "threshold": 10,  "icon": "🛍️","xp_reward": 200, "coin_reward": 0,   "order": 2},
]


class Command(BaseCommand):
    help = "Seed the database with default achievement definitions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing achievements before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Achievement.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing achievements."))

        created_count = 0
        updated_count = 0

        for data in ACHIEVEMENTS:
            is_secret = data.pop("is_secret", False)
            obj, created = Achievement.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    **data,
                    "is_secret":  is_secret,
                    "is_active":  True,
                    "badge_color": "#FFD700",
                    "description": f"Reach {data['threshold']} {data['type'].replace('_', ' ')}.",
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Seeded {created_count} new + {updated_count} updated achievements."
            )
        )
