"""AD_FORMATS/video_ad.py — Video ad (non-rewarded) format handler."""
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class VideoAdConfig:
    duration_seconds: int = 30
    skip_after_seconds: int = 5
    autoplay: bool = True
    muted_autoplay: bool = True
    controls_visible: bool = False
    fullscreen: bool = False
    vast_version: str = "4.1"
    vpaid_enabled: bool = False


class VideoAdHandler:
    """Handles instream / outstream video ads."""

    INSTREAM_POSITIONS = ["pre_roll", "mid_roll", "post_roll"]
    OUTSTREAM_LAYOUTS  = ["in_feed", "in_article", "sticky"]

    @classmethod
    def get_config(cls, duration: int = 30,
                    skip_after: int = 5) -> VideoAdConfig:
        return VideoAdConfig(duration_seconds=duration, skip_after_seconds=skip_after)

    @classmethod
    def get_ecpm_estimate(cls, position: str = "pre_roll",
                           country: str = "US") -> Decimal:
        pos_mult = {"pre_roll": Decimal("1.5"), "mid_roll": Decimal("1.3"),
                    "post_roll": Decimal("0.8")}.get(position, Decimal("1.0"))
        base = Decimal("5.00")
        tier = {"US": Decimal("3.0"), "GB": Decimal("2.5"),
                "BD": Decimal("0.5")}.get(country, Decimal("1.0"))
        return (base * pos_mult * tier).quantize(Decimal("0.0001"))

    @staticmethod
    def build_vast_wrapper(tag_url: str, version: str = "4.1") -> str:
        return (
            f'''<?xml version="1.0" encoding="UTF-8"?>'''
            f'''<VAST version="{version}">'''
            f'''<Ad><Wrapper><VASTAdTagURI><![CDATA[{tag_url}]]>'''
            f'''</VASTAdTagURI></Wrapper></Ad></VAST>'''
        )
