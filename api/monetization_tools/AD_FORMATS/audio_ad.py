"""AD_FORMATS/audio_ad.py — Audio ad format handler."""
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class AudioAdConfig:
    duration_seconds: int = 15
    skip_after_seconds: int = 0
    autoplay: bool = True
    companion_banner: bool = True
    companion_width: int = 300
    companion_height: int = 250


class AudioAdHandler:
    """Handles audio ads (podcasts, music apps)."""

    DEFAULT_ECPM = Decimal("1.50")

    @classmethod
    def get_config(cls, duration: int = 15) -> AudioAdConfig:
        return AudioAdConfig(duration_seconds=duration)

    @classmethod
    def get_ecpm_estimate(cls, country: str = "US") -> Decimal:
        mult = {"US": Decimal("2.5"), "GB": Decimal("2.0"),
                "BD": Decimal("0.3")}.get(country, Decimal("0.8"))
        return (cls.DEFAULT_ECPM * mult).quantize(Decimal("0.0001"))

    @staticmethod
    def build_daast_tag(asset_url: str, duration: int = 15) -> str:
        return (
            f'''<?xml version="1.0" encoding="UTF-8"?>'''
            f'''<DAAST version="1.0">'''
            f'''<Ad><InLine><Duration>00:00:{duration:02d}</Duration>'''
            f'''<MediaFiles><MediaFile><![CDATA[{asset_url}]]>'''
            f'''</MediaFile></MediaFiles></InLine></Ad></DAAST>'''
        )
