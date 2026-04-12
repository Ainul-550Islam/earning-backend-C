"""
DATABASE_MODELS/setting_table.py — Marketplace Settings Reference
"""
from api.marketplace.MOBILE_MARKETPLACE.mobile_app_config import MobileAppConfig, get_app_config, set_config
from api.marketplace.PROMOTION_MARKETING.loyalty_reward import LoyaltyAccount, LoyaltyTransaction, LoyaltyService
from api.marketplace.PAYMENT_SETTLEMENT.seller_payout_schedule import PayoutSchedule, get_sellers_due_for_payout


class MarketplaceSettings:
    """
    Runtime settings for the marketplace.
    Values read from MobileAppConfig or Django settings.
    """

    def __init__(self, tenant):
        self.tenant  = tenant
        self._config = get_app_config(tenant)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def is_feature_enabled(self, feature: str) -> bool:
        features = self._config.get("features", {})
        return features.get(feature, True)

    def update(self, key: str, value, value_type: str = "string"):
        set_config(self.tenant, key, value, value_type)
        self._config = get_app_config(self.tenant)


__all__ = [
    "MobileAppConfig","LoyaltyAccount","LoyaltyTransaction","LoyaltyService",
    "PayoutSchedule","get_app_config","get_sellers_due_for_payout",
    "MarketplaceSettings",
]
