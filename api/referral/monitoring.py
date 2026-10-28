# api/referral/monitoring.py
# Real-time monitoring, alerting, and health metrics for referral module
# Integrates with project's admin_panel + audit_logs
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, List
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class ReferralMonitor:
    """
    Real-time monitoring for the referral system.
    Tracks anomalies, sends alerts, logs performance metrics.
    """

    # ── Alert Thresholds ──────────────────────────────────────────────────────

    ALERT_FRAUD_RATE_PCT      = 10.0   # Alert if >10% of new referrals are suspicious
    ALERT_FAILED_COMMISSIONS  = 50     # Alert if >50 failed commissions in 1 hour
    ALERT_OVERDUE_HOLDS       = 100    # Alert if >100 commissions overdue
    ALERT_K_FACTOR_DROP       = 0.3    # Alert if K-factor drops below this
    ALERT_PAYOUT_STUCK        = 24     # Alert if payouts stuck for >24 hours

    @staticmethod
    def check_fraud_rate(hours: int = 1) -> Dict:
        """Check recent fraud rate — alert if above threshold."""
        from api.referral.models import Referral, SuspiciousReferral
        cutoff = timezone.now() - timedelta(hours=hours)

        new_referrals = Referral.objects.filter(created_at__gte=cutoff).count()
        new_suspicious = SuspiciousReferral.objects.filter(
            detected_at__gte=cutoff
        ).count()

        if new_referrals == 0:
            fraud_rate = 0.0
        else:
            fraud_rate = (new_suspicious / new_referrals) * 100

        alert = fraud_rate > ReferralMonitor.ALERT_FRAUD_RATE_PCT

        if alert:
            ReferralMonitor._send_alert(
                level='WARNING',
                title='High Fraud Rate Detected',
                message=f'Fraud rate: {fraud_rate:.1f}% in last {hours}h '
                        f'({new_suspicious}/{new_referrals} referrals)',
                data={'fraud_rate': fraud_rate, 'period_hours': hours},
            )

        return {
            'fraud_rate_pct': round(fraud_rate, 2),
            'new_referrals': new_referrals,
            'suspicious': new_suspicious,
            'alert_triggered': alert,
        }

    @staticmethod
    def check_commission_health() -> Dict:
        """Check for stuck/failed commissions."""
        from api.referral.models import CommissionHold, CommissionPayout

        overdue_holds = CommissionHold.objects.filter(
            is_released=False,
            release_at__lt=timezone.now() - timedelta(hours=1),
        ).count()

        stuck_payouts = CommissionPayout.objects.filter(
            status='processing',
            updated_at__lt=timezone.now() - timedelta(hours=ReferralMonitor.ALERT_PAYOUT_STUCK),
        ).count()

        alerts = []
        if overdue_holds > ReferralMonitor.ALERT_OVERDUE_HOLDS:
            alerts.append(f'{overdue_holds} overdue commission holds')
            ReferralMonitor._send_alert('ERROR', 'Overdue Commissions',
                                         f'{overdue_holds} holds overdue',
                                         {'overdue': overdue_holds})
        if stuck_payouts > 0:
            alerts.append(f'{stuck_payouts} stuck payouts')

        return {
            'overdue_holds': overdue_holds,
            'stuck_payouts': stuck_payouts,
            'alerts': alerts,
            'healthy': len(alerts) == 0,
        }

    @staticmethod
    def check_viral_health() -> Dict:
        """Check K-factor trend."""
        from api.referral.models import ViralCoefficient
        today = timezone.now().date()

        today_vc = ViralCoefficient.objects.filter(date=today).first()
        k = float(today_vc.k_factor) if today_vc else 0.0

        alert = k > 0 and k < ReferralMonitor.ALERT_K_FACTOR_DROP
        if alert:
            ReferralMonitor._send_alert('WARNING', 'K-Factor Drop',
                                         f'K-factor: {k:.4f} (below {ReferralMonitor.ALERT_K_FACTOR_DROP})',
                                         {'k_factor': k})

        return {
            'k_factor': k,
            'is_viral': k >= 1.0,
            'alert_triggered': alert,
        }

    @staticmethod
    def run_all_checks() -> Dict:
        """Run all monitoring checks and return consolidated report."""
        return {
            'timestamp':        timezone.now().isoformat(),
            'fraud_rate':       ReferralMonitor.check_fraud_rate(),
            'commission_health':ReferralMonitor.check_commission_health(),
            'viral_health':     ReferralMonitor.check_viral_health(),
        }

    @staticmethod
    def _send_alert(level: str, title: str, message: str, data: dict = None) -> None:
        """Send alert via audit log + notification."""
        logger.log(
            logging.ERROR if level == 'ERROR' else logging.WARNING,
            f'[Monitor] {title}: {message}'
        )
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
            ReferralAuditLogger.log(
                action=f'REFERRAL_MONITOR_{level}',
                user=None,
                level=level,
                data={'title': title, 'message': message, **(data or {})},
            )
        except Exception:
            pass