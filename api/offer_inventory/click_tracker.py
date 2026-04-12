# api/offer_inventory/click_tracker.py
"""
Click Tracker — Full click lifecycle management.
Records, validates, deduplicates, and analyzes all clicks.
Integrates with fraud detection, geo targeting, and device detection.
"""
import secrets
import logging
import hashlib
from decimal import Decimal
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CLICK_TOKEN_BYTES = 32   # 64-char hex token
CLICK_CACHE_TTL   = 86400   # 24h


class ClickTracker:
    """
    Single entry point for recording all offer clicks.
    Performs: bot check → IP block → rate limit → dedup → create → sign.
    """

    @classmethod
    @transaction.atomic
    def record(cls, offer, user, request_meta: dict) -> 'Click':
        """
        Record a click with full validation.
        Returns Click object or raises exception.
        """
        from api.offer_inventory.models import Click, SubID
        from api.offer_inventory.security_fraud.bot_detection import BotDetector
        from api.offer_inventory.security_fraud.ip_blacklist import IPBlacklistManager
        from api.offer_inventory.security_fraud.duplicate_click_prevention import DuplicateClickPrevention
        from api.offer_inventory.exceptions import (
            FraudDetectedException, IPBlockedException,
            RateLimitExceededException, OfferNotAvailableException,
        )

        ip         = request_meta.get('ip_address', '')
        user_agent = request_meta.get('user_agent', '')
        country    = request_meta.get('country_code', '')
        device     = request_meta.get('device_type', 'desktop')
        os_name    = request_meta.get('os', '')
        browser    = request_meta.get('browser', '')
        referrer   = request_meta.get('referrer', '')
        s1         = request_meta.get('s1', '')
        s2         = request_meta.get('s2', '')

        # 1. Offer available?
        if not offer.is_available:
            raise OfferNotAvailableException()

        # 2. IP blocked?
        if IPBlacklistManager.is_blocked(ip):
            raise IPBlockedException()

        # 3. Bot detection
        bot_score = BotDetector.score(ip, user_agent, user.id if user else None)
        if bot_score >= 70:
            BotDetector.record_click(ip)
            if bot_score >= 90:
                IPBlacklistManager.block(ip, reason=f'bot_score:{bot_score:.0f}', hours=24)
            raise FraudDetectedException(f'Bot detected (score={bot_score:.0f})')

        # 4. Duplicate click check
        if user:
            dup_result = DuplicateClickPrevention.check_and_record(
                user_id=user.id, offer_id=str(offer.id),
                ip=ip, click_token='pending',
            )
            if not dup_result['allowed']:
                raise RateLimitExceededException(
                    f'Duplicate click: {dup_result["reason"]}'
                )

        # 5. Generate token
        token = secrets.token_hex(CLICK_TOKEN_BYTES)

        # 6. Sub-ID handling
        sub_id_obj = None
        if s1 and user:
            sub_id_obj, _ = SubID.objects.get_or_create(
                offer=offer, user=user, s1=s1,
                defaults={'s2': s2}
            )

        # 7. Create click record
        click = Click.objects.create(
            offer        =offer,
            user         =user,
            sub_id       =sub_id_obj,
            ip_address   =ip,
            user_agent   =user_agent,
            country_code =country,
            device_type  =device,
            os           =os_name,
            browser      =browser,
            referrer     =referrer,
            click_token  =token,
            is_unique    =True,
            is_fraud     =bot_score >= 40,
            fraud_reason =f'bot_score:{bot_score:.0f}' if bot_score >= 40 else '',
        )

        # 8. Cache token for fast lookup
        cache.set(f'click:{token}', str(click.id), CLICK_CACHE_TTL)

        # 9. Create HMAC signature
        from api.offer_inventory.security_fraud.click_signature import ClickSignatureManager
        ClickSignatureManager.store(click)

        # 10. Track velocity
        BotDetector.record_click(ip)

        logger.info(
            f'Click recorded | id={click.id} | '
            f'offer={offer.id} | user={user.id if user else "anon"} | '
            f'ip={ip} | country={country}'
        )
        return click

    @staticmethod
    def get_by_token(token: str):
        """Fast click lookup via cache + DB fallback."""
        from api.offer_inventory.models import Click

        # Cache first
        click_id = cache.get(f'click:{token}')
        if click_id:
            try:
                return Click.objects.select_related('offer', 'user').get(id=click_id)
            except Click.DoesNotExist:
                pass

        # DB fallback
        try:
            click = Click.objects.select_related('offer', 'user').get(click_token=token)
            cache.set(f'click:{token}', str(click.id), CLICK_CACHE_TTL)
            return click
        except Click.DoesNotExist:
            return None

    @staticmethod
    def mark_fraud(click_id: str, reason: str):
        """Flag a click as fraudulent."""
        from api.offer_inventory.models import Click
        from django.db.models import F
        Click.objects.filter(id=click_id).update(
            is_fraud=True, fraud_reason=reason[:255]
        )

    @staticmethod
    def get_stats(offer_id: str = None, days: int = 7) -> dict:
        """Click statistics."""
        from api.offer_inventory.models import Click
        from django.db.models import Count
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        qs    = Click.objects.filter(created_at__gte=since)
        if offer_id:
            qs = qs.filter(offer_id=offer_id)

        agg = qs.aggregate(
            total =Count('id'),
            unique=Count('ip_address', distinct=True),
            fraud =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_fraud=True)),
            conv  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(converted=True)),
        )
        total = agg['total'] or 1
        return {
            'total_clicks'     : agg['total'],
            'unique_clicks'    : agg['unique'],
            'fraud_clicks'     : agg['fraud'],
            'fraud_rate_pct'   : round(agg['fraud'] / total * 100, 2),
            'conversions'      : agg['conv'],
            'cvr_pct'          : round(agg['conv'] / total * 100, 2),
        }
