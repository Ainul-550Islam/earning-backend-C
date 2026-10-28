"""
Cap Enforcement Service - Real Implementation
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CapEnforcementService:
    """Enforces offer caps (daily, weekly, global)."""

    def __init__(self):
        self._stats = {}

    def _get_cache(self):
        import offer_routing.services.cache as _cm
        return _cm.cache_service

    def check_user_cap(self, cap_id: int, user_id: int) -> dict:
        cs = self._get_cache()
        cache_key = f'user_cap:{cap_id}:{user_id}'
        raw = cs.get(cache_key)
        cached_data = None
        if isinstance(raw, dict):
            if 'count' in raw:
                cached_data = raw
            elif raw.get('found') and isinstance(raw.get('value'), dict):
                cached_data = raw['value']
        try:
            from offer_routing.models import UserOfferCap
            cap = UserOfferCap.objects.get(id=cap_id)
        except Exception:
            return {'success': False, 'error': 'Cap not found'}
        if cached_data is not None:
            count = cached_data.get('count', 0)
            remaining = max(0, cap.max_shows_per_day - count)
            return {'can_show': remaining > 0, 'remaining_offers': remaining,
                    'cap_id': cap_id, 'cap_type': cap.cap_type,
                    'max_offers': cap.max_shows_per_day, 'cached': True}
        from django.utils import timezone
        from offer_routing.models import UserOfferHistory
        today = timezone.now().date()
        # Try offer FK match, then route FK match as fallback
        count = UserOfferHistory.objects.filter(user_id=user_id, offer=cap.offer).count()
        if count == 0:
            count = UserOfferHistory.objects.filter(user_id=user_id, route=cap.offer).count()
        remaining = max(0, cap.max_shows_per_day - count)
        result = {'can_show': remaining > 0, 'remaining_offers': remaining,
                  'cap_id': cap_id, 'cap_type': cap.cap_type,
                  'max_offers': cap.max_shows_per_day}
        if not remaining:
            result['reason'] = 'User daily cap exceeded'
        cs.set(cache_key, {'count': count, 'timestamp': timezone.now().isoformat()}, 300)
        return result

    def check_global_cap(self, cap_id: int, user_id: int) -> dict:
        cs = self._get_cache()
        cache_key = f'global_cap:{cap_id}:{user_id}'
        raw = cs.get(cache_key)
        cached_data = None
        if isinstance(raw, dict):
            if 'count' in raw:
                cached_data = raw
            elif raw.get('found') and isinstance(raw.get('value'), dict):
                cached_data = raw['value']
        try:
            from offer_routing.models import OfferRoutingCap
            cap = OfferRoutingCap.objects.get(id=cap_id)
        except Exception:
            return {'success': False, 'error': 'Cap not found'}
        if cached_data is not None:
            count = cached_data.get('count', 0)
            remaining = max(0, cap.cap_value - count)
            return {'can_show': remaining > 0, 'remaining_offers': remaining,
                    'cap_id': cap_id, 'cap_type': cap.cap_type,
                    'max_offers': cap.cap_value}
        from django.utils import timezone
        from offer_routing.models import UserOfferHistory
        today = timezone.now().date()
        # Try offer FK match, then route FK match as fallback
        count = UserOfferHistory.objects.filter(user_id=user_id, offer=cap.offer).count()
        if count == 0:
            count = UserOfferHistory.objects.filter(user_id=user_id, route=cap.offer).count()
        remaining = max(0, cap.cap_value - count)
        result = {'can_show': remaining > 0, 'remaining_offers': remaining,
                  'cap_id': cap_id, 'cap_type': cap.cap_type,
                  'max_offers': cap.cap_value}
        if not remaining:
            result['reason'] = 'Global daily cap exceeded'
        cs.set(cache_key, {'count': count, 'timestamp': timezone.now().isoformat()}, 300)
        return result

    def increment_cap_usage(self, cap_id: int, increment: int = 1) -> dict:
        try:
            from offer_routing.models import UserOfferCap
            cap = UserOfferCap.objects.get(id=cap_id)
            cap.shown_today += increment
            cap.save(update_fields=['shown_today'])
            return {'success': True, 'new_count': cap.shown_today, 'cap_id': cap_id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def reset_cap_usage(self, cap_id: int, cap_type: str = 'daily') -> dict:
        try:
            from offer_routing.models import UserOfferCap
            cap = UserOfferCap.objects.get(id=cap_id)
            cap.shown_today = 0
            if cap_type == 'weekly':
                cap.weekly_count = 0
                cap.save(update_fields=['shown_today', 'weekly_count'])
            else:
                cap.save(update_fields=['shown_today'])
            return {'success': True, 'cap_id': cap_id, 'cap_type': cap_type}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_cap_status(self, user_id: int) -> dict:
        try:
            from offer_routing.models import UserOfferCap
            caps = UserOfferCap.objects.filter(user_id=user_id)
            caps_data = []
            for cap in caps:
                current = cap.weekly_count if cap.cap_type == 'weekly' else cap.shown_today
                caps_data.append({'cap_id': cap.id, 'cap_type': cap.cap_type,
                                   'max_offers': cap.max_shows_per_day,
                                   'current_count': current,
                                   'remaining': max(0, cap.max_shows_per_day - current)})
            return {'success': True, 'caps': caps_data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_cap_with_override(self, cap_id: int, user_id: int) -> dict:
        try:
            from offer_routing.models import UserOfferCap, CapOverride
            cap = UserOfferCap.objects.get(id=cap_id)
            override = CapOverride.objects.filter(
                user_id=user_id, cap_type=cap.cap_type, is_active=True).first()
            effective_max = cap.max_shows_per_day
            has_override = False
            override_value = None
            if override and override.override_value is not None:
                effective_max = override.override_value
                has_override = True
                override_value = override.override_value
            remaining = max(0, effective_max - cap.shown_today)
            return {'can_show': remaining > 0, 'remaining_offers': remaining,
                    'has_override': has_override, 'override_value': override_value,
                    'cap_id': cap_id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_cap(self, config: dict) -> dict:
        errors = []
        valid_types = {'daily', 'weekly', 'monthly', 'lifetime', 'hourly'}
        if not config.get('cap_type'):
            errors.append('cap_type')
        elif config['cap_type'] not in valid_types:
            errors.append('cap_type')
        cap_value = config.get('cap_value') or config.get('max_offers')
        if cap_value is None or (isinstance(cap_value, (int, float)) and cap_value <= 0):
            errors.append('max_offers')
        return {'valid': len(errors) == 0, 'is_valid': len(errors) == 0, 'errors': errors}

    def health_check(self) -> dict:
        try:
            from offer_routing.models import UserOfferCap
            return {'status': 'healthy', 'cache_status': 'ok',
                    'performance_stats': {'total_caps': UserOfferCap.objects.count()}}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
