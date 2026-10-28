# engagement/management/commands/seed_shop.py
"""
Usage:
    python manage.py seed_shop
    python manage.py seed_shop --clear
"""
from django.core.management.base import BaseCommand
from engagement.models.shop import ShopItem

DEFAULT_ITEMS = [
    {
        "slug":         "streak-shield",
        "name":         "Streak Shield",
        "description":  "Protects your streak if you miss one day. Automatically applied.",
        "type":         "streak_shield",
        "icon":         "🛡️",
        "price_coins":  50,
        "stock":        -1,
        "max_per_user": 5,
        "effect_days":  7,
        "order":        1,
    },
    {
        "slug":         "spin-boost",
        "name":         "Spin Boost",
        "description":  "Doubles your coin winnings on the spin wheel for 24 hours.",
        "type":         "spin_boost",
        "icon":         "⚡",
        "price_coins":  75,
        "stock":        -1,
        "max_per_user": -1,
        "effect_days":  1,
        "order":        2,
    },
    {
        "slug":         "xp-multiplier",
        "name":         "XP Multiplier",
        "description":  "Doubles all XP earned for 24 hours.",
        "type":         "xp_multiplier",
        "icon":         "✨",
        "price_coins":  100,
        "stock":        -1,
        "max_per_user": -1,
        "effect_days":  1,
        "order":        3,
    },
    {
        "slug":         "coin-pack-small",
        "name":         "Coin Pack (Small)",
        "description":  "Instantly receive 25 bonus coins.",
        "type":         "coin_pack",
        "icon":         "💰",
        "price_coins":  20,
        "stock":        -1,
        "max_per_user": -1,
        "effect_days":  0,
        "order":        4,
    },
    {
        "slug":         "coin-pack-large",
        "name":         "Coin Pack (Large)",
        "description":  "Instantly receive 100 bonus coins.",
        "type":         "coin_pack",
        "icon":         "💎",
        "price_coins":  75,
        "stock":        -1,
        "max_per_user": -1,
        "effect_days":  0,
        "order":        5,
    },
    {
        "slug":         "avatar-frame-gold",
        "name":         "Gold Avatar Frame",
        "description":  "An exclusive gold frame for your profile avatar.",
        "type":         "avatar_frame",
        "icon":         "🖼️",
        "price_coins":  200,
        "stock":        -1,
        "max_per_user": 1,
        "effect_days":  0,
        "order":        6,
    },
    {
        "slug":         "exclusive-badge-vip",
        "name":         "VIP Badge",
        "description":  "A rare VIP badge displayed on your profile.",
        "type":         "badge",
        "icon":         "💠",
        "price_coins":  500,
        "stock":        100,
        "max_per_user": 1,
        "effect_days":  0,
        "order":        7,
    },
]


class Command(BaseCommand):
    help = "Seed the database with default coin shop items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing shop items before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = ShopItem.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing items."))

        created = updated = 0
        for data in DEFAULT_ITEMS:
            obj, was_created = ShopItem.objects.update_or_create(
                slug=data["slug"],
                defaults={**data, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"✅ Shop items seeded: {created} created + {updated} updated.")
        )
