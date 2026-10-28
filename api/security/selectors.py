"""
Security Selectors Module
Query selector classes for clean data access patterns
"""

import logging
from typing import List, Dict, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from .querysets import SecurityQuerySet, SecurityLogQuerySet, DeviceInfoQuerySet

User = get_user_model()
logger = logging.getLogger('security.selectors')


class BaseSelector:
    """Base selector class with common functionality"""
    
    def __init__(self, queryset: models.QuerySet):
        self.queryset = queryset
    
    def get_by_id(self, id: int):
        """Get record by ID"""
        try:
            return self.queryset.get(id=id)
        except self.queryset.model.DoesNotExist:
            return None
    
    def get_by_ids(self, ids: List[int]):
        """Get records by list of IDs"""
        return self.queryset.filter(id__in=ids)
    
    def filter_active(self):
        """Filter for active records"""
        if hasattr(self.queryset.model, 'is_active'):
            return self.queryset.filter(is_active=True)
        return self.queryset
    
    def filter_by_date_range(self, start_date: datetime, end_date: datetime):
        """Filter by date range"""
        if hasattr(self.queryset.model, 'created_at'):
            return self.queryset.filter(created_at__range=[start_date, end_date])
        return self.queryset
    
    def filter_recent(self, days: int = 7):
        """Filter for recent records"""
        cutoff_date = timezone.now() - timedelta(days=days)
        if hasattr(self.queryset.model, 'created_at'):
            return self.queryset.filter(created_at__gte=cutoff_date)
        return self.queryset
    
    def order_by_created(self, descending: bool = True):
        """Order by creation date"""
        if hasattr(self.queryset.model, 'created_at'):
            order_field = '-created_at' if descending else 'created_at'
            return self.queryset.order_by(order_field)
        return self.queryset
    
    def count(self):
        """Get count of records"""
        return self.queryset.count()
    
    def exists(self):
        """Check if any records exist"""
        return self.queryset.exists()


class SecurityLogSelector(BaseSelector):
    """Selector for SecurityLog model"""
    
    def __init__(self, queryset: models.QuerySet = None):
        from .models import SecurityLog
        if queryset is None:
            queryset = SecurityLog.objects.all()
        super().__init__(queryset)
    
    def filter_by_security_type(self, security_types: Union[str, List[str]]):
        """Filter by security type(s)"""
        if isinstance(security_types, str):
            return self.queryset.filter(security_type=security_types)
        return self.queryset.filter(security_type__in=security_types)
    
    def filter_by_severity(self, severities: Union[str, List[str]]):
        """Filter by severity level(s)"""
        if isinstance(severities, str):
            return self.queryset.filter(severity=severities)
        return self.queryset.filter(severity__in=severities)
    
    def filter_by_user(self, user: Union[User, int, str]):
        """Filter by user"""
        if isinstance(user, User):
            return self.queryset.filter(user=user)
        elif isinstance(user, int):
            return self.queryset.filter(user_id=user)
        elif isinstance(user, str):
            return self.queryset.filter(user__username=user)
        return self.queryset
    
    def filter_by_ip_address(self, ip_addresses: Union[str, List[str]]):
        """Filter by IP address(es)"""
        if isinstance(ip_addresses, str):
            return self.queryset.filter(ip_address=ip_addresses)
        return self.queryset.filter(ip_address__in=ip_addresses)
    
    def filter_by_risk_score_range(self, min_score: int, max_score: int):
        """Filter by risk score range"""
        return self.queryset.filter(risk_score__gte=min_score, risk_score__lte=max_score)
    
    def filter_high_risk(self, threshold: int = 70):
        """Filter for high risk logs"""
        return self.queryset.filter(risk_score__gte=threshold)
    
    def filter_low_risk(self, threshold: int = 30):
        """Filter for low risk logs"""
        return self.queryset.filter(risk_score__lte=threshold)
    
    def filter_failed_attempts(self):
        """Filter for failed attempts"""
        return self.queryset.filter(security_type__in=['login_failed', 'access_denied', 'permission_denied'])
    
    def filter_successful_attempts(self):
        """Filter for successful attempts"""
        return self.queryset.filter(security_type__in=['login_success', 'access_granted'])
    
    def filter_slow_responses(self, threshold_ms: int = 1000):
        """Filter for slow responses"""
        return self.queryset.filter(response_time_ms__gt=threshold_ms)
    
    def filter_by_user_agent(self, user_agent: str):
        """Filter by user agent"""
        return self.queryset.filter(user_agent__icontains=user_agent)
    
    def filter_by_metadata_key(self, key: str, value: Any = None):
        """Filter by metadata key/value"""
        if value is not None:
            return self.queryset.filter(metadata__contains={key: value})
        return self.queryset.filter(metadata__has_key=key)
    
    def filter_by_country(self, countries: Union[str, List[str]]):
        """Filter by country"""
        if isinstance(countries, str):
            return self.queryset.filter(metadata__country=countries)
        return self.queryset.filter(metadata__country__in=countries)
    
    def get_by_date(self, date: datetime.date):
        """Get logs for specific date"""
        start_datetime = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)
        return self.queryset.filter(created_at__range=[start_datetime, end_datetime])
    
    def get_top_ip_addresses(self, limit: int = 10):
        """Get top IP addresses by activity"""
        return list(
            self.queryset.values('ip_address')
            .annotate(count=models.Count('id'))
            .order_by('-count')[:limit]
        )
    
    def get_top_users(self, limit: int = 10):
        """Get top users by activity"""
        return list(
            self.queryset.filter(user__isnull=False)
            .values('user__username')
            .annotate(count=models.Count('id'))
            .order_by('-count')[:limit]
        )
    
    def get_security_types_count(self):
        """Get count by security type"""
        return dict(
            self.queryset.values('security_type')
            .annotate(count=models.Count('id'))
            .values_list('security_type', 'count')
        )
    
    def get_severity_distribution(self):
        """Get distribution by severity"""
        return dict(
            self.queryset.values('severity')
            .annotate(count=models.Count('id'))
            .values_list('severity', 'count')
        )
    
    def get_hourly_activity(self, hours: int = 24):
        """Get hourly activity breakdown"""
        start_time = timezone.now() - timedelta(hours=hours)
        return list(
            self.queryset.filter(created_at__gte=start_time)
            .extra(select={'hour': 'strftime("%%H", created_at)'})
            .values('hour')
            .annotate(count=models.Count('id'))
            .order_by('hour')
        )


class DeviceInfoSelector(BaseSelector):
    """Selector for DeviceInfo model"""
    
    def __init__(self, queryset: models.QuerySet = None):
        from .models import DeviceInfo
        if queryset is None:
            queryset = DeviceInfo.objects.all()
        super().__init__(queryset)
    
    def filter_by_user(self, user: Union[User, int, str]):
        """Filter by user"""
        if isinstance(user, User):
            return self.queryset.filter(user=user)
        elif isinstance(user, int):
            return self.queryset.filter(user_id=user)
        elif isinstance(user, str):
            return self.queryset.filter(user__username=user)
        return self.queryset
    
    def filter_trusted(self):
        """Filter for trusted devices"""
        return self.queryset.filter(is_trusted=True)
    
    def filter_untrusted(self):
        """Filter for untrusted devices"""
        return self.queryset.filter(is_trusted=False)
    
    def filter_rooted(self):
        """Filter for rooted devices"""
        return self.queryset.filter(is_rooted=True)
    
    def filter_emulators(self):
        """Filter for emulator devices"""
        return self.queryset.filter(is_emulator=True)
    
    def filter_vpn_users(self):
        """Filter for VPN users"""
        return self.queryset.filter(is_vpn=True)
    
    def filter_proxy_users(self):
        """Filter for proxy users"""
        return self.queryset.filter(is_proxy=True)
    
    def filter_by_risk_score_range(self, min_score: int, max_score: int):
        """Filter by risk score range"""
        return self.queryset.filter(risk_score__gte=min_score, risk_score__lte=max_score)
    
    def filter_high_risk_devices(self, threshold: int = 70):
        """Filter for high risk devices"""
        return self.queryset.filter(risk_score__gte=threshold)
    
    def filter_by_trust_level(self, trust_level: int):
        """Filter by trust level"""
        return self.queryset.filter(trust_level=trust_level)
    
    def filter_by_device_type(self, device_type: str):
        """Filter by device type"""
        return self.queryset.filter(device_type__icontains=device_type)
    
    def filter_by_device_brand(self, brand: str):
        """Filter by device brand"""
        return self.queryset.filter(device_brand__icontains=brand)
    
    def filter_by_android_version(self, version: str):
        """Filter by Android version"""
        return self.queryset.filter(android_version=version)
    
    def filter_by_app_version(self, version: str):
        """Filter by app version"""
        return self.queryset.filter(app_version=version)
    
    def filter_by_fingerprint(self, fingerprint: str):
        """Filter by device fingerprint"""
        return self.queryset.filter(device_fingerprint=fingerprint)
    
    def filter_by_ip_range(self, ip_start: str, ip_end: str):
        """Filter by IP range"""
        return self.queryset.filter(last_ip__range=[ip_start, ip_end])
    
    def filter_recently_active(self, hours: int = 24):
        """Filter for recently active devices"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(last_activity__gte=cutoff_time)
    
    def filter_inactive_devices(self, days: int = 30):
        """Filter for inactive devices"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.queryset.filter(last_activity__lt=cutoff_time)
    
    def get_duplicate_devices(self):
        """Find potentially duplicate devices"""
        return list(
            self.queryset.values('device_id_hash')
            .annotate(count=models.Count('id'))
            .filter(count__gt=1)
        )
    
    def get_risk_distribution(self):
        """Get distribution by risk score ranges"""
        return {
            'low': self.queryset.filter(risk_score__lt=30).count(),
            'medium': self.queryset.filter(risk_score__gte=30, risk_score__lt=70).count(),
            'high': self.queryset.filter(risk_score__gte=70).count(),
        }
    
    def get_trust_level_distribution(self):
        """Get distribution by trust level"""
        return dict(
            self.queryset.values('trust_level')
            .annotate(count=models.Count('id'))
            .values_list('trust_level', 'count')
        )
    
    def get_device_brand_distribution(self):
        """Get distribution by device brand"""
        return dict(
            self.queryset.values('device_brand')
            .annotate(count=models.Count('id'))
            .values_list('device_brand', 'count')
        )
    
    def get_top_risky_devices(self, limit: int = 10):
        """Get top risky devices"""
        return self.queryset.order_by('-risk_score')[:limit]
    
    def get_user_device_count(self, user: Union[User, int, str]):
        """Get device count for user"""
        if isinstance(user, User):
            return self.queryset.filter(user=user).count()
        elif isinstance(user, int):
            return self.queryset.filter(user_id=user).count()
        elif isinstance(user, str):
            return self.queryset.filter(user__username=user).count()
        return 0


class SecurityIncidentSelector(BaseSelector):
    """Selector for SecurityIncident model"""
    
    def __init__(self, queryset: models.QuerySet = None):
        from .models import SecurityIncident
        if queryset is None:
            queryset = SecurityIncident.objects.all()
        super().__init__(queryset)
    
    def filter_open(self):
        """Filter for open incidents"""
        return self.queryset.filter(status='open')
    
    def filter_investigating(self):
        """Filter for investigating incidents"""
        return self.queryset.filter(status='investigating')
    
    def filter_contained(self):
        """Filter for contained incidents"""
        return self.queryset.filter(status='contained')
    
    def filter_resolved(self):
        """Filter for resolved incidents"""
        return self.queryset.filter(status='resolved')
    
    def filter_unresolved(self):
        """Filter for unresolved incidents"""
        return self.queryset.filter(status__in=['open', 'investigating', 'contained'])
    
    def filter_by_incident_type(self, incident_types: Union[str, List[str]]):
        """Filter by incident type(s)"""
        if isinstance(incident_types, str):
            return self.queryset.filter(incident_type=incident_types)
        return self.queryset.filter(incident_type__in=incident_types)
    
    def filter_by_priority(self, priorities: Union[str, List[str]]):
        """Filter by priority"""
        if isinstance(priorities, str):
            return self.queryset.filter(priority=priorities)
        return self.queryset.filter(priority__in=priorities)
    
    def filter_critical(self):
        """Filter for critical incidents"""
        return self.queryset.filter(priority='critical')
    
    def filter_high_priority(self):
        """Filter for high priority incidents"""
        return self.queryset.filter(priority='high')
    
    def filter_by_assigned_user(self, user: Union[User, int, str]):
        """Filter by assigned user"""
        if isinstance(user, User):
            return self.queryset.filter(assigned_to=user)
        elif isinstance(user, int):
            return self.queryset.filter(assigned_to_id=user)
        elif isinstance(user, str):
            return self.queryset.filter(assigned_to__username=user)
        return self.queryset
    
    def filter_unassigned(self):
        """Filter for unassigned incidents"""
        return self.queryset.filter(assigned_to__isnull=True)
    
    def filter_by_affected_systems(self, systems: Union[str, List[str]]):
        """Filter by affected systems"""
        if isinstance(systems, str):
            return self.queryset.filter(affected_systems__contains=[systems])
        return self.queryset.filter(affected_systems__overlap=systems)
    
    def filter_by_date_opened(self, start_date: datetime, end_date: datetime):
        """Filter by date opened"""
        return self.queryset.filter(opened_at__range=[start_date, end_date])
    
    def filter_by_date_resolved(self, start_date: datetime, end_date: datetime):
        """Filter by date resolved"""
        return self.queryset.filter(resolved_at__range=[start_date, end_date])
    
    def filter_recently_opened(self, hours: int = 24):
        """Filter for recently opened incidents"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(opened_at__gte=cutoff_time)
    
    def filter_old_open_incidents(self, days: int = 7):
        """Filter for old open incidents"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.queryset.filter(status='open', opened_at__lt=cutoff_time)
    
    def get_status_distribution(self):
        """Get distribution by status"""
        return dict(
            self.queryset.values('status')
            .annotate(count=models.Count('id'))
            .values_list('status', 'count')
        )
    
    def get_priority_distribution(self):
        """Get distribution by priority"""
        return dict(
            self.queryset.values('priority')
            .annotate(count=models.Count('id'))
            .values_list('priority', 'count')
        )
    
    def get_type_distribution(self):
        """Get distribution by incident type"""
        return dict(
            self.queryset.values('incident_type')
            .annotate(count=models.Count('id'))
            .values_list('incident_type', 'count')
        )
    
    def get_average_resolution_time(self):
        """Calculate average resolution time"""
        resolved = self.queryset.filter(status='resolved', resolved_at__isnull=False)
        if not resolved.exists():
            return None
        
        total_seconds = resolved.annotate(
            resolution_time=models.F(models.F('resolved_at') - models.F('opened_at'))
        ).aggregate(total=models.Sum('resolution_time'))['total']
        
        count = resolved.count()
        if count > 0:
            return timedelta(seconds=total_seconds.total_seconds() / count)
        
        return None
    
    def get_top_assigned_users(self, limit: int = 10):
        """Get top users by incident count"""
        return list(
            self.queryset.filter(assigned_to__isnull=False)
            .values('assigned_to__username')
            .annotate(count=models.Count('id'))
            .order_by('-count')[:limit]
            .values('assigned_to__username', 'count')
        )
    
    def get_incidents_with_resolution_time(self):
        """Get incidents with resolution time annotation"""
        return self.queryset.annotate(
            resolution_time=models.F(models.F('resolved_at') - models.F('opened_at'))
        )


class ThreatIntelligenceSelector(BaseSelector):
    """Selector for ThreatIntelligence model"""
    
    def __init__(self, queryset: models.QuerySet = None):
        from .models import ThreatIntelligence
        if queryset is None:
            queryset = ThreatIntelligence.objects.all()
        super().__init__(queryset)
    
    def filter_active(self):
        """Filter for active threats"""
        return self.queryset.filter(is_active=True)
    
    def filter_expired(self):
        """Filter for expired threats"""
        return self.queryset.filter(expires_at__lt=timezone.now())
    
    def filter_by_threat_type(self, threat_types: Union[str, List[str]]):
        """Filter by threat type(s)"""
        if isinstance(threat_types, str):
            return self.queryset.filter(threat_type=threat_types)
        return self.queryset.filter(threat_type__in=threat_types)
    
    def filter_by_source(self, source: str):
        """Filter by source"""
        return self.queryset.filter(source__icontains=source)
    
    def filter_by_confidence_range(self, min_conf: float, max_conf: float):
        """Filter by confidence range"""
        return self.queryset.filter(confidence__gte=min_conf, confidence__lte=max_conf)
    
    def filter_high_confidence(self, threshold: float = 0.8):
        """Filter for high confidence threats"""
        return self.queryset.filter(confidence__gte=threshold)
    
    def filter_low_confidence(self, threshold: float = 0.3):
        """Filter for low confidence threats"""
        return self.queryset.filter(confidence__lte=threshold)
    
    def filter_by_severity(self, severities: Union[str, List[str]]):
        """Filter by severity"""
        if isinstance(severities, str):
            return self.queryset.filter(severity=severities)
        return self.queryset.filter(severity__in=severities)
    
    def filter_critical_threats(self):
        """Filter for critical threats"""
        return self.queryset.filter(severity='critical')
    
    def filter_by_indicator_type(self, indicator_type: str):
        """Filter by indicator type"""
        return self.queryset.filter(indicator_type=indicator_type)
    
    def filter_by_ip_range(self, ip_range: str):
        """Filter by IP range"""
        return self.queryset.filter(ip_range=ip_range)
    
    def filter_by_indicator(self, indicator: str):
        """Filter by indicator"""
        return self.queryset.filter(indicator=indicator)
    
    def filter_recently_added(self, hours: int = 24):
        """Filter for recently added threats"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(created_at__gte=cutoff_time)
    
    def filter_expiring_soon(self, days: int = 7):
        """Filter for threats expiring soon"""
        cutoff_time = timezone.now() + timedelta(days=days)
        return self.queryset.filter(
            expires_at__lte=cutoff_time,
            expires_at__gt=timezone.now()
        )
    
    def get_type_distribution(self):
        """Get distribution by threat type"""
        return dict(
            self.queryset.values('threat_type')
            .annotate(count=models.Count('id'))
            .values_list('threat_type', 'count')
        )
    
    def get_source_distribution(self):
        """Get distribution by source"""
        return dict(
            self.queryset.values('source')
            .annotate(count=models.Count('id'))
            .values_list('source', 'count')
        )
    
    def get_severity_distribution(self):
        """Get distribution by severity"""
        return dict(
            self.queryset.values('severity')
            .annotate(count=models.Count('id'))
            .values_list('severity', 'count')
        )
    
    def get_average_confidence(self):
        """Calculate average confidence"""
        result = self.queryset.aggregate(avg_confidence=models.Avg('confidence'))
        return result['avg_confidence']
    
    def get_by_confidence_threshold(self, threshold: float):
        """Filter by confidence threshold"""
        return self.queryset.filter(confidence__gte=threshold)


class UserBanSelector(BaseSelector):
    """Selector for UserBan model"""
    
    def __init__(self, queryset: models.QuerySet = None):
        from .models import UserBan
        if queryset is None:
            queryset = UserBan.objects.all()
        super().__init__(queryset)
    
    def filter_active(self):
        """Filter for active bans"""
        return self.queryset.filter(is_active=True)
    
    def filter_expired(self):
        """Filter for expired bans"""
        return self.queryset.filter(
            models.Q(expires_at__lt=timezone.now()) |
            models.Q(expires_at__isnull=False, is_active=False)
        )
    
    def filter_permanent(self):
        """Filter for permanent bans"""
        return self.queryset.filter(expires_at__isnull=True)
    
    def filter_temporary(self):
        """Filter for temporary bans"""
        return self.queryset.filter(expires_at__isnull=False)
    
    def filter_by_reason(self, reason: str):
        """Filter by reason"""
        return self.queryset.filter(reason__icontains=reason)
    
    def filter_expires_soon(self, days: int = 7):
        """Filter for bans expiring soon"""
        cutoff_time = timezone.now() + timedelta(days=days)
        return self.queryset.filter(
            expires_at__lte=cutoff_time,
            expires_at__gt=timezone.now(),
            is_active=True
        )
    
    def filter_by_banned_user(self, user: Union[User, int, str]):
        """Filter by banned user"""
        if isinstance(user, User):
            return self.queryset.filter(user=user)
        elif isinstance(user, int):
            return self.queryset.filter(user_id=user)
        elif isinstance(user, str):
            return self.queryset.filter(user__username=user)
        return self.queryset
    
    def filter_recently_banned(self, hours: int = 24):
        """Filter for recently banned users"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(created_at__gte=cutoff_time)
    
    def get_reason_distribution(self):
        """Get distribution by reason"""
        return dict(
            self.queryset.values('reason')
            .annotate(count=models.Count('id'))
            .values_list('reason', 'count')
        )
    
    def get_duration_distribution(self):
        """Get distribution by duration type"""
        return {
            'permanent': self.queryset.filter(expires_at__isnull=True).count(),
            'temporary': self.queryset.filter(expires_at__isnull=False).count(),
        }


# Selector factory
class SelectorFactory:
    """Factory for creating selectors"""
    
    @staticmethod
    def create_selector(model_class: Type[models.Model], queryset: models.QuerySet = None):
        """Create appropriate selector for model"""
        selector_map = {
            'SecurityLog': SecurityLogSelector,
            'DeviceInfo': DeviceInfoSelector,
            'SecurityIncident': SecurityIncidentSelector,
            'ThreatIntelligence': ThreatIntelligenceSelector,
            'UserBan': UserBanSelector,
        }
        
        model_name = model_class.__name__
        selector_class = selector_map.get(model_name, BaseSelector)
        
        if queryset is None:
            return selector_class()
        else:
            return selector_class(queryset)


# Export selector classes
__all__ = [
    'BaseSelector',
    'SecurityLogSelector',
    'DeviceInfoSelector',
    'SecurityIncidentSelector',
    'ThreatIntelligenceSelector',
    'UserBanSelector',
    'SelectorFactory'
]