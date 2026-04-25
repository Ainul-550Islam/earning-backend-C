# api/wallet/config.py
"""
Runtime wallet configuration.
Fee rates, limits, gateway settings loaded from DB or settings.py.
Cached for performance.
"""
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger("wallet.config")

CONFIG_CACHE_TTL = 300  # 5 minutes


class WalletConfig:
    """Runtime configuration with DB override capability."""

    _defaults = {
        "MIN_WITHDRAWAL":          "50.00",
        "MAX_WITHDRAWAL":          "100000.00",
        "MAX_DAILY_WITHDRAWAL":    "50000.00",
        "DEFAULT_FEE_PERCENT":     "2.00",
        "CRYPTO_FEE_PERCENT":      "1.00",
        "INSTANT_FEE_PERCENT":     "1.50",
        "MIN_FEE_BDT":             "5.00",
        "NEW_PUBLISHER_HOLD_DAYS": "30",
        "FRAUD_AUTO_BLOCK_SCORE":  "85",
        "VELOCITY_MAX_PER_HOUR":   "10",
        "SECURITY_LOCK_HOURS":     "24",
        "IDEMPOTENCY_TTL":         "86400",
        "POINTS_PER_DOLLAR":       "1000",
        "DAILY_EARN_CAP":          "10000.00",
        "REFERRAL_L1_RATE":        "0.10",
        "REFERRAL_L2_RATE":        "0.05",
        "REFERRAL_L3_RATE":        "0.02",
        "REFERRAL_MONTHS":         "6",
        "GATEWAY_ENABLED_BKASH":   "true",
        "GATEWAY_ENABLED_NAGAD":   "true",
        "GATEWAY_ENABLED_USDT":    "true",
        "GATEWAY_ENABLED_PAYPAL":  "false",
        "GATEWAY_ENABLED_STRIPE":  "false",
    }

    @classmethod
    def get(cls, key: str, default=None):
        """Get config value. Checks DB first, then settings, then defaults."""
        cache_key = f"wallet_config:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Try DB
        try:
            from .models.config import WalletConfigModel
            cfg = WalletConfigModel.objects.filter(key=key, is_active=True).first()
            if cfg:
                value = cfg.value
                cache.set(cache_key, value, CONFIG_CACHE_TTL)
                return value
        except Exception:
            pass

        # Try settings
        settings_value = getattr(settings, f"WALLET_{key}", None)
        if settings_value is not None:
            return str(settings_value)

        # Default
        return cls._defaults.get(key, default)

    @classmethod
    def get_decimal(cls, key: str, default: Decimal = Decimal("0")) -> Decimal:
        val = cls.get(key)
        try:
            return Decimal(str(val)) if val else default
        except Exception:
            return default

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        val = cls.get(key)
        try:
            return int(val) if val else default
        except Exception:
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        val = cls.get(key, "")
        return str(val).lower() in ("true", "1", "yes", "on")

    @classmethod
    def set(cls, key: str, value: str, description: str = ""):
        """Update a config value (admin use)."""
        try:
            from .models.config import WalletConfigModel
            cfg, _ = WalletConfigModel.objects.update_or_create(
                key=key, defaults={"value": str(value), "description": description}
            )
            cache.delete(f"wallet_config:{key}")
            logger.info(f"Config updated: {key}={value}")
            return cfg
        except Exception as e:
            logger.error(f"Config set failed: {e}")
            return None

    @classmethod
    def all(cls) -> dict:
        """Get all current config values."""
        result = {}
        for key in cls._defaults:
            result[key] = cls.get(key)
        return result
