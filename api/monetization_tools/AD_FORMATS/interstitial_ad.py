"""AD_FORMATS/interstitial_ad.py — Interstitial (fullscreen) ad handler."""
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class InterstitialConfig:
    display_after_seconds: int = 0
    close_button_delay_sec: int = 5
    skip_enabled: bool = True
    skip_after_sec: int = 3
    animation: str = "fade"         # fade | slide | zoom
    background_overlay: str = "#000000CC"
    z_index: int = 9999
    frequency_cap_per_session: int = 2
    min_interval_seconds: int = 60


class InterstitialAdHandler:
    """Handles interstitial ad display logic, frequency capping, and skip."""

    DEFAULT_ECPM_USD = Decimal("3.50")

    TRIGGER_POINTS = [
        "app_open", "level_complete", "offer_complete",
        "screen_transition", "before_reward", "after_reward",
    ]

    @classmethod
    def get_config(cls, skip_after: int = 5,
                    freq_cap: int = 2) -> InterstitialConfig:
        return InterstitialConfig(
            skip_after_sec=skip_after,
            frequency_cap_per_session=freq_cap,
        )

    @classmethod
    def should_show(cls, session_count: int, last_shown_sec_ago: int,
                     config: InterstitialConfig = None) -> bool:
        cfg = config or InterstitialConfig()
        if session_count >= cfg.frequency_cap_per_session:
            return False
        if last_shown_sec_ago < cfg.min_interval_seconds:
            return False
        return True

    @classmethod
    def get_ecpm_estimate(cls, country: str = "US") -> Decimal:
        mult = {"US": Decimal("4.0"), "GB": Decimal("3.2"),
                "BD": Decimal("0.5"), "IN": Decimal("0.6")}.get(country, Decimal("1.0"))
        return (cls.DEFAULT_ECPM_USD * mult).quantize(Decimal("0.0001"))

    @staticmethod
    def build_close_timer(delay_sec: int) -> dict:
        return {"type": "countdown", "seconds": delay_sec, "label": "Close ad"}
