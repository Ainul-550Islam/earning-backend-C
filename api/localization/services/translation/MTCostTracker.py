# services/translation/MTCostTracker.py
"""Machine translation cost tracking per provider."""
import logging
from decimal import Decimal
from typing import Dict
from django.core.cache import cache
logger = logging.getLogger(__name__)

# Approximate cost per 1M characters (USD)
PROVIDER_COSTS = {
    "google":  Decimal("20.00"),
    "deepl":   Decimal("25.00"),
    "azure":   Decimal("10.00"),
    "amazon":  Decimal("15.00"),
    "openai":  Decimal("150.00"),  # Approx for gpt-4o-mini input
    "memory":  Decimal("0.00"),    # Free!
    "manual":  Decimal("0.00"),
}

FREE_TIER_CHARS = {
    "google":  500_000,
    "deepl":   500_000,
    "azure":   2_000_000,
    "amazon":  2_000_000,
    "openai":  0,
}


class MTCostTracker:
    """Track and estimate MT costs per provider."""

    def record(self, provider: str, char_count: int, success: bool = True):
        """Translation cost record করে।"""
        try:
            from ..models.analytics import LocalizationAnalytics
            LocalizationAnalytics.log_event(
                event_type="mt_usage",
                extra_data={
                    "provider": provider,
                    "chars": char_count,
                    "success": success,
                    "cost_usd": float(self.estimate_cost(provider, char_count)),
                }
            )
        except Exception as e:
            logger.debug(f"MTCostTracker.record failed: {e}")

    def estimate_cost(self, provider: str, char_count: int, include_free_tier: bool = True) -> Decimal:
        """Cost estimate করে।"""
        cost_per_million = PROVIDER_COSTS.get(provider, Decimal("20.00"))
        if cost_per_million == 0:
            return Decimal("0.00")
        billable_chars = char_count
        if include_free_tier:
            used = self._get_monthly_usage(provider)
            free = FREE_TIER_CHARS.get(provider, 0)
            remaining_free = max(0, free - used)
            billable_chars = max(0, char_count - remaining_free)
        return Decimal(str(billable_chars)) / Decimal("1000000") * cost_per_million

    def get_monthly_report(self) -> Dict:
        """Monthly cost report।"""
        try:
            from ..models.analytics import LocalizationAnalytics
            from django.db.models import Sum
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=30)
            events = LocalizationAnalytics.objects.filter(
                event_type="mt_usage", created_at__gte=cutoff
            ).values_list("extra_data", flat=True)
            total_cost = Decimal("0")
            by_provider: Dict = {}
            for data in events:
                if isinstance(data, dict):
                    provider = data.get("provider", "unknown")
                    cost = Decimal(str(data.get("cost_usd", 0)))
                    chars = data.get("chars", 0)
                    total_cost += cost
                    if provider not in by_provider:
                        by_provider[provider] = {"cost_usd": Decimal("0"), "chars": 0}
                    by_provider[provider]["cost_usd"] += cost
                    by_provider[provider]["chars"] += chars
            return {
                "period": "last_30_days",
                "total_cost_usd": float(total_cost),
                "by_provider": {k: {"cost_usd": float(v["cost_usd"]), "chars": v["chars"]}
                                for k, v in by_provider.items()},
                "estimated_savings_from_tm": self._estimate_tm_savings(),
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_monthly_usage(self, provider: str) -> int:
        cache_key = f"mt_monthly_chars_{provider}"
        return cache.get(cache_key) or 0

    def _estimate_tm_savings(self) -> float:
        try:
            from ..models.translation import TranslationMemory
            tm_hits = TranslationMemory.objects.filter(usage_count__gt=0).aggregate(
                total=__import__("django.db.models", fromlist=["Sum"]).Sum("usage_count")
            )["total"] or 0
            avg_chars = 50  # Average chars per TM hit
            return float(Decimal(str(tm_hits * avg_chars)) / Decimal("1000000") * Decimal("20"))
        except Exception:
            return 0
