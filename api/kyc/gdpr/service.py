# kyc/gdpr/service.py  ── WORLD #1
"""
GDPR Compliance Service.
- Right to Erasure: Delete all PII for a user
- Right of Access: Export all user data as JSON
- Consent management
- Data retention enforcement
"""
import json
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class GDPRService:

    @staticmethod
    def handle_erasure_request(user, reason='', actor=None) -> dict:
        """
        GDPR Article 17 — Right to Erasure.
        Anonymizes KYC data while preserving audit trail (legal obligation).
        Returns dict with summary of what was deleted/anonymized.
        """
        from kyc.models import KYC, KYCSubmission
        summary = {'user_id': user.id, 'anonymized': [], 'deleted': [], 'retained': []}

        # ── Anonymize KYC ─────────────────────────────────
        try:
            kyc = KYC.objects.filter(user=user).first()
            if kyc:
                kyc.full_name     = 'REDACTED'
                kyc.phone_number  = 'REDACTED'
                kyc.payment_number = 'REDACTED'
                kyc.address_line  = 'REDACTED'
                kyc.document_number = 'REDACTED'
                kyc.extracted_name = 'REDACTED'
                kyc.extracted_nid  = 'REDACTED'
                kyc.date_of_birth  = None
                kyc.extracted_dob  = None
                # Remove image files
                if kyc.document_front: kyc.document_front.delete(save=False)
                if kyc.document_back:  kyc.document_back.delete(save=False)
                if kyc.selfie_photo:   kyc.selfie_photo.delete(save=False)
                kyc.document_front = None
                kyc.document_back  = None
                kyc.selfie_photo   = None
                kyc.save()
                summary['anonymized'].append('KYC record')
        except Exception as e:
            logger.error(f"GDPR erasure KYC error: {e}")

        # ── Delete KYCSubmission images ───────────────────
        try:
            for sub in KYCSubmission.objects.filter(user=user):
                if sub.nid_front: sub.nid_front.delete(save=False)
                if sub.nid_back:  sub.nid_back.delete(save=False)
                if sub.selfie_with_note: sub.selfie_with_note.delete(save=False)
                sub.document_number = 'REDACTED'
                sub.save()
                summary['anonymized'].append(f'KYCSubmission #{sub.id}')
        except Exception as e:
            logger.error(f"GDPR erasure KYCSubmission error: {e}")

        # ── Retain audit trail (legal obligation) ────────
        summary['retained'].append('Audit trail — legal obligation under FATF Rec. 11')
        summary['retained'].append('AML screening logs — regulatory requirement')

        # ── Log the erasure itself ────────────────────────
        try:
            from kyc.models import KYCAuditTrail
            KYCAuditTrail.log(
                entity_type='kyc', entity_id=user.id, action='gdpr_erasure',
                actor=actor, description=f'GDPR erasure: {reason}', severity='high',
            )
        except Exception: pass

        logger.info(f"GDPR erasure completed for user {user.id}: {summary}")
        return summary

    @staticmethod
    def export_user_data(user) -> dict:
        """
        GDPR Article 15 — Right of Access.
        Export all KYC-related data for a user as structured JSON.
        """
        from kyc.models import KYC, KYCSubmission, KYCVerificationLog, KYCNotificationLog

        export = {
            'generated_at': timezone.now().isoformat(),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': str(user.date_joined),
            },
            'kyc_records': [],
            'kyc_submissions': [],
            'verification_logs': [],
            'notifications': [],
            'aml_screenings': [],
        }

        # KYC records
        for kyc in KYC.objects.filter(user=user):
            export['kyc_records'].append({
                'id':            kyc.id,
                'status':        kyc.status,
                'document_type': kyc.document_type,
                'risk_score':    kyc.risk_score,
                'created_at':    str(kyc.created_at),
                'verified_at':   str(kyc.verified_at) if kyc.verified_at else None,
                'expires_at':    str(kyc.expires_at)  if kyc.expires_at  else None,
            })

        # KYC submissions
        for sub in KYCSubmission.objects.filter(user=user):
            export['kyc_submissions'].append({
                'id':            sub.id,
                'status':        sub.status,
                'document_type': sub.document_type,
                'submitted_at':  str(sub.submitted_at) if sub.submitted_at else None,
            })

        # Verification logs
        for kyc in KYC.objects.filter(user=user):
            for log in kyc.kyc_kycverificationlog_tenant.all():
                export['verification_logs'].append({
                    'action':     log.action,
                    'details':    log.details,
                    'created_at': str(log.created_at),
                })

        # Notifications
        for notif in KYCNotificationLog.objects.filter(user=user):
            export['notifications'].append({
                'event_type': notif.event_type,
                'title':      notif.title,
                'sent_at':    str(notif.sent_at) if notif.sent_at else None,
            })

        # AML screenings (anonymized)
        try:
            from kyc.aml.models import PEPSanctionsScreening
            for screen in PEPSanctionsScreening.objects.filter(user=user):
                export['aml_screenings'].append({
                    'provider':      screen.provider,
                    'status':        screen.status,
                    'is_pep':        screen.is_pep,
                    'is_sanctioned': screen.is_sanctioned,
                    'screened_at':   str(screen.screened_at),
                })
        except Exception: pass

        return export

    @staticmethod
    def enforce_data_retention():
        """
        Enforce data retention policy.
        Delete old data beyond retention period.
        """
        import datetime
        from django.utils import timezone
        from kyc.models import KYCExportJob, KYCOTPLog, KYCAnalyticsSnapshot

        cutoff_5yr  = timezone.now() - datetime.timedelta(days=365*5)
        cutoff_1yr  = timezone.now() - datetime.timedelta(days=365)
        cutoff_30d  = timezone.now() - datetime.timedelta(days=30)

        deleted = {}

        # Export files older than 30 days
        d, _ = KYCExportJob.objects.filter(completed_at__lt=cutoff_30d).delete()
        deleted['export_jobs'] = d

        # OTP logs older than 1 year
        d, _ = KYCOTPLog.objects.filter(expires_at__lt=cutoff_1yr).delete()
        deleted['otp_logs'] = d

        # Analytics older than 5 years
        d, _ = KYCAnalyticsSnapshot.objects.filter(period_start__lt=cutoff_5yr).delete()
        deleted['analytics_snapshots'] = d

        logger.info(f"Data retention enforcement: {deleted}")
        return deleted
