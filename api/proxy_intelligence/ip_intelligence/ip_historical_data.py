"""IP Historical Data — tracks an IP's detection history and risk trends."""
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg


class IPHistoricalDataService:
    @staticmethod
    def get_history(ip_address: str, days: int = 30, tenant=None) -> dict:
        from ..models import (IPIntelligence, VPNDetectionLog,
                              ProxyDetectionLog, FraudAttempt, AnomalyDetectionLog)
        since = timezone.now() - timedelta(days=days)
        intel = IPIntelligence.objects.filter(ip_address=ip_address).first()

        vpn_qs   = VPNDetectionLog.objects.filter(ip_address=ip_address, created_at__gte=since)
        proxy_qs = ProxyDetectionLog.objects.filter(ip_address=ip_address, created_at__gte=since)
        fraud_qs = FraudAttempt.objects.filter(ip_address=ip_address, created_at__gte=since)
        anom_qs  = AnomalyDetectionLog.objects.filter(ip_address=ip_address, created_at__gte=since)

        if tenant:
            vpn_qs   = vpn_qs.filter(tenant=tenant)
            proxy_qs = proxy_qs.filter(tenant=tenant)
            fraud_qs = fraud_qs.filter(tenant=tenant)
            anom_qs  = anom_qs.filter(tenant=tenant)

        return {
            'ip_address':         ip_address,
            'first_seen':         str(intel.created_at) if intel else None,
            'last_checked':       str(intel.last_checked) if intel else None,
            'total_checks':       intel.check_count if intel else 0,
            'current_risk_score': intel.risk_score if intel else 0,
            'risk_level':         intel.risk_level if intel else 'unknown',
            'is_vpn':             intel.is_vpn if intel else False,
            'is_proxy':           intel.is_proxy if intel else False,
            'is_tor':             intel.is_tor if intel else False,
            'is_datacenter':      intel.is_datacenter if intel else False,
            'country_code':       intel.country_code if intel else '',
            'isp':                intel.isp if intel else '',
            'asn':                intel.asn if intel else '',
            'period_days':        days,
            'detections': {
                'vpn':             vpn_qs.count(),
                'proxy':           proxy_qs.count(),
                'fraud_attempts':  fraud_qs.count(),
                'confirmed_fraud': fraud_qs.filter(status='confirmed').count(),
                'anomalies':       anom_qs.count(),
            },
        }

    @staticmethod
    def is_repeat_offender(ip_address: str, min_attempts: int = 3,
                           days: int = 30) -> bool:
        from ..models import FraudAttempt
        since = timezone.now() - timedelta(days=days)
        return FraudAttempt.objects.filter(
            ip_address=ip_address, created_at__gte=since, status='confirmed'
        ).count() >= min_attempts
