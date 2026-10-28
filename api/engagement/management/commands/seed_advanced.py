# engagement/management/commands/seed_advanced.py
"""
Seeds all advanced system data in one command.
Usage:
    python manage.py seed_advanced
    python manage.py seed_advanced --clear
"""
from decimal import Decimal
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed all advanced engagement systems (milestones, combos, energy, chests, anti-cheat)."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete existing data before seeding.")

    def handle(self, *args, **options):
        clear = options["clear"]
        self.stdout.write(self.style.MIGRATE_HEADING("\n🚀 Seeding advanced engagement systems…\n"))

        self._seed_milestones(clear)
        self._seed_combo_config(clear)
        self._seed_energy_config(clear)
        self._seed_chest_types(clear)
        self._seed_anti_cheat_rules(clear)
        self._seed_prestige_levels(clear)
        self._seed_user_titles(clear)

        self.stdout.write(self.style.SUCCESS("\n✅ Advanced systems seeded successfully!\n"))

    def _seed_milestones(self, clear):
        from engagement.models.prestige import Milestone
        if clear:
            Milestone.objects.all().delete()
        milestones = [
            {"slug": "checkin-10",    "name": "10 Check-ins",         "metric": "total_checkins",   "threshold": 10,      "coin_reward": 20,   "xp_reward": 50,   "order": 1},
            {"slug": "checkin-100",   "name": "100 Check-ins",        "metric": "total_checkins",   "threshold": 100,     "coin_reward": 100,  "xp_reward": 200,  "order": 2},
            {"slug": "checkin-365",   "name": "365 Check-ins",        "metric": "total_checkins",   "threshold": 365,     "coin_reward": 500,  "xp_reward": 1000, "order": 3},
            {"slug": "streak-30",     "name": "30-Day Streak",        "metric": "checkin_streak",   "threshold": 30,      "coin_reward": 100,  "xp_reward": 300,  "order": 4},
            {"slug": "streak-100",    "name": "100-Day Streak",       "metric": "checkin_streak",   "threshold": 100,     "coin_reward": 500,  "xp_reward": 1000, "order": 5},
            {"slug": "streak-365",    "name": "1-Year Streak!",       "metric": "checkin_streak",   "threshold": 365,     "coin_reward": 2000, "xp_reward": 5000, "order": 6, "title_reward": "streak-legend"},
            {"slug": "spins-500",     "name": "500 Spins",            "metric": "total_spins",      "threshold": 500,     "coin_reward": 50,   "xp_reward": 100,  "order": 7},
            {"slug": "spins-5000",    "name": "5000 Spins",           "metric": "total_spins",      "threshold": 5000,    "coin_reward": 300,  "xp_reward": 500,  "order": 8},
            {"slug": "coins-1k",      "name": "1,000 Coins Earned",   "metric": "total_xp",         "threshold": 1000,    "coin_reward": 25,   "xp_reward": 50,   "order": 9},
            {"slug": "coins-100k",    "name": "100,000 XP",           "metric": "total_xp",         "threshold": 100000,  "coin_reward": 500,  "xp_reward": 1000, "order": 10},
            {"slug": "referrals-50",  "name": "50 Referrals",         "metric": "total_referrals",  "threshold": 50,      "coin_reward": 500,  "xp_reward": 1000, "order": 11, "title_reward": "top-referrer"},
            {"slug": "prestige-1",    "name": "First Prestige",       "metric": "prestige_level",   "threshold": 1,       "coin_reward": 200,  "xp_reward": 500,  "order": 12},
            {"slug": "prestige-5",    "name": "Prestige V",           "metric": "prestige_level",   "threshold": 5,       "coin_reward": 1000, "xp_reward": 2000, "order": 13, "title_reward": "prestige-master"},
            {"slug": "friends-10",    "name": "10 Friends",           "metric": "friends_count",    "threshold": 10,      "coin_reward": 30,   "xp_reward": 50,   "order": 14},
            {"slug": "purchases-25",  "name": "25 Purchases",         "metric": "total_purchases",  "threshold": 25,      "coin_reward": 75,   "xp_reward": 150,  "order": 15},
        ]
        created = 0
        for m in milestones:
            title_reward = m.pop("title_reward", "")
            obj, was_created = Milestone.objects.get_or_create(
                slug=m["slug"],
                defaults={**m, "is_active": True, "title_reward": title_reward,
                          "description": f"Reach {m['threshold']} {m['metric'].replace('_', ' ')}."},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"  ✅ Milestones: {created} created."))

    def _seed_combo_config(self, clear):
        from engagement.models.combo import ComboConfig
        if clear:
            ComboConfig.objects.all().delete()
        combos = [
            {"action": "checkin", "window_seconds": 86400, "max_multiplier": Decimal("2"), "step_multiplier": Decimal("0.1")},
            {"action": "spin",    "window_seconds": 3600,  "max_multiplier": Decimal("3"), "step_multiplier": Decimal("0.25")},
        ]
        created = 0
        for c in combos:
            _, was_created = ComboConfig.objects.get_or_create(action=c["action"], defaults={**c, "is_active": True})
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"  ✅ Combo configs: {created} created."))

    def _seed_energy_config(self, clear):
        from engagement.models.combo import EnergyConfig, EnergyCost
        if clear:
            EnergyConfig.objects.all().delete()
            EnergyCost.objects.all().delete()
        config, _ = EnergyConfig.objects.get_or_create(defaults={"max_energy": 100, "regen_per_hour": 10, "is_active": True})
        costs = [("spin", 5), ("scratch_card", 10), ("auction_bid", 2), ("chest_open", 3)]
        created = 0
        for action, cost in costs:
            _, was_created = EnergyCost.objects.get_or_create(action=action, defaults={"cost": cost, "is_active": True})
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"  ✅ Energy config + {created} cost rules created."))

    def _seed_chest_types(self, clear):
        from engagement.models.loot_box import ChestType, ChestDropTable
        if clear:
            ChestType.objects.all().delete()
        chests = [
            ("bronze-chest",    "Bronze Chest",    "common",    Decimal("50"),  "📦"),
            ("silver-chest",    "Silver Chest",    "rare",      Decimal("150"), "🎁"),
            ("gold-chest",      "Gold Chest",      "epic",      Decimal("400"), "🏆"),
            ("legendary-chest", "Legendary Chest", "legendary", Decimal("0"),   "💎"),  # earned only
        ]
        chest_drops = {
            "bronze-chest":    [(Decimal("10"), Decimal("30"),  0,  0, "coins", 60), (0, 0, 20, 50, "xp", 40)],
            "silver-chest":    [(Decimal("30"), Decimal("80"),  0,  0, "coins", 50), (0, 0, 50, 150, "xp", 30), (0, 0, 0, 0, "spin", 20)],
            "gold-chest":      [(Decimal("80"), Decimal("200"), 0,  0, "coins", 40), (0, 0, 100, 300, "xp", 30), (0, 0, 0, 0, "spin", 20), (0, 0, 0, 0, "shop_item", 10)],
            "legendary-chest": [(Decimal("200"), Decimal("500"), 0, 0, "coins", 30), (0, 0, 300, 1000, "xp", 20), (0, 0, 0, 0, "shop_item", 30), (0, 0, 0, 0, "achievement", 20)],
        }
        created = 0
        for slug, name, rarity, price, icon in chests:
            ct, was_created = ChestType.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "rarity": rarity, "price_coins": price, "icon": icon, "is_active": True},
            )
            if was_created:
                created += 1
                for cmin, cmax, xmin, xmax, rtype, weight in chest_drops.get(slug, []):
                    ChestDropTable.objects.create(
                        chest_type=ct, reward_type=rtype, coins_min=cmin, coins_max=cmax,
                        xp_min=xmin, xp_max=xmax, weight=weight, is_active=True,
                    )
        self.stdout.write(self.style.SUCCESS(f"  ✅ Chest types: {created} created."))

    def _seed_anti_cheat_rules(self, clear):
        from engagement.services.anti_cheat_service import AntiCheatService
        if clear:
            from engagement.models.anti_cheat import AntiCheatRule
            AntiCheatRule.objects.all().delete()
        AntiCheatService.seed_default_rules()
        self.stdout.write(self.style.SUCCESS("  ✅ Anti-cheat rules seeded."))

    def _seed_prestige_levels(self, clear):
        from engagement.models.prestige import PrestigeLevel
        if clear:
            PrestigeLevel.objects.all().delete()
        levels = [
            (1, "Bronze",    50,  Decimal("1.1"), Decimal("1.1"), 0,  "#CD7F32"),
            (2, "Silver",    100, Decimal("1.2"), Decimal("1.2"), 1,  "#C0C0C0"),
            (3, "Gold",      150, Decimal("1.5"), Decimal("1.5"), 2,  "#FFD700"),
            (4, "Platinum",  200, Decimal("2.0"), Decimal("2.0"), 3,  "#00FFFF"),
            (5, "Diamond",   250, Decimal("3.0"), Decimal("3.0"), 5,  "#B9F2FF"),
        ]
        created = 0
        for lvl, name, req_level, coin_m, xp_m, spin_b, color in levels:
            _, was_created = PrestigeLevel.objects.get_or_create(
                level=lvl,
                defaults={"name": name, "required_level": req_level,
                          "coin_multiplier": coin_m, "xp_multiplier": xp_m,
                          "spin_bonus": spin_b, "badge_color": color},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"  ✅ Prestige levels: {created} created."))

    def _seed_user_titles(self, clear):
        from engagement.models.prestige import UserTitle
        if clear:
            UserTitle.objects.all().delete()
        titles = [
            ("streak-legend",    "Streak Legend",    "legendary", "#FFD700", "milestone"),
            ("top-referrer",     "Top Referrer",     "epic",      "#9C27B0", "milestone"),
            ("prestige-master",  "Prestige Master",  "legendary", "#00FFFF", "prestige"),
            ("early-adopter",    "Early Adopter",    "rare",      "#2196F3", "event"),
            ("coin-whale",       "Coin Whale",        "epic",      "#4CAF50", "milestone"),
            ("spin-wizard",      "Spin Wizard",       "rare",      "#FF9800", "milestone"),
        ]
        created = 0
        for slug, name, rarity, color, source in titles:
            _, was_created = UserTitle.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "rarity": rarity, "color": color, "source": source},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"  ✅ User titles: {created} created."))
