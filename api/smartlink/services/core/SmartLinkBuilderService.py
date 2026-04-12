import logging
from django.db import transaction
from ...models import SmartLink, OfferPool, OfferPoolEntry, TargetingRule, SmartLinkFallback, SmartLinkRotation
from .SmartLinkService import SmartLinkService
from ...exceptions import TargetingConfigError
from ...validators import validate_redirect_url

logger = logging.getLogger('smartlink.builder')


class SmartLinkBuilderService:
    """
    Builder pattern service: create a SmartLink with all rules,
    pool entries, fallback, and rotation config in a single transaction.
    Used by the API create endpoint and management commands.
    """

    def __init__(self):
        self.smartlink_service = SmartLinkService()

    @transaction.atomic
    def build(self, publisher, config: dict) -> SmartLink:
        """
        Build a fully configured SmartLink from a config dict.

        Config structure:
        {
            'name': str,
            'slug': str (optional),
            'type': str,
            'rotation_method': str,
            'offers': [{'offer_id': int, 'weight': int, 'cap_per_day': int}, ...],
            'fallback_url': str (optional),
            'targeting': {
                'geo': {'mode': 'whitelist', 'countries': ['US', 'GB']},
                'device': {'mode': 'whitelist', 'device_types': ['mobile']},
                'os': {'mode': 'whitelist', 'os_types': ['android']},
                'time': {'days_of_week': [0,1,2,3,4], 'start_hour': 9, 'end_hour': 17},
                'isp': {'mode': 'whitelist', 'isps': ['Grameenphone']},
                'language': {'mode': 'whitelist', 'languages': ['en', 'bn']},
            },
            'rotation': {
                'auto_optimize_epc': True,
                'optimization_interval_minutes': 30,
            },
        }
        """
        # 1. Create base SmartLink
        smartlink = self.smartlink_service.create(publisher, config)

        # 2. Create OfferPool
        pool = OfferPool.objects.create(
            smartlink=smartlink,
            name=f"Pool: {smartlink.slug}",
        )

        # 3. Add offers to pool
        for offer_config in config.get('offers', []):
            self._add_offer_to_pool(pool, offer_config)

        # 4. Create targeting rules
        targeting_config = config.get('targeting', {})
        if targeting_config:
            self._setup_targeting(smartlink, targeting_config)

        # 5. Setup fallback
        fallback_url = config.get('fallback_url')
        if fallback_url:
            validate_redirect_url(fallback_url)
            SmartLinkFallback.objects.create(
                smartlink=smartlink,
                url=fallback_url,
            )

        # 6. Setup rotation config
        rotation_config = config.get('rotation', {})
        SmartLinkRotation.objects.create(
            smartlink=smartlink,
            method=config.get('rotation_method', 'weighted'),
            auto_optimize_epc=rotation_config.get('auto_optimize_epc', False),
            optimization_interval_minutes=rotation_config.get('optimization_interval_minutes', 30),
        )

        logger.info(f"SmartLink built: [{smartlink.slug}] with {pool.entries.count()} offers")
        return smartlink

    def _add_offer_to_pool(self, pool: OfferPool, offer_config: dict):
        """Add a single offer entry to the pool."""
        try:
            from api.offer_inventory.models import Offer
            offer = Offer.objects.get(pk=offer_config['offer_id'])
            OfferPoolEntry.objects.create(
                pool=pool,
                offer=offer,
                weight=offer_config.get('weight', 100),
                priority=offer_config.get('priority', 0),
                cap_per_day=offer_config.get('cap_per_day'),
                cap_per_month=offer_config.get('cap_per_month'),
                epc_override=offer_config.get('epc_override'),
            )
        except Exception as e:
            logger.error(f"Failed to add offer {offer_config.get('offer_id')} to pool: {e}")

    def _setup_targeting(self, smartlink: SmartLink, targeting_config: dict):
        """Create all targeting sub-models for the SmartLink."""
        rule = TargetingRule.objects.create(
            smartlink=smartlink,
            logic=targeting_config.get('logic', 'AND'),
        )

        if 'geo' in targeting_config:
            from ...models import GeoTargeting
            geo = targeting_config['geo']
            GeoTargeting.objects.create(
                rule=rule,
                mode=geo.get('mode', 'whitelist'),
                countries=geo.get('countries', []),
                regions=geo.get('regions', []),
                cities=geo.get('cities', []),
            )

        if 'device' in targeting_config:
            from ...models import DeviceTargeting
            dev = targeting_config['device']
            DeviceTargeting.objects.create(
                rule=rule,
                mode=dev.get('mode', 'whitelist'),
                device_types=dev.get('device_types', []),
            )

        if 'os' in targeting_config:
            from ...models import OSTargeting
            os_cfg = targeting_config['os']
            OSTargeting.objects.create(
                rule=rule,
                mode=os_cfg.get('mode', 'whitelist'),
                os_types=os_cfg.get('os_types', []),
            )

        if 'time' in targeting_config:
            from ...models import TimeTargeting
            t = targeting_config['time']
            TimeTargeting.objects.create(
                rule=rule,
                days_of_week=t.get('days_of_week', []),
                start_hour=t.get('start_hour', 0),
                end_hour=t.get('end_hour', 23),
                timezone_name=t.get('timezone_name', 'UTC'),
            )

        if 'isp' in targeting_config:
            from ...models import ISPTargeting
            isp = targeting_config['isp']
            ISPTargeting.objects.create(
                rule=rule,
                mode=isp.get('mode', 'whitelist'),
                isps=isp.get('isps', []),
                asns=isp.get('asns', []),
            )

        if 'language' in targeting_config:
            from ...models import LanguageTargeting
            lang = targeting_config['language']
            LanguageTargeting.objects.create(
                rule=rule,
                mode=lang.get('mode', 'whitelist'),
                languages=lang.get('languages', []),
            )
