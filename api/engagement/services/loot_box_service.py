# engagement/services/loot_box_service.py
import random
import logging
from decimal import Decimal
from django.db import transaction
from .coin_service import CoinService
from .xp_service import XPService
from ..models.loot_box import ChestType, ChestDropTable, UserChest, ChestOpening
from ..exceptions import ItemNotAvailableError, InsufficientCoinsError

logger = logging.getLogger(__name__)


class LootBoxService:

    @classmethod
    @transaction.atomic
    def open_chest(cls, user, chest_type_slug: str, tenant=None) -> dict:
        """
        Open one chest from user's inventory.
        Rolls the drop table and grants the reward.
        """
        chest_type = ChestType.objects.get(slug=chest_type_slug, is_active=True)

        # Check inventory
        inv = UserChest.objects.select_for_update().filter(
            user=user, chest_type=chest_type, quantity__gt=0
        ).first()
        if not inv:
            raise ItemNotAvailableError("You don't have this chest.")

        # Roll drop table
        drop = cls._roll_drop(chest_type)
        if not drop:
            raise ItemNotAvailableError("No active drops configured for this chest.")

        # Grant reward
        coins_won = Decimal("0")
        xp_won    = 0
        if drop.reward_type == "coins":
            coins_won = Decimal(str(random.uniform(
                float(drop.coins_min), float(drop.coins_max)
            ))).quantize(Decimal("1"))
            CoinService.add(user, coins_won, source="chest", ref_id=str(chest_type.pk))
        elif drop.reward_type == "xp":
            xp_won = random.randint(drop.xp_min, drop.xp_max)
            XPService.grant(user, xp_won, source="chest", ref_id=str(chest_type.pk))
        elif drop.reward_type == "shop_item" and drop.reward_slug:
            from .shop_service import ShopService
            try:
                ShopService.purchase(user, drop.reward_slug, quantity=drop.quantity, tenant=tenant)
            except Exception as exc:
                logger.warning("LootBoxService: shop item grant failed: %s", exc)
        elif drop.reward_type == "spin":
            from ..models.spinwheel import SpinWheel
            for _ in range(drop.quantity):
                from .spin_service import SpinService
                SpinService.spin(user, tenant=tenant)
        elif drop.reward_type == "chest" and drop.reward_slug:
            bonus_chest = ChestType.objects.filter(slug=drop.reward_slug, is_active=True).first()
            if bonus_chest:
                cls.grant_chest(user, bonus_chest, quantity=drop.quantity, source="chest_drop", tenant=tenant)

        # Decrement inventory
        inv.quantity -= 1
        inv.save(update_fields=["quantity"])

        # Record
        opening = ChestOpening.objects.create(
            user=user, tenant=tenant or getattr(user, "tenant", None),
            chest_type=chest_type, drop_table_entry=drop,
            reward_type=drop.reward_type, reward_slug=drop.reward_slug,
            coins_won=coins_won, xp_won=xp_won, quantity=drop.quantity,
        )
        logger.info("LootBoxService: user=%s opened %s → %s", user.pk, chest_type.slug, drop.reward_type)
        return {
            "chest":       chest_type.slug,
            "reward_type": drop.reward_type,
            "reward_slug": drop.reward_slug,
            "coins_won":   float(coins_won),
            "xp_won":      xp_won,
            "quantity":    drop.quantity,
            "label":       f"{'💰' if drop.reward_type=='coins' else '✨'} {drop.reward_type.replace('_',' ').title()}",
        }

    @classmethod
    @transaction.atomic
    def grant_chest(cls, user, chest_type: ChestType, quantity: int = 1,
                    source: str = "", tenant=None) -> UserChest:
        """Add chests to a user's inventory."""
        inv, _ = UserChest.objects.get_or_create(
            user=user, chest_type=chest_type,
            defaults={"tenant": tenant or getattr(user, "tenant", None), "quantity": 0, "source": source},
        )
        inv.quantity += quantity
        inv.save(update_fields=["quantity"])
        return inv

    @classmethod
    @transaction.atomic
    def buy_chest(cls, user, chest_type_slug: str, tenant=None) -> dict:
        """Buy a chest from the shop using coins."""
        chest_type = ChestType.objects.get(slug=chest_type_slug, is_active=True)
        if chest_type.price_coins <= 0:
            raise ItemNotAvailableError("This chest is not for sale.")
        CoinService.deduct(user, chest_type.price_coins, source="chest_purchase")
        cls.grant_chest(user, chest_type, quantity=1, source="purchase", tenant=tenant)
        return {"success": True, "chest": chest_type.slug, "coins_spent": float(chest_type.price_coins)}

    @staticmethod
    def _roll_drop(chest_type: ChestType) -> "ChestDropTable | None":
        drops = list(ChestDropTable.objects.filter(chest_type=chest_type, is_active=True))
        if not drops:
            return None
        total_weight = sum(d.weight for d in drops)
        roll = random.randint(1, total_weight)
        cumulative = 0
        for drop in drops:
            cumulative += drop.weight
            if roll <= cumulative:
                return drop
        return drops[-1]
