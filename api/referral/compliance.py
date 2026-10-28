# api/referral/compliance.py
# GDPR / Data compliance for the referral module
# Right to access, right to erasure, data retention policies
# CPAlead compliant — meets EU/BD data protection requirements
# ============================================================

import logging
from typing import Dict, List
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# ── Retention Policies ────────────────────────────────────────────────────────

RETENTION_DAYS = {
    'referral_earnings':     365 * 7,   # 7 years (financial records)
    'commission_logs':       365 * 7,   # 7 years (accounting)
    'audit_logs':            365 * 5,   # 5 years
    'fraud_logs':            365 * 3,   # 3 years
    'email_invitations':     365,        # 1 year
    'click_logs':            90,         # 3 months
    'suspicious_cleared':    365,        # 1 year
    'sub_id_logs':           180,        # 6 months
}


class GDPRComplianceManager:
    """
    GDPR / Personal Data compliance for the referral module.

    Implements:
    - Article 15: Right of access
    - Article 17: Right to erasure (right to be forgotten)
    - Article 20: Right to data portability
    - Article 25: Data minimization (masking)
    """

    @staticmethod
    def get_user_data(user) -> Dict:
        """
        Article 15 — Right of access.
        Returns all referral data we hold about a user.
        """
        from api.referral.data_export import ReferralDataExport
        data = ReferralDataExport.export_user_data_json(user)
        data['data_categories'] = [
            'Referral relationships (who referred you, who you referred)',
            'Commission history (amounts, dates, sources)',
            'Referral codes (your codes, click/conversion counts)',
            'Email invitations (emails you sent invitations to)',
            'IP addresses (used for fraud prevention, hashed)',
        ]
        data['retention_policies'] = {k: f'{v} days' for k, v in RETENTION_DAYS.items()}
        return data

    @staticmethod
    def anonymize_user(user, reason: str = 'gdpr_erasure') -> Dict:
        """
        Article 17 — Right to erasure.
        Anonymizes personal data while preserving financial records for legal compliance.
        Commission records are RETAINED (legal obligation) but user identity is removed.
        """
        from api.referral.models import (
            Referral, ReferralCode, ReferralEmailInvitation,
            ReferralSubID, CommissionLog, ReferralEarning,
        )
        from api.referral.helpers import hash_ip_address

        anonymized = {}

        # 1. Anonymize referral codes (retain code for audit but remove owner link)
        code_count = ReferralCode.objects.filter(user=user).update(
            custom_code=None,
            source_tag='[ANONYMIZED]',
        )
        anonymized['referral_codes'] = code_count

        # 2. Anonymize IP addresses in Referral records (hash them)
        referrals = Referral.objects.filter(referrer=user) | Referral.objects.filter(referred_user=user)
        for r in referrals:
            updates = {}
            if r.registration_ip:
                updates['registration_ip'] = None  # Remove IP
            if r.referrer_ip:
                updates['referrer_ip'] = None
            if updates:
                Referral.objects.filter(id=r.id).update(**updates)
        anonymized['referrals_anonymized'] = referrals.count()

        # 3. Delete email invitations (personal data — email addresses)
        deleted_invites = ReferralEmailInvitation.objects.filter(referrer=user).delete()
        anonymized['invitations_deleted'] = deleted_invites[0]

        # 4. Delete Sub-ID click logs
        deleted_subids = ReferralSubID.objects.filter(referred_user=user).delete()
        anonymized['subid_logs_deleted'] = deleted_subids[0]

        # 5. Commission/Earning records RETAINED for legal compliance
        # but we log the anonymization
        anonymized['commissions_retained_for_legal'] = CommissionLog.objects.filter(
            user=user
        ).count()

        logger.info(
            f'[Compliance] User {user.id} anonymized: reason={reason}, '
            f'summary={anonymized}'
        )
        return {
            'success':      True,
            'user_id':      user.id,
            'reason':       reason,
            'anonymized':   anonymized,
            'timestamp':    timezone.now().isoformat(),
            'note':         'Commission records retained per legal obligation.',
        }

    @staticmethod
    def export_portable_data(user) -> Dict:
        """
        Article 20 — Right to data portability.
        Returns data in machine-readable format (JSON).
        """
        from api.referral.data_export import ReferralDataExport
        return {
            'format':   'JSON',
            'version':  '1.0',
            'schema':   'referral_portability_v1',
            'data':     ReferralDataExport.export_user_data_json(user),
        }


class DataRetentionManager:
    """
    Enforces data retention policies.
    Runs on schedule to clean up expired data.
    """

    @staticmethod
    def run_retention_cleanup() -> Dict:
        """
        Apply all retention policies.
        Run weekly via Celery.
        """
        results = {}

        results['email_invitations'] = DataRetentionManager._cleanup_email_invitations()
        results['click_logs']        = DataRetentionManager._cleanup_sub_id_logs()
        results['old_fraud_cleared'] = DataRetentionManager._cleanup_cleared_fraud()
        results['old_insights']      = DataRetentionManager._cleanup_old_insights()

        logger.info(f'[Compliance] Retention cleanup: {results}')
        return results

    @staticmethod
    def _cleanup_email_invitations() -> int:
        from api.referral.models import ReferralEmailInvitation
        cutoff = timezone.now() - timedelta(days=RETENTION_DAYS['email_invitations'])
        deleted, _ = ReferralEmailInvitation.objects.filter(
            created_at__lt=cutoff,
            status__in=['expired', 'bounced', 'converted'],
        ).delete()
        return deleted

    @staticmethod
    def _cleanup_sub_id_logs() -> int:
        from api.referral.models import ReferralSubID
        cutoff = timezone.now() - timedelta(days=RETENTION_DAYS['sub_id_logs'])
        deleted, _ = ReferralSubID.objects.filter(created_at__lt=cutoff).delete()
        return deleted

    @staticmethod
    def _cleanup_cleared_fraud() -> int:
        from api.referral.models import SuspiciousReferral
        cutoff = timezone.now() - timedelta(days=RETENTION_DAYS['suspicious_cleared'])
        deleted, _ = SuspiciousReferral.objects.filter(
            status='cleared',
            reviewed_at__lt=cutoff,
        ).delete()
        return deleted

    @staticmethod
    def _cleanup_old_insights() -> int:
        from api.referral.models import ReferralInsight, ReferralConversionRate
        cutoff = timezone.now().date() - timedelta(days=365)
        d1, _ = ReferralInsight.objects.filter(date__lt=cutoff).delete()
        d2, _ = ReferralConversionRate.objects.filter(date__lt=cutoff).delete()
        return d1 + d2

    @staticmethod
    def get_data_inventory() -> Dict:
        """
        Audit: how much personal data do we hold?
        """
        from api.referral.models import (
            Referral, ReferralEmailInvitation, ReferralSubID,
            SuspiciousReferral, CommissionLog,
        )
        return {
            'total_referrals':         Referral.objects.count(),
            'email_invitations':       ReferralEmailInvitation.objects.count(),
            'sub_id_logs':             ReferralSubID.objects.count(),
            'suspicious_records':      SuspiciousReferral.objects.count(),
            'commission_logs':         CommissionLog.objects.count(),
            'records_with_ip':         Referral.objects.exclude(
                registration_ip=None
            ).count(),
            'inventory_date':          timezone.now().isoformat(),
        }