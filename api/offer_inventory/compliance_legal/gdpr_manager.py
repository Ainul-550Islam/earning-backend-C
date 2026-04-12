# api/offer_inventory/compliance_legal/gdpr_manager.py
"""
Compliance & Legal Package — all 10 modules.
GDPR, terms validation, privacy consent, KYC, AML,
ad content filter, DMCA, cookie policy, disclaimer, TOS versioning.
"""
import logging
import json
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# 1. GDPR MANAGER (re-exported from business/compliance_manager.py)
# ════════════════════════════════════════════════════════

from api.offer_inventory.business.compliance_manager import GDPRManager, KYCAMLChecker, AdContentFilter


# ════════════════════════════════════════════════════════
# 2. TERMS VALIDATOR
# ════════════════════════════════════════════════════════

class TermsValidator:
    """Validate users have accepted current Terms of Service."""

    CURRENT_TOS_VERSION = '3.0'

    @staticmethod
    def has_accepted_current(user) -> bool:
        """Check if user has accepted the current TOS version."""
        from api.offer_inventory.models import SystemSetting
        key     = f'tos_accepted:{user.id}'
        cached  = cache.get(key)
        if cached is not None:
            return cached == TermsValidator.CURRENT_TOS_VERSION

        try:
            setting = SystemSetting.objects.get(key=f'user_tos:{user.id}')
            result  = setting.value == TermsValidator.CURRENT_TOS_VERSION
            cache.set(key, setting.value, 3600)
            return result
        except Exception:
            return False

    @staticmethod
    def record_acceptance(user, tos_version: str = None, ip: str = '') -> bool:
        """Record user's TOS acceptance."""
        from api.offer_inventory.models import SystemSetting
        version = tos_version or TermsValidator.CURRENT_TOS_VERSION
        data    = json.dumps({
            'version'  : version,
            'accepted_at': timezone.now().isoformat(),
            'ip'       : ip,
        })
        SystemSetting.objects.update_or_create(
            key=f'user_tos:{user.id}',
            defaults={
                'value'      : version,
                'value_type' : 'string',
                'description': f'TOS acceptance: {data}',
            }
        )
        cache.set(f'tos_accepted:{user.id}', version, 3600)
        logger.info(f'TOS accepted: user={user.id} version={version}')
        return True

    @staticmethod
    def get_acceptance_rate() -> dict:
        """Platform-wide TOS acceptance statistics."""
        from api.offer_inventory.models import SystemSetting
        from django.contrib.auth import get_user_model
        User = get_user_model()

        total_users = User.objects.filter(is_active=True).count()
        accepted    = SystemSetting.objects.filter(
            key__startswith='user_tos:',
            value=TermsValidator.CURRENT_TOS_VERSION,
        ).count()

        return {
            'current_version' : TermsValidator.CURRENT_TOS_VERSION,
            'total_users'     : total_users,
            'accepted'        : accepted,
            'acceptance_rate' : round(accepted / max(total_users, 1) * 100, 1),
            'not_accepted'    : total_users - accepted,
        }


# ════════════════════════════════════════════════════════
# 3. PRIVACY CONSENT MANAGER
# ════════════════════════════════════════════════════════

class PrivacyConsentManager:
    """Manage user privacy consent (GDPR Article 7)."""

    CONSENT_TYPES = [
        'marketing_email',
        'marketing_push',
        'analytics_tracking',
        'data_sharing',
        'personalization',
    ]

    @staticmethod
    def record_consent(user, consent_type: str, granted: bool, ip: str = '') -> bool:
        """Record or update a user's consent decision."""
        if consent_type not in PrivacyConsentManager.CONSENT_TYPES:
            raise ValueError(f'Unknown consent type: {consent_type}')

        from api.offer_inventory.models import SystemSetting
        record = json.dumps({
            'granted'   : granted,
            'timestamp' : timezone.now().isoformat(),
            'ip'        : ip,
            'type'      : consent_type,
        })
        SystemSetting.objects.update_or_create(
            key=f'consent:{user.id}:{consent_type}',
            defaults={'value': record, 'value_type': 'json',
                      'description': f'Privacy consent: {consent_type}'}
        )
        cache.delete(f'consent:{user.id}')
        logger.info(f'Consent recorded: user={user.id} type={consent_type} granted={granted}')
        return True

    @staticmethod
    def get_user_consents(user) -> dict:
        """Get all consent records for a user."""
        from api.offer_inventory.models import SystemSetting

        cache_key = f'consent:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        records = {}
        for setting in SystemSetting.objects.filter(key__startswith=f'consent:{user.id}:'):
            try:
                consent_type = setting.key.split(':')[-1]
                data         = json.loads(setting.value)
                records[consent_type] = data
            except Exception:
                pass

        cache.set(cache_key, records, 600)
        return records

    @staticmethod
    def has_consent(user, consent_type: str) -> bool:
        """Check if user has given consent for a specific type."""
        consents = PrivacyConsentManager.get_user_consents(user)
        record   = consents.get(consent_type, {})
        return record.get('granted', False)

    @staticmethod
    def withdraw_all_consents(user):
        """Withdraw all consents (right to object)."""
        from api.offer_inventory.models import SystemSetting
        SystemSetting.objects.filter(key__startswith=f'consent:{user.id}:').delete()
        cache.delete(f'consent:{user.id}')


# ════════════════════════════════════════════════════════
# 4. KYC VERIFICATION (detailed)
# ════════════════════════════════════════════════════════

class KYCVerificationService:
    """Full KYC verification workflow."""

    @staticmethod
    def submit_kyc(user, id_type: str, id_number: str,
                    front_url: str, back_url: str, selfie_url: str) -> object:
        """Submit KYC documents for review."""
        from api.offer_inventory.models import UserKYC
        from api.offer_inventory.validators import validate_nid

        if id_type == 'nid':
            validate_nid(id_number)

        kyc, _ = UserKYC.objects.update_or_create(
            user=user,
            defaults={
                'id_type'    : id_type,
                'id_number'  : id_number,
                'id_front_url': front_url,
                'id_back_url' : back_url,
                'selfie_url' : selfie_url,
                'status'     : 'pending',
            }
        )
        logger.info(f'KYC submitted: user={user.id} type={id_type}')
        return kyc

    @staticmethod
    def auto_verify(kyc) -> bool:
        """
        Basic automated KYC checks before human review.
        Returns True if passes basic checks.
        """
        checks = []
        checks.append(bool(kyc.id_number))
        checks.append(bool(kyc.id_front_url))
        checks.append(bool(kyc.selfie_url))

        if id_type := kyc.id_type:
            if id_type == 'nid':
                import re
                checks.append(bool(re.fullmatch(r'\d{10}|\d{17}', kyc.id_number or '')))

        return all(checks)

    @staticmethod
    def approve(kyc, reviewer) -> bool:
        """Approve KYC and notify user."""
        from api.offer_inventory.models import UserKYC
        UserKYC.objects.filter(id=kyc.id).update(
            status     ='approved',
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )
        logger.info(f'KYC approved: user={kyc.user_id} reviewer={reviewer.id}')
        return True

    @staticmethod
    def reject(kyc, reviewer, reason: str) -> bool:
        """Reject KYC with reason."""
        from api.offer_inventory.models import UserKYC
        UserKYC.objects.filter(id=kyc.id).update(
            status       ='rejected',
            reviewed_by  =reviewer,
            reviewed_at  =timezone.now(),
            reject_reason=reason,
        )
        logger.info(f'KYC rejected: user={kyc.user_id} reason={reason}')
        return True


# ════════════════════════════════════════════════════════
# 5. AML CHECKS (re-exported from compliance_manager.py)
# ════════════════════════════════════════════════════════

class AMLService:
    """Anti-Money Laundering check service."""

    # Suspicious patterns
    LARGE_TX_THRESHOLD   = 50000    # BDT
    RAPID_TX_LIMIT       = 5        # transactions per hour
    STRUCTURING_THRESHOLD = 49000   # Just below large tx

    @classmethod
    def check_transaction(cls, user, amount, tx_type: str = 'withdrawal') -> dict:
        from api.offer_inventory.business.compliance_manager import KYCAMLChecker
        return KYCAMLChecker.check_withdrawal_aml(user, amount)

    @staticmethod
    def flag_suspicious(user, reason: str, evidence: dict = None):
        """Flag a user for AML review."""
        from api.offer_inventory.models import SuspiciousActivity
        SuspiciousActivity.objects.create(
            user      =user,
            activity  =f'aml_flag:{reason}',
            details   =evidence or {},
            risk_score=80.0,
        )
        logger.warning(f'AML flag: user={user.id} reason={reason}')


# ════════════════════════════════════════════════════════
# 6–10. DMCA, COOKIE, DISCLAIMER, TOS VERSION CONTROL
# ════════════════════════════════════════════════════════

class DMCAHandler:
    """DMCA takedown request management."""

    @staticmethod
    def submit_takedown(reporter_email: str, content_url: str,
                         description: str, original_url: str = '') -> dict:
        """Record a DMCA takedown request."""
        from api.offer_inventory.models import FeedbackTicket
        import uuid
        ticket_no = f'DMCA-{str(uuid.uuid4())[:6].upper()}'
        ticket = FeedbackTicket.objects.create(
            user_id  =None,
            ticket_no=ticket_no,
            subject  =f'DMCA Takedown: {content_url[:100]}',
            message  =(
                f'Reporter: {reporter_email}\n'
                f'Infringing URL: {content_url}\n'
                f'Original URL: {original_url}\n'
                f'Description: {description}'
            ),
            priority ='high',
        )
        logger.info(f'DMCA submitted: {ticket_no} by {reporter_email}')
        return {'ticket_no': ticket_no, 'status': 'received'}


class CookiePolicyManager:
    """Cookie consent and policy management."""

    COOKIE_CATEGORIES = ['necessary', 'analytics', 'marketing', 'preferences']

    @staticmethod
    def record_cookie_consent(user_or_session: str, categories: list, ip: str = ''):
        """Record cookie consent choices."""
        cache_key = f'cookie_consent:{user_or_session}'
        cache.set(cache_key, {
            'categories' : categories,
            'timestamp'  : timezone.now().isoformat(),
            'ip'         : ip,
        }, 86400 * 365)

    @staticmethod
    def get_consent(user_or_session: str) -> dict:
        """Get stored cookie consent."""
        return cache.get(f'cookie_consent:{user_or_session}', {})

    @staticmethod
    def has_analytics_consent(user_or_session: str) -> bool:
        """Check analytics cookie consent."""
        consent = CookiePolicyManager.get_consent(user_or_session)
        return 'analytics' in consent.get('categories', [])


class DisclaimerManager:
    """Platform disclaimers and risk disclosures."""

    DISCLAIMERS = {
        'earnings'  : 'Earnings are not guaranteed. Past performance does not indicate future results.',
        'tax'       : 'Users are responsible for their own tax obligations. Consult a tax professional.',
        'age'       : 'This platform is for users 18 years and older only.',
        'country'   : 'Availability varies by country. Some offers may not be available in your region.',
        'withdrawal': 'Withdrawal processing may take 1–5 business days.',
    }

    @classmethod
    def get_disclaimer(cls, disclaimer_type: str, language: str = 'en') -> str:
        """Get disclaimer text for a given type."""
        base = cls.DISCLAIMERS.get(disclaimer_type, '')
        if language == 'bn':
            translations = {
                'earnings': 'আয়ের কোনো গ্যারান্টি নেই। পূর্ববর্তী ফলাফল ভবিষ্যতের ফলাফল নির্দেশ করে না।',
                'age'     : 'এই প্ল্যাটফর্ম শুধুমাত্র ১৮ বছর বা তার বেশি বয়সীদের জন্য।',
            }
            return translations.get(disclaimer_type, base)
        return base

    @classmethod
    def get_all_disclaimers(cls, language: str = 'en') -> dict:
        return {k: cls.get_disclaimer(k, language) for k in cls.DISCLAIMERS}


class TOSVersionControl:
    """Terms of Service version management."""

    @staticmethod
    def get_current_version() -> str:
        return TermsValidator.CURRENT_TOS_VERSION

    @staticmethod
    def get_changelog() -> list:
        return [
            {'version': '3.0', 'date': '2025-01-01', 'changes': ['GDPR compliance update', 'Referral terms update']},
            {'version': '2.5', 'date': '2024-07-01', 'changes': ['Added Bangladesh-specific terms', 'AML policy update']},
            {'version': '2.0', 'date': '2024-01-01', 'changes': ['Initial multi-tenant terms', 'KYC requirements']},
        ]

    @staticmethod
    def notify_users_of_new_tos(new_version: str):
        """Notify all active users about TOS update."""
        from api.offer_inventory.tasks import send_bulk_notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:100000])
        send_bulk_notification.delay(
            user_ids,
            f'📋 Terms of Service Update (v{new_version})',
            'আমাদের Terms of Service আপডেট হয়েছে। নতুন শর্তাবলী পড়ুন এবং সম্মতি দিন।',
            notif_type='system',
        )
        logger.info(f'TOS update notification sent: {len(user_ids)} users for v{new_version}')
