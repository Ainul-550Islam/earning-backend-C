import logging
from django.core.cache import cache
from ...models import SmartLink, OfferPoolEntry
from ...constants import CACHE_TTL_TARGETING
from .GeoTargetingService import GeoTargetingService
from .DeviceTargetingService import DeviceTargetingService
from .OSTargetingService import OSTargetingService
from .TimeTargetingService import TimeTargetingService
from .ISPTargetingService import ISPTargetingService
from .LanguageTargetingService import LanguageTargetingService
from .TargetingRuleEvaluator import TargetingRuleEvaluator

logger = logging.getLogger('smartlink.targeting')


class TargetingEngine:
    """
    Main targeting evaluator.
    Given a SmartLink and request context, returns the list of
    eligible OfferPoolEntry objects that pass all targeting rules.
    """

    def __init__(self):
        self.geo = GeoTargetingService()
        self.device = DeviceTargetingService()
        self.os = OSTargetingService()
        self.time = TimeTargetingService()
        self.isp = ISPTargetingService()
        self.language = LanguageTargetingService()
        self.evaluator = TargetingRuleEvaluator()

    def evaluate(self, smartlink: SmartLink, context: dict) -> list:
        """
        Evaluate all targeting rules for a SmartLink.

        Returns a list of OfferPoolEntry objects that are eligible
        for the given request context. Empty list = no match (use fallback).
        """
        # Load targeting rule (cache-first)
        rule = self._load_rule(smartlink)

        if rule is None:
            # No targeting rules: all offers in pool are eligible
            return self._get_all_active_entries(smartlink)

        # Build match context
        match_results = {}

        # Geo targeting
        if hasattr(rule, 'geo_targeting'):
            geo_t = rule.geo_targeting
            match_results['geo'] = self.geo.matches(
                geo_targeting=geo_t,
                country=context.get('country', ''),
                region=context.get('region', ''),
                city=context.get('city', ''),
            )

        # Device targeting
        if hasattr(rule, 'device_targeting'):
            match_results['device'] = self.device.matches(
                device_targeting=rule.device_targeting,
                device_type=context.get('device_type', ''),
            )

        # OS targeting
        if hasattr(rule, 'os_targeting'):
            match_results['os'] = self.os.matches(
                os_targeting=rule.os_targeting,
                os_type=context.get('os', ''),
            )

        # Time targeting
        if hasattr(rule, 'time_targeting'):
            from ...utils import get_day_of_week_utc, get_current_hour_utc
            match_results['time'] = self.time.matches(
                time_targeting=rule.time_targeting,
                day_of_week=get_day_of_week_utc(),
                hour=get_current_hour_utc(),
            )

        # ISP targeting
        if hasattr(rule, 'isp_targeting'):
            match_results['isp'] = self.isp.matches(
                isp_targeting=rule.isp_targeting,
                isp_name=context.get('isp', ''),
                asn=context.get('asn', ''),
            )

        # Language targeting
        if hasattr(rule, 'language_targeting'):
            match_results['language'] = self.language.matches(
                language_targeting=rule.language_targeting,
                language=context.get('language', ''),
            )

        # Evaluate combined result using AND/OR logic
        is_match = self.evaluator.evaluate(match_results, logic=rule.logic)

        if not is_match:
            logger.debug(
                f"Targeting NO MATCH for [{smartlink.slug}]: "
                f"country={context.get('country')} device={context.get('device_type')} "
                f"results={match_results}"
            )
            return []

        # Return active pool entries
        return self._get_all_active_entries(smartlink)

    def _load_rule(self, smartlink: SmartLink):
        """Load targeting rule with all sub-rules (cache or DB)."""
        cache_key = f"sl_targeting:{smartlink.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            rule = smartlink.targeting_rule
            # Preload all related targeting sub-models
            try:
                _ = rule.geo_targeting
            except Exception:
                pass
            try:
                _ = rule.device_targeting
            except Exception:
                pass
            try:
                _ = rule.os_targeting
            except Exception:
                pass
            try:
                _ = rule.time_targeting
            except Exception:
                pass
            try:
                _ = rule.isp_targeting
            except Exception:
                pass
            try:
                _ = rule.language_targeting
            except Exception:
                pass

            cache.set(cache_key, rule, CACHE_TTL_TARGETING)
            return rule

        except Exception:
            # No targeting rule configured — cache None sentinel
            cache.set(cache_key, False, CACHE_TTL_TARGETING)
            return None

    def _get_all_active_entries(self, smartlink: SmartLink) -> list:
        """Return all active, non-capped offer pool entries."""
        try:
            return list(
                smartlink.offer_pool.entries
                .filter(is_active=True)
                .select_related('offer')
                .order_by('-priority', '-weight')
            )
        except Exception:
            return []
