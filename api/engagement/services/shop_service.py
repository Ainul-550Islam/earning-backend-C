# engagement/services/shop_service.py
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from ..models.shop import ShopItem, ShopPurchase, UserInventory
from ..exceptions import InsufficientCoinsError, ItemNotAvailableError

logger = logging.getLogger(__name__)


class ShopService:

    @classmethod
    @transaction.atomic
    def purchase(cls, user, item_slug: str, quantity: int = 1, tenant=None) -> dict:
        """
        Purchase a ShopItem. Deducts coins, creates purchase record & inventory entry.
        Raises ItemNotAvailableError, InsufficientCoinsError.
        """
        item = ShopItem.objects.select_for_update().filter(
            slug=item_slug, is_active=True
        ).first()
        if not item:
            raise ItemNotAvailableError(f"Item '{item_slug}' not found.")

        # Stock check
        if item.stock != -1 and item.stock < quantity:
            raise ItemNotAvailableError("Not enough stock.")

        # Per-user limit check
        if item.max_per_user != -1:
            already_bought = ShopPurchase.objects.filter(
                user=user, item=item
            ).aggregate(total=sum)["total"] or 0
            # aggregate correctly
            from django.db.models import Sum as DSum
            already_bought = ShopPurchase.objects.filter(
                user=user, item=item
            ).aggregate(total=DSum("quantity"))["total"] or 0
            if already_bought + quantity > item.max_per_user:
                raise ItemNotAvailableError(f"Purchase limit of {item.max_per_user} reached.")

        total_cost = item.price_coins * quantity

        # Deduct coins (raises InsufficientCoinsError if insufficient)
        CoinService.deduct(user, total_cost, source="shop_purchase", ref_id=item.slug)

        # Reduce stock
        if item.stock != -1:
            ShopItem.objects.filter(pk=item.pk).update(stock=item.stock - quantity)

        # Create purchase record
        expires_at = timezone.now() + timedelta(days=item.effect_days) if item.effect_days > 0 else None
        purchase = ShopPurchase.objects.create(
            user       = user,
            tenant     = tenant or getattr(user, "tenant", None),
            item       = item,
            quantity   = quantity,
            coins_spent = total_cost,
            expires_at = expires_at,
        )

        # Upsert inventory
        inv, created = UserInventory.objects.get_or_create(
            user=user, item=item,
            defaults={"tenant": tenant or getattr(user, "tenant", None), "quantity": 0},
        )
        inv.quantity   += quantity
        inv.expires_at  = expires_at
        inv.save(update_fields=["quantity", "expires_at"])

        logger.info("Shop: user=%s bought '%s' ×%d for %s coins", user.pk, item.slug, quantity, total_cost)

        return {
            "purchase":    purchase,
            "item":        item,
            "quantity":    quantity,
            "coins_spent": float(total_cost),
            "new_balance": float(CoinService.balance(user)),
            "expires_at":  expires_at.isoformat() if expires_at else None,
        }

    @staticmethod
    def inventory(user) -> list:
        """Return user's active inventory items."""
        now = timezone.now()
        return list(
            UserInventory.objects.filter(user=user, quantity__gt=0)
            .exclude(expires_at__lt=now)
            .select_related("item")
        )

    @staticmethod
    def available_items(tenant=None) -> list:
        qs = ShopItem.objects.filter(is_active=True)
        return list(qs.order_by("order", "price_coins"))
