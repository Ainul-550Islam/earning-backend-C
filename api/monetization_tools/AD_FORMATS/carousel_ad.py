"""AD_FORMATS/carousel_ad.py — Carousel / swipeable multi-card ad."""
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List


@dataclass
class CarouselCard:
    title: str
    description: str
    image_url: str
    cta_text: str = "Learn More"
    landing_url: str = ""


@dataclass
class CarouselAdConfig:
    cards: List[CarouselCard] = field(default_factory=list)
    auto_scroll: bool = False
    scroll_interval_sec: int = 3
    show_indicators: bool = True
    max_cards: int = 10


class CarouselAdHandler:
    """Multi-card carousel ad for high-engagement placements."""

    MIN_CARDS = 2
    MAX_CARDS = 10

    @classmethod
    def build(cls, cards: List[dict]) -> CarouselAdConfig:
        card_objs = [
            CarouselCard(
                title=c.get("title", ""),
                description=c.get("description", ""),
                image_url=c.get("image_url", ""),
                cta_text=c.get("cta_text", "Learn More"),
                landing_url=c.get("landing_url", ""),
            )
            for c in cards[:cls.MAX_CARDS]
        ]
        return CarouselAdConfig(cards=card_objs)

    @classmethod
    def get_ecpm_estimate(cls, card_count: int = 5,
                           country: str = "US") -> Decimal:
        base = Decimal("2.00") + Decimal("0.10") * card_count
        mult = {"US": Decimal("2.5"), "BD": Decimal("0.4")}.get(country, Decimal("1.0"))
        return (base * mult).quantize(Decimal("0.0001"))

    @classmethod
    def validate(cls, config: CarouselAdConfig) -> list:
        errors = []
        if len(config.cards) < cls.MIN_CARDS:
            errors.append(f"Minimum {cls.MIN_CARDS} cards required.")
        for i, card in enumerate(config.cards):
            if not card.title:
                errors.append(f"Card {i+1}: title required.")
            if not card.image_url:
                errors.append(f"Card {i+1}: image_url required.")
        return errors
