"""
api/users/settings/data_settings.py
Data collection consent tracking — GDPR/CCPA
কোন data collect করা যাবে সেটা user ঠিক করবে
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

CONSENT_TYPES = {
    'analytics':      'Allow usage analytics collection',
    'marketing':      'Allow marketing emails and promotions',
    'personalization':'Allow personalized offer recommendations',
    'third_party':    'Allow data sharing with ad networks',
    'profiling':      'Allow behavioral profiling',
    'location':       'Allow location-based features',
    'device_tracking':'Allow device fingerprinting for security',
    'cookie_analytics':'Allow analytics cookies',
}

# Required consents — এগুলো ছাড়া service দেওয়া যাবে না
REQUIRED_CONSENTS = ['device_tracking']


class DataSettings:

    def get_all_consents(self, user) -> dict:
        """User-এর সব consent status দাও"""
        try:
            from django.apps import apps
            Consent = apps.get_model('users', 'UserConsent')
            records = {
                c.consent_type: {
                    'granted':    c.is_granted,
                    'granted_at': c.granted_at.isoformat() if c.granted_at else None,
                    'required':   c.consent_type in REQUIRED_CONSENTS,
                    'description':CONSENT_TYPES.get(c.consent_type, ''),
                }
                for c in Consent.objects.filter(user=user)
            }
            # যেগুলো এখনো set করা হয়নি সেগুলো default দাও
            for ctype, desc in CONSENT_TYPES.items():
                if ctype not in records:
                    records[ctype] = {
                        'granted':    ctype in REQUIRED_CONSENTS,
                        'granted_at': None,
                        'required':   ctype in REQUIRED_CONSENTS,
                        'description':desc,
                    }
            return records
        except Exception as e:
            logger.error(f'Get consents failed: {e}')
            return {}

    def grant(self, user, consent_type: str, ip: str = '') -> bool:
        """Consent দাও"""
        return self._set_consent(user, consent_type, True, ip)

    def revoke(self, user, consent_type: str) -> bool:
        """Consent তুলে নাও"""
        if consent_type in REQUIRED_CONSENTS:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'consent': f'"{consent_type}" consent is required for using this service.'
            })
        return self._set_consent(user, consent_type, False)

    def bulk_update(self, user, consents: dict, ip: str = '') -> dict:
        """
        একসাথে multiple consent update।
        consents = {'analytics': True, 'marketing': False, ...}
        """
        results = {}
        for ctype, granted in consents.items():
            if ctype not in CONSENT_TYPES:
                continue
            if not granted and ctype in REQUIRED_CONSENTS:
                results[ctype] = {'success': False, 'reason': 'Required consent cannot be revoked'}
                continue
            success = self._set_consent(user, ctype, granted, ip)
            results[ctype] = {'success': success}
        return results

    def has_consent(self, user, consent_type: str) -> bool:
        """Specific consent আছে কিনা check করো"""
        if consent_type in REQUIRED_CONSENTS:
            return True
        try:
            from django.apps import apps
            Consent = apps.get_model('users', 'UserConsent')
            consent = Consent.objects.filter(
                user=user, consent_type=consent_type
            ).first()
            return consent.is_granted if consent else False
        except Exception:
            return False

    def get_data_usage_summary(self, user) -> dict:
        """User-এর data কীভাবে use হচ্ছে তার summary"""
        consents = self.get_all_consents(user)
        return {
            'analytics_enabled':       consents.get('analytics', {}).get('granted', False),
            'marketing_enabled':       consents.get('marketing', {}).get('granted', False),
            'personalization_enabled': consents.get('personalization', {}).get('granted', False),
            'third_party_enabled':     consents.get('third_party', {}).get('granted', False),
            'data_collected': [
                'Account information (username, email)',
                'Transaction history',
                'Login history for security',
                'Device information for fraud prevention',
            ],
            'your_rights': [
                'Export your data (GDPR Article 20)',
                'Delete your account (GDPR Article 17)',
                'Correct your data (GDPR Article 16)',
                'Restrict processing (GDPR Article 18)',
            ],
        }

    def _set_consent(self, user, consent_type: str, granted: bool, ip: str = '') -> bool:
        try:
            from django.apps import apps
            Consent = apps.get_model('users', 'UserConsent')
            Consent.objects.update_or_create(
                user         = user,
                consent_type = consent_type,
                defaults={
                    'is_granted': granted,
                    'granted_at': timezone.now() if granted else None,
                    'ip_address': ip,
                }
            )
            logger.info(f'Consent {"granted" if granted else "revoked"}: {consent_type} for user {user.id}')
            return True
        except Exception as e:
            logger.error(f'Consent update failed: {e}')
            return False


# Singleton
data_settings = DataSettings()
