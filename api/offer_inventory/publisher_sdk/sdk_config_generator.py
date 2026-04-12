# api/offer_inventory/publisher_sdk/sdk_config_generator.py
"""SDK Config Generator — Generate platform-specific SDK configurations."""
import logging
import json
from django.conf import settings

logger = logging.getLogger(__name__)


class SDKConfigGenerator:
    """Generate SDK configuration for Android, iOS, Unity, and Web."""

    @staticmethod
    def for_android(publisher_id: str, app_id: str,
                     placement_id: str = '') -> dict:
        """Android SDK configuration."""
        site_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return {
            'sdk_version'   : '2.0.0',
            'platform'      : 'android',
            'publisher_id'  : publisher_id,
            'app_id'        : app_id,
            'placement_id'  : placement_id,
            'endpoint'      : f'{site_url}/api/offer-inventory/sdk/',
            'offerwall_url' : f'{site_url}/api/offer-inventory/sdk/offers/',
            'postback_url'  : f'{site_url}/api/offer-inventory/postback/',
            'timeout_ms'    : 10000,
            'currency_name' : 'Coins',
            'currency_rate' : 100,
            'min_android_version': '5.0',
            'features'      : {
                'offerwall'  : True,
                'rewarded_video': False,
                'banner'     : True,
                'interstitial': False,
            },
            'initialization': {
                'java': (
                    'OfferInventorySDK.initialize(context, '
                    f'"{publisher_id}", "{app_id}", new SDKCallback() {{}});'
                ),
                'kotlin': (
                    'OfferInventorySDK.initialize(context, '
                    f'"{publisher_id}", "{app_id}")'
                ),
            },
        }

    @staticmethod
    def for_ios(publisher_id: str, app_id: str,
                 placement_id: str = '') -> dict:
        """iOS SDK configuration."""
        site_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return {
            'sdk_version'   : '2.0.0',
            'platform'      : 'ios',
            'publisher_id'  : publisher_id,
            'app_id'        : app_id,
            'placement_id'  : placement_id,
            'endpoint'      : f'{site_url}/api/offer-inventory/sdk/',
            'min_ios_version': '12.0',
            'features'      : {
                'offerwall'  : True,
                'rewarded_video': False,
            },
            'initialization': {
                'swift'     : (
                    f'OfferInventorySDK.shared.initialize(publisherId: "{publisher_id}", '
                    f'appId: "{app_id}")'
                ),
                'objc'      : (
                    f'[OfferInventorySDK.shared initializeWithPublisherId:@"{publisher_id}" '
                    f'appId:@"{app_id}"];'
                ),
            },
        }

    @staticmethod
    def for_unity(publisher_id: str, app_id: str) -> dict:
        """Unity (mobile game) SDK configuration."""
        site_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return {
            'sdk_version'     : '2.0.0',
            'platform'        : 'unity',
            'publisher_id'    : publisher_id,
            'app_id'          : app_id,
            'endpoint'        : f'{site_url}/api/offer-inventory/sdk/',
            'min_unity_version': '2019.4',
            'initialization'  : {
                'csharp': (
                    'OfferInventorySDK.Initialize('
                    f'"{publisher_id}", "{app_id}", OnInitialized);'
                ),
            },
            'showOfferwall'   : 'OfferInventorySDK.ShowOfferwall(placementId, OnOfferwallClosed);',
        }

    @staticmethod
    def for_web(publisher_id: str, app_id: str) -> dict:
        """Web/JavaScript SDK configuration."""
        site_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return {
            'sdk_version'  : '2.0.0',
            'platform'     : 'web',
            'publisher_id' : publisher_id,
            'app_id'       : app_id,
            'script_tag'   : f'<script src="{site_url}/static/sdk/offer-inventory-sdk-v2.min.js"></script>',
            'initialization': f'OfferInventorySDK.init("{publisher_id}", "{app_id}");',
            'show_offerwall': 'OfferInventorySDK.showOfferwall();',
        }

    @staticmethod
    def generate_integration_guide(platform: str, publisher_id: str,
                                    app_id: str) -> str:
        """Generate step-by-step integration guide."""
        configs = {
            'android': SDKConfigGenerator.for_android,
            'ios'    : SDKConfigGenerator.for_ios,
            'unity'  : SDKConfigGenerator.for_unity,
            'web'    : SDKConfigGenerator.for_web,
        }
        fn = configs.get(platform)
        if not fn:
            return f'Unsupported platform: {platform}'
        config = fn(publisher_id, app_id)
        return json.dumps(config, indent=2)
