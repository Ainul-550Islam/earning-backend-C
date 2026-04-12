"""
PAYMENT_SETTLEMENT/commission_calculator.py — Multi-level Commission Engine
============================================================================
Priority order (highest wins):
  1. Seller-specific override (SellerCommissionOverride)
  2. Category-level CommissionConfig
  3. Parent category CommissionConfig (walks up the tree)
  4. Global default CommissionConfig (category IS NULL)
  5. Hard-coded fallback: 10% + 5 BDT

Commission formula:
  commission = (gross_amount × rate / 100) + flat_fee

Supports:
  - Tiered rates (revenue-based seller tiers)
  - Promotional zero-commission windows
  - Category tree walk (child → parent → root → global)
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

from api.marketplace.models import Category, CommissionConfig, SellerProfile

logger = logging.getLogger(__name__)

CACHE_TTL   = 300   # seconds
FALLBACK_RATE    = Decimal("10.00")
FALLBACK_FLAT    = Decimal("5.00")


# ─────────────────────────────────────────────────────────────────────────────
# Seller override model (inline — no separate migration needed if added here)
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: SellerCommissionOverride is defined in models.py
#       If not yet added, CommissionCalculator gracefully falls back.


class CommissionCalculator:
    """
    Multi-level commission calculation engine.
    Usage:
        calc = CommissionCalculator()
        rate, amount = calc.calculate(amount=Decimal("1000"), category=cat, tenant=tenant)
    """

    def calculate(
        self,
        amount: Decimal,
        category: Optional[Category],
        tenant,
        seller: Optional[SellerProfile] = None,
    ) -> Tuple[Decimal, Decimal]:
        """
        Returns (commission_rate, commission_amount).
        rate is in % (e.g. Decimal("12.50")).
        amount is the absolute BDT value.
        """
        config = self._resolve_config(category, tenant, seller)
        commission = (amount * config["rate"] / 100) + config["flat_fee"]
        commission = commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Commission cannot exceed the item value
        commission = min(commission, amount)

        logger.debug(
            "[Commission] amount=%s | rate=%s%% | flat=%s | commission=%s",
            amount, config["rate"], config["flat_fee"], commission,
        )
        return config["rate"], commission

    def calculate_batch(self, items: list, tenant) -> list:
        """
        Batch calculate for a list of dicts:
        [{"amount": Decimal, "category": Category, "seller": SellerProfile}]
        Returns list of (rate, commission) tuples.
        """
        return [
            self.calculate(
                amount=item["amount"],
                category=item.get("category"),
                tenant=tenant,
                seller=item.get("seller"),
            )
            for item in items
        ]

    # ── Resolution chain ─────────────────────────────────────────────────────
    def _resolve_config(
        self,
        category: Optional[Category],
        tenant,
        seller: Optional[SellerProfile],
    ) -> dict:
        # 1. Seller-specific override
        if seller:
            override = self._seller_override(seller, tenant)
            if override:
                return override

        # 2. Category chain (child → parent → root)
        if category:
            cfg = self._category_chain(category, tenant)
            if cfg:
                return cfg

        # 3. Global default
        global_cfg = self._global_config(tenant)
        if global_cfg:
            return global_cfg

        # 4. Hard-coded fallback
        logger.warning("[Commission] No config found for tenant=%s. Using fallback.", tenant)
        return {"rate": FALLBACK_RATE, "flat_fee": FALLBACK_FLAT}

    def _seller_override(self, seller: SellerProfile, tenant) -> Optional[dict]:
        """Check if seller has a custom commission rate (e.g. platinum seller)."""
        cache_key = f"commission:seller:{seller.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from api.marketplace.models import SellerCommissionOverride  # optional model
            now = timezone.now().date()
            override = SellerCommissionOverride.objects.filter(
                seller=seller,
                tenant=tenant,
                is_active=True,
                effective_from__lte=now,
            ).filter(
                effective_until__isnull=True
            ).first() or SellerCommissionOverride.objects.filter(
                seller=seller, tenant=tenant,
                is_active=True, effective_from__lte=now,
                effective_until__gte=now,
            ).first()

            if override:
                result = {"rate": override.rate, "flat_fee": override.flat_fee}
                cache.set(cache_key, result, CACHE_TTL)
                return result
        except Exception:
            pass  # Model doesn't exist yet → fall through
        cache.set(cache_key, None, CACHE_TTL)
        return None

    def _category_chain(self, category: Category, tenant) -> Optional[dict]:
        """Walk category tree: child → parent → grandparent → ..."""
        node = category
        while node:
            cfg = self._get_category_config(node, tenant)
            if cfg:
                return cfg
            node = node.parent
        return None

    def _get_category_config(self, category: Category, tenant) -> Optional[dict]:
        cache_key = f"commission:cat:{tenant.pk}:{category.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            # Cache stores False for "not found" to avoid repeated DB hits
            return cached if cached else None

        now = timezone.now().date()
        try:
            cfg = CommissionConfig.objects.filter(
                tenant=tenant,
                category=category,
                is_active=True,
                effective_from__lte=now,
            ).filter(
                effective_until__isnull=True
            ).first() or CommissionConfig.objects.filter(
                tenant=tenant,
                category=category,
                is_active=True,
                effective_from__lte=now,
                effective_until__gte=now,
            ).first()

            if cfg:
                result = {"rate": cfg.rate, "flat_fee": cfg.flat_fee}
                cache.set(cache_key, result, CACHE_TTL)
                return result
        except Exception as e:
            logger.error("[Commission] DB error fetching config for cat#%s: %s", category.pk, e)

        cache.set(cache_key, False, CACHE_TTL)  # negative cache
        return None

    def _global_config(self, tenant) -> Optional[dict]:
        cache_key = f"commission:global:{tenant.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached if cached else None

        try:
            cfg = CommissionConfig.objects.filter(
                tenant=tenant,
                category__isnull=True,
                is_active=True,
            ).first()
            if cfg:
                result = {"rate": cfg.rate, "flat_fee": cfg.flat_fee}
                cache.set(cache_key, result, CACHE_TTL)
                return result
        except Exception:
            pass

        cache.set(cache_key, False, CACHE_TTL)
        return None

    # ── Admin helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def preview(amount: Decimal, category: Optional[Category], tenant, seller=None) -> dict:
        """
        Preview commission without persisting anything.
        Useful for seller dashboard: "You will earn X for this product".
        """
        calc = CommissionCalculator()
        rate, commission = calc.calculate(amount, category, tenant, seller)
        seller_net = amount - commission
        return {
            "gross": str(amount),
            "commission_rate": f"{rate}%",
            "commission_amount": str(commission),
            "seller_net": str(seller_net),
            "platform_revenue": str(commission),
        }

    @staticmethod
    def effective_rate(category: Optional[Category], tenant) -> Decimal:
        """Shortcut: just the rate (%) for display purposes."""
        calc = CommissionCalculator()
        rate, _ = calc.calculate(Decimal("100"), category, tenant)
        return rate

    @staticmethod
    def invalidate_cache(tenant, category=None, seller=None):
        """Call after updating CommissionConfig in admin."""
        if category:
            cache.delete(f"commission:cat:{tenant.pk}:{category.pk}")
        if seller:
            cache.delete(f"commission:seller:{seller.pk}")
        cache.delete(f"commission:global:{tenant.pk}")


# ── Module-level shorthand ────────────────────────────────────────────────────
_calc = CommissionCalculator()


def calculate(amount: Decimal, category, tenant, seller=None) -> Tuple[Decimal, Decimal]:
    """Shorthand: returns (rate, commission_amount)."""
    return _calc.calculate(amount, category, tenant, seller)
