# api/offer_inventory/maintenance_logs/security_audit_report.py
"""Security Audit Report — Generate comprehensive security reports."""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count

logger = logging.getLogger(__name__)


class SecurityAuditReporter:
    """Generate security audit reports for compliance and ops review."""

    @staticmethod
    def generate_report(days: int = 30) -> dict:
        """Full security audit report for the given period."""
        from api.offer_inventory.models import (
            FraudAttempt, BlacklistedIP, SecurityIncident,
            HoneypotLog, UserRiskProfile, AuditLog, Click,
        )
        since = timezone.now() - timedelta(days=days)

        return {
            'period'             : f'Last {days} days',
            'generated_at'       : timezone.now().isoformat(),
            'fraud_attempts'     : FraudAttempt.objects.filter(created_at__gte=since).count(),
            'ips_blocked'        : BlacklistedIP.objects.filter(created_at__gte=since).count(),
            'security_incidents' : SecurityIncident.objects.filter(created_at__gte=since).count(),
            'honeypot_triggers'  : HoneypotLog.objects.filter(created_at__gte=since).count(),
            'high_risk_users'    : UserRiskProfile.objects.filter(risk_level__in=['high', 'critical']).count(),
            'suspended_users'    : UserRiskProfile.objects.filter(is_suspended=True).count(),
            'fraud_clicks'       : Click.objects.filter(is_fraud=True, created_at__gte=since).count(),
            'total_clicks'       : Click.objects.filter(created_at__gte=since).count(),
            'admin_actions'      : AuditLog.objects.filter(created_at__gte=since).count(),
            'top_fraud_countries': SecurityAuditReporter._top_fraud_countries(since),
            'top_blocked_ips'    : SecurityAuditReporter._top_blocked_ips(),
        }

    @staticmethod
    def _top_fraud_countries(since) -> list:
        from api.offer_inventory.models import Click
        return list(
            Click.objects.filter(is_fraud=True, created_at__gte=since)
            .exclude(country_code='')
            .values('country_code')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

    @staticmethod
    def _top_blocked_ips() -> list:
        from api.offer_inventory.models import BlacklistedIP
        return list(
            BlacklistedIP.objects.filter(is_permanent=True)
            .values('ip_address', 'reason', 'created_at')
            .order_by('-created_at')[:10]
        )

    @staticmethod
    def generate_fraud_trend(days: int = 30) -> list:
        """Daily fraud rate trend."""
        from api.offer_inventory.models import Click
        from django.db.models.functions import TruncDate
        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                total=Count('id'),
                fraud=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_fraud=True)),
            )
            .order_by('date')
        )

    @staticmethod
    def get_suspicious_users(min_score: float = 60.0, limit: int = 50) -> list:
        """Users with high fraud risk scores."""
        from api.offer_inventory.models import UserRiskProfile
        return list(
            UserRiskProfile.objects.filter(risk_score__gte=min_score)
            .select_related('user')
            .values('user__username', 'risk_score', 'risk_level', 'is_suspended', 'flag_count')
            .order_by('-risk_score')[:limit]
        )
