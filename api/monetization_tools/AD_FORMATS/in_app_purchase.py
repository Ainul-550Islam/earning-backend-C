"""AD_FORMATS/in_app_purchase.py — In-app purchase ad/prompt handler."""
from decimal import Decimal
from dataclasses import dataclass
from typing import List


@dataclass
class IAPPromptConfig:
    product_id: str
    product_name: str
    price: Decimal
    currency: str = "BDT"
    coins_granted: Decimal = Decimal("0")
    cta_label: str = "Buy Now"
    description: str = ""
    icon_url: str = ""
    highlight_value: str = ""
    is_limited_offer: bool = False
    discount_pct: Decimal = Decimal("0")


class IAPPromptHandler:
    """Builds in-app purchase prompts and validates pricing."""

    @classmethod
    def build(cls, product_id: str, product_name: str,
               price: Decimal, coins: Decimal,
               currency: str = "BDT") -> IAPPromptConfig:
        return IAPPromptConfig(
            product_id=product_id,
            product_name=product_name,
            price=price,
            currency=currency,
            coins_granted=coins,
        )

    @classmethod
    def calculate_value_label(cls, price: Decimal,
                               coins: Decimal) -> str:
        if price and price > 0:
            per_coin = price / coins if coins else Decimal("0")
            return f"{coins:,.0f} coins for {price} (${per_coin:.4f}/coin)"
        return f"{coins:,.0f} coins"

    @classmethod
    def apply_discount(cls, config: IAPPromptConfig,
                        pct: Decimal) -> IAPPromptConfig:
        discounted = config.price * (1 - pct / 100)
        config.price           = discounted.quantize(Decimal("0.01"))
        config.discount_pct    = pct
        config.is_limited_offer = True
        return config

    @staticmethod
    def to_store_payload(config: IAPPromptConfig) -> dict:
        return {
            "product_id":    config.product_id,
            "display_name":  config.product_name,
            "price":         str(config.price),
            "currency":      config.currency,
            "coins_granted": str(config.coins_granted),
        }
