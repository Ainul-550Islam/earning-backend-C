"""
Proxy Intelligence Repository  (PRODUCTION-READY - COMPLETE REWRITE)
=====================================================================
Data Access Layer — isolates all ORM queries from business logic.
Views and Services call repositories, not ORM directly.

Repositories:
  IPIntelligenceRepository
  BlacklistRepository
  WhitelistRepository
  FraudRepository
  UserRiskRepository
  DeviceFingerprintRepository
  ThreatFeedRepository
  VelocityRepository
  AuditRepository
  AnalyticsRepository
"""
import logging
from datetime import timedelta
from typing import Optional, List

from django.db.models import Q, Count, Avg, Max, Min, F
from django.utils import timezone

from .models import (
    IPIntelligence, IPBlacklist, IPWhitelist, FraudAttempt,
    UserRiskProfile, DeviceFingerprint, ThreatFeedProvider,
    MaliciousIPDatabase, VelocityMetric, VPNDetectionLog,
    ProxyDetectionLog, TorExitNode, AnomalyDetectionLog,
    RiskScoreHistory, MultiAccountLink, SystemAuditTrail,
    ClickFraudRecord, APIRequestLog,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# 1. IP INTELLIGENCE REPOSITORY
# ══════════════════════════════════════════════════════════════════

class IPIntelligenceRepository:

    @staticmethod
    def get_by_ip(ip_address: str, tenant=None) -> Optional[IPIntelligence]:
        qs = IPIntelligence.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def get_or_none(ip_address: str, tenant=None) -> Optional[IPIntelligence]:
        try:
            return IPIntelligenceRepository.get_by_ip(ip_address, tenant)
        except Exception:
            return None

    @staticmethod
    def get_high_risk(threshold: int = 61, tenant=None, limit: int = 100):
        qs = IPIntelligence.objects.filter(risk_score__gte=threshold)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score')[:limit]

    @staticmethod
    def get_by_flag(flag: str, tenant=None, limit: int = 500):
        """flag: 'is_vpn' | 'is_proxy' | 'is_tor' | 'is_datacenter'"""
        qs = IPIntelligence.objects.filter(**{flag: True})
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-last_checked')[:limit]

    @staticmethod
    def get_recent(hours: int = 24, tenant=None):
        since = timezone.now() - timedelta(hours=hours)
        qs = IPIntelligence.objects.filter(last_checked__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-last_checked')

    @staticmethod
    def get_by_country(country_code: str, tenant=None):
        qs = IPIntelligence.objects.filter(country_code=country_code.upper())
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def get_statistics(tenant=None) -> dict:
        qs = IPIntelligence.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total':         qs.count(),
            'vpn':           qs.filter(is_vpn=True).count(),
            'proxy':         qs.filter(is_proxy=True).count(),
            'tor':           qs.filter(is_tor=True).count(),
            'datacenter':    qs.filter(is_datacenter=True).count(),
            'high_risk':     qs.filter(risk_score__gte=61).count(),
            'critical':      qs.filter(risk_score__gte=81).count(),
            'avg_risk':      round(qs.aggregate(a=Avg('risk_score'))['a'] or 0, 1),
            'max_risk':      qs.aggregate(m=Max('risk_score'))['m'] or 0,
        }

    @staticmethod
    def update_risk_score(ip_address: str, risk_score: int, tenant=None) -> int:
        qs = IPIntelligence.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.update(risk_score=risk_score, last_checked=timezone.now())

    @staticmethod
    def search(query: str, tenant=None, limit: int = 50):
        """Search by IP, ISP, ASN, or country."""
        qs = IPIntelligence.objects.filter(
            Q(ip_address__icontains=query) |
            Q(isp__icontains=query) |
            Q(asn__icontains=query) |
            Q(asn_name__icontains=query) |
            Q(country_code__icontains=query)
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs[:limit]

    @staticmethod
    def bulk_update_flags(ip_list: list, flag: str, value: bool, tenant=None) -> int:
        qs = IPIntelligence.objects.filter(ip_address__in=ip_list)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.update(**{flag: value, 'last_checked': timezone.now()})


# ══════════════════════════════════════════════════════════════════
# 2. BLACKLIST REPOSITORY
# ══════════════════════════════════════════════════════════════════

class BlacklistRepository:

    @staticmethod
    def get_active(tenant=None):
        qs = IPBlacklist.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    @staticmethod
    def get_by_ip(ip_address: str, tenant=None):
        qs = IPBlacklist.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def is_blocked(ip_address: str, tenant=None) -> bool:
        qs = IPBlacklist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return any(not entry.is_expired() for entry in qs)

    @staticmethod
    def get_by_reason(reason: str, tenant=None):
        qs = IPBlacklist.objects.filter(reason=reason, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def get_expiring_soon(hours: int = 24, tenant=None):
        """IPs whose blacklist expires within N hours."""
        cutoff = timezone.now() + timedelta(hours=hours)
        qs = IPBlacklist.objects.filter(
            is_active=True, is_permanent=False,
            expires_at__lte=cutoff, expires_at__gte=timezone.now()
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def count_by_reason(tenant=None) -> list:
        qs = IPBlacklist.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.values('reason').annotate(count=Count('id')).order_by('-count'))

    @staticmethod
    def deactivate_expired() -> int:
        """Batch-deactivate all expired entries. Returns count."""
        qs = IPBlacklist.objects.filter(
            is_active=True, is_permanent=False,
            expires_at__lt=timezone.now()
        )
        count = qs.count()
        qs.update(is_active=False)
        return count


# ══════════════════════════════════════════════════════════════════
# 3. WHITELIST REPOSITORY
# ══════════════════════════════════════════════════════════════════

class WhitelistRepository:

    @staticmethod
    def get_active(tenant=None):
        qs = IPWhitelist.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('label')

    @staticmethod
    def is_whitelisted(ip_address: str, tenant=None) -> bool:
        qs = IPWhitelist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.exists()

    @staticmethod
    def search(query: str, tenant=None):
        qs = IPWhitelist.objects.filter(
            Q(ip_address__icontains=query) |
            Q(label__icontains=query) |
            Q(description__icontains=query)
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs


# ══════════════════════════════════════════════════════════════════
# 4. FRAUD REPOSITORY
# ══════════════════════════════════════════════════════════════════

class FraudRepository:

    @staticmethod
    def get_recent(hours: int = 24, tenant=None):
        since = timezone.now() - timedelta(hours=hours)
        qs = FraudAttempt.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    @staticmethod
    def get_pending_review(tenant=None):
        qs = FraudAttempt.objects.filter(status='detected')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score', '-created_at')

    @staticmethod
    def get_by_ip(ip_address: str, tenant=None, limit: int = 50):
        qs = FraudAttempt.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def get_user_history(user, limit: int = 50):
        return FraudAttempt.objects.filter(user=user).order_by('-created_at')[:limit]

    @staticmethod
    def get_by_type(fraud_type: str, tenant=None, days: int = 30):
        since = timezone.now() - timedelta(days=days)
        qs = FraudAttempt.objects.filter(
            fraud_type=fraud_type, created_at__gte=since
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    @staticmethod
    def get_statistics(days: int = 30, tenant=None) -> dict:
        since = timezone.now() - timedelta(days=days)
        qs = FraudAttempt.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total':          qs.count(),
            'confirmed':      qs.filter(status='confirmed').count(),
            'false_positive': qs.filter(status='false_positive').count(),
            'pending':        qs.filter(status='detected').count(),
            'resolved':       qs.filter(status='resolved').count(),
            'avg_risk_score': round(qs.aggregate(a=Avg('risk_score'))['a'] or 0, 1),
            'by_type':        list(qs.values('fraud_type').annotate(n=Count('id'))),
        }

    @staticmethod
    def get_top_fraud_ips(limit: int = 10, days: int = 30, tenant=None) -> list:
        since = timezone.now() - timedelta(days=days)
        qs = FraudAttempt.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('ip_address')
            .annotate(count=Count('id'), avg_risk=Avg('risk_score'))
            .order_by('-count')[:limit]
        )

    @staticmethod
    def resolve(fraud_id: str, resolved_by, is_false_positive: bool,
                notes: str = '') -> Optional[FraudAttempt]:
        try:
            attempt = FraudAttempt.objects.get(id=fraud_id)
            attempt.status = 'false_positive' if is_false_positive else 'resolved'
            attempt.resolved_by = resolved_by
            attempt.resolved_at = timezone.now()
            attempt.resolution_notes = notes
            attempt.save()
            return attempt
        except FraudAttempt.DoesNotExist:
            return None

    @staticmethod
    def get_click_fraud_stats(tenant=None, hours: int = 24) -> dict:
        since = timezone.now() - timedelta(hours=hours)
        qs = ClickFraudRecord.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total_clicks': qs.count(),
            'bot_clicks':   qs.filter(is_bot=True).count(),
            'duplicate':    qs.filter(is_duplicate=True).count(),
            'avg_fraud_score': round(qs.aggregate(a=Avg('fraud_score'))['a'] or 0, 1),
        }


# ══════════════════════════════════════════════════════════════════
# 5. USER RISK REPOSITORY
# ══════════════════════════════════════════════════════════════════

class UserRiskRepository:

    @staticmethod
    def get_profile(user) -> UserRiskProfile:
        profile, _ = UserRiskProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def get_or_none(user) -> Optional[UserRiskProfile]:
        return UserRiskProfile.objects.filter(user=user).first()

    @staticmethod
    def get_high_risk_users(tenant=None, threshold: int = 61, limit: int = 100):
        qs = UserRiskProfile.objects.filter(overall_risk_score__gte=threshold)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-overall_risk_score')[:limit]

    @staticmethod
    def get_under_review(tenant=None):
        qs = UserRiskProfile.objects.filter(is_under_review=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def get_risk_distribution(tenant=None) -> list:
        qs = UserRiskProfile.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.values('risk_level').annotate(count=Count('id')))

    @staticmethod
    def get_score_history(user, days: int = 30):
        since = timezone.now() - timedelta(days=days)
        return RiskScoreHistory.objects.filter(
            user=user, created_at__gte=since
        ).order_by('-created_at')

    @staticmethod
    def flag_for_review(user, reason: str = '', tenant=None) -> UserRiskProfile:
        profile = UserRiskRepository.get_profile(user)
        profile.is_under_review = True
        if reason:
            notes = list(profile.assessment_notes or [])
            notes.append({'reason': reason, 'time': timezone.now().isoformat()})
            profile.assessment_notes = notes[-20:]
        profile.save()
        return profile

    @staticmethod
    def get_multi_account_links(user, confirmed_only: bool = False):
        qs = MultiAccountLink.objects.filter(
            Q(primary_user=user) | Q(linked_user=user)
        )
        if confirmed_only:
            qs = qs.filter(is_confirmed=True)
        return qs.order_by('-created_at')


# ══════════════════════════════════════════════════════════════════
# 6. DEVICE FINGERPRINT REPOSITORY
# ══════════════════════════════════════════════════════════════════

class DeviceFingerprintRepository:

    @staticmethod
    def get_by_hash(fingerprint_hash: str) -> Optional[DeviceFingerprint]:
        return DeviceFingerprint.objects.filter(
            fingerprint_hash=fingerprint_hash
        ).first()

    @staticmethod
    def get_user_devices(user, limit: int = 20):
        return DeviceFingerprint.objects.filter(user=user).order_by('-last_seen')[:limit]

    @staticmethod
    def get_suspicious(tenant=None, limit: int = 100):
        qs = DeviceFingerprint.objects.filter(is_suspicious=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score')[:limit]

    @staticmethod
    def get_shared_fingerprints(min_users: int = 2, tenant=None) -> list:
        """Fingerprints associated with more than min_users distinct users."""
        qs = DeviceFingerprint.objects.exclude(user=None)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('fingerprint_hash')
            .annotate(user_count=Count('user', distinct=True))
            .filter(user_count__gte=min_users)
            .order_by('-user_count')
        )

    @staticmethod
    def get_by_ip(ip_address: str, limit: int = 20):
        """All fingerprints that include this IP in their ip_addresses list."""
        # Django JSONField contains lookup
        return DeviceFingerprint.objects.filter(
            ip_addresses__contains=ip_address
        ).order_by('-last_seen')[:limit]

    @staticmethod
    def update_risk(fingerprint_hash: str, risk_score: int,
                    is_suspicious: bool) -> int:
        return DeviceFingerprint.objects.filter(
            fingerprint_hash=fingerprint_hash
        ).update(risk_score=risk_score, is_suspicious=is_suspicious)


# ══════════════════════════════════════════════════════════════════
# 7. THREAT FEED REPOSITORY
# ══════════════════════════════════════════════════════════════════

class ThreatFeedRepository:

    @staticmethod
    def get_active_providers():
        return ThreatFeedProvider.objects.filter(is_active=True).order_by('priority')

    @staticmethod
    def get_provider(name: str) -> Optional[ThreatFeedProvider]:
        return ThreatFeedProvider.objects.filter(name=name).first()

    @staticmethod
    def is_malicious(ip_address: str, threat_type: str = None) -> bool:
        qs = MaliciousIPDatabase.objects.filter(ip_address=ip_address, is_active=True)
        if threat_type:
            qs = qs.filter(threat_type=threat_type)
        return qs.exists()

    @staticmethod
    def get_malicious_entries(ip_address: str):
        return MaliciousIPDatabase.objects.filter(
            ip_address=ip_address, is_active=True
        ).select_related('threat_feed')

    @staticmethod
    def get_malicious_by_type(threat_type: str, limit: int = 100):
        return MaliciousIPDatabase.objects.filter(
            threat_type=threat_type, is_active=True
        ).order_by('-last_reported')[:limit]

    @staticmethod
    def get_stats() -> dict:
        return {
            'total_malicious': MaliciousIPDatabase.objects.filter(is_active=True).count(),
            'by_type': list(
                MaliciousIPDatabase.objects
                .filter(is_active=True)
                .values('threat_type')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
            'active_providers': ThreatFeedProvider.objects.filter(is_active=True).count(),
        }


# ══════════════════════════════════════════════════════════════════
# 8. VELOCITY REPOSITORY
# ══════════════════════════════════════════════════════════════════

class VelocityRepository:

    @staticmethod
    def get_exceeded(tenant=None, hours: int = 1):
        since = timezone.now() - timedelta(hours=hours)
        qs = VelocityMetric.objects.filter(exceeded=True, created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-request_count')

    @staticmethod
    def get_by_ip(ip_address: str, hours: int = 24):
        since = timezone.now() - timedelta(hours=hours)
        return VelocityMetric.objects.filter(
            ip_address=ip_address, created_at__gte=since
        ).order_by('-created_at')

    @staticmethod
    def get_top_ips_by_velocity(limit: int = 20, hours: int = 1) -> list:
        since = timezone.now() - timedelta(hours=hours)
        return list(
            VelocityMetric.objects
            .filter(created_at__gte=since)
            .values('ip_address')
            .annotate(max_count=Max('request_count'), total=Count('id'))
            .order_by('-max_count')[:limit]
        )


# ══════════════════════════════════════════════════════════════════
# 9. AUDIT REPOSITORY
# ══════════════════════════════════════════════════════════════════

class AuditRepository:

    @staticmethod
    def get_recent(hours: int = 24, tenant=None, limit: int = 100):
        since = timezone.now() - timedelta(hours=hours)
        qs = SystemAuditTrail.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def get_by_model(model_name: str, tenant=None):
        qs = SystemAuditTrail.objects.filter(model_name=model_name)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    @staticmethod
    def get_by_user(user, days: int = 30):
        since = timezone.now() - timedelta(days=days)
        return SystemAuditTrail.objects.filter(
            user=user, created_at__gte=since
        ).order_by('-created_at')

    @staticmethod
    def get_api_logs(ip_address: str = None, endpoint: str = None,
                     hours: int = 24, tenant=None, limit: int = 200):
        since = timezone.now() - timedelta(hours=hours)
        qs = APIRequestLog.objects.filter(created_at__gte=since)
        if ip_address:
            qs = qs.filter(ip_address=ip_address)
        if endpoint:
            qs = qs.filter(endpoint__icontains=endpoint)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')[:limit]


# ══════════════════════════════════════════════════════════════════
# 10. ANALYTICS REPOSITORY
# ══════════════════════════════════════════════════════════════════

class AnalyticsRepository:

    @staticmethod
    def get_daily_ip_checks(days: int = 30, tenant=None) -> list:
        from django.db.models.functions import TruncDay
        since = timezone.now() - timedelta(days=days)
        qs = IPIntelligence.objects.filter(last_checked__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.annotate(day=TruncDay('last_checked'))
            .values('day')
            .annotate(count=Count('id'), avg_risk=Avg('risk_score'))
            .order_by('day')
        )

    @staticmethod
    def get_geo_risk_heatmap(limit: int = 30, tenant=None) -> list:
        qs = IPIntelligence.objects.exclude(country_code='')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('country_code')
            .annotate(avg_risk=Avg('risk_score'), count=Count('id'))
            .filter(count__gte=3)
            .order_by('-avg_risk')[:limit]
        )

    @staticmethod
    def get_isp_risk_breakdown(limit: int = 20, tenant=None) -> list:
        qs = IPIntelligence.objects.exclude(isp='')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('isp')
            .annotate(avg_risk=Avg('risk_score'), count=Count('id'))
            .filter(count__gte=5)
            .order_by('-avg_risk')[:limit]
        )

    @staticmethod
    def get_anomaly_trend(days: int = 7, tenant=None) -> list:
        from django.db.models.functions import TruncDay
        since = timezone.now() - timedelta(days=days)
        qs = AnomalyDetectionLog.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.annotate(day=TruncDay('created_at'))
            .values('day', 'anomaly_type')
            .annotate(count=Count('id'))
            .order_by('day', 'anomaly_type')
        )
