"""AD_FORMATS/offerwall_ad.py — Offerwall ad format display logic."""
from decimal import Decimal
from dataclasses import dataclass
from typing import List


@dataclass
class OfferwallDisplayConfig:
    items_per_page: int = 10
    show_featured_first: bool = True
    show_hot_badge: bool = True
    sort_by: str = "point_value"    # point_value | featured | newest
    filter_country: str = ""
    filter_type: str = ""           # all | survey | app_install | video
    theme: str = "light"            # light | dark
    show_timer_on_expiry: bool = True


class OfferwallAdHandler:
    """Handles offerwall layout, sorting, and filtering."""

    @classmethod
    def get_config(cls, items: int = 10,
                    sort: str = "point_value") -> OfferwallDisplayConfig:
        return OfferwallDisplayConfig(items_per_page=items, sort_by=sort)

    @classmethod
    def sort_offers(cls, offers: list, config: OfferwallDisplayConfig) -> list:
        featured = [o for o in offers if getattr(o, "is_featured", False)]
        rest     = [o for o in offers if not getattr(o, "is_featured", False)]
        if config.sort_by == "point_value":
            rest.sort(key=lambda o: getattr(o, "point_value", 0), reverse=True)
        elif config.sort_by == "newest":
            rest.sort(key=lambda o: getattr(o, "created_at", 0), reverse=True)
        return (featured + rest) if config.show_featured_first else (rest + featured)

    @classmethod
    def filter_offers(cls, offers: list, country: str = "",
                       offer_type: str = "") -> list:
        result = offers
        if country:
            result = [
                o for o in result
                if not getattr(o, "target_countries", []) or
                   country.upper() in (getattr(o, "target_countries", []) or [])
            ]
        if offer_type:
            result = [
                o for o in result
                if getattr(o, "offer_type", "") == offer_type
            ]
        return result

    @staticmethod
    def build_embed_url(offerwall_slug: str, user_id: str,
                         base_url: str = "") -> str:
        return f"{base_url}/ow/{offerwall_slug}?uid={user_id}"
