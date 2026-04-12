import logging
import time
from django.core.cache import cache
from django.utils import timezone
from ...models import SmartLink
from ...exceptions import SmartLinkNotFound, SmartLinkInactive, NoOfferAvailable
from ...constants import CACHE_TTL_SMARTLINK
from ...utils import timing_decorator
from ..targeting.TargetingEngine import TargetingEngine
from ..rotation.OfferRotationService import OfferRotationService
from ..rotation.FallbackService import FallbackService
from ..click.ClickFraudService import ClickFraudService
from ..click.BotDetectionService import BotDetectionService
from .SmartLinkCacheService import SmartLinkCacheService

logger = logging.getLogger('smartlink.resolver')


class SmartLinkResolverService:
    """
    Main entry point: slug → offer URL in <5ms.

    Flow:
    1. Cache lookup (Redis) — target <1ms
    2. DB lookup + SmartLink validation — if cache miss
    3. Fraud/bot check
    4. Targeting engine evaluation
    5. Offer rotation / selection
    6. URL build + return
    7. Async click record (Celery)
    """

    def __init__(self):
        self.cache_service = SmartLinkCacheService()
        self.targeting_engine = TargetingEngine()
        self.rotation_service = OfferRotationService()
        self.fallback_service = FallbackService()
        self.fraud_service = ClickFraudService()
        self.bot_service = BotDetectionService()

    @timing_decorator
    def resolve(self, slug: str, request_context: dict) -> dict:
        """
        Resolve a SmartLink slug to a redirect URL.

        Args:
            slug: SmartLink slug
            request_context: {
                'ip': str,
                'user_agent': str,
                'country': str,
                'region': str,
                'city': str,
                'device_type': str,
                'os': str,
                'browser': str,
                'isp': str,
                'language': str,
                'referrer': str,
                'sub1'-'sub5': str,
                'custom_params': dict,
            }

        Returns:
            {
                'url': str,            # final redirect URL
                'offer_id': int,
                'click_id': int | None,
                'was_cached': bool,
                'was_fallback': bool,
                'redirect_type': str,
                'response_time_ms': float,
            }
        """
        start = time.perf_counter()

        # ── Step 1: Load SmartLink (cache-first) ─────────────────────
        smartlink = self.cache_service.get_smartlink(slug)
        if smartlink is None:
            try:
                smartlink = SmartLink.objects.select_related(
                    'offer_pool', 'targeting_rule', 'fallback', 'rotation_config'
                ).get(slug=slug)
            except SmartLink.DoesNotExist:
                raise SmartLinkNotFound()
            self.cache_service.set_smartlink(slug, smartlink)

        if not smartlink.is_active:
            raise SmartLinkInactive()

        ip = request_context.get('ip', '0.0.0.0')
        user_agent = request_context.get('user_agent', '')

        # ── Step 2: Bot detection ─────────────────────────────────────
        if smartlink.enable_bot_filter:
            is_bot, bot_type = self.bot_service.detect(ip, user_agent)
            if is_bot:
                self._log_bot_async(smartlink, request_context, bot_type)
                # Bots go to fallback, not to offer
                fallback_url = self.fallback_service.get_url(smartlink)
                return self._build_result(
                    url=fallback_url, offer_id=None,
                    was_fallback=True, redirect_type=smartlink.redirect_type,
                    start=start, was_cached=False,
                )

        # ── Step 3: Fraud check ───────────────────────────────────────
        if smartlink.enable_fraud_filter:
            fraud_score, fraud_signals = self.fraud_service.score(ip, user_agent, request_context)
            if fraud_score >= 85:
                from ...exceptions import ClickBlocked
                raise ClickBlocked()

        # ── Step 4: Targeting engine ──────────────────────────────────
        matched = self.targeting_engine.evaluate(smartlink, request_context)

        # ── Step 5: Offer rotation ────────────────────────────────────
        if matched:
            offer_entry = self.rotation_service.select(
                smartlink=smartlink,
                eligible_entries=matched,
                request_context=request_context,
            )
        else:
            offer_entry = None

        if offer_entry is None:
            fallback_url = self.fallback_service.get_url(smartlink)
            if not fallback_url:
                raise NoOfferAvailable()
            return self._build_result(
                url=fallback_url, offer_id=None,
                was_fallback=True, redirect_type=smartlink.redirect_type,
                start=start, was_cached=False,
            )

        # ── Step 6: Build redirect URL ────────────────────────────────
        from ..redirect.URLBuilderService import URLBuilderService
        url_builder = URLBuilderService()
        final_url = url_builder.build(
            offer=offer_entry.offer,
            smartlink=smartlink,
            request_context=request_context,
        )

        # ── Step 7: Async click tracking ──────────────────────────────
        self._track_click_async(smartlink, offer_entry.offer, request_context)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug(f"Resolved [{slug}] → offer#{offer_entry.offer_id} in {elapsed_ms:.2f}ms")

        return self._build_result(
            url=final_url,
            offer_id=offer_entry.offer_id,
            was_fallback=False,
            redirect_type=smartlink.redirect_type,
            start=start,
            was_cached=False,
        )

    def _build_result(self, url, offer_id, was_fallback, redirect_type, start, was_cached, click_id=None):
        return {
            'url': url,
            'offer_id': offer_id,
            'click_id': click_id,
            'was_cached': was_cached,
            'was_fallback': was_fallback,
            'redirect_type': redirect_type,
            'response_time_ms': (time.perf_counter() - start) * 1000,
        }

    def _track_click_async(self, smartlink, offer, request_context):
        """Fire-and-forget: record click in Celery background task."""
        try:
            from ...tasks.click_processing_tasks import process_click_async
            process_click_async.delay(
                smartlink_id=smartlink.pk,
                offer_id=offer.pk if offer else None,
                **request_context,
            )
        except Exception as e:
            logger.error(f"Failed to queue click tracking task: {e}")

    def _log_bot_async(self, smartlink, context, bot_type):
        try:
            from ...tasks.click_processing_tasks import record_bot_click
            record_bot_click.delay(
                smartlink_id=smartlink.pk,
                ip=context.get('ip'),
                user_agent=context.get('user_agent'),
                bot_type=bot_type,
                country=context.get('country', ''),
            )
        except Exception as e:
            logger.error(f"Failed to queue bot click task: {e}")
