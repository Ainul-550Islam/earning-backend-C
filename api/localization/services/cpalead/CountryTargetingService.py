# services/cpalead/CountryTargetingService.py
"""CPAlead country-based offer targeting — payment methods, blocks, earning config."""
import logging
from typing import Dict, List
from django.core.cache import cache
logger = logging.getLogger(__name__)

PAYMENT_METHODS = {
    "BD": [
        {"id":"bkash","name":"bKash","type":"mobile_banking","min":200,"currency":"BDT"},
        {"id":"nagad","name":"Nagad","type":"mobile_banking","min":200,"currency":"BDT"},
        {"id":"rocket","name":"Rocket","type":"mobile_banking","min":200,"currency":"BDT"},
        {"id":"bank","name":"Bank Transfer","type":"bank","min":1000,"currency":"BDT"},
        {"id":"paypal","name":"PayPal","type":"digital_wallet","min":5,"currency":"USD"},
    ],
    "IN": [
        {"id":"upi","name":"UPI","type":"upi","min":100,"currency":"INR"},
        {"id":"paytm","name":"Paytm","type":"mobile_wallet","min":100,"currency":"INR"},
        {"id":"bank","name":"NEFT/IMPS","type":"bank","min":500,"currency":"INR"},
        {"id":"paypal","name":"PayPal","type":"digital_wallet","min":1,"currency":"USD"},
    ],
    "PK": [
        {"id":"easypaisa","name":"EasyPaisa","type":"mobile_banking","min":500,"currency":"PKR"},
        {"id":"jazzcash","name":"JazzCash","type":"mobile_banking","min":500,"currency":"PKR"},
        {"id":"paypal","name":"PayPal","type":"digital_wallet","min":5,"currency":"USD"},
    ],
    "NP": [
        {"id":"esewa","name":"eSewa","type":"mobile_wallet","min":200,"currency":"NPR"},
        {"id":"bank","name":"Bank Transfer","type":"bank","min":1000,"currency":"NPR"},
        {"id":"paypal","name":"PayPal","type":"digital_wallet","min":5,"currency":"USD"},
    ],
    "LK": [
        {"id":"bank","name":"Bank Transfer","type":"bank","min":500,"currency":"LKR"},
        {"id":"paypal","name":"PayPal","type":"digital_wallet","min":5,"currency":"USD"},
    ],
    "DEFAULT": [
        {"id":"paypal","name":"PayPal","type":"digital_wallet","min":5,"currency":"USD"},
        {"id":"payoneer","name":"Payoneer","type":"digital_wallet","min":20,"currency":"USD"},
        {"id":"wise","name":"Wise","type":"digital_wallet","min":10,"currency":"USD"},
        {"id":"crypto","name":"USDT/Crypto","type":"cryptocurrency","min":10,"currency":"USDT"},
    ],
}

COUNTRY_EARNING_CONFIG = {
    "BD": {"currency":"BDT","min_withdrawal":200,"max_daily":50000,"tax_rate":0},
    "IN": {"currency":"INR","min_withdrawal":100,"max_daily":10000,"tax_rate":0.18},
    "PK": {"currency":"PKR","min_withdrawal":500,"max_daily":50000,"tax_rate":0},
    "NP": {"currency":"NPR","min_withdrawal":200,"max_daily":20000,"tax_rate":0},
    "LK": {"currency":"LKR","min_withdrawal":500,"max_daily":50000,"tax_rate":0},
    "DEFAULT": {"currency":"USD","min_withdrawal":5,"max_daily":1000,"tax_rate":0},
}


class CountryTargetingService:
    """Country-based offer targeting + payment method localization."""

    def is_offer_available(self, offer_id: int, country_code: str) -> bool:
        cache_key = f"offer_avail_{offer_id}_{country_code}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from ..models.region import ContentRegion
            region = ContentRegion.get_region_for_country(country_code)
            flags = region.feature_flags if region else {}
            result = offer_id not in (flags.get("blocked_offers", []) if flags else [])
            cache.set(cache_key, result, 3600)
            return result
        except Exception as e:
            logger.error(f"is_offer_available failed: {e}")
            return True

    def get_payment_methods(self, country_code: str) -> List[Dict]:
        """Country-এর available payment methods।"""
        country_methods = PAYMENT_METHODS.get(country_code.upper(), [])
        default_methods = PAYMENT_METHODS["DEFAULT"]
        existing_ids = {m["id"] for m in country_methods}
        combined = country_methods + [m for m in default_methods if m["id"] not in existing_ids]
        return combined

    def get_earning_config(self, country_code: str) -> Dict:
        """Country-specific earning + withdrawal config।"""
        return COUNTRY_EARNING_CONFIG.get(country_code.upper(), COUNTRY_EARNING_CONFIG["DEFAULT"])

    def get_localized_offer_content(self, offer_id: int, language_code: str) -> Dict:
        """Offer-এর localized content।"""
        try:
            from ..models.content import LocalizedContent
            fields = LocalizedContent.objects.filter(
                content_type="offer", object_id=str(offer_id),
                language__code=language_code, is_approved=True,
            ).values("field_name", "value")
            return {f["field_name"]: f["value"] for f in fields}
        except Exception as e:
            logger.error(f"get_localized_offer_content failed: {e}")
            return {}

    def get_gdpr_requirements(self, country_code: str) -> Dict:
        """GDPR/privacy requirements for country।"""
        EU = {"AT","BE","BG","CY","CZ","DE","DK","EE","ES","FI","FR","GR",
              "HR","HU","IE","IT","LT","LU","LV","MT","NL","PL","PT","RO","SE","SI","SK"}
        is_eu = country_code.upper() in EU
        return {
            "requires_gdpr": is_eu,
            "requires_cookie_consent": is_eu,
            "data_retention_days": 365 if is_eu else 730,
            "right_to_erasure": is_eu,
        }
