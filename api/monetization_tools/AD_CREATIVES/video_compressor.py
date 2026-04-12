"""AD_CREATIVES/video_compressor.py — Video asset compression config."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class VideoCompressionConfig:
    target_bitrate_kbps: int = 800
    max_file_size_mb: float = 5.0
    target_resolution: str = "720p"    # 480p | 720p | 1080p
    codec: str = "h264"
    container: str = "mp4"
    fps: int = 30
    audio_bitrate_kbps: int = 128


class VideoCompressor:
    """Provides video compression recommendations for ad creatives."""

    RESOLUTION_MAP = {
        "480p":  (854,  480),
        "720p":  (1280, 720),
        "1080p": (1920, 1080),
    }

    @classmethod
    def get_config(cls, ad_format: str = "rewarded_video") -> VideoCompressionConfig:
        if ad_format in ("rewarded_video", "interstitial"):
            return VideoCompressionConfig(target_bitrate_kbps=1200, max_file_size_mb=10.0)
        if ad_format == "banner":
            return VideoCompressionConfig(target_bitrate_kbps=400, max_file_size_mb=2.0)
        return VideoCompressionConfig()

    @classmethod
    def estimated_size_mb(cls, duration_sec: int,
                           bitrate_kbps: int = 800) -> Decimal:
        bits   = bitrate_kbps * 1000 * duration_sec
        mb     = Decimal(bits) / (8 * 1024 * 1024)
        return mb.quantize(Decimal("0.01"))

    @classmethod
    def dimensions(cls, resolution: str = "720p") -> tuple:
        return cls.RESOLUTION_MAP.get(resolution, (1280, 720))
