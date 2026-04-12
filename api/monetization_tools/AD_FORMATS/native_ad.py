"""AD_FORMATS/native_ad.py — Native ad format handler."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class NativeAdAssets:
    headline: str = ""
    body: str = ""
    cta_text: str = "Learn More"
    advertiser_name: str = ""
    icon_url: str = ""
    image_url: str = ""
    star_rating: float = 0.0
    price: str = ""


class NativeAdHandler:
    """Native ad — blends into content feed."""

    LAYOUTS = ["content_feed", "app_wall", "chat_list",
               "article_inline", "card_grid"]

    @classmethod
    def build_assets(cls, headline: str, body: str, cta: str,
                      advertiser: str, icon_url: str = "",
                      image_url: str = "") -> NativeAdAssets:
        return NativeAdAssets(
            headline=headline[:90], body=body[:150],
            cta_text=cta[:20], advertiser_name=advertiser[:25],
            icon_url=icon_url, image_url=image_url,
        )

    @classmethod
    def get_ecpm_estimate(cls, layout: str = "content_feed",
                           country: str = "US") -> Decimal:
        base = {"content_feed": Decimal("2.5"), "app_wall": Decimal("1.8"),
                "article_inline": Decimal("2.0")}.get(layout, Decimal("1.5"))
        mult = {"US": Decimal("3.0"), "GB": Decimal("2.5"),
                "BD": Decimal("0.4")}.get(country, Decimal("1.0"))
        return (base * mult).quantize(Decimal("0.0001"))

    @classmethod
    def validate_assets(cls, assets: NativeAdAssets) -> list:
        errors = []
        if not assets.headline:
            errors.append("headline is required")
        if not assets.cta_text:
            errors.append("cta_text is required")
        return errors
