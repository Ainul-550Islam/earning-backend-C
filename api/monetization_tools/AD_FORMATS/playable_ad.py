"""AD_FORMATS/playable_ad.py — Playable (interactive HTML5) ad handler."""
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class PlayableAdConfig:
    duration_seconds: int = 30
    end_card_duration: int = 5
    mraid_version: str = "2.0"
    orientation: str = "auto"      # portrait | landscape | auto
    close_on_end: bool = False
    require_interaction: bool = True


class PlayableAdHandler:
    """Handles playable / interactive HTML5 ad units — premium eCPM."""

    DEFAULT_ECPM = Decimal("15.00")

    @classmethod
    def get_config(cls, duration: int = 30) -> PlayableAdConfig:
        return PlayableAdConfig(duration_seconds=duration)

    @classmethod
    def get_ecpm_estimate(cls, country: str = "US") -> Decimal:
        mult = {"US": Decimal("4.0"), "GB": Decimal("3.5"),
                "BD": Decimal("0.5")}.get(country, Decimal("1.5"))
        return (cls.DEFAULT_ECPM * mult).quantize(Decimal("0.0001"))

    @staticmethod
    def validate_mraid_url(url: str) -> bool:
        return url.startswith(("http://", "https://")) and url.endswith(".html")

    @staticmethod
    def build_mraid_wrapper(html_url: str, width: int = 320,
                             height: int = 480) -> str:
        return (
            f'''<iframe src="{html_url}" width="{width}" height="{height}" '''
            f'''frameborder="0" scrolling="no" allowfullscreen></iframe>'''
        )
