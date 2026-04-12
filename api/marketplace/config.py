"""
marketplace/config.py — Runtime configuration helpers
"""

from django.conf import settings


def get_marketplace_setting(key: str, default=None):
    """Read MARKETPLACE_* settings from Django settings."""
    mp_settings = getattr(settings, "MARKETPLACE", {})
    return mp_settings.get(key, default)


# Defaults (override in settings.py under MARKETPLACE = {...})
COMMISSION_RATE       = get_marketplace_setting("COMMISSION_RATE", 10.0)
FREE_SHIPPING_ABOVE   = get_marketplace_setting("FREE_SHIPPING_ABOVE", 500)
ESCROW_RELEASE_DAYS   = get_marketplace_setting("ESCROW_RELEASE_DAYS", 7)
VAT_RATE              = get_marketplace_setting("VAT_RATE", 0.15)
MIN_PAYOUT            = get_marketplace_setting("MIN_PAYOUT", 100)
CURRENCY              = get_marketplace_setting("CURRENCY", "BDT")
ENABLE_COD            = get_marketplace_setting("ENABLE_COD", True)
ENABLE_FLASH_SALE     = get_marketplace_setting("ENABLE_FLASH_SALE", True)
MAX_CART_ITEMS        = get_marketplace_setting("MAX_CART_ITEMS", 100)
REVIEW_WINDOW_DAYS    = get_marketplace_setting("REVIEW_WINDOW_DAYS", 30)
