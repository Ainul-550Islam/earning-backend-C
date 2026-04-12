# api/offer_inventory/compliance_legal/privacy_consent.py
"""Privacy Consent Manager — GDPR Article 7 consent management."""
import json
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

CONSENT_TYPES = [
    'marketing_email', 'marketing_push', 'analytics_tracking',
    'data_sharing', 'personalization',
]


class PrivacyConsentManager:
    """Manage user privacy consent choices."""

    @staticmethod
    def record_consent(user, consent_type: str, granted: bool, ip: str = '') -> bool:
        if consent_type not in CONSENT_TYPES:
            raise ValueError(f'Unknown consent type: {consent_type}')
        from api.offer_inventory.models import SystemSetting
        record = json.dumps({
            'granted'  : granted,
            'timestamp': timezone.now().isoformat(),
            'ip'       : ip,
            'type'     : consent_type,
        })
        SystemSetting.objects.update_or_create(
            key=f'consent:{user.id}:{consent_type}',
            defaults={'value': record, 'value_type': 'json',
                      'description': f'Privacy consent: {consent_type}'}
        )
        cache.delete(f'consent:{user.id}')
        logger.info(f'Consent: user={user.id} type={consent_type} granted={granted}')
        return True

    @staticmethod
    def get_user_consents(user) -> dict:
        from api.offer_inventory.models import SystemSetting
        key    = f'consent:{user.id}'
        cached = cache.get(key)
        if cached:
            return cached
        records = {}
        for s in SystemSetting.objects.filter(key__startswith=f'consent:{user.id}:'):
            try:
                ct = s.key.split(':')[-1]
                records[ct] = json.loads(s.value)
            except Exception:
                pass
        cache.set(key, records, 600)
        return records

    @staticmethod
    def has_consent(user, consent_type: str) -> bool:
        return PrivacyConsentManager.get_user_consents(user).get(consent_type, {}).get('granted', False)

    @staticmethod
    def withdraw_all_consents(user):
        from api.offer_inventory.models import SystemSetting
        SystemSetting.objects.filter(key__startswith=f'consent:{user.id}:').delete()
        cache.delete(f'consent:{user.id}')

    @staticmethod
    def get_available_consent_types() -> list:
        return CONSENT_TYPES
