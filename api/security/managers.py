"""
Security Model Managers
Custom managers for security models with enhanced functionality
Author: System Security Team
Version: 1.0.0
"""

from django.db import models
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


class SecurityLogManager(models.Manager):
    """
    Custom manager for SecurityLog model with enhanced query methods
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related('user').order_by('-created_at')
    
    def by_user(self, user):
        """Get logs by user"""
        return self.filter(user=user)
    
    def by_ip(self, ip_address):
        """Get logs by IP address"""
        return self.filter(ip_address=ip_address)
    
    def by_event_type(self, event_type):
        """Get logs by event type"""
        return self.filter(event_type=event_type)
    
    def by_severity(self, severity):
        """Get logs by severity level"""
        return self.filter(severity=severity)
    
    def by_date_range(self, start_date, end_date):
        """Get logs within date range"""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def recent(self, hours=24):
        """Get recent logs within specified hours"""
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since)
    
    def suspicious(self):
        """Get suspicious activity logs"""
        suspicious_events = [
            'login_failure', 'vpn_detected', 'proxy_detected',
            'suspicious_activity', 'security_violation', 'brute_force_attempt'
        ]
        return self.filter(event_type__in=suspicious_events)
    
    def high_risk(self):
        """Get high risk logs"""
        return self.filter(severity__in=['error', 'critical', 'security'])
    
    def by_country(self, country):
        """Get logs by country"""
        return self.filter(country=country)
    
    def failed_logins(self):
        """Get failed login attempts"""
        return self.filter(event_type='login_failed')
    
    def successful_logins(self):
        """Get successful login attempts"""
        return self.filter(event_type='login_success')
    
    def security_breaches(self):
        """Get security breach events"""
        return self.filter(event_type='security_breach')
    
    def fraud_events(self):
        """Get fraud-related events"""
        fraud_events = ['fraud_detected', 'fraud_attempt', 'withdrawal_blocked']
        return self.filter(event_type__in=fraud_events)
    
    def device_events(self):
        """Get device-related events"""
        device_events = ['new_device', 'device_compromised', 'device_trusted']
        return self.filter(event_type__in=device_events)
    
    def get_event_statistics(self, days=7):
        """Get event statistics for specified days"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(created_at__gte=since).values(
            'event_type'
        ).annotate(
            count=Count('id'),
            unique_users=Count('user', distinct=True),
            unique_ips=Count('ip_address', distinct=True)
        ).order_by('-count')
    
    def get_severity_distribution(self, days=7):
        """Get severity distribution for specified days"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(created_at__gte=since).values(
            'severity'
        ).annotate(
            count=Count('id')
        ).order_by('severity')
    
    def get_top_ips(self, days=7, limit=10):
        """Get top IP addresses by event count"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(created_at__gte=since).values(
            'ip_address'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:limit]
    
    def get_top_users(self, days=7, limit=10):
        """Get top users by event count"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(created_at__gte=since).values(
            'user__username'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:limit]
    
    def get_hourly_distribution(self, days=1):
        """Get hourly event distribution"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(created_at__gte=since).extra(
            select={'hour': 'extract(hour from created_at)'}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
    
    def search_events(self, query):
        """Search events by text"""
        return self.filter(
            Q(event_type__icontains=query) |
            Q(ip_address__icontains=query) |
            Q(user_agent__icontains=query) |
            Q(metadata__icontains=query)
        )


class SecurityIncidentManager(models.Manager):
    """
    Custom manager for SecurityIncident model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related(
            'user', 'assigned_to', 'created_by'
        ).order_by('-created_at')
    
    def open_incidents(self):
        """Get open incidents"""
        return self.filter(status='open')
    
    def investigating_incidents(self):
        """Get investigating incidents"""
        return self.filter(status='investigating')
    
    def resolved_incidents(self):
        """Get resolved incidents"""
        return self.filter(status='resolved')
    
    def closed_incidents(self):
        """Get closed incidents"""
        return self.filter(status='closed')
    
    def by_severity(self, severity):
        """Get incidents by severity"""
        return self.filter(severity=severity)
    
    def by_type(self, incident_type):
        """Get incidents by type"""
        return self.filter(incident_type=incident_type)
    
    def by_assignee(self, user):
        """Get incidents assigned to user"""
        return self.filter(assigned_to=user)
    
    def unassigned(self):
        """Get unassigned incidents"""
        return self.filter(assigned_to__isnull=True)
    
    def high_severity(self):
        """Get high severity incidents"""
        return self.filter(severity__in=['high', 'critical'])
    
    def critical(self):
        """Get critical incidents"""
        return self.filter(severity='critical')
    
    def recent(self, days=7):
        """Get recent incidents within specified days"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def overdue(self):
        """Get overdue incidents"""
        return self.filter(
            due_date__lt=timezone.now(),
            status__in=['open', 'investigating']
        )
    
    def by_date_range(self, start_date, end_date):
        """Get incidents within date range"""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def get_incident_statistics(self, days=30):
        """Get incident statistics"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(created_at__gte=since).aggregate(
            total=Count('id'),
            open_count=Count('id', filter=Q(status='open')),
            investigating_count=Count('id', filter=Q(status='investigating')),
            resolved_count=Count('id', filter=Q(status='resolved')),
            critical_count=Count('id', filter=Q(severity='critical')),
            high_count=Count('id', filter=Q(severity='high')),
            avg_resolution_time=Avg('resolution_time'),
        )
    
    def get_resolution_trends(self, days=30):
        """Get resolution trends"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(
            created_at__gte=since,
            resolved_at__isnull=False
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            resolved_count=Count('id'),
            avg_resolution_time=Avg('resolution_time')
        ).order_by('day')
    
    def get_assignee_workload(self):
        """Get assignee workload"""
        return self.filter(
            status__in=['open', 'investigating']
        ).values(
            'assigned_to__username'
        ).annotate(
            count=Count('id'),
            critical_count=Count('id', filter=Q(severity='critical')),
            high_count=Count('id', filter=Q(severity='high'))
        ).order_by('-count')


class IPBlacklistManager(models.Manager):
    """
    Custom manager for IPBlacklist model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().order_by('-created_at')
    
    def active(self):
        """Get active blacklist entries"""
        return self.filter(is_active=True)
    
    def expired(self):
        """Get expired blacklist entries"""
        return self.filter(expires_at__lt=timezone.now())
    
    def permanent(self):
        """Get permanent blacklist entries"""
        return self.filter(expires_at__isnull=True)
    
    def by_type(self, blacklist_type):
        """Get entries by blacklist type"""
        return self.filter(blacklist_type=blacklist_type)
    
    def by_source(self, source):
        """Get entries by source"""
        return self.filter(source=source)
    
    def by_ip(self, ip_address):
        """Get entry by IP address"""
        return self.filter(ip_address=ip_address)
    
    def by_ip_range(self, ip_network):
        """Get entries by IP network"""
        # This would require IP range functionality
        return self.filter(ip_address__startswith=ip_network.split('.')[0])
    
    def by_confidence(self, min_confidence=None, max_confidence=None):
        """Get entries by confidence range"""
        queryset = self.all()
        if min_confidence is not None:
            queryset = queryset.filter(confidence__gte=min_confidence)
        if max_confidence is not None:
            queryset = queryset.filter(confidence__lte=max_confidence)
        return queryset
    
    def high_confidence(self, min_confidence=80):
        """Get high confidence entries"""
        return self.filter(confidence__gte=min_confidence)
    
    def recent(self, days=7):
        """Get recent blacklist entries"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def expiring_soon(self, days=7):
        """Get entries expiring soon"""
        until = timezone.now() + timedelta(days=days)
        return self.filter(
            expires_at__lte=until,
            expires_at__gt=timezone.now()
        )
    
    def is_blacklisted(self, ip_address):
        """Check if IP is blacklisted"""
        return self.active().filter(ip_address=ip_address).exists()
    
    def get_blacklist_reason(self, ip_address):
        """Get blacklist reason for IP"""
        try:
            return self.active().get(ip_address=ip_address)
        except self.model.DoesNotExist:
            return None
    
    def get_blacklist_statistics(self):
        """Get blacklist statistics"""
        return self.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            expired=Count('id', filter=Q(expires_at__lt=timezone.now())),
            permanent=Count('id', filter=Q(expires_at__isnull=True)),
            avg_confidence=Avg('confidence'),
        )
    
    def get_type_distribution(self):
        """Get blacklist type distribution"""
        return self.active().values(
            'blacklist_type'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
    
    def get_source_distribution(self):
        """Get blacklist source distribution"""
        return self.active().values(
            'source'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
    
    def cleanup_expired(self):
        """Cleanup expired blacklist entries"""
        expired_count = self.expired().update(is_active=False)
        logger.info(f"Deactivated {expired_count} expired blacklist entries")
        return expired_count


class DeviceInfoManager(models.Manager):
    """
    Custom manager for DeviceInfo model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related('user').order_by('-last_seen_at')
    
    def trusted(self):
        """Get trusted devices"""
        return self.filter(is_trusted=True)
    
    def untrusted(self):
        """Get untrusted devices"""
        return self.filter(is_trusted=False)
    
    def by_user(self, user):
        """Get devices by user"""
        return self.filter(user=user)
    
    def by_type(self, device_type):
        """Get devices by type"""
        return self.filter(device_type=device_type)
    
    def by_platform(self, platform):
        """Get devices by platform"""
        return self.filter(platform=platform)
    
    def by_ip(self, ip_address):
        """Get devices by IP address"""
        return self.filter(ip_address=ip_address)
    
    def mobile(self):
        """Get mobile devices"""
        mobile_platforms = ['android', 'ios', 'mobile', 'tablet']
        return self.filter(platform__in=mobile_platforms)
    
    def desktop(self):
        """Get desktop devices"""
        desktop_platforms = ['windows', 'mac', 'linux', 'unix']
        return self.filter(platform__in=desktop_platforms)
    
    def high_trust_score(self, min_score=80):
        """Get devices with high trust score"""
        return self.filter(trust_score__gte=min_score)
    
    def low_trust_score(self, max_score=30):
        """Get devices with low trust score"""
        return self.filter(trust_score__lte=max_score)
    
    def recent(self, days=30):
        """Get recently seen devices"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(last_seen_at__gte=since)
    
    def inactive(self, days=90):
        """Get inactive devices"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(last_seen_at__lt=since)
    
    def by_fingerprint(self, fingerprint):
        """Get device by fingerprint"""
        return self.filter(device_fingerprint=fingerprint)
    
    def has_fingerprint(self):
        """Get devices with fingerprint"""
        return self.filter(device_fingerprint__isnull=False)
    
    def get_device_statistics(self):
        """Get device statistics"""
        return self.aggregate(
            total=Count('id'),
            trusted=Count('id', filter=Q(is_trusted=True)),
            mobile=Count('id', filter=Q(platform__in=['android', 'ios', 'mobile'])),
            avg_trust_score=Avg('trust_score'),
        )
    
    def get_platform_distribution(self):
        """Get platform distribution"""
        return self.values('platform').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def get_type_distribution(self):
        """Get device type distribution"""
        return self.values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def get_user_device_count(self, user):
        """Get device count for user"""
        return self.filter(user=user).count()
    
    def cleanup_inactive_devices(self, days=180):
        """Cleanup very old inactive devices"""
        since = timezone.now() - timedelta(days=days)
        deleted_count = self.filter(last_seen_at__lt=since).delete()[0]
        logger.info(f"Deleted {deleted_count} inactive devices older than {days} days")
        return deleted_count


class RiskScoreManager(models.Manager):
    """
    Custom manager for RiskScore model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related('user').order_by('-calculated_at')
    
    def by_user(self, user):
        """Get risk scores by user"""
        return self.filter(user=user)
    
    def high_risk(self, min_score=70):
        """Get high risk scores"""
        return self.filter(current_score__gte=min_score)
    
    def medium_risk(self, min_score=40, max_score=69):
        """Get medium risk scores"""
        return self.filter(current_score__gte=min_score, current_score__lte=max_score)
    
    def low_risk(self, max_score=39):
        """Get low risk scores"""
        return self.filter(current_score__lte=max_score)
    
    def expired(self):
        """Get expired risk scores"""
        return self.filter(expires_at__lt=timezone.now())
    
    def recent(self, days=7):
        """Get recent risk scores"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(calculated_at__gte=since)
    
    def by_score_range(self, min_score=None, max_score=None):
        """Get scores by range"""
        queryset = self.all()
        if min_score is not None:
            queryset = queryset.filter(current_score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(current_score__lte=max_score)
        return queryset
    
    def get_latest_for_user(self, user):
        """Get latest risk score for user"""
        return self.filter(user=user).order_by('-calculated_at').first()
    
    def get_risk_distribution(self):
        """Get risk score distribution"""
        return self.aggregate(
            total=Count('id'),
            high_risk=Count('id', filter=Q(current_score__gte=70)),
            medium_risk=Count('id', filter=Q(current_score__gte=40, current_score__lte=69)),
            low_risk=Count('id', filter=Q(current_score__lte=39)),
            avg_score=Avg('current_score'),
            max_score=Max('current_score'),
            min_score=Min('current_score'),
        )
    
    def get_top_risk_users(self, limit=10):
        """Get users with highest risk scores"""
        return self.values(
            'user__username'
        ).annotate(
            latest_score=Max('current_score')
        ).order_by('-latest_score')[:limit]
    
    def get_risk_trends(self, days=30):
        """Get risk score trends"""
        since = timezone.now() - timedelta(days=days)
        
        return self.filter(calculated_at__gte=since).extra(
            select={'day': 'date(calculated_at)'}
        ).values('day').annotate(
            avg_score=Avg('current_score'),
            max_score=Max('current_score'),
            min_score=Min('current_score'),
            count=Count('id')
        ).order_by('day')
    
    def cleanup_expired_scores(self):
        """Cleanup expired risk scores"""
        expired_count = self.expired().delete()[0]
        logger.info(f"Deleted {expired_count} expired risk scores")
        return expired_count


class UserBanManager(models.Manager):
    """
    Custom manager for UserBan model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related(
            'user', 'created_by'
        ).order_by('-created_at')
    
    def active(self):
        """Get active bans"""
        return self.filter(is_active=True)
    
    def expired(self):
        """Get expired bans"""
        return self.filter(expires_at__lt=timezone.now())
    
    def permanent(self):
        """Get permanent bans"""
        return self.filter(expires_at__isnull=True)
    
    def by_user(self, user):
        """Get bans by user"""
        return self.filter(user=user)
    
    def by_creator(self, creator):
        """Get bans by creator"""
        return self.filter(created_by=creator)
    
    def by_type(self, ban_type):
        """Get bans by type"""
        return self.filter(ban_type=ban_type)
    
    def by_reason(self, reason):
        """Get bans by reason"""
        return self.filter(reason__icontains=reason)
    
    def recent(self, days=7):
        """Get recent bans"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def expiring_soon(self, days=7):
        """Get bans expiring soon"""
        until = timezone.now() + timedelta(days=days)
        return self.filter(
            expires_at__lte=until,
            expires_at__gt=timezone.now()
        )
    
    def is_banned(self, user):
        """Check if user is banned"""
        return self.active().filter(user=user).exists()
    
    def get_active_ban(self, user):
        """Get active ban for user"""
        try:
            return self.active().get(user=user)
        except self.model.DoesNotExist:
            return None
    
    def get_ban_statistics(self):
        """Get ban statistics"""
        return self.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            expired=Count('id', filter=Q(expires_at__lt=timezone.now())),
            permanent=Count('id', filter=Q(expires_at__isnull=True)),
        )
    
    def get_type_distribution(self):
        """Get ban type distribution"""
        return self.active().values('ban_type').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def cleanup_expired_bans(self):
        """Cleanup expired bans"""
        expired_count = self.expired().update(is_active=False)
        logger.info(f"Deactivated {expired_count} expired bans")
        return expired_count


class SecurityPolicyManager(models.Manager):
    """
    Custom manager for SecurityPolicy model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related('user').order_by('-created_at')
    
    def active(self):
        """Get active policies"""
        return self.filter(is_active=True)
    
    def inactive(self):
        """Get inactive policies"""
        return self.filter(is_active=False)
    
    def by_key(self, policy_key):
        """Get policies by key"""
        return self.filter(policy_key=policy_key)
    
    def by_type(self, policy_type):
        """Get policies by type"""
        return self.filter(policy_type=policy_type)
    
    def mandatory(self):
        """Get mandatory policies"""
        return self.filter(is_mandatory=True)
    
    def optional(self):
        """Get optional policies"""
        return self.filter(is_mandatory=False)
    
    def by_priority(self, priority):
        """Get policies by priority"""
        return self.filter(priority=priority)
    
    def high_priority(self, min_priority=1):
        """Get high priority policies"""
        return self.filter(priority__lte=min_priority)
    
    def recent(self, days=30):
        """Get recent policies"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def get_policy_value(self, policy_key):
        """Get policy value by key"""
        try:
            policy = self.active().get(policy_key=policy_key)
            return policy.value
        except self.model.DoesNotExist:
            return None
    
    def get_policy_statistics(self):
        """Get policy statistics"""
        return self.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            mandatory=Count('id', filter=Q(is_mandatory=True)),
            avg_priority=Avg('priority'),
        )
    
    def get_type_distribution(self):
        """Get policy type distribution"""
        return self.active().values('policy_type').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def get_priority_distribution(self):
        """Get priority distribution"""
        return self.active().values('priority').annotate(
            count=Count('id')
        ).order_by('priority')


class SecurityInsightManager(models.Manager):
    """
    Custom manager for SecurityInsight model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().order_by('-insight_date')
    
    def by_date(self, date):
        """Get insights by date"""
        return self.filter(insight_date=date)
    
    def by_date_range(self, start_date, end_date):
        """Get insights within date range"""
        return self.filter(
            insight_date__gte=start_date,
            insight_date__lte=end_date
        )
    
    def recent(self, days=30):
        """Get recent insights"""
        since = timezone.now().date() - timedelta(days=days)
        return self.filter(insight_date__gte=since)
    
    def high_risk_days(self, min_events=10):
        """Get days with high risk events"""
        return self.filter(high_risk_events__gte=min_events)
    
    def by_event_count(self, min_events=None, max_events=None):
        """Get insights by event count range"""
        queryset = self.all()
        if min_events is not None:
            queryset = queryset.filter(total_security_events__gte=min_events)
        if max_events is not None:
            queryset = queryset.filter(total_security_events__lte=max_events)
        return queryset
    
    def get_insight_summary(self, days=30):
        """Get insight summary for specified days"""
        since = timezone.now().date() - timedelta(days=days)
        
        return self.filter(insight_date__gte=since).aggregate(
            total_days=Count('id'),
            total_events=Sum('total_security_events'),
            total_high_risk=Sum('high_risk_events'),
            total_vpn_detections=Sum('vpn_detections'),
            total_proxy_detections=Sum('proxy_detections'),
            total_failed_logins=Sum('failed_logins'),
            total_successful_logins=Sum('successful_logins'),
            avg_events_per_day=Avg('total_security_events'),
            max_events_per_day=Max('total_security_events'),
        )
    
    def get_daily_trends(self, days=30):
        """Get daily security trends"""
        since = timezone.now().date() - timedelta(days=days)
        
        return self.filter(insight_date__gte=since).values(
            'insight_date'
        ).annotate(
            total_events=Sum('total_security_events'),
            high_risk_events=Sum('high_risk_events'),
            vpn_detections=Sum('vpn_detections'),
            proxy_detections=Sum('proxy_detections'),
            failed_logins=Sum('failed_logins'),
            successful_logins=Sum('successful_logins'),
        ).order_by('insight_date')
    
    def get_top_risk_days(self, days=30, limit=10):
        """Get days with highest risk events"""
        since = timezone.now().date() - timedelta(days=days)
        
        return self.filter(insight_date__gte=since).order_by(
            '-high_risk_events'
        )[:limit]
    
    def get_event_type_trends(self, days=30):
        """Get event type trends over time"""
        since = timezone.now().date() - timedelta(days=days)
        
        return self.filter(insight_date__gte=since).aggregate(
            avg_total_events=Avg('total_security_events'),
            avg_high_risk=Avg('high_risk_events'),
            avg_vpn_detections=Avg('vpn_detections'),
            avg_proxy_detections=Avg('proxy_detections'),
            avg_failed_logins=Avg('failed_logins'),
            avg_successful_logins=Avg('successful_logins'),
        )


class PasswordHistoryManager(models.Manager):
    """
    Custom manager for PasswordHistory model
    """
    
    def get_queryset(self):
        """Get base queryset with optimizations"""
        return super().get_queryset().select_related('user').order_by('-created_at')
    
    def by_user(self, user):
        """Get password history by user"""
        return self.filter(user=user)
    
    def recent(self, days=365):
        """Get recent password history"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=since)
    
    def by_algorithm(self, algorithm):
        """Get passwords by algorithm"""
        return self.filter(password_algorithm=algorithm)
    
    def by_ip(self, ip_address):
        """Get passwords changed from IP"""
        return self.filter(ip_address=ip_address)
    
    def get_latest_passwords(self, user, count=5):
        """Get latest passwords for user"""
        return self.filter(user=user)[:count]
    
    def check_password_reuse(self, user, password_hash, history_limit=12):
        """Check if password has been used before"""
        return self.filter(
            user=user,
            password_hash=password_hash
        ).order_by('-created_at')[:history_limit].exists()
    
    def get_password_change_frequency(self, user, days=365):
        """Get password change frequency for user"""
        since = timezone.now() - timedelta(days=days)
        return self.filter(user=user, created_at__gte=since).count()
    
    def get_algorithm_distribution(self):
        """Get password algorithm distribution"""
        return self.values('password_algorithm').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def cleanup_old_passwords(self, days=730):
        """Cleanup old password history (2 years)"""
        since = timezone.now() - timedelta(days=days)
        deleted_count = self.filter(created_at__lt=since).delete()[0]
        logger.info(f"Deleted {deleted_count} old password history entries")
        return deleted_count


# Export all managers for use in models
__all__ = [
    'SecurityLogManager',
    'SecurityIncidentManager',
    'IPBlacklistManager',
    'DeviceInfoManager',
    'RiskScoreManager',
    'UserBanManager',
    'SecurityPolicyManager',
    'SecurityInsightManager',
    'PasswordHistoryManager',
]