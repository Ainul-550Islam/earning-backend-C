# api/offer_inventory/compliance_legal/terms_validator.py
"""Terms Validator — TOS acceptance tracking."""
import json
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)
CURRENT_TOS_VERSION = '3.0'


class TermsValidator:
    """Validate and record TOS acceptance."""

    @staticmethod
    def has_accepted_current(user) -> bool:
        from api.offer_inventory.models import SystemSetting
        key    = f'tos_accepted:{user.id}'
        cached = cache.get(key)
        if cached is not None:
            return cached == CURRENT_TOS_VERSION
        try:
            setting = SystemSetting.objects.get(key=f'user_tos:{user.id}')
            result  = setting.value == CURRENT_TOS_VERSION
            cache.set(key, setting.value, 3600)
            return result
        except Exception:
            return False

    @staticmethod
    def record_acceptance(user, tos_version: str = None, ip: str = '') -> bool:
        from api.offer_inventory.models import SystemSetting
        version = tos_version or CURRENT_TOS_VERSION
        SystemSetting.objects.update_or_create(
            key=f'user_tos:{user.id}',
            defaults={
                'value'      : version,
                'value_type' : 'string',
                'description': json.dumps({'version': version, 'accepted_at': timezone.now().isoformat(), 'ip': ip}),
            }
        )
        cache.set(f'tos_accepted:{user.id}', version, 3600)
        return True

    @staticmethod
    def get_acceptance_stats() -> dict:
        from api.offer_inventory.models import SystemSetting
        from django.contrib.auth import get_user_model
        User  = get_user_model()
        total = User.objects.filter(is_active=True).count()
        acc   = SystemSetting.objects.filter(
            key__startswith='user_tos:', value=CURRENT_TOS_VERSION
        ).count()
        return {
            'current_version' : CURRENT_TOS_VERSION,
            'total_users'     : total,
            'accepted'        : acc,
            'acceptance_pct'  : round(acc / max(total, 1) * 100, 1),
            'not_accepted'    : total - acc,
        }
