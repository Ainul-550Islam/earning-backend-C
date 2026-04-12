"""AD_FORMATS/rewarded_video.py — Rewarded video ad handler."""
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class RewardedVideoConfig:
    min_watch_seconds: int = 15
    full_duration_seconds: int = 30
    reward_on_complete: bool = True
    skip_enabled: bool = False
    mute_on_start: bool = True
    fullscreen: bool = True
    countdown_visible: bool = True


class RewardedVideoHandler:
    """Handles rewarded video — highest eCPM format."""

    DEFAULT_ECPM_USD = Decimal("8.00")
    DEFAULT_REWARD_COINS = Decimal("50.00")

    @classmethod
    def get_config(cls, min_watch: int = 15) -> RewardedVideoConfig:
        return RewardedVideoConfig(min_watch_seconds=min_watch)

    @classmethod
    def calculate_reward(cls, base_coins: Decimal,
                          multiplier: Decimal = Decimal("1.0")) -> Decimal:
        return (base_coins * multiplier).quantize(Decimal("0.01"))

    @classmethod
    def get_ecpm_estimate(cls, country: str = "US") -> Decimal:
        mult = {"US": Decimal("5.0"), "GB": Decimal("4.0"),
                "BD": Decimal("0.6"), "IN": Decimal("0.7")}.get(country, Decimal("1.2"))
        return (cls.DEFAULT_ECPM_USD * mult).quantize(Decimal("0.0001"))

    @classmethod
    def validate_completion(cls, watched_seconds: int,
                             config: RewardedVideoConfig = None) -> bool:
        cfg = config or RewardedVideoConfig()
        return watched_seconds >= cfg.min_watch_seconds

    @staticmethod
    def build_completion_payload(user_id: str, unit_id: str,
                                  coins: Decimal) -> dict:
        return {
            "user_id": user_id, "unit_id": unit_id,
            "coins_earned": str(coins), "format": "rewarded_video",
        }
