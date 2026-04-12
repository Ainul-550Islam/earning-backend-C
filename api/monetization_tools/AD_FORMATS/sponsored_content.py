"""AD_FORMATS/sponsored_content.py — Sponsored content / native article ad."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SponsoredContentConfig:
    headline: str
    author_name: str
    brand_name: str
    article_url: str
    thumbnail_url: str = ""
    read_time_minutes: int = 3
    category: str = ""
    label: str = "Sponsored"
    cta_text: str = "Read More"
    engagement_goal: str = "30s_view"   # 30s_view | click | scroll_50


class SponsoredContentHandler:
    """Handles sponsored article / content placement ads."""

    DEFAULT_ECPM = Decimal("3.00")

    @classmethod
    def build(cls, headline: str, author: str, brand: str,
               article_url: str, thumbnail: str = "") -> SponsoredContentConfig:
        return SponsoredContentConfig(
            headline=headline[:100], author_name=author[:50],
            brand_name=brand[:50], article_url=article_url,
            thumbnail_url=thumbnail,
        )

    @classmethod
    def get_ecpm_estimate(cls, country: str = "US") -> Decimal:
        mult = {"US": Decimal("3.5"), "GB": Decimal("3.0"),
                "BD": Decimal("0.4")}.get(country, Decimal("1.0"))
        return (cls.DEFAULT_ECPM * mult).quantize(Decimal("0.0001"))

    @staticmethod
    def validate(config: SponsoredContentConfig) -> list:
        errors = []
        if not config.headline:
            errors.append("headline required")
        if not config.article_url:
            errors.append("article_url required")
        if not config.brand_name:
            errors.append("brand_name required")
        return errors
