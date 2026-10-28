"""
Security QuerySets Module
Enhanced QuerySet classes for security module operations
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Q, Count, Avg, Max, Min, Sum, F, Func, Value
from django.db.models.functions import Coalesce, Greatest, Least
from django.utils import timezone
from django.contrib.auth import get_user_model

from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.querysets')


class SecurityQuerySet(models.QuerySet):
    """Base QuerySet for security models with common methods"""
    
    def active(self):
        """Filter for active records"""
        if hasattr(self.model, 'is_active'):
            return self.filter(is_active=True)
        return self
    
    def inactive(self):
        """Filter for inactive records"""
        if hasattr(self.model, 'is_active'):
            return self.filter(is_active=False)
        return self
    
    def recent(self, days: int = 7):
        """Filter for recent records within specified days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        if hasattr(self.model, 'created_at'):
            return self.filter(created_at__gte=cutoff_date)
        return self
    
    def by_user(self, user: Union[User, int, str]):
        """Filter by user (accepts User object, ID, or username)"""
        if isinstance(user, User):
            return self.filter(user=user)
        elif isinstance(user, int):
            return self.filter(user_id=user)
        elif isinstance(user, str):
            return self.filter(user__username=user)
        return self
    
    def by_ip(self, ip_address: str):
        """Filter by IP address"""
        if hasattr(self.model, 'ip_address'):
            return self.filter(ip_address=ip_address)
        return self
    
    def by_severity(self, severity: Union[str, List[str]]):
        """Filter by severity level"""
        if hasattr(self.model, 'severity'):
            if isinstance(severity, list):
                return self.filter(severity__in=severity)
            return self.filter(severity=severity)
        return self
    
    def by_status(self, status: Union[str, List[str]]):
        """Filter by status"""
        if hasattr(self.model, 'status'):
            if isinstance(status, list):
                return self.filter(status__in=status)
            return self.filter(status=status)
        return self
    
    def by_date_range(self, start_date: datetime, end_date: datetime):
        """Filter by date range"""
        if hasattr(self.model, 'created_at'):
            return self.filter(created_at__range=[start_date, end_date])
        return self
    
    def search(self, query: str, fields: List[str] = None):
        """Search across specified fields"""
        if not query or not fields:
            return self
        
        q_objects = Q()
        for field in fields:
            if hasattr(self.model, field):
                q_objects |= Q(**{f"{field}__icontains": query})
        
        return self.filter(q_objects)
    
    def annotate_count(self, field: str = 'id') -> models.QuerySet:
        """Annotate with count"""
        return self.annotate(count=Count(field))
    
    def annotate_average(self, field: str) -> models.QuerySet:
        """Annotate with average"""
        return self.annotate(average=Avg(field))
    
    def annotate_max(self, field: str) -> models.QuerySet:
        """Annotate with maximum"""
        return self.annotate(maximum=Max(field))
    
    def annotate_min(self, field: str) -> models.QuerySet:
        """Annotate with minimum"""
        return self.annotate(minimum=Min(field))
    
    def annotate_sum(self, field: str) -> models.QuerySet:
        """Annotate with sum"""
        return self.annotate(total=Sum(field))
    
    def with_user_info(self) -> models.QuerySet:
        """Select related user information"""
        return self.select_related('user')
    
    def prefetch_related_data(self) -> models.QuerySet:
        """Prefetch related data"""
        return self.prefetch_related('user')
    
    def order_by_recent(self) -> models.QuerySet:
        """Order by most recent"""
        if hasattr(self.model, 'created_at'):
            return self.order_by('-created_at')
        return self
    
    def order_by_priority(self) -> models.QuerySet:
        """Order by priority (if available)"""
        if hasattr(self.model, 'priority'):
            return self.order_by('-priority')
        return self


class SecurityLogQuerySet(SecurityQuerySet):
    """QuerySet for SecurityLog model"""
    
    def by_security_type(self, security_type: Union[str, List[str]]):
        """Filter by security type"""
        if isinstance(security_type, list):
            return self.filter(security_type__in=security_type)
        return self.filter(security_type=security_type)
    
    def by_risk_score_range(self, min_score: int, max_score: int):
        """Filter by risk score range"""
        return self.filter(risk_score__gte=min_score, risk_score__lte=max_score)
    
    def high_risk(self, threshold: int = 70):
        """Filter for high risk logs"""
        return self.filter(risk_score__gte=threshold)
    
    def low_risk(self, threshold: int = 30):
        """Filter for low risk logs"""
        return self.filter(risk_score__lte=threshold)
    
    def failed_attempts(self):
        """Filter for failed attempts"""
        return self.filter(security_type__in=['login_failed', 'access_denied', 'permission_denied'])
    
    def successful_attempts(self):
        """Filter for successful attempts"""
        return self.filter(security_type__in=['login_success', 'access_granted'])
    
    def by_response_time(self, max_ms: int):
        """Filter by maximum response time"""
        return self.filter(response_time_ms__lte=max_ms)
    
    def slow_responses(self, threshold_ms: int = 1000):
        """Filter for slow responses"""
        return self.filter(response_time_ms__gt=threshold_ms)
    
    def with_device_info(self) -> models.QuerySet:
        """Include device information"""
        return self.select_related('device_info', 'user')
    
    def by_user_agent(self, user_agent: str):
        """Filter by user agent"""
        return self.filter(user_agent__icontains=user_agent)
    
    def by_metadata_key(self, key: str, value: Any = None):
        """Filter by metadata key/value"""
        if value is not None:
            return self.filter(metadata__contains={key: value})
        return self.filter(metadata__has_key=key)
    
    def aggregate_by_type(self) -> Dict[str, int]:
        """Aggregate logs by security type"""
        return dict(self.values('security_type').annotate(count=Count('id')).values_list('security_type', 'count'))
    
    def aggregate_by_severity(self) -> Dict[str, int]:
        """Aggregate logs by severity"""
        return dict(self.values('severity').annotate(count=Count('id')).values_list('severity', 'count'))
    
    def aggregate_by_hour(self, hours: int = 24) -> Dict[str, int]:
        """Aggregate logs by hour for specified period"""
        start_time = timezone.now() - timedelta(hours=hours)
        return dict(
            self.filter(created_at__gte=start_time)
            .extra(select={'hour': 'strftime("%%H", created_at)'})
            .values('hour')
            .annotate(count=Count('id'))
            .values_list('hour', 'count')
        )
    
    def top_ip_addresses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top IP addresses by activity"""
        return list(
            self.values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
            .values('ip_address', 'count')
        )
    
    def top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by activity"""
        return list(
            self.filter(user__isnull=False)
            .values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
            .values('user__username', 'count')
        )


class DeviceInfoQuerySet(SecurityQuerySet):
    """QuerySet for DeviceInfo model"""
    
    def trusted(self):
        """Filter for trusted devices"""
        return self.filter(is_trusted=True)
    
    def untrusted(self):
        """Filter for untrusted devices"""
        return self.filter(is_trusted=False)
    
    def rooted(self):
        """Filter for rooted devices"""
        return self.filter(is_rooted=True)
    
    def emulators(self):
        """Filter for emulator devices"""
        return self.filter(is_emulator=True)
    
    def vpn_users(self):
        """Filter for VPN users"""
        return self.filter(is_vpn=True)
    
    def proxy_users(self):
        """Filter for proxy users"""
        return self.filter(is_proxy=True)
    
    def by_risk_score_range(self, min_score: int, max_score: int):
        """Filter by risk score range"""
        return self.filter(risk_score__gte=min_score, risk_score__lte=max_score)
    
    def high_risk_devices(self, threshold: int = 70):
        """Filter for high risk devices"""
        return self.filter(risk_score__gte=threshold)
    
    def by_trust_level(self, trust_level: int):
        """Filter by trust level"""
        return self.filter(trust_level=trust_level)
    
    def by_device_type(self, device_type: str):
        """Filter by device type"""
        return self.filter(device_type__icontains=device_type)
    
    def by_device_brand(self, brand: str):
        """Filter by device brand"""
        return self.filter(device_brand__icontains=brand)
    
    def by_android_version(self, version: str):
        """Filter by Android version"""
        return self.filter(android_version=version)
    
    def by_app_version(self, version: str):
        """Filter by app version"""
        return self.filter(app_version=version)
    
    def by_fingerprint(self, fingerprint: str):
        """Filter by device fingerprint"""
        return self.filter(device_fingerprint=fingerprint)
    
    def by_ip_range(self, ip_start: str, ip_end: str):
        """Filter by IP range"""
        return self.filter(last_ip__range=[ip_start, ip_end])
    
    def recently_active(self, hours: int = 24):
        """Filter for recently active devices"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(last_activity__gte=cutoff_time)
    
    def inactive_devices(self, days: int = 30):
        """Filter for inactive devices"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.filter(last_activity__lt=cutoff_time)
    
    def duplicate_devices(self) -> models.QuerySet:
        """Find potentially duplicate devices"""
        return self.values('device_id_hash').annotate(count=Count('id')).filter(count__gt=1)
    
    def aggregate_by_risk_score(self) -> Dict[str, int]:
        """Aggregate devices by risk score ranges"""
        ranges = {
            'low': self.filter(risk_score__lt=30).count(),
            'medium': self.filter(risk_score__gte=30, risk_score__lt=70).count(),
            'high': self.filter(risk_score__gte=70).count(),
        }
        return ranges
    
    def aggregate_by_trust_level(self) -> Dict[str, int]:
        """Aggregate devices by trust level"""
        return dict(self.values('trust_level').annotate(count=Count('id')).values_list('trust_level', 'count'))
    
    def aggregate_by_device_brand(self) -> Dict[str, int]:
        """Aggregate devices by brand"""
        return dict(self.values('device_brand').annotate(count=Count('id')).values_list('device_brand', 'count'))
    
    def top_risky_devices(self, limit: int = 10):
        """Get top risky devices"""
        return self.order_by('-risk_score')[:limit]
    
    def with_session_count(self) -> models.QuerySet:
        """Annotate with session count"""
        return self.annotate(session_count=Count('usersession'))
    
    def with_security_log_count(self) -> models.QuerySet:
        """Annotate with security log count"""
        return self.annotate(log_count=Count('securitylog'))


class SecurityIncidentQuerySet(SecurityQuerySet):
    """QuerySet for SecurityIncident model"""
    
    def open(self):
        """Filter for open incidents"""
        return self.filter(status='open')
    
    def investigating(self):
        """Filter for investigating incidents"""
        return self.filter(status='investigating')
    
    def contained(self):
        """Filter for contained incidents"""
        return self.filter(status='contained')
    
    def resolved(self):
        """Filter for resolved incidents"""
        return self.filter(status='resolved')
    
    def unresolved(self):
        """Filter for unresolved incidents"""
        return self.filter(status__in=['open', 'investigating', 'contained'])
    
    def by_incident_type(self, incident_type: Union[str, List[str]]):
        """Filter by incident type"""
        if isinstance(incident_type, list):
            return self.filter(incident_type__in=incident_type)
        return self.filter(incident_type=incident_type)
    
    def by_priority(self, priority: Union[str, List[str]]):
        """Filter by priority"""
        if isinstance(priority, list):
            return self.filter(priority__in=priority)
        return self.filter(priority=priority)
    
    def critical(self):
        """Filter for critical incidents"""
        return self.filter(priority='critical')
    
    def high_priority(self):
        """Filter for high priority incidents"""
        return self.filter(priority='high')
    
    def by_assigned_user(self, user: Union[User, int, str]):
        """Filter by assigned user"""
        if isinstance(user, User):
            return self.filter(assigned_to=user)
        elif isinstance(user, int):
            return self.filter(assigned_to_id=user)
        elif isinstance(user, str):
            return self.filter(assigned_to__username=user)
        return self
    
    def unassigned(self):
        """Filter for unassigned incidents"""
        return self.filter(assigned_to__isnull=True)
    
    def by_affected_systems(self, system: Union[str, List[str]]):
        """Filter by affected systems"""
        if isinstance(system, list):
            return self.filter(affected_systems__overlap=system)
        return self.filter(affected_systems__contains=[system])
    
    def by_date_opened(self, start_date: datetime, end_date: datetime):
        """Filter by date opened"""
        return self.filter(opened_at__range=[start_date, end_date])
    
    def by_date_resolved(self, start_date: datetime, end_date: datetime):
        """Filter by date resolved"""
        return self.filter(resolved_at__range=[start_date, end_date])
    
    def recently_opened(self, hours: int = 24):
        """Filter for recently opened incidents"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(opened_at__gte=cutoff_time)
    
    def old_open_incidents(self, days: int = 7):
        """Filter for old open incidents"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.filter(status='open', opened_at__lt=cutoff_time)
    
    def with_resolution_time(self) -> models.QuerySet:
        """Annotate with resolution time"""
        return self.annotate(
            resolution_time=Func(
                F('resolved_at') - F('opened_at'),
                output_field=models.DurationField()
            )
        )
    
    def aggregate_by_status(self) -> Dict[str, int]:
        """Aggregate incidents by status"""
        return dict(self.values('status').annotate(count=Count('id')).values_list('status', 'count'))
    
    def aggregate_by_priority(self) -> Dict[str, int]:
        """Aggregate incidents by priority"""
        return dict(self.values('priority').annotate(count=Count('id')).values_list('priority', 'count'))
    
    def aggregate_by_type(self) -> Dict[str, int]:
        """Aggregate incidents by type"""
        return dict(self.values('incident_type').annotate(count=Count('id')).values_list('incident_type', 'count'))
    
    def average_resolution_time(self) -> Optional[timedelta]:
        """Calculate average resolution time"""
        resolved = self.filter(status='resolved', resolved_at__isnull=False)
        if not resolved.exists():
            return None
        
        total_seconds = resolved.annotate(
            resolution_time=Func(F('resolved_at') - F('opened_at'))
        ).aggregate(total=Sum('resolution_time'))['total']
        
        count = resolved.count()
        if count > 0:
            return timedelta(seconds=total_seconds.total_seconds() / count)
        
        return None
    
    def top_assigned_users(self, limit: int = 10):
        """Get top users by incident count"""
        return list(
            self.filter(assigned_to__isnull=False)
            .values('assigned_to__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
            .values('assigned_to__username', 'count')
        )


class ThreatIntelligenceQuerySet(SecurityQuerySet):
    """QuerySet for ThreatIntelligence model"""
    
    def active(self):
        """Filter for active threats"""
        return self.filter(is_active=True)
    
    def expired(self):
        """Filter for expired threats"""
        return self.filter(expires_at__lt=timezone.now())
    
    def by_threat_type(self, threat_type: Union[str, List[str]]):
        """Filter by threat type"""
        if isinstance(threat_type, list):
            return self.filter(threat_type__in=threat_type)
        return self.filter(threat_type=threat_type)
    
    def by_source(self, source: str):
        """Filter by source"""
        return self.filter(source__icontains=source)
    
    def by_confidence_range(self, min_conf: float, max_conf: float):
        """Filter by confidence range"""
        return self.filter(confidence__gte=min_conf, confidence__lte=max_conf)
    
    def high_confidence(self, threshold: float = 0.8):
        """Filter for high confidence threats"""
        return self.filter(confidence__gte=threshold)
    
    def low_confidence(self, threshold: float = 0.3):
        """Filter for low confidence threats"""
        return self.filter(confidence__lte=threshold)
    
    def by_severity(self, severity: Union[str, List[str]]):
        """Filter by severity"""
        if isinstance(severity, list):
            return self.filter(severity__in=severity)
        return self.filter(severity=severity)
    
    def critical_threats(self):
        """Filter for critical threats"""
        return self.filter(severity='critical')
    
    def by_indicator_type(self, indicator_type: str):
        """Filter by indicator type"""
        return self.filter(indicator_type=indicator_type)
    
    def by_ip_range(self, ip_range: str):
        """Filter by IP range"""
        return self.filter(ip_range=ip_range)
    
    def by_indicator(self, indicator: str):
        """Filter by indicator"""
        return self.filter(indicator=indicator)
    
    def recently_added(self, hours: int = 24):
        """Filter for recently added threats"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff_time)
    
    def expiring_soon(self, days: int = 7):
        """Filter for threats expiring soon"""
        cutoff_time = timezone.now() + timedelta(days=days)
        return self.filter(expires_at__lte=cutoff_time, expires_at__gt=timezone.now())
    
    def aggregate_by_type(self) -> Dict[str, int]:
        """Aggregate threats by type"""
        return dict(self.values('threat_type').annotate(count=Count('id')).values_list('threat_type', 'count'))
    
    def aggregate_by_source(self) -> Dict[str, int]:
        """Aggregate threats by source"""
        return dict(self.values('source').annotate(count=Count('id')).values_list('source', 'count'))
    
    def aggregate_by_severity(self) -> Dict[str, int]:
        """Aggregate threats by severity"""
        return dict(self.values('severity').annotate(count=Count('id')).values_list('severity', 'count'))
    
    def average_confidence(self) -> Optional[float]:
        """Calculate average confidence"""
        result = self.aggregate(avg_confidence=Avg('confidence'))
        return result['avg_confidence']
    
    def by_confidence_threshold(self, threshold: float):
        """Filter by confidence threshold"""
        return self.filter(confidence__gte=threshold)


class UserBanQuerySet(SecurityQuerySet):
    """QuerySet for UserBan model"""
    
    def active(self):
        """Filter for active bans"""
        return self.filter(is_active=True)
    
    def expired(self):
        """Filter for expired bans"""
        return self.filter(
            models.Q(expires_at__lt=timezone.now()) |
            models.Q(expires_at__isnull=False, is_active=False)
        )
    
    def permanent(self):
        """Filter for permanent bans"""
        return self.filter(expires_at__isnull=True)
    
    def temporary(self):
        """Filter for temporary bans"""
        return self.filter(expires_at__isnull=False)
    
    def by_reason(self, reason: str):
        """Filter by reason"""
        return self.filter(reason__icontains=reason)
    
    def expires_soon(self, days: int = 7):
        """Filter for bans expiring soon"""
        cutoff_time = timezone.now() + timedelta(days=days)
        return self.filter(
            expires_at__lte=cutoff_time,
            expires_at__gt=timezone.now(),
            is_active=True
        )
    
    def by_banned_user(self, user: Union[User, int, str]):
        """Filter by banned user"""
        if isinstance(user, User):
            return self.filter(user=user)
        elif isinstance(user, int):
            return self.filter(user_id=user)
        elif isinstance(user, str):
            return self.filter(user__username=user)
        return self
    
    def recently_banned(self, hours: int = 24):
        """Filter for recently banned users"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff_time)
    
    def aggregate_by_reason(self) -> Dict[str, int]:
        """Aggregate bans by reason"""
        return dict(self.values('reason').annotate(count=Count('id')).values_list('reason', 'count'))
    
    def aggregate_by_duration(self) -> Dict[str, int]:
        """Aggregate bans by duration type"""
        return {
            'permanent': self.filter(expires_at__isnull=True).count(),
            'temporary': self.filter(expires_at__isnull=False).count(),
        }


class QuerySetManager:
    """Manager for custom QuerySets"""
    
    @staticmethod
    def get_queryset_for_model(model_class: Type[models.Model]) -> Type[models.QuerySet]:
        """Get appropriate QuerySet for model"""
        queryset_map = {
            'SecurityLog': SecurityLogQuerySet,
            'DeviceInfo': DeviceInfoQuerySet,
            'SecurityIncident': SecurityIncidentQuerySet,
            'ThreatIntelligence': ThreatIntelligenceQuerySet,
            'UserBan': UserBanQuerySet,
        }
        
        model_name = model_class.__name__
        return queryset_map.get(model_name, SecurityQuerySet)
    
    @staticmethod
    def apply_queryset_to_manager(manager_class: Type[models.Manager], 
                                  queryset_class: Type[models.QuerySet]) -> Type[models.Manager]:
        """Apply custom QuerySet to Manager"""
        return manager_class.from_queryset(queryset_class)


# Export QuerySet classes
__all__ = [
    'SecurityQuerySet',
    'SecurityLogQuerySet',
    'DeviceInfoQuerySet',
    'SecurityIncidentQuerySet',
    'ThreatIntelligenceQuerySet',
    'UserBanQuerySet',
    'QuerySetManager'
]