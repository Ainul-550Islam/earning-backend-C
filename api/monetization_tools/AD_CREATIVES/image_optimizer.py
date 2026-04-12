"""AD_CREATIVES/image_optimizer.py — Image asset optimization for ads."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ImageOptimizationConfig:
    max_width: int = 1200
    max_height: int = 628
    quality: int = 85               # 1-100
    format: str = "webp"            # webp | jpeg | png
    max_size_kb: int = 150
    strip_metadata: bool = True
    progressive: bool = True


class ImageOptimizer:
    """Validates and provides optimization configs for ad image assets."""

    FORMAT_ECPM_BONUS = {"webp": Decimal("0.10"), "jpeg": Decimal("0"), "png": Decimal("0.05")}

    @classmethod
    def get_config(cls, ad_format: str = "banner") -> ImageOptimizationConfig:
        if ad_format == "native":
            return ImageOptimizationConfig(max_width=1200, max_height=628, quality=90)
        if ad_format == "banner":
            return ImageOptimizationConfig(max_width=970, max_height=250, quality=85)
        return ImageOptimizationConfig()

    @classmethod
    def validate_dimensions(cls, width: int, height: int,
                             config: ImageOptimizationConfig = None) -> list:
        cfg = config or ImageOptimizationConfig()
        errors = []
        if width > cfg.max_width:
            errors.append(f"Width {width}px exceeds max {cfg.max_width}px.")
        if height > cfg.max_height:
            errors.append(f"Height {height}px exceeds max {cfg.max_height}px.")
        return errors

    @classmethod
    def validate_size_kb(cls, size_kb: int, config: ImageOptimizationConfig = None) -> bool:
        cfg = config or ImageOptimizationConfig()
        return size_kb <= cfg.max_size_kb

    @classmethod
    def format_ecpm_bonus(cls, fmt: str) -> Decimal:
        return cls.FORMAT_ECPM_BONUS.get(fmt.lower(), Decimal("0"))
