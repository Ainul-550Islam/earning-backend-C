# api/offer_inventory/business/compliance_manager.py
"""
Compliance & Legal Manager.
GDPR, KYC/AML checks, data privacy, consent management,
ad content filtering, and regulatory reporting.
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class GDPRManager:
    """GDPR compliance — data access, deletion, portability."""

    @staticmethod
    @transaction.atomic
    def export_user_data(user) -> dict:
        """
        GDPR data export (Article 20 — Right to Portability).
        Returns all data we hold about a user.
        """
        from api.offer_inventory.models import (
            Click, Conversion, WithdrawalRequest,
            UserProfile, UserKYC, UserReferral,
            WalletAudit, AuditLog, Notification, EmailLog,
        )

        data = {
            'user': {
                'id'         : str(user.id),
                'username'   : user.username,
                'email'      : user.email,
                'date_joined': user.date_joined.isoformat(),
                'last_login' : user.last_login.isoformat() if user.last_login else None,
            },
            'profile'     : None,
            'kyc'         : None,
            'clicks'      : [],
            'conversions' : [],
            'withdrawals' : [],
            'wallet_audit': [],
            'notifications': [],
            'referrals'   : [],
        }

        # Profile
        try:
            profile = UserProfile.objects.get(user=user)
            data['profile'] = {
                'total_points': profile.total_points,
                'total_offers': profile.total_offers,
                'loyalty_level': profile.loyalty_level.name if profile.loyalty_level else None,
            }
        except Exception:
            pass

        # KYC
        try:
            kyc = UserKYC.objects.get(user=user)
            data['kyc'] = {
                'status'   : kyc.status,
                'id_type'  : kyc.id_type,
                'submitted': kyc.created_at.isoformat(),
            }
        except Exception:
            pass

        # Clicks (last 90 days)
        since = timezone.now() - timedelta(days=90)
        data['clicks'] = list(
            Click.objects.filter(user=user, created_at__gte=since)
            .values('click_token', 'ip_address', 'country_code', 'device_type', 'created_at')[:500]
        )

        # Conversions
        data['conversions'] = list(
            Conversion.objects.filter(user=user)
            .values('id', 'payout_amount', 'reward_amount', 'country_code', 'created_at')[:500]
        )

        # Withdrawals
        data['withdrawals'] = list(
            WithdrawalRequest.objects.filter(user=user)
            .values('reference_no', 'amount', 'status', 'created_at')[:200]
        )

        # Wallet audit
        data['wallet_audit'] = list(
            WalletAudit.objects.filter(user=user)
            .values('transaction_type', 'amount', 'balance_before', 'balance_after', 'created_at')[:500]
        )

        # Referrals
        data['referrals'] = list(
            UserReferral.objects.filter(referrer=user)
            .values('referred__username', 'is_converted', 'created_at')[:100]
        )

        logger.info(f'GDPR data export: user={user.id}')
        return data

    @staticmethod
    @transaction.atomic
    def delete_user_data(user, reason: str = 'gdpr_request') -> dict:
        """
        GDPR erasure (Article 17 — Right to be Forgotten).
        Anonymizes PII while preserving financial audit records.
        """
        from api.offer_inventory.models import (
            Click, UserProfile, UserKYC, DeviceFingerprint,
            HoneypotLog, SessionValidator,
        )
        from django.utils.crypto import get_random_string

        anon_username = f'deleted_{get_random_string(12)}'
        anon_email    = f'{anon_username}@deleted.invalid'

        # Anonymize user (don't delete — preserves audit trail)
        user.username   = anon_username
        user.email      = anon_email
        user.first_name = ''
        user.last_name  = ''
        user.is_active  = False
        user.save()

        # Delete PII-containing records
        deleted = {}
        deleted['fingerprints'] = DeviceFingerprint.objects.filter(user=user).delete()[0]
        deleted['kyc']          = UserKYC.objects.filter(user=user).delete()[0]
        deleted['profile']      = UserProfile.objects.filter(user=user).update(
            notification_prefs={}, preferred_currency='BDT'
        )

        # Anonymize clicks (keep for fraud analysis, remove PII)
        Click.objects.filter(user=user).update(user=None)

        logger.info(f'GDPR deletion: user={user.id} | new_username={anon_username}')
        return {'anonymized': True, 'new_username': anon_username, 'deleted': deleted}


class KYCAMLChecker:
    """KYC and Anti-Money Laundering checks."""

    # Suspicious transaction thresholds (BDT)
    LARGE_TRANSACTION_THRESHOLD = 50000    # ৫০,০০০ টাকা
    RAPID_WITHDRAWAL_LIMIT      = 3        # withdrawals in 24h
    STRUCTURING_THRESHOLD       = 49000    # Just below large transaction

    @staticmethod
    def check_withdrawal_aml(user, amount) -> dict:
        """
        AML check for withdrawals.
        Returns {'approved': bool, 'flags': list, 'risk_level': str}
        """
        from api.offer_inventory.models import WithdrawalRequest
        from decimal import Decimal

        flags = []
        since = timezone.now() - timedelta(hours=24)

        # Check 1: Large transaction
        if Decimal(str(amount)) >= KYCAMLChecker.LARGE_TRANSACTION_THRESHOLD:
            flags.append('large_transaction')

        # Check 2: Structuring (multiple transactions just below threshold)
        structuring_count = WithdrawalRequest.objects.filter(
            user=user,
            created_at__gte=since,
            amount__gte=KYCAMLChecker.STRUCTURING_THRESHOLD,
        ).count()
        if structuring_count >= 2:
            flags.append('structuring_suspected')

        # Check 3: Rapid withdrawals
        rapid_count = WithdrawalRequest.objects.filter(
            user=user, created_at__gte=since
        ).count()
        if rapid_count >= KYCAMLChecker.RAPID_WITHDRAWAL_LIMIT:
            flags.append('rapid_withdrawals')

        # Check 4: KYC required for large withdrawals
        if Decimal(str(amount)) >= 5000:
            from api.offer_inventory.models import UserKYC
            if not UserKYC.objects.filter(user=user, status='approved').exists():
                flags.append('kyc_required')

        risk_level = 'low'
        if len(flags) >= 2:
            risk_level = 'high'
        elif len(flags) == 1:
            risk_level = 'medium'

        approved = 'kyc_required' not in flags and risk_level != 'high'

        if flags:
            logger.warning(f'AML flags for user={user.id}: {flags}')

        return {'approved': approved, 'flags': flags, 'risk_level': risk_level}

    @staticmethod
    def check_kyc_status(user) -> str:
        """Returns 'approved' | 'pending' | 'rejected' | 'not_submitted'"""
        from api.offer_inventory.models import UserKYC
        try:
            kyc = UserKYC.objects.get(user=user)
            return kyc.status
        except UserKYC.DoesNotExist:
            return 'not_submitted'


class AdContentFilter:
    """
    Ad content compliance filtering.
    Blocks prohibited content categories.
    """

    PROHIBITED_KEYWORDS = [
        'gambling', 'casino', 'lottery', 'bet', 'wager',
        'adult', 'xxx', 'porn', 'sex',
        'drug', 'cocaine', 'heroin', 'meth',
        'weapon', 'gun', 'explosive',
        'scam', 'fraud', 'fake',
    ]

    PROHIBITED_CATEGORIES = [
        'gambling', 'adult_content', 'illegal_substances',
        'weapons', 'hate_speech', 'malware',
    ]

    @classmethod
    def is_compliant(cls, title: str, description: str,
                      category: str = '') -> dict:
        """
        Check if offer content is compliant.
        Returns {'compliant': bool, 'violations': list}
        """
        violations = []
        text = f'{title} {description}'.lower()

        for keyword in cls.PROHIBITED_KEYWORDS:
            if keyword in text:
                violations.append(f'prohibited_keyword:{keyword}')

        if category.lower() in cls.PROHIBITED_CATEGORIES:
            violations.append(f'prohibited_category:{category}')

        return {
            'compliant' : len(violations) == 0,
            'violations': violations,
        }

    @staticmethod
    def auto_reject_offer(offer) -> bool:
        """Auto-reject non-compliant offers."""
        from api.offer_inventory.models import Offer, OfferLog
        result = AdContentFilter.is_compliant(
            title      =offer.title,
            description=offer.description,
        )
        if not result['compliant']:
            Offer.objects.filter(id=offer.id).update(status='rejected')
            OfferLog.objects.create(
                offer     =offer,
                old_status=offer.status,
                new_status='rejected',
                note      =f'Auto-rejected: {result["violations"]}',
            )
            logger.warning(f'Offer auto-rejected: {offer.id} | {result["violations"]}')
            return True
        return False
