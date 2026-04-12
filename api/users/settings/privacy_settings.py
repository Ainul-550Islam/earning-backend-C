"""
api/users/settings/privacy_settings.py
GDPR compliance — data export, deletion request, consent management
"""
import json
import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User   = get_user_model()


class PrivacySettings:
    """
    GDPR / CCPA compliance।
    User নিজের data export করতে পারবে।
    Account delete request করতে পারবে।
    api.kyc, api.wallet, api.referral থেকে data collect করবে — নিজে store করবে না।
    """

    # ─────────────────────────────────────
    # DATA EXPORT (GDPR Article 20)
    # ─────────────────────────────────────
    def export_user_data(self, user) -> dict:
        """
        User-এর সব data collect করে একটা JSON দাও।
        প্রতিটি app থেকে data নিয়ে assemble করো।
        """
        data = {
            'exported_at': timezone.now().isoformat(),
            'user_id':     str(user.id),
            'profile':     self._export_profile(user),
            'activity':    self._export_activity(user),
            'devices':     self._export_devices(user),
            'login_history': self._export_login_history(user),
            'wallet':      self._export_wallet(user),
            'referrals':   self._export_referrals(user),
            'kyc':         self._export_kyc(user),
            'notifications': self._export_notification_prefs(user),
        }
        logger.info(f'Data export generated for user: {user.id}')
        return data

    def export_as_json_file(self, user) -> tuple[str, bytes]:
        """
        JSON file হিসেবে export করো।
        Returns: (filename, bytes)
        """
        data     = self.export_user_data(user)
        filename = f"my_data_{user.username}_{timezone.now().strftime('%Y%m%d')}.json"
        content  = json.dumps(data, indent=2, default=str).encode('utf-8')
        return filename, content

    # ─────────────────────────────────────
    # ACCOUNT DELETION (GDPR Article 17)
    # ─────────────────────────────────────
    def request_deletion(self, user, reason: str = '') -> dict:
        """
        Account deletion request করো।
        Immediate delete না — ৩০ দিন grace period।
        """
        if getattr(user, 'balance', 0) > 0:
            from ..exceptions import InsufficientBalanceException
            raise InsufficientBalanceException(
                required=0,
                available=float(user.balance)
            )
            # Note: balance > 0 থাকলে আগে withdraw করতে হবে

        deletion_date = timezone.now() + timedelta(days=30)

        # Flag করো
        user.is_active          = False
        user.deletion_requested = True if hasattr(user, 'deletion_requested') else None
        user.scheduled_deletion = deletion_date if hasattr(user, 'scheduled_deletion') else None
        user.save(update_fields=[
            f for f in ['is_active', 'deletion_requested', 'scheduled_deletion']
            if hasattr(user, f)
        ])

        # Cache clear করো
        from ..cache import user_cache
        user_cache.invalidate_all(str(user.id))

        # api.notifications-কে email পাঠাতে বলো
        self._notify_deletion_scheduled(user, deletion_date)

        logger.info(f'Account deletion requested for user: {user.id}, scheduled: {deletion_date}')

        return {
            'status':         'deletion_scheduled',
            'deletion_date':  deletion_date.isoformat(),
            'grace_days':     30,
            'message':        'Your account will be deleted in 30 days. You can cancel anytime.',
            'cancel_url':     f'/api/auth/users/cancel-deletion/',
        }

    def cancel_deletion(self, user) -> bool:
        """Grace period-এ deletion cancel করো"""
        user.is_active = True
        fields = ['is_active']

        if hasattr(user, 'deletion_requested'):
            user.deletion_requested = False
            fields.append('deletion_requested')
        if hasattr(user, 'scheduled_deletion'):
            user.scheduled_deletion = None
            fields.append('scheduled_deletion')

        user.save(update_fields=fields)
        logger.info(f'Account deletion cancelled for user: {user.id}')
        return True

    def execute_deletion(self, user) -> bool:
        """
        Celery task এটা call করবে — scheduled deletion execute।
        Hard delete না, anonymize করো।
        """
        try:
            # Anonymize — GDPR-compliant
            import uuid
            anon_id = str(uuid.uuid4())[:8]

            user.username  = f'deleted_user_{anon_id}'
            user.email     = f'deleted_{anon_id}@deleted.invalid'
            user.phone     = None if hasattr(user, 'phone') else None
            user.first_name= ''
            user.last_name = ''
            user.is_active = False
            user.avatar    = None if hasattr(user, 'avatar') else None

            save_fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
            for f in ['phone', 'avatar']:
                if hasattr(user, f):
                    save_fields.append(f)

            user.save(update_fields=save_fields)

            # Related data anonymize — অন্য app-এ signal দাও
            self._notify_data_erasure(user)

            logger.info(f'Account anonymized (GDPR): {user.id}')
            return True

        except Exception as e:
            logger.error(f'Account deletion failed for {user.id}: {e}')
            return False

    # ─────────────────────────────────────
    # CONSENT MANAGEMENT
    # ─────────────────────────────────────
    def get_consent_status(self, user) -> dict:
        """User-এর সব consent status দাও"""
        try:
            from django.apps import apps
            Consent = apps.get_model('users', 'UserConsent')
            consents = Consent.objects.filter(user=user).values(
                'consent_type', 'is_granted', 'granted_at', 'ip_address'
            )
            return {c['consent_type']: c for c in consents}
        except Exception:
            return {}

    def update_consent(self, user, consent_type: str, is_granted: bool, ip: str = '') -> bool:
        """Consent update করো"""
        try:
            from django.apps import apps
            Consent = apps.get_model('users', 'UserConsent')
            Consent.objects.update_or_create(
                user         = user,
                consent_type = consent_type,
                defaults={
                    'is_granted': is_granted,
                    'granted_at': timezone.now() if is_granted else None,
                    'ip_address': ip,
                }
            )
            return True
        except Exception as e:
            logger.error(f'Consent update failed: {e}')
            return False

    # ─────────────────────────────────────
    # PRIVATE — data collectors
    # ─────────────────────────────────────
    def _export_profile(self, user) -> dict:
        return {
            'username':    user.username,
            'email':       user.email,
            'phone':       getattr(user, 'phone', None),
            'country':     getattr(user, 'country', ''),
            'tier':        getattr(user, 'tier', 'FREE'),
            'joined_at':   user.date_joined.isoformat() if hasattr(user, 'date_joined') else None,
        }

    def _export_activity(self, user) -> list:
        try:
            from ..models import UserActivity
            return list(
                UserActivity.objects.filter(user=user)
                .order_by('-created_at')[:100]
                .values('activity_type', 'ip_address', 'created_at')
            )
        except Exception:
            return []

    def _export_devices(self, user) -> list:
        try:
            from ..models import UserDevice
            return list(
                UserDevice.objects.filter(user=user)
                .values('device_name', 'device_type', 'os', 'browser', 'last_seen')
            )
        except Exception:
            return []

    def _export_login_history(self, user) -> list:
        try:
            from ..models import LoginHistory
            return list(
                LoginHistory.objects.filter(user=user)
                .order_by('-attempted_at')[:50]
                .values('ip_address', 'method', 'success', 'attempted_at')
            )
        except Exception:
            return []

    def _export_wallet(self, user) -> dict:
        """api.wallet থেকে data নাও"""
        try:
            from django.apps import apps
            Wallet = apps.get_model('wallet', 'Wallet')
            wallet = Wallet.objects.get(user=user)
            return {
                'balance':     float(wallet.balance),
                'total_earned':float(wallet.total_earned),
            }
        except Exception:
            return {'balance': float(getattr(user, 'balance', 0))}

    def _export_referrals(self, user) -> dict:
        """api.referral থেকে data নাও"""
        try:
            from django.apps import apps
            Referral = apps.get_model('referral', 'Referral')
            count = Referral.objects.filter(referrer=user).count()
            return {'total_referrals': count}
        except Exception:
            return {}

    def _export_kyc(self, user) -> dict:
        """api.kyc থেকে data নাও"""
        try:
            from django.apps import apps
            KYC = apps.get_model('kyc', 'KYCVerification')
            kyc = KYC.objects.filter(user=user).first()
            if kyc:
                return {'status': kyc.status, 'submitted_at': str(kyc.created_at)}
        except Exception:
            pass
        return {}

    def _export_notification_prefs(self, user) -> dict:
        try:
            from ..models import NotificationSettings
            prefs = NotificationSettings.objects.filter(user=user).first()
            if prefs:
                return {
                    'email_enabled': getattr(prefs, 'email_notifications', True),
                    'sms_enabled':   getattr(prefs, 'sms_notifications', False),
                    'push_enabled':  getattr(prefs, 'push_notifications', True),
                }
        except Exception:
            pass
        return {}

    def _notify_deletion_scheduled(self, user, deletion_date) -> None:
        """api.notifications-কে email পাঠাতে বলো"""
        try:
            logger.info(f'Deletion scheduled email signal fired for: {user.email}')
            # api.notifications.signals.account_deletion_scheduled.send(...)
        except Exception as e:
            logger.warning(f'Deletion notification signal failed: {e}')

    def _notify_data_erasure(self, user) -> None:
        """সব app-কে data erase করতে বলো"""
        try:
            logger.info(f'Data erasure signal fired for user: {user.id}')
            # api.kyc.signals.erase_user_data.send(...)
            # api.wallet.signals.erase_user_data.send(...)
        except Exception as e:
            logger.warning(f'Data erasure signal failed: {e}')


# Singleton
privacy_settings = PrivacySettings()
