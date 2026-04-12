# api/offer_inventory/compliance_legal/tos_version_control.py
"""TOS Version Control — Terms of Service version management and notification."""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

CURRENT_VERSION = '3.0'

TOS_CHANGELOG = [
    {
        'version': '3.0',
        'date'   : '2025-01-01',
        'changes': [
            'GDPR compliance update — data export and erasure rights',
            'Referral terms updated — commission structure clarified',
            'AML policy added — withdrawal monitoring',
            'Bangladesh-specific withdrawal terms',
        ],
    },
    {
        'version': '2.5',
        'date'   : '2024-07-01',
        'changes': [
            'Bangladesh-specific legal terms added',
            'AML policy update for large withdrawals',
            'KYC requirements for withdrawals above ৳500',
        ],
    },
    {
        'version': '2.0',
        'date'   : '2024-01-01',
        'changes': [
            'Multi-tenant terms of service',
            'KYC requirements introduced',
            'Fraud policy expanded',
        ],
    },
    {
        'version': '1.0',
        'date'   : '2023-06-01',
        'changes': ['Initial Terms of Service'],
    },
]


class TOSVersionControl:
    """Manage TOS versions, track acceptance, notify users of updates."""

    @staticmethod
    def get_current_version() -> str:
        return CURRENT_VERSION

    @staticmethod
    def get_changelog() -> list:
        return TOS_CHANGELOG

    @staticmethod
    def get_version_diff(from_version: str, to_version: str) -> list:
        """Get changes between two TOS versions."""
        changes = []
        collecting = False
        for entry in TOS_CHANGELOG:
            if entry['version'] == to_version:
                collecting = True
            if collecting:
                changes.extend(entry['changes'])
            if entry['version'] == from_version:
                break
        return changes

    @staticmethod
    def users_needing_acceptance() -> list:
        """Get users who haven't accepted the current TOS."""
        from api.offer_inventory.models import SystemSetting
        from django.contrib.auth import get_user_model
        User = get_user_model()
        accepted_ids = set(
            SystemSetting.objects.filter(
                key__startswith='user_tos:',
                value=CURRENT_VERSION,
            ).values_list('key', flat=True)
        )
        accepted_user_ids = set()
        for key in accepted_ids:
            try:
                uid = key.split('user_tos:')[1]
                accepted_user_ids.add(uid)
            except Exception:
                pass
        return list(
            User.objects.filter(is_active=True)
            .exclude(id__in=accepted_user_ids)
            .values_list('id', flat=True)[:100000]
        )

    @staticmethod
    def notify_users_of_update(new_version: str = None) -> dict:
        """Notify all active users about a TOS update."""
        from api.offer_inventory.tasks import send_bulk_notification
        from django.contrib.auth import get_user_model
        User      = get_user_model()
        version   = new_version or CURRENT_VERSION
        user_ids  = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:100000])

        send_bulk_notification.delay(
            user_ids,
            f'📋 Terms of Service Updated (v{version})',
            'আমাদের Terms of Service আপডেট হয়েছে। অনুগ্রহ করে নতুন শর্তাবলী পড়ুন এবং সম্মতি দিন।',
            'system',
        )
        logger.info(f'TOS update notification sent: {len(user_ids)} users for v{version}')
        return {'notified': len(user_ids), 'version': version}

    @staticmethod
    def acceptance_rate() -> dict:
        """Platform-wide TOS acceptance statistics."""
        from .terms_validator import TermsValidator
        return TermsValidator.get_acceptance_stats()
