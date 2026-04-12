# api/publisher_tools/config.py
"""Publisher Tools — Configuration management."""
from django.conf import settings
from .constants import (
    DEFAULT_REVENUE_SHARE, DEFAULT_CURRENCY, MIN_PAYOUT_THRESHOLDS,
    PROCESSING_FEES, CACHE_TTL_MEDIUM
)


class PublisherToolsConfig:
    """
    Publisher Tools global configuration।
    settings.py থেকে PUBLISHER_TOOLS_CONFIG dict পড়ে।
    """

    _config = None

    @classmethod
    def get(cls) -> dict:
        if cls._config is None:
            cls._config = {
                # Revenue
                'default_revenue_share': getattr(settings, 'PT_DEFAULT_REVENUE_SHARE', DEFAULT_REVENUE_SHARE),
                'min_revenue_share':     getattr(settings, 'PT_MIN_REVENUE_SHARE', 30.0),
                'max_revenue_share':     getattr(settings, 'PT_MAX_REVENUE_SHARE', 95.0),
                # Currency
                'default_currency':      getattr(settings, 'PT_DEFAULT_CURRENCY', DEFAULT_CURRENCY),
                # Payout
                'min_payout_thresholds': getattr(settings, 'PT_MIN_PAYOUT_THRESHOLDS', MIN_PAYOUT_THRESHOLDS),
                'processing_fees':       getattr(settings, 'PT_PROCESSING_FEES', PROCESSING_FEES),
                # Site
                'ads_txt_check_interval':getattr(settings, 'PT_ADS_TXT_CHECK_INTERVAL', 24),
                'max_sites_per_publisher':getattr(settings, 'PT_MAX_SITES_PER_PUBLISHER', 50),
                'max_apps_per_publisher': getattr(settings, 'PT_MAX_APPS_PER_PUBLISHER', 20),
                'max_ad_units_per_site':  getattr(settings, 'PT_MAX_AD_UNITS_PER_SITE', 30),
                # Fraud
                'fraud_score_block_threshold': getattr(settings, 'PT_FRAUD_SCORE_BLOCK', 80),
                'max_ivt_percentage':         getattr(settings, 'PT_MAX_IVT_PCT', 20.0),
                'critical_ivt_threshold':     getattr(settings, 'PT_CRITICAL_IVT_PCT', 40.0),
                # A/B Testing
                'min_statistical_confidence': getattr(settings, 'PT_MIN_CONFIDENCE', 95.0),
                'min_test_duration_days':     getattr(settings, 'PT_MIN_TEST_DAYS', 7),
                # CDN
                'cdn_base_url':              getattr(settings, 'PT_CDN_BASE_URL', 'https://cdn.publishertools.io'),
                'ad_tag_cdn_url':            getattr(settings, 'PT_AD_TAG_CDN', 'https://cdn.publishertools.io/pt.js'),
                # Platform
                'platform_name':             getattr(settings, 'PT_PLATFORM_NAME', 'Publisher Tools'),
                'platform_domain':           getattr(settings, 'PT_PLATFORM_DOMAIN', 'publishertools.io'),
                'support_email':             getattr(settings, 'PT_SUPPORT_EMAIL', 'support@publishertools.io'),
                # Cache
                'cache_ttl':                 getattr(settings, 'PT_CACHE_TTL', CACHE_TTL_MEDIUM),
                # Webhooks
                'webhook_timeout':           getattr(settings, 'PT_WEBHOOK_TIMEOUT', 10),
                'webhook_max_retries':       getattr(settings, 'PT_WEBHOOK_MAX_RETRIES', 3),
                # Features
                'feature_kyc_required':      getattr(settings, 'PT_FEATURE_KYC_REQUIRED', False),
                'feature_header_bidding':    getattr(settings, 'PT_FEATURE_HEADER_BIDDING', True),
                'feature_ab_testing':        getattr(settings, 'PT_FEATURE_AB_TESTING', True),
                'feature_white_label':       getattr(settings, 'PT_FEATURE_WHITE_LABEL', False),
            }
        return cls._config

    @classmethod
    def get_value(cls, key: str, default=None):
        return cls.get().get(key, default)

    @classmethod
    def reset(cls):
        cls._config = None


def get_pt_config() -> dict:
    """Shortcut to get Publisher Tools config."""
    return PublisherToolsConfig.get()


def is_feature_enabled(feature_name: str) -> bool:
    """Feature flag check।"""
    config = PublisherToolsConfig.get()
    return config.get(f'feature_{feature_name}', False)
