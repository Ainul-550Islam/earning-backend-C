# api/offer_inventory/api_connectivity/sdk_bridge.py
"""
SDK Bridge — Mobile and Web SDK integration layer.
Provides simplified API wrappers for Android, iOS, and JavaScript SDKs.
Handles SDK token authentication, session management, and event tracking.
"""
import logging
import secrets
import hashlib
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SDK_TOKEN_TTL    = 3600 * 24    # 24 hour SDK session token
SDK_TOKEN_PREFIX = 'sdk_'


class SDKBridge:
    """
    Bridge between mobile/web SDKs and the offer inventory system.
    Handles SDK authentication, offer delivery, and event reporting.
    """

    # ── SDK Authentication ─────────────────────────────────────────

    @staticmethod
    def create_sdk_token(user_id, app_id: str, platform: str,
                          device_id: str = '', tenant=None) -> dict:
        """
        Create an authenticated SDK session token.
        Called when user opens the app/offerwall.
        """
        raw_token = secrets.token_urlsafe(32)
        token     = f'{SDK_TOKEN_PREFIX}{raw_token}'

        payload = {
            'user_id'  : str(user_id),
            'app_id'   : app_id,
            'platform' : platform,
            'device_id': device_id,
            'tenant_id': str(tenant.id) if tenant else None,
            'created_at': timezone.now().isoformat(),
            'expires_at': (timezone.now() + timedelta(seconds=SDK_TOKEN_TTL)).isoformat(),
        }
        cache.set(f'sdk_token:{token}', payload, SDK_TOKEN_TTL)
        logger.info(f'SDK token created: user={user_id} platform={platform}')

        return {
            'token'     : token,
            'expires_in': SDK_TOKEN_TTL,
            'platform'  : platform,
        }

    @staticmethod
    def validate_sdk_token(token: str) -> dict:
        """
        Validate SDK token and return session payload.
        Returns None if invalid or expired.
        """
        if not token or not token.startswith(SDK_TOKEN_PREFIX):
            return None
        data = cache.get(f'sdk_token:{token}')
        return data

    @staticmethod
    def refresh_sdk_token(token: str) -> dict:
        """Extend SDK token TTL."""
        data = SDKBridge.validate_sdk_token(token)
        if not data:
            return None
        cache.set(f'sdk_token:{token}', data, SDK_TOKEN_TTL)
        return {'token': token, 'expires_in': SDK_TOKEN_TTL}

    @staticmethod
    def revoke_sdk_token(token: str):
        """Revoke/invalidate SDK token."""
        cache.delete(f'sdk_token:{token}')

    # ── Offer Delivery ─────────────────────────────────────────────

    @staticmethod
    def get_offers_for_sdk(sdk_payload: dict, limit: int = 20) -> list:
        """
        Get offers formatted for SDK consumption.
        Includes all data needed for native rendering.
        """
        from api.offer_inventory.models import Offer
        from api.offer_inventory.geo_targeting import GeoTargetingEngine
        from api.offer_inventory.device_targeting import DeviceTargetingEngine

        platform = sdk_payload.get('platform', 'android')
        tenant   = sdk_payload.get('tenant_id')

        device_type = 'mobile' if platform in ('android', 'ios') else 'desktop'

        qs = Offer.objects.filter(
            status='active'
        ).prefetch_related('caps', 'visibility_rules', 'tags', 'creatives')

        if tenant:
            qs = qs.filter(tenant_id=tenant)

        offers = []
        for offer in qs[:limit * 2]:  # Over-fetch for filtering
            if not offer.is_available:
                continue
            offers.append(SDKBridge._format_offer_for_sdk(offer, platform))
            if len(offers) >= limit:
                break

        return offers

    @staticmethod
    def _format_offer_for_sdk(offer, platform: str) -> dict:
        """Format an offer for SDK response."""
        creative  = offer.creatives.filter(is_approved=True).first()
        image_url = creative.asset_url if creative else offer.image_url

        return {
            'id'            : str(offer.id),
            'title'         : offer.title,
            'description'   : offer.description,
            'instructions'  : offer.instructions,
            'image_url'     : image_url,
            'offer_url'     : offer.offer_url,
            'reward_type'   : offer.reward_type,
            'reward_amount' : str(offer.reward_amount),
            'estimated_time': offer.estimated_time,
            'difficulty'    : offer.difficulty,
            'is_featured'   : offer.is_featured,
            'category'      : offer.category.name if offer.category else None,
            'network'       : offer.network.name if offer.network else None,
            'tags'          : [t.name for t in offer.tags.all()],
            'expires_at'    : offer.expires_at.isoformat() if offer.expires_at else None,
            'platform'      : platform,
        }

    # ── SDK Event Tracking ─────────────────────────────────────────

    @staticmethod
    def track_event(sdk_token: str, event_type: str,
                     event_data: dict = None) -> bool:
        """
        Track SDK events: offer_view, offer_click, offer_complete, etc.
        """
        payload = SDKBridge.validate_sdk_token(sdk_token)
        if not payload:
            logger.warning(f'Invalid SDK token for event: {event_type}')
            return False

        event = {
            'user_id'   : payload.get('user_id'),
            'event_type': event_type,
            'platform'  : payload.get('platform'),
            'data'      : event_data or {},
            'timestamp' : timezone.now().isoformat(),
        }

        # Queue for async processing
        cache_key = f'sdk_events:{payload["user_id"]}'
        events    = cache.get(cache_key, [])
        events.append(event)
        cache.set(cache_key, events[-100:], 3600)  # Keep last 100 events

        logger.debug(f'SDK event: {event_type} user={payload.get("user_id")}')
        return True

    @staticmethod
    def get_sdk_config(app_id: str, platform: str) -> dict:
        """Return SDK configuration for a given app."""
        from api.offer_inventory.models import SystemSetting
        from django.db.models import Q
        import json

        config = {
            'version'         : '2.0',
            'platform'        : platform,
            'min_sdk_version' : '1.5',
            'offerwall_enabled': True,
            'max_daily_offers': 30,
            'supported_rewards': ['coins', 'cash', 'points'],
            'refresh_interval': 300,
            'debug_mode'      : False,
        }

        # Try loading from SystemSetting
        try:
            setting = SystemSetting.objects.filter(
                key=f'sdk_config:{platform}', is_public=True
            ).first()
            if setting:
                config.update(json.loads(setting.value))
        except Exception:
            pass

        return config
