"""
Security Repositories Module
Repository pattern implementation for data access
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan, DeviceInfo
from .selectors import (
    SecurityLogSelector, DeviceInfoSelector, SecurityIncidentSelector,
    ThreatIntelligenceSelector, UserBanSelector
)
from .querysets import SecurityQuerySet, SecurityLogQuerySet

User = get_user_model()
logger = logging.getLogger('security.repositories')


class BaseRepository:
    """Base repository with common functionality"""
    
    def __init__(self, model_class: Type[models.Model]):
        self.model_class = model_class
        self.queryset = model_class.objects.all()
        self.cache_timeout = 300  # 5 minutes
    
    def get_by_id(self, id: int):
        """Get record by ID"""
        try:
            return self.queryset.get(id=id)
        except self.model_class.DoesNotExist:
            return None
    
    def get_by_ids(self, ids: List[int]):
        """Get records by list of IDs"""
        return self.queryset.filter(id__in=ids)
    
    def create(self, **kwargs):
        """Create new record"""
        try:
            return self.model_class.objects.create(**kwargs)
        except Exception as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise
    
    def update(self, id: int, **kwargs):
        """Update existing record"""
        try:
            instance = self.get_by_id(id)
            if not instance:
                return None
            
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            
            instance.save()
            return instance
        except Exception as e:
            logger.error(f"Error updating {self.model_class.__name__} {id}: {e}")
            raise
    
    def delete(self, id: int):
        """Delete record"""
        try:
            instance = self.get_by_id(id)
            if not instance:
                return False
            
            instance.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting {self.model_class.__name__} {id}: {e}")
            return False
    
    def bulk_create(self, objects: List[models.Model]):
        """Bulk create records"""
        try:
            return self.model_class.objects.bulk_create(objects)
        except Exception as e:
            logger.error(f"Error bulk creating {self.model_class.__name__}: {e}")
            raise
    
    def bulk_update(self, objects: List[models.Model], fields: List[str]):
        """Bulk update records"""
        try:
            return self.model_class.objects.bulk_update(objects, fields)
        except Exception as e:
            logger.error(f"Error bulk updating {self.model_class.__name__}: {e}")
            raise
    
    def bulk_delete(self, ids: List[int]):
        """Bulk delete records"""
        try:
            return self.queryset.filter(id__in=ids).delete()
        except Exception as e:
            logger.error(f"Error bulk deleting {self.model_class.__name__}: {e}")
            return 0, {}
    
    def count(self):
        """Get count of records"""
        return self.queryset.count()
    
    def exists(self):
        """Check if any records exist"""
        return self.queryset.exists()
    
    def all(self):
        """Get all records"""
        return self.queryset.all()
    
    def filter(self, **kwargs):
        """Filter records"""
        return self.queryset.filter(**kwargs)
    
    def order_by(self, *fields):
        """Order records"""
        return self.queryset.order_by(*fields)


class SecurityLogRepository(BaseRepository):
    """Repository for SecurityLog model"""
    
    def __init__(self):
        super().__init__(SecurityLog)
        self.selector = SecurityLogSelector()
    
    def get_by_security_type(self, security_type: str):
        """Get logs by security type"""
        return self.selector.filter_by_security_type(security_type)
    
    def get_by_severity(self, severity: str):
        """Get logs by severity"""
        return self.selector.filter_by_severity(severity)
    
    def get_by_user(self, user: Union[User, int, str]):
        """Get logs by user"""
        return self.selector.filter_by_user(user)
    
    def get_by_ip_address(self, ip_address: str):
        """Get logs by IP address"""
        return self.selector.filter_by_ip_address(ip_address)
    
    def get_high_risk_logs(self, threshold: int = 70):
        """Get high risk logs"""
        return self.selector.filter_high_risk(threshold)
    
    def get_failed_attempts(self):
        """Get failed attempts"""
        return self.selector.filter_failed_attempts()
    
    def get_recent_logs(self, hours: int = 24):
        """Get recent logs"""
        return self.selector.filter_recent(hours)
    
    def get_logs_by_date_range(self, start_date: datetime, end_date: datetime):
        """Get logs by date range"""
        return self.selector.filter_by_date_range(start_date, end_date)
    
    def get_security_types_count(self):
        """Get count by security type"""
        return self.selector.get_security_types_count()
    
    def get_severity_distribution(self):
        """Get distribution by severity"""
        return self.selector.get_severity_distribution()
    
    def get_top_ip_addresses(self, limit: int = 10):
        """Get top IP addresses"""
        return self.selector.get_top_ip_addresses(limit)
    
    def get_top_users(self, limit: int = 10):
        """Get top users"""
        return self.selector.get_top_users(limit)
    
    def get_hourly_activity(self, hours: int = 24):
        """Get hourly activity"""
        return self.selector.get_hourly_activity(hours)
    
    def create_log(self, user: User = None, security_type: str = '', 
                   severity: str = 'info', ip_address: str = '', 
                   description: str = '', metadata: Dict[str, Any] = None):
        """Create security log"""
        return self.create(
            user=user,
            security_type=security_type,
            severity=severity,
            ip_address=ip_address,
            description=description,
            metadata=metadata or {}
        )
    
    def create_bulk_logs(self, log_data_list: List[Dict[str, Any]]):
        """Create multiple logs"""
        logs = []
        for log_data in log_data_list:
            logs.append(SecurityLog(**log_data))
        
        return self.bulk_create(logs)
    
    def cleanup_old_logs(self, days: int = 90):
        """Clean up old logs"""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = self.queryset.filter(created_at__lt=cutoff_date).delete()
        return deleted_count
    
    def get_log_statistics(self, days: int = 7):
        """Get log statistics"""
        start_date = timezone.now() - timedelta(days=days)
        logs = self.get_logs_by_date_range(start_date, timezone.now())
        
        return {
            'total_logs': logs.count(),
            'by_severity': logs.get_severity_distribution(),
            'by_type': logs.get_security_types_count(),
            'high_risk_count': logs.filter_high_risk().count(),
            'failed_attempts': logs.filter_failed_attempts().count()
        }


class DeviceInfoRepository(BaseRepository):
    """Repository for DeviceInfo model"""
    
    def __init__(self):
        super().__init__(DeviceInfo)
        self.selector = DeviceInfoSelector()
    
    def get_by_user(self, user: Union[User, int, str]):
        """Get devices by user"""
        return self.selector.filter_by_user(user)
    
    def get_trusted_devices(self):
        """Get trusted devices"""
        return self.selector.filter_trusted()
    
    def get_untrusted_devices(self):
        """Get untrusted devices"""
        return self.selector.filter_untrusted()
    
    def get_rooted_devices(self):
        """Get rooted devices"""
        return self.selector.filter_rooted()
    
    def get_high_risk_devices(self, threshold: int = 70):
        """Get high risk devices"""
        return self.selector.filter_high_risk_devices(threshold)
    
    def get_recently_active_devices(self, hours: int = 24):
        """Get recently active devices"""
        return self.selector.filter_recently_active(hours)
    
    def get_inactive_devices(self, days: int = 30):
        """Get inactive devices"""
        return self.selector.filter_inactive_devices(days)
    
    def get_device_by_fingerprint(self, fingerprint: str):
        """Get device by fingerprint"""
        return self.selector.filter_by_fingerprint(fingerprint).first()
    
    def create_device(self, user: User, device_info: Dict[str, Any]):
        """Create device info"""
        return self.create(
            user=user,
            device_id=device_info.get('device_id'),
            device_type=device_info.get('device_type'),
            device_brand=device_info.get('device_brand'),
            device_model=device_info.get('device_model'),
            android_version=device_info.get('android_version'),
            app_version=device_info.get('app_version'),
            ip_address=device_info.get('ip_address'),
            user_agent=device_info.get('user_agent'),
            is_trusted=device_info.get('is_trusted', False),
            is_rooted=device_info.get('is_rooted', False),
            is_emulator=device_info.get('is_emulator', False),
            is_vpn=device_info.get('is_vpn', False),
            is_proxy=device_info.get('is_proxy', False),
            risk_score=device_info.get('risk_score', 0),
            metadata=device_info.get('metadata', {})
        )
    
    def update_device_risk_score(self, device_id: int, risk_score: int):
        """Update device risk score"""
        return self.update(device_id, risk_score=risk_score)
    
    def trust_device(self, device_id: int):
        """Mark device as trusted"""
        return self.update(device_id, is_trusted=True)
    
    def untrust_device(self, device_id: int):
        """Mark device as untrusted"""
        return self.update(device_id, is_trusted=False)
    
    def get_device_statistics(self):
        """Get device statistics"""
        return {
            'total_devices': self.count(),
            'trusted_devices': self.get_trusted_devices().count(),
            'untrusted_devices': self.get_untrusted_devices().count(),
            'rooted_devices': self.get_rooted_devices().count(),
            'high_risk_devices': self.get_high_risk_devices().count(),
            'risk_distribution': self.selector.get_risk_distribution(),
            'trust_level_distribution': self.selector.get_trust_level_distribution()
        }


class SecurityIncidentRepository(BaseRepository):
    """Repository for SecurityIncident model"""
    
    def __init__(self):
        super().__init__(SecurityIncident)
        self.selector = SecurityIncidentSelector()
    
    def get_open_incidents(self):
        """Get open incidents"""
        return self.selector.filter_open()
    
    def get_investigating_incidents(self):
        """Get investigating incidents"""
        return self.selector.filter_investigating()
    
    def get_resolved_incidents(self):
        """Get resolved incidents"""
        return self.selector.filter_resolved()
    
    def get_unresolved_incidents(self):
        """Get unresolved incidents"""
        return self.selector.filter_unresolved()
    
    def get_by_priority(self, priority: str):
        """Get incidents by priority"""
        return self.selector.filter_by_priority(priority)
    
    def get_critical_incidents(self):
        """Get critical incidents"""
        return self.selector.filter_critical()
    
    def get_by_assigned_user(self, user: Union[User, int, str]):
        """Get incidents assigned to user"""
        return self.selector.filter_by_assigned_user(user)
    
    def get_unassigned_incidents(self):
        """Get unassigned incidents"""
        return self.selector.filter_unassigned()
    
    def get_recent_incidents(self, hours: int = 24):
        """Get recent incidents"""
        return self.selector.filter_recently_opened(hours)
    
    def get_old_open_incidents(self, days: int = 7):
        """Get old open incidents"""
        return self.selector.filter_old_open_incidents(days)
    
    def create_incident(self, title: str, incident_type: str, description: str = '',
                       severity: str = 'medium', priority: str = 'medium',
                       user: User = None, affected_systems: List[str] = None,
                       assigned_to: User = None, metadata: Dict[str, Any] = None):
        """Create security incident"""
        return self.create(
            title=title,
            incident_type=incident_type,
            description=description,
            severity=severity,
            priority=priority,
            user=user,
            affected_systems=affected_systems or [],
            assigned_to=assigned_to,
            metadata=metadata or {}
        )
    
    def assign_incident(self, incident_id: int, assigned_to: User):
        """Assign incident to user"""
        return self.update(incident_id, assigned_to=assigned_to, status='investigating')
    
    def resolve_incident(self, incident_id: int, resolution_notes: str = ''):
        """Resolve incident"""
        return self.update(
            incident_id,
            status='resolved',
            resolved_at=timezone.now(),
            resolution_notes=resolution_notes
        )
    
    def escalate_incident(self, incident_id: int, new_priority: str = None):
        """Escalate incident priority"""
        priority_order = ['low', 'medium', 'high', 'critical']
        
        incident = self.get_by_id(incident_id)
        if not incident:
            return None
        
        if new_priority:
            return self.update(incident_id, priority=new_priority, status='investigating')
        else:
            # Auto-escalate
            try:
                current_index = priority_order.index(incident.priority)
                if current_index < len(priority_order) - 1:
                    new_priority = priority_order[current_index + 1]
                    return self.update(incident_id, priority=new_priority, status='investigating')
            except ValueError:
                pass
        
        return incident
    
    def get_incident_statistics(self, days: int = 30):
        """Get incident statistics"""
        start_date = timezone.now() - timedelta(days=days)
        incidents = self.selector.filter_by_date_opened(start_date, timezone.now())
        
        return {
            'total_incidents': incidents.count(),
            'by_status': incidents.get_status_distribution(),
            'by_priority': incidents.get_priority_distribution(),
            'by_type': incidents.get_type_distribution(),
            'open_incidents': incidents.filter_open().count(),
            'critical_incidents': incidents.filter_critical().count(),
            'average_resolution_time': incidents.get_average_resolution_time()
        }


class ThreatIntelligenceRepository(BaseRepository):
    """Repository for ThreatIntelligence model"""
    
    def __init__(self):
        super().__init__(ThreatIntelligence)
        self.selector = ThreatIntelligenceSelector()
    
    def get_active_threats(self):
        """Get active threats"""
        return self.selector.filter_active()
    
    def get_expired_threats(self):
        """Get expired threats"""
        return self.selector.filter_expired()
    
    def get_by_threat_type(self, threat_type: str):
        """Get threats by type"""
        return self.selector.filter_by_threat_type(threat_type)
    
    def get_by_source(self, source: str):
        """Get threats by source"""
        return self.selector.filter_by_source(source)
    
    def get_high_confidence_threats(self, threshold: float = 0.8):
        """Get high confidence threats"""
        return self.selector.filter_high_confidence(threshold)
    
    def get_critical_threats(self):
        """Get critical threats"""
        return self.selector.filter_critical_threats()
    
    def get_recent_threats(self, hours: int = 24):
        """Get recent threats"""
        return self.selector.filter_recently_added(hours)
    
    def get_expiring_threats(self, days: int = 7):
        """Get threats expiring soon"""
        return self.selector.filter_expiring_soon(days)
    
    def create_threat(self, threat_type: str, indicator: str, indicator_type: str,
                      confidence: float = 0.5, severity: str = 'medium',
                      source: str = '', description: str = '',
                      ip_range: str = '', expires_at: datetime = None,
                      metadata: Dict[str, Any] = None):
        """Create threat intelligence"""
        return self.create(
            threat_type=threat_type,
            indicator=indicator,
            indicator_type=indicator_type,
            confidence=confidence,
            severity=severity,
            source=source,
            description=description,
            ip_range=ip_range,
            expires_at=expires_at,
            metadata=metadata or {}
        )
    
    def update_threat_confidence(self, threat_id: int, confidence: float):
        """Update threat confidence"""
        return self.update(threat_id, confidence=confidence)
    
    def expire_threat(self, threat_id: int):
        """Expire threat"""
        return self.update(threat_id, is_active=False)
    
    def bulk_expire_threats(self):
        """Bulk expire outdated threats"""
        return self.get_expired_threats().update(is_active=False)
    
    def get_threat_statistics(self):
        """Get threat statistics"""
        active_threats = self.get_active_threats()
        
        return {
            'total_active_threats': active_threats.count(),
            'by_type': active_threats.get_type_distribution(),
            'by_severity': active_threats.get_severity_distribution(),
            'by_source': active_threats.get_source_distribution(),
            'average_confidence': active_threats.get_average_confidence(),
            'expiring_soon': self.get_expiring_threats().count()
        }


class UserBanRepository(BaseRepository):
    """Repository for UserBan model"""
    
    def __init__(self):
        super().__init__(UserBan)
        self.selector = UserBanSelector()
    
    def get_active_bans(self):
        """Get active bans"""
        return self.selector.filter_active()
    
    def get_expired_bans(self):
        """Get expired bans"""
        return self.selector.filter_expired()
    
    def get_permanent_bans(self):
        """Get permanent bans"""
        return self.selector.filter_permanent()
    
    def get_temporary_bans(self):
        """Get temporary bans"""
        return self.selector.filter_temporary()
    
    def get_by_banned_user(self, user: Union[User, int, str]):
        """Get bans for user"""
        return self.selector.filter_by_banned_user(user)
    
    def get_recent_bans(self, hours: int = 24):
        """Get recent bans"""
        return self.selector.filter_recently_banned(hours)
    
    def get_expiring_soon(self, days: int = 7):
        """Get bans expiring soon"""
        return self.selector.filter_expires_soon(days)
    
    def ban_user(self, user: User, reason: str = '', expires_at: datetime = None,
                 banned_by: User = None, metadata: Dict[str, Any] = None):
        """Ban user"""
        # Check if already banned
        existing_ban = self.get_by_banned_user(user).filter_active().first()
        if existing_ban:
            return existing_ban
        
        return self.create(
            user=user,
            reason=reason,
            expires_at=expires_at,
            banned_by=banned_by,
            metadata=metadata or {}
        )
    
    def unban_user(self, user: Union[User, int, str]):
        """Unban user"""
        bans = self.get_by_banned_user(user).filter_active()
        return bans.update(is_active=False)
    
    def permanent_ban_user(self, user: User, reason: str = '',
                          banned_by: User = None, metadata: Dict[str, Any] = None):
        """Permanently ban user"""
        return self.ban_user(user, reason, None, banned_by, metadata)
    
    def temporary_ban_user(self, user: User, duration_hours: int = 24,
                          reason: str = '', banned_by: User = None,
                          metadata: Dict[str, Any] = None):
        """Temporarily ban user"""
        expires_at = timezone.now() + timedelta(hours=duration_hours)
        return self.ban_user(user, reason, expires_at, banned_by, metadata)
    
    def get_ban_statistics(self):
        """Get ban statistics"""
        return {
            'total_bans': self.count(),
            'active_bans': self.get_active_bans().count(),
            'permanent_bans': self.get_permanent_bans().count(),
            'temporary_bans': self.get_temporary_bans().count(),
            'expired_bans': self.get_expired_bans().count(),
            'by_reason': self.get_active_bans().get_reason_distribution()
        }


# Repository factory
class RepositoryFactory:
    """Factory for creating repositories"""
    
    @staticmethod
    def create_repository(model_class: Type[models.Model]):
        """Create appropriate repository for model"""
        repository_map = {
            SecurityLog: SecurityLogRepository,
            DeviceInfo: DeviceInfoRepository,
            SecurityIncident: SecurityIncidentRepository,
            ThreatIntelligence: ThreatIntelligenceRepository,
            UserBan: UserBanRepository,
        }
        
        repository_class = repository_map.get(model_class, BaseRepository)
        return repository_class()
    
    @staticmethod
    def get_security_log_repository():
        """Get security log repository"""
        return SecurityLogRepository()
    
    @staticmethod
    def get_device_info_repository():
        """Get device info repository"""
        return DeviceInfoRepository()
    
    @staticmethod
    def get_security_incident_repository():
        """Get security incident repository"""
        return SecurityIncidentRepository()
    
    @staticmethod
    def get_threat_intelligence_repository():
        """Get threat intelligence repository"""
        return ThreatIntelligenceRepository()
    
    @staticmethod
    def get_user_ban_repository():
        """Get user ban repository"""
        return UserBanRepository()


# Unit of work pattern for transaction management
class SecurityUnitOfWork:
    """Unit of work for security operations"""
    
    def __init__(self):
        self.security_logs = RepositoryFactory.get_security_log_repository()
        self.device_info = RepositoryFactory.get_device_info_repository()
        self.security_incidents = RepositoryFactory.get_security_incident_repository()
        self.threat_intelligence = RepositoryFactory.get_threat_intelligence_repository()
        self.user_bans = RepositoryFactory.get_user_ban_repository()
        self._repositories = [
            self.security_logs,
            self.device_info,
            self.security_incidents,
            self.threat_intelligence,
            self.user_bans
        ]
    
    def __enter__(self):
        """Enter transaction context"""
        self.transaction = transaction.atomic()
        self.transaction.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context"""
        if exc_type is not None:
            # Rollback on exception
            self.transaction.__exit__(exc_type, exc_val, exc_tb)
            raise
        else:
            # Commit on success
            self.transaction.__exit__(None, None, None)
    
    def commit(self):
        """Commit transaction"""
        self.transaction.__exit__(None, None, None)
    
    def rollback(self):
        """Rollback transaction"""
        self.transaction.__exit__(Exception(), None, None)
    
    def create_security_log(self, **kwargs):
        """Create security log within transaction"""
        return self.security_logs.create_log(**kwargs)
    
    def create_incident(self, **kwargs):
        """Create security incident within transaction"""
        return self.security_incidents.create_incident(**kwargs)
    
    def ban_user(self, **kwargs):
        """Ban user within transaction"""
        return self.user_bans.ban_user(**kwargs)
    
    def create_threat(self, **kwargs):
        """Create threat intelligence within transaction"""
        return self.threat_intelligence.create_threat(**kwargs)


# Export repository classes
__all__ = [
    'BaseRepository',
    'SecurityLogRepository',
    'DeviceInfoRepository',
    'SecurityIncidentRepository',
    'ThreatIntelligenceRepository',
    'UserBanRepository',
    'RepositoryFactory',
    'SecurityUnitOfWork'
]