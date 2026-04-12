# services/cpalead/ContentRegionService.py
"""
CPAlead ContentRegion Service — country-based feature flags।
কোন দেশে কোন feature দেখাবে সেটা control করে।
- Offer eligibility per country
- Age verification requirements
- GDPR consent requirements
- Payment methods per region
- Minimum payout per region
"""
import logging
from typing import Dict, List, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)
CACHE_TTL = 3600


class ContentRegionService:
    """
    Country → Region → Feature Flags।
    CPAlead এ: BD users দেখে bKash/Nagad, US users দেখে PayPal/Stripe।
    """

    # Built-in region definitions
    REGIONS = {
        'south_asia': {
            'countries': ['BD', 'IN', 'PK', 'NP', 'LK', 'MM', 'KH', 'VN', 'TH', 'ID', 'MY', 'PH'],
            'payment_methods': ['bkash', 'nagad', 'upi', 'jazzcash', 'easypaisa', 'payoneer'],
            'min_payout_usd': 5.0,
            'age_required': 18,
            'currency': 'USD',  # Payouts in USD, display in local
            'features': {
                'survey_offers': True, 'app_installs': True, 'video_offers': True,
                'casino_offers': False,  # Bangladesh regulations
                'crypto_payout': False,
            },
        },
        'middle_east': {
            'countries': ['SA', 'AE', 'EG', 'IQ', 'IR', 'KW', 'QA', 'BH', 'JO', 'LB'],
            'payment_methods': ['paypal', 'payoneer', 'wise'],
            'min_payout_usd': 10.0,
            'age_required': 18,
            'rtl': True,
            'features': {
                'survey_offers': True, 'app_installs': True, 'video_offers': True,
                'casino_offers': False,  # Islamic finance rules
                'crypto_payout': True,
            },
        },
        'europe': {
            'countries': ['GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'NO', 'DK', 'FI',
                         'PL', 'AT', 'BE', 'CH', 'PT', 'GR', 'CZ', 'HU', 'RO'],
            'payment_methods': ['paypal', 'stripe', 'wise', 'bank_transfer'],
            'min_payout_usd': 10.0,
            'age_required': 18,
            'requires_gdpr': True,
            'features': {
                'survey_offers': True, 'app_installs': True, 'video_offers': True,
                'casino_offers': True, 'crypto_payout': True,
            },
        },
        'north_america': {
            'countries': ['US', 'CA'],
            'payment_methods': ['paypal', 'check', 'bank_transfer', 'crypto'],
            'min_payout_usd': 1.0,
            'age_required': 18,
            'features': {
                'survey_offers': True, 'app_installs': True, 'video_offers': True,
                'casino_offers': True, 'crypto_payout': True,
            },
        },
        'africa': {
            'countries': ['NG', 'GH', 'KE', 'ZA', 'TZ', 'UG', 'ET', 'CM', 'CI', 'SN'],
            'payment_methods': ['payoneer', 'mobile_money', 'crypto'],
            'min_payout_usd': 5.0,
            'age_required': 18,
            'features': {
                'survey_offers': True, 'app_installs': True, 'video_offers': True,
                'casino_offers': False, 'crypto_payout': True,
            },
        },
        'default': {
            'countries': [],
            'payment_methods': ['paypal', 'payoneer'],
            'min_payout_usd': 10.0,
            'age_required': 18,
            'features': {
                'survey_offers': True, 'app_installs': True, 'video_offers': False,
                'casino_offers': False, 'crypto_payout': False,
            },
        },
    }

    def get_region_for_country(self, country_code: str) -> Dict:
        """Country code থেকে region info পাওয়া"""
        cache_key = f"region_{country_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        country_upper = (country_code or '').upper()

        # Check DB first
        try:
            from ...models.region import ContentRegion
            region_obj = ContentRegion.objects.filter(
                country_codes__contains=[country_upper]
            ).select_related('default_language', 'default_currency').first()

            if region_obj:
                result = {
                    'name': region_obj.name,
                    'slug': region_obj.slug,
                    'country': country_upper,
                    'default_language': region_obj.default_language.code if region_obj.default_language else 'en',
                    'default_currency': region_obj.default_currency.code if region_obj.default_currency else 'USD',
                    'requires_gdpr': region_obj.requires_gdpr,
                    'requires_age_verification': region_obj.requires_age_verification,
                    'min_age': region_obj.min_age_requirement,
                    'feature_flags': region_obj.feature_flags or {},
                    'payment_methods': region_obj.feature_flags.get('payment_methods', []) if region_obj.feature_flags else [],
                    'min_payout_usd': float(region_obj.min_payout_usd) if hasattr(region_obj, 'min_payout_usd') else 5.0,
                    'source': 'db',
                }
                cache.set(cache_key, result, CACHE_TTL)
                return result
        except Exception:
            pass

        # Fall back to built-in definitions
        for region_name, region_data in self.REGIONS.items():
            if country_upper in region_data['countries']:
                result = {
                    'name': region_name.replace('_', ' ').title(),
                    'slug': region_name,
                    'country': country_upper,
                    'default_language': self._get_country_language(country_upper),
                    'default_currency': self._get_country_currency(country_upper),
                    'requires_gdpr': region_data.get('requires_gdpr', False),
                    'requires_age_verification': True,
                    'min_age': region_data.get('age_required', 18),
                    'feature_flags': region_data.get('features', {}),
                    'payment_methods': region_data.get('payment_methods', []),
                    'min_payout_usd': region_data.get('min_payout_usd', 10.0),
                    'is_rtl': region_data.get('rtl', False),
                    'source': 'builtin',
                }
                cache.set(cache_key, result, CACHE_TTL)
                return result

        # Default region
        result = {
            **self.REGIONS['default'],
            'name': 'Default', 'slug': 'default', 'country': country_upper,
            'default_language': 'en', 'default_currency': 'USD',
            'requires_gdpr': False, 'requires_age_verification': True,
            'min_age': 18, 'source': 'default',
        }
        return result

    def is_feature_enabled(self, country_code: str, feature: str) -> bool:
        """Country-তে feature enabled কিনা"""
        region = self.get_region_for_country(country_code)
        flags = region.get('feature_flags') or region.get('features', {})
        return bool(flags.get(feature, False))

    def get_payment_methods(self, country_code: str) -> List[str]:
        """Country-র available payment methods"""
        region = self.get_region_for_country(country_code)
        return region.get('payment_methods', ['paypal'])

    def get_min_payout(self, country_code: str) -> float:
        """Country-র minimum payout amount (USD)"""
        region = self.get_region_for_country(country_code)
        return region.get('min_payout_usd', 10.0)

    def requires_gdpr(self, country_code: str) -> bool:
        """Country GDPR require করে কিনা (EU/EEA)"""
        EU_EEA = {
            'AT','BE','BG','CY','CZ','DE','DK','EE','ES','FI','FR','GR','HR','HU',
            'IE','IT','LT','LU','LV','MT','NL','PL','PT','RO','SE','SI','SK',
            'IS','LI','NO','GB',  # Post-Brexit UK still enforces similar rules
        }
        return (country_code or '').upper() in EU_EEA

    def get_gdpr_consent_text(self, country_code: str, language_code: str = 'en') -> str:
        """GDPR consent text for country"""
        try:
            from ...models.core import Translation
            key = 'gdpr.consent_text'
            trans = Translation.objects.filter(
                key__key=key, language__code=language_code, is_approved=True
            ).first()
            if trans:
                return trans.value
        except Exception:
            pass
        return ("By continuing, you agree to our Terms of Service and Privacy Policy. "
                "Your data is processed in accordance with GDPR regulations.")

    def get_localized_offer_config(self, country_code: str) -> Dict:
        """Offer display config for country — CPAlead offer targeting"""
        region = self.get_region_for_country(country_code)
        return {
            'country': country_code,
            'region': region.get('name', 'Unknown'),
            'language': region.get('default_language', 'en'),
            'currency': region.get('default_currency', 'USD'),
            'is_rtl': region.get('is_rtl', False),
            'payment_methods': region.get('payment_methods', []),
            'min_payout_usd': region.get('min_payout_usd', 10.0),
            'requires_gdpr': region.get('requires_gdpr', False),
            'min_age': region.get('min_age', 18),
            'features': region.get('feature_flags', {}),
            'show_casino_offers': region.get('feature_flags', {}).get('casino_offers', False),
            'show_crypto_payout': region.get('feature_flags', {}).get('crypto_payout', False),
        }

    def get_all_regions_summary(self) -> List[Dict]:
        """All regions summary — admin dashboard-এর জন্য"""
        cache_key = 'all_regions_summary'
        cached = cache.get(cache_key)
        if cached:
            return cached
        result = []
        try:
            from ...models.region import ContentRegion
            for region in ContentRegion.objects.filter(is_active=True).order_by('name'):
                result.append({
                    'name': region.name, 'slug': region.slug,
                    'country_count': len(region.country_codes or []),
                    'features': region.feature_flags,
                    'requires_gdpr': region.requires_gdpr,
                })
        except Exception:
            # Fallback to built-in
            for name, data in self.REGIONS.items():
                result.append({
                    'name': name.replace('_', ' ').title(), 'slug': name,
                    'country_count': len(data['countries']),
                    'features': data.get('features', {}),
                    'requires_gdpr': data.get('requires_gdpr', False),
                })
        cache.set(cache_key, result, CACHE_TTL)
        return result

    def _get_country_language(self, cc: str) -> str:
        LANG_MAP = {
            'BD': 'bn', 'IN': 'hi', 'PK': 'ur', 'NP': 'ne', 'LK': 'si',
            'SA': 'ar', 'AE': 'ar', 'EG': 'ar', 'IQ': 'ar', 'DE': 'de',
            'FR': 'fr', 'ES': 'es', 'CN': 'zh', 'JP': 'ja', 'KR': 'ko',
            'ID': 'id', 'MY': 'ms', 'TH': 'th', 'TR': 'tr', 'NG': 'en',
            'GH': 'en', 'KE': 'sw', 'US': 'en', 'GB': 'en', 'CA': 'en',
        }
        return LANG_MAP.get(cc, 'en')

    def _get_country_currency(self, cc: str) -> str:
        CURR_MAP = {
            'BD': 'BDT', 'IN': 'INR', 'PK': 'PKR', 'NP': 'NPR', 'LK': 'LKR',
            'SA': 'SAR', 'AE': 'AED', 'EG': 'EGP', 'DE': 'EUR', 'FR': 'EUR',
            'GB': 'GBP', 'ID': 'IDR', 'MY': 'MYR', 'TR': 'TRY', 'NG': 'NGN',
            'US': 'USD', 'CA': 'CAD', 'AU': 'AUD', 'JP': 'JPY', 'KR': 'KRW',
        }
        return CURR_MAP.get(cc, 'USD')
