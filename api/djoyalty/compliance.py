# api/djoyalty/compliance.py
"""
Djoyalty Compliance -- GDPR, PDPA, Bangladesh data privacy compliance।
Right to be forgotten, data access, consent management।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class GDPRComplianceManager:
    """
    GDPR / PDPA compliance operations।
    Handles: data access requests, right to deletion, consent tracking।

    Bangladesh context: Digital Security Act 2018 + PDPA (draft 2023)।
    """

    @staticmethod
    def handle_data_access_request(customer) -> dict:
        """
        Right to Access -- export all customer data।
        Returns complete data as dict (caller saves/sends to customer)।
        """
        from .data_export import LoyaltyDataExporter
        from .models.audit import AdminAuditLog

        try:
            data = LoyaltyDataExporter.export_customer_data_json(customer)

            AdminAuditLog.log(
                action='gdpr_data_access_request',
                category='customer',
                customer=customer,
                description='Customer data access request fulfilled',
                severity='info',
            )
            logger.info('GDPRComplianceManager: data access fulfilled for %s', customer.code)
            return {'success': True, 'data': data}
        except Exception as e:
            logger.error('GDPRComplianceManager.handle_data_access_request error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def handle_deletion_request(customer) -> dict:
        """
        Right to be Forgotten -- anonymize customer data।
        NOTE: We anonymize (don't delete) to maintain referential integrity।
        Points ledger and audit trail are retained per financial regulations।
        """
        from .models.audit import AdminAuditLog

        try:
            # Anonymize PII
            customer_code = customer.code  # Keep code for audit trail
            customer.email = None
            customer.phone = None
            customer.firstname = 'ANONYMIZED'
            customer.lastname = 'ANONYMIZED'
            if hasattr(customer, 'date_of_birth'):
                customer.date_of_birth = None
            if hasattr(customer, 'referral_code'):
                customer.referral_code = None
            customer.is_active = False
            customer.save()

            # Anonymize consent records
            try:
                from .models.family_eco import CustomerConsent
                CustomerConsent.objects.filter(customer=customer).update(
                    consent_text='ANONYMIZED',
                )
            except Exception:
                pass

            AdminAuditLog.log(
                action='gdpr_deletion_request',
                category='customer',
                customer=customer,
                description=f'Customer {customer_code} anonymized per deletion request',
                severity='critical',
                old_value={'customer_code': customer_code},
            )
            logger.info('GDPRComplianceManager: deletion fulfilled for %s', customer_code)
            return {'success': True, 'message': f'Customer {customer_code} data anonymized.'}

        except Exception as e:
            logger.error('GDPRComplianceManager.handle_deletion_request error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def record_consent(customer, consent_type: str, value: bool,
                        ip_address: str = '', channel: str = 'web') -> bool:
        """Record customer consent action।"""
        try:
            from .models.family_eco import CustomerConsent
            CustomerConsent.objects.create(
                customer=customer,
                tenant=customer.tenant,
                consent_type=consent_type,
                consent_given=value,
                ip_address=ip_address or '',
                channel=channel,
                consent_text=f'{consent_type}: {"granted" if value else "withdrawn"} at {timezone.now().isoformat()}',
            )
            logger.info('Consent recorded: %s for %s = %s', consent_type, customer.code, value)
            return True
        except Exception as e:
            logger.error('GDPRComplianceManager.record_consent error: %s', e)
            return False

    @staticmethod
    def get_consent_history(customer) -> list:
        """Get full consent history for customer।"""
        try:
            from .models.family_eco import CustomerConsent
            return list(
                CustomerConsent.objects.filter(customer=customer)
                .order_by('-created_at')
                .values('consent_type', 'consent_given', 'created_at', 'channel')
            )
        except Exception:
            return []

    @staticmethod
    def check_marketing_consent(customer) -> bool:
        """Check if customer has consented to marketing communications।"""
        try:
            from .models.family_eco import CustomerConsent
            latest = CustomerConsent.objects.filter(
                customer=customer,
                consent_type='marketing',
            ).order_by('-created_at').first()
            if latest:
                return latest.consent_given
        except Exception:
            pass
        return bool(getattr(customer, 'newsletter', False))

    @staticmethod
    def check_sms_consent(customer) -> bool:
        """Check if customer has consented to SMS communications।"""
        try:
            from .models.family_eco import CustomerConsent
            latest = CustomerConsent.objects.filter(
                customer=customer,
                consent_type='sms',
            ).order_by('-created_at').first()
            if latest:
                return latest.consent_given
        except Exception:
            pass
        return bool(getattr(customer, 'sms_opt_in', False))


class DataRetentionPolicy:
    """
    Data retention policies per data category।
    Bangladesh: financial records must be kept 7 years।
    """

    # Retention periods in days
    PERIODS = {
        'audit_logs':       365 * 7,   # 7 years (financial regulation)
        'points_ledger':    365 * 7,   # 7 years
        'cashout_records':  365 * 7,   # 7 years
        'notifications':    90,        # 3 months
        'session_data':     30,        # 30 days
        'analytics_raw':    365,       # 1 year
        'receipt_images':   90,        # 3 months (after processing)
        'postback_logs':    365,       # 1 year
    }

    @classmethod
    def should_retain(cls, record_type: str, record_age_days: int) -> bool:
        """Check if a record should be retained।"""
        max_days = cls.PERIODS.get(record_type, 365)
        return record_age_days <= max_days

    @classmethod
    def get_retention_days(cls, record_type: str) -> int:
        return cls.PERIODS.get(record_type, 365)

    @classmethod
    def run_retention_cleanup(cls, dry_run: bool = True) -> dict:
        """Run data retention cleanup based on policies।"""
        from datetime import timedelta
        results = {}

        # Notifications cleanup (90 days)
        try:
            from .models.notifications import NotificationCenter
            cutoff = timezone.now() - timedelta(days=cls.PERIODS['notifications'])
            qs = NotificationCenter.objects.filter(
                is_read=True, created_at__lt=cutoff
            )
            count = qs.count()
            if not dry_run:
                qs.delete()
            results['notifications'] = {'eligible': count, 'deleted': count if not dry_run else 0}
        except Exception as e:
            results['notifications'] = {'error': str(e)}

        # Receipt scan raw data (90 days)
        try:
            from .models.family_eco import ReceiptScan
            cutoff = timezone.now() - timedelta(days=cls.PERIODS['receipt_images'])
            qs = ReceiptScan.objects.filter(
                submitted_at__lt=cutoff,
                status__in=['approved', 'rejected', 'fraud_suspected'],
            )
            count = qs.count()
            if not dry_run:
                qs.update(raw_ocr_text='', items_detected=[])
            results['receipt_raw_data'] = {'eligible': count, 'cleared': count if not dry_run else 0}
        except Exception as e:
            results['receipt_raw_data'] = {'error': str(e)}

        logger.info('DataRetentionPolicy.run_retention_cleanup: %s (dry_run=%s)', results, dry_run)
        return results
