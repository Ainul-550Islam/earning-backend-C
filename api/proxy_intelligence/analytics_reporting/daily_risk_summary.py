"""
Daily Risk Summary
==================
Generates and optionally emails a daily digest of proxy intelligence activity.
"""
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class DailyRiskSummary:
    """
    Generates a daily risk summary for admins.
    Can be triggered via Celery beat task or management command.
    """

    def generate(self, date=None) -> dict:
        """Generate the daily summary report."""
        report_date = date or timezone.now().date()
        since = timezone.datetime.combine(report_date, timezone.datetime.min.time())
        since = timezone.make_aware(since) if timezone.is_naive(since) else since
        until = since + timedelta(days=1)

        from ..models import (
            IPIntelligence, FraudAttempt, IPBlacklist,
            VPNDetectionLog, AnomalyDetectionLog, APIRequestLog
        )

        new_ips = IPIntelligence.objects.filter(created_at__gte=since, created_at__lt=until).count()
        new_fraud = FraudAttempt.objects.filter(created_at__gte=since, created_at__lt=until).count()
        new_blacklist = IPBlacklist.objects.filter(created_at__gte=since, created_at__lt=until).count()
        new_vpn = VPNDetectionLog.objects.filter(created_at__gte=since, created_at__lt=until).count()
        new_anomalies = AnomalyDetectionLog.objects.filter(created_at__gte=since, created_at__lt=until).count()
        api_calls = APIRequestLog.objects.filter(created_at__gte=since, created_at__lt=until).count()

        from ..models import UserRiskProfile
        from django.db.models import Count
        high_risk_users = UserRiskProfile.objects.filter(is_high_risk=True).count()

        return {
            'report_date': str(report_date),
            'new_ips_checked': new_ips,
            'fraud_attempts': new_fraud,
            'new_blacklists': new_blacklist,
            'vpn_detections': new_vpn,
            'anomalies': new_anomalies,
            'total_api_calls': api_calls,
            'total_high_risk_users': high_risk_users,
            'generated_at': timezone.now().isoformat(),
        }

    def send_email(self, recipients: list, date=None) -> bool:
        """Send the daily summary as an email."""
        report = self.generate(date)
        subject = f"[Proxy Intelligence] Daily Summary — {report['report_date']}"
        body = (
            f"Daily Proxy Intelligence Report\n"
            f"================================\n"
            f"Date: {report['report_date']}\n\n"
            f"New IPs Checked:    {report['new_ips_checked']}\n"
            f"Fraud Attempts:     {report['fraud_attempts']}\n"
            f"New Blacklists:     {report['new_blacklists']}\n"
            f"VPN Detections:     {report['vpn_detections']}\n"
            f"Anomalies:          {report['anomalies']}\n"
            f"Total API Calls:    {report['total_api_calls']}\n"
            f"High Risk Users:    {report['total_high_risk_users']}\n"
        )
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=recipients,
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Daily summary email failed: {e}")
            return False
