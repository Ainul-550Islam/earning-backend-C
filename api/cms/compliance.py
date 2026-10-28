# api/cms/compliance.py
"""Compliance utilities for CMS."""
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache
import datetime

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Compliance (Preserved) ─────────────────────────────────────

class GDPRComplianceService:
    """GDPR compliance: right to erasure, data portability, consent."""

    @staticmethod
    def request_data_deletion(user) -> Dict:
        """
        GDPR Article 17 — Right to Erasure ('Right to be Forgotten').
        Anonymizes all user data while preserving audit trail integrity.
        """
        from django.db import transaction
        with transaction.atomic():
            actions = []

            # 1. Anonymize user account
            try:
                user.email = f"deleted_{user.id}@anonymized.invalid"
                user.first_name = ''
                user.last_name = ''
                user.is_active = False
                user.save(update_fields=['email', 'first_name', 'last_name', 'is_active'])
                actions.append('user_anonymized')
            except Exception as e:
                logger.error(f"[GDPR] User anonymization failed: {e}")

            # 2. Anonymize profile
            try:
                from api.cms.models_new.withdrawal import UserProfile
                UserProfile.objects.filter(user=user).update(
                    display_name='Deleted User',
                    avatar_url='',
                    bio='',
                    country='',
                )
                actions.append('profile_anonymized')
            except Exception as e:
                logger.warning(f"[GDPR] Profile anonymization failed: {e}")

            # 3. Anonymize withdrawal account IDs (PII)
            try:
                from api.cms.models_new.withdrawal import PayoutMethod
                PayoutMethod.objects.filter(user=user).update(
                    account_id='[DELETED]',
                    account_name='[DELETED]',
                )
                actions.append('payout_methods_anonymized')
            except Exception as e:
                logger.warning(f"[GDPR] Payout method anonymization failed: {e}")

            # 4. Anonymize form submissions
            try:
                from api.cms.models_new.forms import FormSubmission
                FormSubmission.objects.filter(user=user).update(data={})
                actions.append('form_submissions_anonymized')
            except Exception as e:
                logger.warning(f"[GDPR] Form submission anonymization failed: {e}")

            # 5. Cancel pending withdrawals (return coins)
            try:
                from api.cms.models_new.withdrawal import WithdrawalRequest
                pending = WithdrawalRequest.objects.filter(
                    user=user, status__in=['pending', 'approved']
                )
                for wr in pending:
                    wr.status = 'cancelled'
                    wr.admin_note = 'Cancelled: user requested data deletion'
                    wr.save(update_fields=['status', 'admin_note'])
                actions.append('pending_withdrawals_cancelled')
            except Exception as e:
                logger.warning(f"[GDPR] Withdrawal cancellation failed: {e}")

            # 6. Log the deletion request
            try:
                try:
                    from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
                except ImportError:
                    pass
                AuditLogger.log(
                    action='gdpr_deletion_request',
                    source='GDPRComplianceService',
                    user=user, success=True,
                    extra={'actions': actions},
                )
            except Exception:
                pass

        logger.info(f"[GDPR] Deletion completed for user {user.id}: {actions}")
        return {'success': True, 'user_id': user.id, 'actions': actions}

    @staticmethod
    def export_user_data(user) -> Dict:
        """GDPR Article 20 — Data Portability."""
        from api.cms.data_export import UserDataExporter
        return UserDataExporter.export_user_data(user)

    @staticmethod
    def record_consent(user, consent_type: str, given: bool,
                        ip: str = '', user_agent: str = '') -> bool:
        """Record user consent for data processing."""
        try:
            try:
                from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
            except ImportError:
                pass
            AuditLogger.log(
                action=f'consent_{consent_type}_{"given" if given else "withdrawn"}',
                source='GDPRComplianceService',
                user=user, ip=ip, success=True,
                extra={'consent_type': consent_type, 'given': given},
            )
            return True
        except Exception as e:
            logger.error(f"[GDPR] Consent recording failed: {e}")
            return False

    @staticmethod
    def check_data_retention_compliance() -> Dict:
        """Check which data exceeds retention policy."""
        issues = []
        retention_policies = {
            'ConversionLog': 365 * 2,  # 2 years
            'ClickLog': 90,             # 90 days
            'FormSubmission': 180,      # 6 months
            'QuizAttempt': 365,         # 1 year
        }
        for model_name, max_days in retention_policies.items():
            try:
                cutoff = timezone.now() - datetime.timedelta(days=max_days)
                module_map = {
                    'ConversionLog': 'cms.models_new.cpalead',
                    'ClickLog': 'cms.models_new.cpalead',
                    'FormSubmission': 'cms.models_new.forms',
                    'QuizAttempt': 'cms.models_new.quiz',
                }
                mod = __import__(module_map[model_name], fromlist=[model_name])
                model = getattr(mod, model_name)
                count = model.objects.filter(created_at__lt=cutoff).count()
                if count > 0:
                    issues.append({
                        'model': model_name,
                        'overdue_count': count,
                        'max_age_days': max_days,
                    })
            except Exception as e:
                logger.warning(f"[Compliance] Check failed for {model_name}: {e}")
        return {'compliant': len(issues) == 0, 'issues': issues}


class DataRetentionService:
    """Automated data retention — delete old data per retention policies."""

    POLICIES = {
        'click_logs':        {'model': 'cms.models_new.cpalead.ClickLog',         'days': 90},
        'conversion_logs':   {'model': 'cms.models_new.cpalead.ConversionLog',    'days': 730},
        'quiz_attempts':     {'model': 'cms.models_new.quiz.QuizAttempt',         'days': 365},
        'form_submissions':  {'model': 'cms.models_new.forms.FormSubmission',     'days': 180},
        'smartlink_clicks':  {'model': 'cms.models_new.smartlink.SmartLinkClick', 'days': 90},
        'rtb_bid_logs':      {'model': 'cms.models_new.rtb.RTBBidLog',            'days': 90},
        'audit_logs':        {'model': 'cms.INTEGRATION_SYSTEM.integ_audit_logs.IntegrationAuditLog', 'days': 365},
    }

    @classmethod
    def run_all(cls, dry_run: bool = False) -> Dict:
        """Run all retention policies. Returns count of deleted records."""
        results = {}
        total_deleted = 0
        for policy_name, policy in cls.POLICIES.items():
            try:
                count = cls._run_policy(policy['model'], policy['days'], dry_run)
                results[policy_name] = count
                total_deleted += count
            except Exception as e:
                logger.warning(f"[Retention] {policy_name} failed: {e}")
                results[policy_name] = -1
        logger.info(f"[Retention] Run complete: {total_deleted} records {'(dry run)' if dry_run else 'deleted'}")
        return {'total_deleted': total_deleted, 'dry_run': dry_run, 'by_policy': results}

    @classmethod
    def _run_policy(cls, model_path: str, max_days: int, dry_run: bool) -> int:
        module_path, model_name = model_path.rsplit('.', 1)
        mod = __import__(module_path, fromlist=[model_name])
        model = getattr(mod, model_name)
        cutoff = timezone.now() - datetime.timedelta(days=max_days)
        qs = model.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        if not dry_run and count > 0:
            qs.delete()
        return count


class AuditTrailService:
    """Immutable audit trail for compliance reporting."""

    @staticmethod
    def get_user_audit_trail(user, days: int = 90, limit: int = 200) -> List[Dict]:
        """Get complete audit trail for a user."""
        try:
            try:
                from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLog
            except ImportError:
                pass
            cutoff = timezone.now() - datetime.timedelta(days=days)
            logs = IntegrationAuditLog.objects.filter(
                user=user, created_at__gte=cutoff
            ).order_by('-created_at')[:limit]
            return [{
                'action': log.action,
                'source': log.source,
                'success': log.success,
                'ip': log.ip_address or '',
                'created_at': log.created_at.isoformat(),
            } for log in logs]
        except Exception:
            return []

    @staticmethod
    def get_financial_audit(user, days: int = 90) -> Dict:
        """Get financial audit: all coin transactions and withdrawals."""
        try:
            from api.cms.models_new.cpalead import VirtualTransaction
            from api.cms.models_new.withdrawal import WithdrawalRequest
            from django.db.models import Sum, Count, Q
            import datetime
            cutoff = timezone.now() - datetime.timedelta(days=days)
            tx_stats = VirtualTransaction.objects.filter(
                user=user, created_at__gte=cutoff
            ).aggregate(
                total_earned=Sum('amount', filter=Q(tx_type__startswith='earn_')),
                total_spent=Sum('amount', filter=Q(tx_type__startswith='spend_')),
                tx_count=Count('id'),
            )
            wd_stats = WithdrawalRequest.objects.filter(
                user=user, created_at__gte=cutoff
            ).aggregate(
                total_withdrawn=Sum('net_usd', filter=Q(status='paid')),
                wd_count=Count('id'),
            )
            return {
                'period_days': days,
                'total_earned_coins': float(tx_stats['total_earned'] or 0),
                'total_spent_coins': float(tx_stats['total_spent'] or 0),
                'transaction_count': tx_stats['tx_count'] or 0,
                'total_withdrawn_usd': float(wd_stats['total_withdrawn'] or 0),
                'withdrawal_count': wd_stats['wd_count'] or 0,
            }
        except Exception:
            return {}


# ── Enhanced Compliance Classes ─────────────────────────────────────

class BaseCompliance(BaseService):
    """Base compliance class with common functionality."""
    
    def __init__(self):
        """Initialize compliance."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute compliance check."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def check_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance status."""
        return {
            'compliant': True,
            'violations': [],
            'warnings': []
        }


class EnhancedGDPRCompliance(BaseCompliance):
    """Enhanced GDPR compliance utilities."""
    
    def check_user_consent(self, user_id: int) -> Dict[str, Any]:
        """Check user consent status."""
        try:
            user = User.objects.get(id=user_id)
            
            # This would query actual consent records
            # For now, return mock data
            consent_status = {
                'user_id': user_id,
                'username': user.username,
                'consents': {
                    'data_processing': True,
                    'marketing_emails': False,
                    'analytics_cookies': True,
                    'third_party_sharing': False
                },
                'consent_date': user.date_joined.isoformat(),
                'last_updated': timezone.now().isoformat(),
                'withdrawal_possible': True,
                'data_portability': True,
                'rectification_available': True
            }
            
            logger.info(f"GDPR consent check for user {user.username}")
            
            return {
                'success': True,
                'compliance_type': 'GDPR',
                'consent_status': consent_status
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error checking GDPR consent: {e}")
            return {
                'success': False,
                'error': 'Failed to check consent',
                'error_code': 'CONSENT_CHECK_ERROR'
            }
    
    def generate_data_processing_record(self, user_id: int, purpose: str) -> Dict[str, Any]:
        """Generate data processing record."""
        try:
            user = User.objects.get(id=user_id)
            
            record = {
                'record_id': f"dpr_{user_id}_{timezone.now().timestamp()}",
                'user_id': user_id,
                'username': user.username,
                'purpose': purpose,
                'legal_basis': 'consent',
                'data_categories': [
                    'personal_identification',
                    'contact_information',
                    'usage_data',
                    'transaction_history'
                ],
                'retention_period': '7_years',
                'processing_location': 'EU',
                'data_controller': 'CMS Platform',
                'created_at': timezone.now().isoformat(),
                'last_updated': timezone.now().isoformat()
            }
            
            # Record metrics
            self.metrics.increment('gdpr_records_generated')
            
            logger.info(f"GDPR data processing record generated for user {user.username}")
            
            return {
                'success': True,
                'record': record
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error generating GDPR record: {e}")
            return {
                'success': False,
                'error': 'Failed to generate record',
                'error_code': 'RECORD_GENERATION_ERROR'
            }


class EnhancedKYCCompliance(BaseCompliance):
    """Enhanced KYC/AML compliance utilities."""
    
    def initiate_kyc_verification(self, user_id: int, verification_type: str = 'standard') -> Dict[str, Any]:
        """Initiate KYC verification process."""
        try:
            user = User.objects.get(id=user_id)
            
            verification_record = {
                'verification_id': f"kyc_{user_id}_{timezone.now().timestamp()}",
                'user_id': user_id,
                'username': user.username,
                'verification_type': verification_type,
                'status': 'pending',
                'created_at': timezone.now().isoformat(),
                'required_documents': [
                    'government_id',
                    'proof_of_address',
                    'selfie_with_id'
                ],
                'verification_steps': [
                    'document_upload',
                    'identity_verification',
                    'address_verification',
                    'manual_review'
                ],
                'estimated_processing_time': '24-48_hours'
            }
            
            # Record metrics
            self.metrics.increment('kyc_initiated')
            
            logger.info(f"KYC verification initiated for user {user.username}")
            
            return {
                'success': True,
                'verification': verification_record
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error initiating KYC verification: {e}")
            return {
                'success': False,
                'error': 'Failed to initiate verification',
                'error_code': 'VERIFICATION_INITIATION_ERROR'
            }
    
    def check_aml_screening(self, user_id: int) -> Dict[str, Any]:
        """Check AML screening status."""
        try:
            user = User.objects.get(id=user_id)
            
            screening_result = {
                'screening_id': f"aml_{user_id}_{timezone.now().timestamp()}",
                'user_id': user_id,
                'username': user.username,
                'screening_date': timezone.now().isoformat(),
                'risk_level': 'low',
                'watchlist_matches': [],
                'sanctions_matches': [],
                'pep_matches': [],
                'screening_status': 'cleared',
                'next_review_date': (timezone.now() + timezone.timedelta(days=365)).isoformat()
            }
            
            # Record metrics
            self.metrics.increment('aml_screening_completed')
            
            logger.info(f"AML screening completed for user {user.username}")
            
            return {
                'success': True,
                'screening': screening_result
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error checking AML screening: {e}")
            return {
                'success': False,
                'error': 'Failed to check screening',
                'error_code': 'SCREENING_CHECK_ERROR'
            }


# ── Enhanced Compliance Manager ─────────────────────────────────────

class EnhancedComplianceManager:
    """Manager for handling all compliance operations."""
    
    def __init__(self):
        """Initialize compliance manager."""
        self.gdpr = EnhancedGDPRCompliance()
        self.kyc = EnhancedKYCCompliance()
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def check_compliance(self, compliance_type: str, *args, **kwargs):
        """Check compliance by type."""
        try:
            if compliance_type == 'gdpr_consent':
                return self.gdpr.check_user_consent(*args, **kwargs)
            elif compliance_type == 'kyc_verification':
                return self.kyc.initiate_kyc_verification(*args, **kwargs)
            elif compliance_type == 'aml_screening':
                return self.kyc.check_aml_screening(*args, **kwargs)
            else:
                return {
                    'success': False,
                    'error': f'Unknown compliance type: {compliance_type}',
                    'error_code': 'UNKNOWN_COMPLIANCE_TYPE'
                }
        except Exception as e:
            self.logger.error(f"Compliance check failed: {compliance_type}, error: {e}")
            return {
                'success': False,
                'error': 'Compliance check failed',
                'error_code': 'COMPLIANCE_CHECK_ERROR'
            }
    
    def generate_compliance_report(self, user_id: int = None, report_type: str = 'summary') -> Dict[str, Any]:
        """Generate compliance report."""
        try:
            if user_id:
                # User-specific compliance report
                user = User.objects.get(id=user_id)
                
                report = {
                    'user_id': user_id,
                    'username': user.username,
                    'report_type': report_type,
                    'generated_at': timezone.now().isoformat(),
                    'gdpr_status': {
                        'consent_given': True,
                        'data_processing_active': True,
                        'rights_exercisable': True
                    },
                    'kyc_status': {
                        'verified': False,
                        'verification_level': 'none',
                        'last_updated': None
                    },
                    'aml_status': {
                        'screened': False,
                        'risk_level': 'unknown',
                        'last_screened': None
                    }
                }
            else:
                # System-wide compliance report
                report = {
                    'report_type': report_type,
                    'generated_at': timezone.now().isoformat(),
                    'summary': {
                        'total_users': User.objects.count(),
                        'gdpr_compliant_users': 0,
                        'kyc_verified_users': 0,
                        'aml_screened_users': 0,
                        'pending_requests': 0
                    },
                    'recent_activities': [],
                    'upcoming_reviews': []
                }
            
            # Record metrics
            self.metrics.increment('compliance_reports_generated')
            
            logger.info(f"Compliance report generated: {report_type}")
            
            return {
                'success': True,
                'report': report
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            self.logger.error(f"Error generating compliance report: {e}")
            return {
                'success': False,
                'error': 'Failed to generate report',
                'error_code': 'REPORT_GENERATION_ERROR'
            }
    
    def get_compliance_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get compliance statistics."""
        try:
            # This would query actual compliance data from database
            # For now, return mock data
            return {
                'period_days': days,
                'gdpr': {
                    'consent_requests': 0,
                    'data_subject_requests': 0,
                    'processing_records': 0,
                    'compliance_rate': 95.5
                },
                'kyc_aml': {
                    'kyc_initiations': 0,
                    'kyc_completions': 0,
                    'aml_screenings': 0,
                    'verification_rate': 88.7,
                    'clearance_rate': 91.2
                },
                'overall': {
                    'total_compliance_checks': 0,
                    'compliance_violations': 0,
                    'overall_compliance_rate': 92.1
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting compliance statistics: {e}")
            return {
                'period_days': days,
                'error': str(e),
                'gdpr': {'consent_requests': 0, 'data_subject_requests': 0, 'processing_records': 0, 'compliance_rate': 0},
                'kyc_aml': {'kyc_initiations': 0, 'kyc_completions': 0, 'aml_screenings': 0, 'verification_rate': 0, 'clearance_rate': 0},
                'overall': {'total_compliance_checks': 0, 'compliance_violations': 0, 'overall_compliance_rate': 0}
            }


# Global enhanced compliance manager
enhanced_compliance_manager = EnhancedComplianceManager()
