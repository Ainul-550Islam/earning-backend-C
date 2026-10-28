# api/admin_panel/compliance.py
"""
Admin Panel Compliance Engine.
GDPR, AML, KYB, PDPA, CCPA, PCI-DSS compliance controls.
Calls api.kyc, api.kyc.gdpr, api.kyc.aml — never stores compliance data itself.
Provides admin interface for: GDPR requests, AML alerts, PCI controls,
data retention, consent management, regulatory reporting.
"""
from __future__ import annotations
from django.db.models import Max
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

logger = logging.getLogger(__name__)


# ===========================================================================
# COMPLIANCE FRAMEWORKS
# ===========================================================================

class ComplianceFramework:
    GDPR       = 'GDPR'       # EU General Data Protection Regulation
    CCPA       = 'CCPA'       # California Consumer Privacy Act
    PDPA       = 'PDPA'       # Bangladesh Personal Data Protection Act
    AML        = 'AML'        # Anti-Money Laundering
    KYC        = 'KYC'        # Know Your Customer
    KYB        = 'KYB'        # Know Your Business (advertisers)
    PCI_DSS    = 'PCI_DSS'    # Payment Card Industry Data Security Standard
    FATF       = 'FATF'       # Financial Action Task Force
    SANCTIONS  = 'SANCTIONS'  # International sanctions compliance


@dataclass
class ComplianceStatus:
    framework: str
    status: str      # compliant | warning | violation | unknown
    score: int       # 0-100
    issues: List[str] = field(default_factory=list)
    last_checked: str = field(default_factory=lambda: timezone.now().isoformat())
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'framework': self.framework, 'status': self.status, 'score': self.score,
            'issues': self.issues, 'last_checked': self.last_checked,
            'recommendations': self.recommendations,
        }


# ===========================================================================
# GDPR COMPLIANCE
# ===========================================================================

class GDPRCompliance:
    """GDPR compliance controls — calls api.kyc.gdpr.service."""

    DATA_RETENTION_DAYS = 365 * 3  # 3 years

    def get_pending_requests(self) -> List[Dict]:
        """Get all pending GDPR data subject requests."""
        try:
            from api.kyc.gdpr.service import GDPRService
            return GDPRService.get_pending_summary()
        except Exception as e:
            logger.debug(f"[GDPR.get_pending] {e}")
            return []

    def process_data_access_request(self, user_id: Any, actor) -> Dict:
        """Process a GDPR data access request (Article 15)."""
        from api.admin_panel.data_export import AdminDataExporter
        data = AdminDataExporter.export_user_data(user_id)
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='gdpr_data_access',
                              model_name='User', object_id=str(user_id),
                              changes={'categories': list(data.keys())})
        except Exception:
            pass
        return {'success': True, 'data': data, 'user_id': user_id}

    def process_erasure_request(self, user_id: Any, actor) -> Dict:
        """Process right to erasure (Article 17 — 'Right to be forgotten')."""
        results = {}
        # Call GDPR service for actual erasure
        try:
            from api.kyc.gdpr.service import GDPRService
            result = GDPRService.erase_user_data(user_id=user_id, requested_by=actor)
            results['gdpr_erasure'] = result
        except Exception as e:
            results['gdpr_erasure'] = str(e)
        # Log
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='gdpr_erasure',
                              model_name='User', object_id=str(user_id),
                              changes=results)
        except Exception:
            pass
        return {'success': True, 'user_id': user_id, 'results': results}

    def check_data_retention(self) -> Dict:
        """Check data retention compliance — flag old data."""
        cutoff = timezone.now() - timedelta(days=self.DATA_RETENTION_DAYS)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        old_users = User.objects.filter(
            is_active=False, last_login__lt=cutoff
        ).count()
        return {
            'retention_policy_days': self.DATA_RETENTION_DAYS,
            'users_eligible_deletion': old_users,
            'cutoff_date': cutoff.date().isoformat(),
            'status': 'warning' if old_users > 0 else 'compliant',
        }

    def get_consent_status(self, user_id: Any) -> Dict:
        """Check user's consent status for data processing."""
        try:
            from api.kyc.gdpr.service import GDPRService
            return GDPRService.get_user_consents(user_id)
        except Exception:
            return {'user_id': user_id, 'consents': {}, 'status': 'unknown'}

    def generate_compliance_report(self, days: int = 30) -> Dict:
        """Generate GDPR compliance report for the period."""
        cutoff = timezone.now() - timedelta(days=days)
        return {
            'framework':           ComplianceFramework.GDPR,
            'period_days':         days,
            'data_retention':      self.check_data_retention(),
            'pending_requests':    len(self.get_pending_requests()),
            'generated_at':        timezone.now().isoformat(),
        }


# ===========================================================================
# AML COMPLIANCE
# ===========================================================================

class AMLCompliance:
    """Anti-Money Laundering compliance — calls api.kyc.aml."""

    # Thresholds
    LARGE_TRANSACTION_THRESHOLD = 10000  # BDT
    SAR_THRESHOLD = 50000                # Suspicious Activity Report threshold
    CTR_THRESHOLD = 1000000              # Currency Transaction Report threshold

    def get_active_alerts(self) -> List[Dict]:
        """Get active AML alerts."""
        try:
            from api.kyc.aml.models import AMLAlert
            return list(
                AMLAlert.objects.filter(status='active')
                .values('id', 'alert_type', 'severity', 'user_id', 'amount', 'created_at')
                .order_by('-severity', '-created_at')[:100]
            )
        except Exception as e:
            logger.debug(f"[AML.alerts] {e}")
            return []

    def flag_suspicious_transaction(self, user_id: Any, amount: float,
                                     reason: str, actor) -> Dict:
        """Flag a transaction as suspicious (create AML alert)."""
        try:
            from api.kyc.aml.models import AMLAlert
            alert = AMLAlert.objects.create(
                user_id=user_id,
                alert_type='suspicious_transaction',
                severity='high' if amount >= self.SAR_THRESHOLD else 'medium',
                amount=amount,
                description=reason,
                status='active',
                flagged_by=actor,
            )
            return {'success': True, 'alert_id': alert.pk}
        except Exception as e:
            logger.debug(f"[AML.flag] {e}")
            return {'success': False, 'error': str(e)}

    def check_transaction_patterns(self, user_id: Any, days: int = 30) -> Dict:
        """Check for suspicious transaction patterns."""
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.wallet.models import WalletTransaction
            from django.db.models import Sum, Count
            txns = WalletTransaction.objects.filter(
                wallet__user_id=user_id, created_at__gte=cutoff
            ).aggregate(
                total=Sum('gross_amount'), count=Count('id'),
                max_single=Max('amount'),
            )
            flags = []
            total = float(txns['total'] or 0)
            if total >= self.LARGE_TRANSACTION_THRESHOLD:
                flags.append(f'Total volume ৳{total:,.0f} in {days} days exceeds threshold')
            if total >= self.SAR_THRESHOLD:
                flags.append('SAR threshold exceeded — requires investigation')
            return {
                'user_id': user_id, 'period_days': days,
                'total_volume': total, 'transaction_count': txns['count'],
                'flags': flags,
                'risk_level': 'high' if total >= self.SAR_THRESHOLD else 'medium' if flags else 'low',
            }
        except Exception as e:
            return {'user_id': user_id, 'error': str(e)}

    def generate_sar(self, user_id: Any, reason: str, evidence: Dict, actor) -> Dict:
        """Generate Suspicious Activity Report."""
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action='generate_sar',
                model_name='User', object_id=str(user_id),
                changes={'reason': reason, 'evidence_keys': list(evidence.keys())},
            )
            return {
                'success': True,
                'sar_id': f"SAR-{user_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                'user_id': user_id,
                'reason': reason,
                'generated_at': timezone.now().isoformat(),
                'generated_by': actor.username if actor else 'system',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ===========================================================================
# COMPLIANCE ENGINE (orchestrator)
# ===========================================================================

class ComplianceEngine:
    """
    Master compliance orchestrator.
    Combines GDPR, AML, KYC, Sanctions into unified compliance view.
    """

    def __init__(self):
        self.gdpr       = GDPRCompliance()
        self.aml        = AMLCompliance()

    def check_user(self, user_id: Any) -> Dict:
        """Full compliance check for a single user."""
        results = {'user_id': user_id, 'checks': {}, 'overall_status': 'compliant'}
        flags = []

        # KYC
        try:
            from api.kyc.models import KYC
            kyc = KYC.objects.filter(user_id=user_id).first()
            results['checks']['kyc'] = {
                'has_kyc': bool(kyc),
                'status': kyc.status if kyc else 'none',
            }
            if not kyc or kyc.status != 'approved':
                flags.append('KYC not verified')
        except Exception:
            pass

        # Sanctions
        try:
            from api.admin_panel.sanctions import screen_user_api
            sanctions = screen_user_api(user_id, actor=None)
            results['checks']['sanctions'] = sanctions.get('data', {})
            if sanctions.get('data', {}).get('overall_risk') in ('blocked', 'review'):
                flags.append('Sanctions match detected')
        except Exception:
            pass

        # AML patterns
        try:
            aml_check = self.aml.check_transaction_patterns(user_id)
            results['checks']['aml'] = aml_check
            if aml_check.get('risk_level') == 'high':
                flags.append('AML high-risk transaction pattern')
        except Exception:
            pass

        # Overall status
        if any('sanctions' in f.lower() or 'blocked' in f.lower() for f in flags):
            results['overall_status'] = 'violation'
        elif flags:
            results['overall_status'] = 'warning'

        results['flags'] = flags
        results['checked_at'] = timezone.now().isoformat()
        return results

    def get_platform_compliance_summary(self) -> Dict:
        """Full platform compliance dashboard."""
        summary = {
            'frameworks': {},
            'overall_score': 100,
            'generated_at': timezone.now().isoformat(),
        }
        # GDPR
        try:
            retention = self.gdpr.check_data_retention()
            pending = len(self.gdpr.get_pending_requests())
            gdpr_status = ComplianceStatus(
                framework=ComplianceFramework.GDPR,
                status='warning' if pending > 0 or retention['users_eligible_deletion'] > 0 else 'compliant',
                score=90 if pending == 0 else max(50, 90 - pending * 2),
                issues=[f"{pending} pending GDPR requests"] if pending else [],
                recommendations=['Process pending data requests within 30 days'] if pending else [],
            )
            summary['frameworks']['gdpr'] = gdpr_status.to_dict()
        except Exception:
            pass
        # AML
        try:
            active_alerts = len(self.aml.get_active_alerts())
            aml_status = ComplianceStatus(
                framework=ComplianceFramework.AML,
                status='warning' if active_alerts > 0 else 'compliant',
                score=max(60, 100 - active_alerts * 5),
                issues=[f"{active_alerts} active AML alerts"] if active_alerts else [],
            )
            summary['frameworks']['aml'] = aml_status.to_dict()
        except Exception:
            pass
        # Calculate overall
        scores = [v.get('score', 100) for v in summary['frameworks'].values()]
        summary['overall_score'] = int(sum(scores) / len(scores)) if scores else 100
        return summary

    def generate_regulatory_report(
        self,
        framework: str,
        period_days: int = 30,
        actor=None,
    ) -> Dict:
        """Generate regulatory compliance report."""
        if framework == ComplianceFramework.GDPR:
            return self.gdpr.generate_compliance_report(period_days)
        elif framework == ComplianceFramework.AML:
            return {
                'framework': ComplianceFramework.AML,
                'period_days': period_days,
                'active_alerts': len(self.aml.get_active_alerts()),
                'generated_at': timezone.now().isoformat(),
            }
        return {'framework': framework, 'status': 'no_report_available'}


# ===========================================================================
# CONVENIENCE FUNCTIONS
# ===========================================================================

_engine = ComplianceEngine()


def check_user_compliance(user_id: Any) -> Dict:
    return _engine.check_user(user_id)


def get_platform_compliance() -> Dict:
    return _engine.get_platform_compliance_summary()


def process_gdpr_request(user_id: Any, request_type: str, actor) -> Dict:
    if request_type == 'access':
        return _engine.gdpr.process_data_access_request(user_id, actor)
    elif request_type == 'erasure':
        return _engine.gdpr.process_erasure_request(user_id, actor)
    return {'success': False, 'error': f'Unknown request type: {request_type}'}


def flag_aml(user_id: Any, amount: float, reason: str, actor) -> Dict:
    return _engine.aml.flag_suspicious_transaction(user_id, amount, reason, actor)