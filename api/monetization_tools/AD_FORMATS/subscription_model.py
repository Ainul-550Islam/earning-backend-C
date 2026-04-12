"""AD_FORMATS/subscription_model.py — Subscription upsell ad/prompt."""
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List


@dataclass
class SubscriptionUpsellConfig:
    plan_name: str
    price: Decimal
    currency: str = "BDT"
    interval: str = "monthly"
    trial_days: int = 0
    features: List[str] = field(default_factory=list)
    cta_label: str = "Start Free Trial"
    highlight_feature: str = ""
    badge_label: str = ""
    discount_pct: Decimal = Decimal("0")


class SubscriptionUpsellHandler:
    """Builds subscription upsell prompts for paywalls and interstitials."""

    @classmethod
    def build(cls, plan_name: str, price: Decimal, features: List[str],
               trial_days: int = 0, currency: str = "BDT") -> SubscriptionUpsellConfig:
        return SubscriptionUpsellConfig(
            plan_name=plan_name, price=price, features=features,
            trial_days=trial_days, currency=currency,
            cta_label="Start Free Trial" if trial_days > 0 else "Subscribe Now",
        )

    @classmethod
    def to_display_dict(cls, config: SubscriptionUpsellConfig) -> dict:
        price_str = f"{config.price} {config.currency}/{config.interval}"
        if config.trial_days:
            price_str = f"{config.trial_days}-day free trial, then {price_str}"
        return {
            "plan_name":    config.plan_name,
            "price_label":  price_str,
            "features":     config.features,
            "cta_label":    config.cta_label,
            "badge":        config.badge_label,
        }

    @classmethod
    def apply_discount(cls, config: SubscriptionUpsellConfig,
                        pct: Decimal) -> SubscriptionUpsellConfig:
        config.price       = (config.price * (1 - pct / 100)).quantize(Decimal("0.01"))
        config.discount_pct = pct
        config.badge_label  = f"{pct:.0f}% OFF"
        return config
