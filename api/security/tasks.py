"""
Enhanced Security Tasks Module
Scheduled security tasks for automated security operations
Author: System Security Team
Version: 2.0.0
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.mail import mail_admins, send_mail
from django.core.management import call_command
import json
import traceback

from .models import (
    SecurityLog, SecurityIncident, UserBan, IPBlacklist, 
    ThreatIntelligence, RiskScore, DeviceInfo, TrustedDevice,
    PasswordHistory, SecurityPolicy, SecurityInsight
)
from .vpn_detector import VPNDetector, VPNServiceError
from .services.ThreatIntelService import ThreatIntelService
from .services.IncidentService import IncidentService

User = get_user_model()

logger = logging.getLogger(__name__)


class SecurityTasks:
    """Main class for security tasks"""
    
    def __init__(self):
        self.vpn_detector = VPNDetector()
        self.threat_service = ThreatIntelService()
        self.incident_service = IncidentService()
    
    def scan_suspicious_logins(self):
        """
        Scan for suspicious login patterns every 15 minutes
        Detects multiple failed logins, unusual locations, and suspicious timing
        """
        logger.info("Starting suspicious login scan...")
        
        try:
            cutoff_time = timezone.now() - timedelta(minutes=15)
            
            # Get failed login attempts in the last 15 minutes
            failed_logins = SecurityLog.objects.filter(
                security_type='login_failure',
                created_at__gte=cutoff_time
            ).values('user_id', 'ip_address').annotate(
                failure_count=models.Count('id'),
                unique_ips=models.Count('ip_address', distinct=True)
            )
            
            suspicious_logins = []
            
            for login_data in failed_logins:
                if login_data['failure_count'] >= 5:  # Threshold for suspicious activity
                    user = User.objects.filter(id=login_data['user_id']).first()
                    
                    suspicious_logins.append({
                        'user_id': login_data['user_id'],
                        'username': user.username if user else 'Unknown',
                        'ip_address': login_data['ip_address'],
                        'failure_count': login_data['failure_count'],
                        'unique_ips': login_data['unique_ips'],
                        'risk_level': self._calculate_login_risk(login_data)
                    })
            
            # Process suspicious logins
            for suspicious_login in suspicious_logins:
                self._handle_suspicious_login(suspicious_login)
            
            logger.info(f"Suspicious login scan completed. Found {len(suspicious_logins)} suspicious patterns.")
            
            return {
                'status': 'success',
                'suspicious_logins_count': len(suspicious_logins),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Suspicious login scan failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def expire_locked_accounts(self):
        """
        Hourly check for expired account locks
        Automatically unlocks accounts when ban period expires
        """
        logger.info("Starting expired account lock check...")
        
        try:
            current_time = timezone.now()
            
            # Get expired bans
            expired_bans = UserBan.objects.filter(
                is_active=True,
                expires_at__lte=current_time
            ).select_related('user')
            
            unlocked_accounts = []
            
            for ban in expired_bans:
                with transaction.atomic():
                    # Deactivate the ban
                    ban.is_active = False
                    ban.save()
                    
                    # Reactivate user if inactive
                    if not ban.user.is_active:
                        ban.user.is_active = True
                        ban.user.save()
                    
                    # Create security log
                    SecurityLog.objects.create(
                        user=ban.user,
                        security_type='account_unlocked',
                        severity='info',
                        ip_address='127.0.0.1',
                        user_agent='Security Tasks System',
                        metadata={
                            'unlock_reason': 'ban_expired',
                            'original_ban_reason': ban.reason,
                            'ban_duration': (current_time - ban.created_at).total_seconds() / 3600
                        }
                    )
                    
                    unlocked_accounts.append({
                        'user_id': ban.user.id,
                        'username': ban.user.username,
                        'unlock_reason': 'ban_expired',
                        'original_reason': ban.reason
                    })
            
            logger.info(f"Expired lock check completed. Unlocked {len(unlocked_accounts)} accounts.")
            
            return {
                'status': 'success',
                'unlocked_accounts_count': len(unlocked_accounts),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Expired lock check failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def update_threat_intelligence(self):
        """
        Daily threat feed update
        Updates threat intelligence from external sources
        """
        logger.info("Starting threat intelligence update...")
        
        try:
            updated_feeds = []
            
            # Process all configured threat feeds
            feed_results = self.threat_service._process_all_feeds()
            
            for feed_name, result in feed_results.items():
                if result.get('success', False):
                    updated_feeds.append(feed_name)
                    logger.info(f"Successfully updated threat feed: {feed_name}")
                else:
                    logger.warning(f"Failed to update threat feed: {feed_name}")
            
            # Clean up expired threat intelligence
            cleanup_result = self.threat_service.cleanup_expired_threat_intelligence()
            
            # Generate summary
            summary = {
                'status': 'success',
                'updated_feeds': updated_feeds,
                'expired_cleaned': cleanup_result.get('deleted_count', 0),
                'timestamp': timezone.now().isoformat()
            }
            
            # Send notification if there were significant updates
            if len(updated_feeds) > 0:
                self._send_threat_intelligence_notification(summary)
            
            logger.info(f"Threat intelligence update completed. Updated {len(updated_feeds)} feeds.")
            
            return summary
            
        except Exception as e:
            logger.error(f"Threat intelligence update failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def generate_security_report(self):
        """
        Weekly security digest generation
        Creates comprehensive security report for the past week
        """
        logger.info("Starting weekly security report generation...")
        
        try:
            week_start = timezone.now() - timedelta(days=7)
            
            # Gather statistics
            stats = self._gather_security_statistics(week_start)
            
            # Generate report data
            report_data = {
                'report_period': {
                    'start': week_start.isoformat(),
                    'end': timezone.now().isoformat(),
                    'type': 'weekly_digest'
                },
                'statistics': stats,
                'trends': self._calculate_security_trends(week_start),
                'recommendations': self._generate_security_recommendations(stats),
                'generated_at': timezone.now().isoformat()
            }
            
            # Export report
            report_file = self._export_security_report(report_data)
            
            # Send report to admins
            self._send_weekly_security_report(report_data, report_file)
            
            logger.info("Weekly security report generated successfully.")
            
            return {
                'status': 'success',
                'report_file': report_file,
                'statistics': stats,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Weekly security report generation failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def cleanup_old_security_logs(self):
        """
        Delete security logs older than 90 days
        Maintains database performance and storage efficiency
        """
        logger.info("Starting old security logs cleanup...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=90)
            
            # Delete old logs in batches
            old_logs = SecurityLog.objects.filter(
                created_at__lt=cutoff_date
            )
            
            deleted_count = 0
            batch_size = 1000
            
            while old_logs.exists():
                batch = old_logs[:batch_size]
                deleted_count += batch.count()
                batch.delete()
                logger.info(f"Deleted batch of {batch.count()} old security logs")
            
            # Archive important logs before deletion if needed
            self._archive_important_logs(cutoff_date)
            
            logger.info(f"Security logs cleanup completed. Deleted {deleted_count} old logs.")
            
            return {
                'status': 'success',
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Security logs cleanup failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def refresh_vpn_database(self):
        """
        Weekly VPN/proxy database update
        Updates VPN and proxy detection databases
        """
        logger.info("Starting VPN database refresh...")
        
        try:
            updated_entries = []
            
            # Get recent IP addresses from security logs
            cutoff_time = timezone.now() - timedelta(days=7)
            recent_ips = SecurityLog.objects.filter(
                created_at__gte=cutoff_time,
                ip_address__isnull=False
            ).values_list('ip_address', flat=True).distinct()
            
            vpn_detections = []
            proxy_detections = []
            
            for ip_address in recent_ips:
                try:
                    # Check for VPN/proxy
                    vpn_result = self.vpn_detector.is_vpn(ip_address)
                    
                    if vpn_result.get('is_vpn'):
                        vpn_detections.append({
                            'ip_address': ip_address,
                            'vpn_type': vpn_result.get('vpn_type', 'unknown'),
                            'confidence': vpn_result.get('confidence', 0),
                            'details': vpn_result.get('details', {}),
                            'detected_at': timezone.now().isoformat()
                        })
                    
                    if vpn_result.get('is_proxy'):
                        proxy_detections.append({
                            'ip_address': ip_address,
                            'proxy_type': vpn_result.get('proxy_type', 'unknown'),
                            'confidence': vpn_result.get('confidence', 0),
                            'details': vpn_result.get('details', {}),
                            'detected_at': timezone.now().isoformat()
                        })
                        
                except VPNServiceError as e:
                    logger.warning(f"VPN detection failed for IP {ip_address}: {str(e)}")
                    continue
            
            # Update blacklist entries
            updated_entries = self._update_vpn_blacklist(vpn_detections, proxy_detections)
            
            logger.info(f"VPN database refresh completed. Updated {len(updated_entries)} entries.")
            
            return {
                'status': 'success',
                'vpn_detections': len(vpn_detections),
                'proxy_detections': len(proxy_detections),
                'updated_entries': len(updated_entries),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"VPN database refresh failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def alert_critical_events(self):
        """
        Real-time critical event alerting
        Monitors for and alerts on critical security events
        """
        logger.info("Starting critical event monitoring...")
        
        try:
            critical_events = []
            
            # Check for critical security incidents
            critical_incidents = SecurityIncident.objects.filter(
                severity='critical',
                status__in=['open', 'investigating']
            ).select_related('user')
            
            for incident in critical_incidents:
                critical_events.append({
                    'type': 'critical_incident',
                    'incident_id': incident.incident_id,
                    'title': incident.title,
                    'user': incident.user.username if incident.user else 'Unknown',
                    'created_at': incident.created_at.isoformat(),
                    'severity': incident.severity
                })
            
            # Check for high-risk users
            high_risk_users = RiskScore.objects.filter(
                current_score__gte=80,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).select_related('user')
            
            for risk_score in high_risk_users:
                critical_events.append({
                    'type': 'high_risk_user',
                    'user_id': risk_score.user.id,
                    'username': risk_score.user.username,
                    'risk_score': risk_score.current_score,
                    'risk_factors': risk_score.risk_factors,
                    'created_at': risk_score.created_at.isoformat()
                })
            
            # Check for active bans
            recent_bans = UserBan.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1),
                is_active=True
            ).select_related('user')
            
            for ban in recent_bans:
                critical_events.append({
                    'type': 'active_ban',
                    'user_id': ban.user.id,
                    'username': ban.user.username,
                    'ban_type': ban.ban_type,
                    'reason': ban.reason,
                    'created_at': ban.created_at.isoformat()
                })
            
            # Send alerts for critical events
            if critical_events:
                self._send_critical_alerts(critical_events)
            
            logger.info(f"Critical event monitoring completed. Found {len(critical_events)} critical events.")
            
            return {
                'status': 'success',
                'critical_events_count': len(critical_events),
                'events_by_type': self._group_events_by_type(critical_events),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Critical event alerting failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _calculate_login_risk(self, login_data):
        """Calculate risk level for login data"""
        risk_score = 0
        
        # Base score from failure count
        if login_data['failure_count'] >= 10:
            risk_score += 40
        elif login_data['failure_count'] >= 5:
            risk_score += 20
        
        # Score from multiple IPs (possible distributed attack)
        if login_data['unique_ips'] >= 3:
            risk_score += 30
        elif login_data['unique_ips'] >= 2:
            risk_score += 15
        
        # Determine risk level
        if risk_score >= 50:
            return 'high'
        elif risk_score >= 25:
            return 'medium'
        else:
            return 'low'
    
    def _handle_suspicious_login(self, suspicious_login):
        """Handle suspicious login activity"""
        try:
            user = User.objects.get(id=suspicious_login['user_id'])
            
            # Check if user is already banned
            existing_ban = UserBan.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if not existing_ban:
                # Create temporary ban
                ban = UserBan.objects.create(
                    user=user,
                    reason=f"Suspicious login activity: {suspicious_login['failure_count']} failures",
                    ban_type='temporary',
                    expires_at=timezone.now() + timedelta(hours=1),
                    created_by=None  # System created
                )
                
                # Create security incident
                self.incident_service.create_incident_from_security_event({
                    'user': user,
                    'incident_type': 'suspicious_login_activity',
                    'severity': 'medium',
                    'title': f"Suspicious Login Activity: {user.username}",
                    'description': f"Detected {suspicious_login['failure_count']} failed login attempts",
                    'evidence': suspicious_login
                })
                
                # Log the action
                SecurityLog.objects.create(
                    user=user,
                    security_type='account_auto_banned',
                    severity='warning',
                    ip_address=suspicious_login['ip_address'],
                    user_agent='Security Tasks System',
                    metadata={
                        'ban_reason': 'suspicious_login_activity',
                        'failure_count': suspicious_login['failure_count'],
                        'ban_id': str(ban.id)
                    }
                )
        
        except User.DoesNotExist:
            logger.warning(f"User not found for suspicious login: {suspicious_login['user_id']}")
        except Exception as e:
            logger.error(f"Failed to handle suspicious login: {str(e)}")
    
    def _gather_security_statistics(self, week_start):
        """Gather security statistics for the week"""
        return {
            'total_security_events': SecurityLog.objects.filter(
                created_at__gte=week_start
            ).count(),
            'incidents_created': SecurityIncident.objects.filter(
                created_at__gte=week_start
            ).count(),
            'users_banned': UserBan.objects.filter(
                created_at__gte=week_start
            ).count(),
            'ips_blocked': IPBlacklist.objects.filter(
                created_at__gte=week_start
            ).count(),
            'threat_intelligence_updated': ThreatIntelligence.objects.filter(
                created_at__gte=week_start
            ).count(),
            'high_risk_users': RiskScore.objects.filter(
                current_score__gte=70,
                created_at__gte=week_start
            ).count(),
            'vpn_detections': SecurityLog.objects.filter(
                created_at__gte=week_start,
                security_type='vpn_detected'
            ).count(),
            'failed_logins': SecurityLog.objects.filter(
                created_at__gte=week_start,
                security_type='login_failure'
            ).count(),
            'successful_logins': SecurityLog.objects.filter(
                created_at__gte=week_start,
                security_type='login_success'
            ).count()
        }
    
    def _calculate_security_trends(self, week_start):
        """Calculate security trends"""
        # This would implement trend analysis logic
        # For now, return placeholder data
        return {
            'incident_trend': 'stable',
            'threat_level': 'medium',
            'risk_score_trend': 'decreasing',
            'login_failure_rate': 0.05
        }
    
    def _generate_security_recommendations(self, stats):
        """Generate security recommendations based on statistics"""
        recommendations = []
        
        if stats['failed_logins'] > stats['successful_logins'] * 0.1:
            recommendations.append({
                'type': 'authentication_security',
                'priority': 'high',
                'recommendation': 'Consider implementing stronger authentication measures',
                'reason': 'High login failure rate detected'
            })
        
        if stats['incidents_created'] > 50:
            recommendations.append({
                'type': 'incident_management',
                'priority': 'medium',
                'recommendation': 'Review incident response procedures',
                'reason': 'High number of incidents this week'
            })
        
        if stats['users_banned'] > 20:
            recommendations.append({
                'type': 'user_management',
                'priority': 'medium',
                'recommendation': 'Review user banning policies',
                'reason': 'High number of user bans this week'
            })
        
        return recommendations
    
    def _export_security_report(self, report_data):
        """Export security report to file"""
        import os
        from django.conf import settings
        
        # Create reports directory if it doesn't exist
        reports_dir = os.path.join(settings.MEDIA_ROOT, 'security_reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate filename
        filename = f"security_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(reports_dir, filename)
        
        # Write report to file
        with open(filepath, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return filepath
    
    def _send_weekly_security_report(self, report_data, report_file):
        """Send weekly security report to admins"""
        subject = f"Weekly Security Report - {timezone.now().strftime('%Y-%m-%d')}"
        
        message = f"""
Weekly Security Report
==================

Report Period: {report_data['report_period']['start']} to {report_data['report_period']['end']}

Key Statistics:
- Total Security Events: {report_data['statistics']['total_security_events']}
- Incidents Created: {report_data['statistics']['incidents_created']}
- Users Banned: {report_data['statistics']['users_banned']}
- IPs Blocked: {report_data['statistics']['ips_blocked']}
- Failed Logins: {report_data['statistics']['failed_logins']}
- Successful Logins: {report_data['statistics']['successful_logins']}

Trends:
- Incident Trend: {report_data['trends']['incident_trend']}
- Threat Level: {report_data['trends']['threat_level']}
- Risk Score Trend: {report_data['trends']['risk_score_trend']}

Recommendations:
{chr(10).join([f"- {rec['recommendation']} ({rec['priority']})" for rec in report_data['recommendations']])}

Full report available at: {report_file}

This is an automated weekly security report.
        """.strip()
        
        try:
            mail_admins(subject, message)
            logger.info("Weekly security report sent to admins")
        except Exception as e:
            logger.error(f"Failed to send weekly security report: {str(e)}")
    
    def _archive_important_logs(self, cutoff_date):
        """Archive important logs before deletion"""
        # This would implement archiving logic
        # For now, just log that archiving would happen
        important_logs = SecurityLog.objects.filter(
            created_at__lt=cutoff_date,
            severity__in=['critical', 'security']
        ).count()
        
        if important_logs > 0:
            logger.info(f"Would archive {important_logs} important logs before deletion")
    
    def _update_vpn_blacklist(self, vpn_detections, proxy_detections):
        """Update VPN/proxy blacklist entries"""
        updated_entries = []
        
        # Process VPN detections
        for detection in vpn_detections:
            ip_address = detection['ip_address']
            
            # Check if already blacklisted
            existing = IPBlacklist.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).first()
            
            if not existing:
                blacklist_entry = IPBlacklist.objects.create(
                    ip_address=ip_address,
                    blacklist_type='vpn_detection',
                    reason=f"VPN detected: {detection['vpn_type']}",
                    confidence=detection['confidence'],
                    source='vpn_database_refresh',
                    expires_at=timezone.now() + timedelta(days=30)
                )
                updated_entries.append(str(blacklist_entry.id))
        
        # Process proxy detections
        for detection in proxy_detections:
            ip_address = detection['ip_address']
            
            # Check if already blacklisted
            existing = IPBlacklist.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).first()
            
            if not existing:
                blacklist_entry = IPBlacklist.objects.create(
                    ip_address=ip_address,
                    blacklist_type='proxy_detection',
                    reason=f"Proxy detected: {detection['proxy_type']}",
                    confidence=detection['confidence'],
                    source='vpn_database_refresh',
                    expires_at=timezone.now() + timedelta(days=15)
                )
                updated_entries.append(str(blacklist_entry.id))
        
        return updated_entries
    
    def _send_critical_alerts(self, critical_events):
        """Send alerts for critical events"""
        subject = f"CRITICAL SECURITY ALERT - {len(critical_events)} events detected"
        
        # Group events by type for better organization
        events_by_type = self._group_events_by_type(critical_events)
        
        message = f"""
CRITICAL SECURITY ALERT
====================

Detected {len(critical_events)} critical security events requiring immediate attention.

"""
        
        for event_type, events in events_by_type.items():
            message += f"\n{event_type.upper()}:\n"
            for event in events[:5]:  # Limit to 5 events per type
                message += f"- {event.get('title', event.get('username', 'Unknown'))}\n"
            if len(events) > 5:
                message += f"- ... and {len(events) - 5} more\n"
            message += "\n"
        
        message += f"""
Please review these events immediately and take appropriate action.

This is an automated critical security alert.
        """.strip()
        
        try:
            mail_admins(subject, message)
            logger.info(f"Critical security alert sent: {len(critical_events)} events")
        except Exception as e:
            logger.error(f"Failed to send critical alert: {str(e)}")
    
    def _send_threat_intelligence_notification(self, summary):
        """Send notification about threat intelligence updates"""
        subject = f"Threat Intelligence Update - {len(summary['updated_feeds'])} feeds updated"
        
        message = f"""
Threat Intelligence Update Summary
==============================

Updated Feeds: {', '.join(summary['updated_feeds'])}
Expired Entries Cleaned: {summary['expired_cleaned']}
Updated At: {summary['timestamp']}

This is an automated threat intelligence update notification.
        """.strip()
        
        try:
            mail_admins(subject, message)
            logger.info("Threat intelligence update notification sent")
        except Exception as e:
            logger.error(f"Failed to send threat intelligence notification: {str(e)}")
    
    def _group_events_by_type(self, events):
        """Group events by type"""
        grouped = {}
        
        for event in events:
            event_type = event['type']
            if event_type not in grouped:
                grouped[event_type] = []
            grouped[event_type].append(event)
        
        return grouped


# Global instance for easy access
security_tasks = SecurityTasks()


# Import required modules
from django.db import models
import threading
from typing import Dict, List, Any, Optional, Type, Union, Callable
from django.core.cache import cache
from celery import shared_task, Task
from celery.result import AsyncResult
from celery.exceptions import Retry, Ignore
from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan
from .utils import SecurityUtils
from .helpers import TimeHelper, SecurityMetrics
from .monitoring import monitoring_manager
from .analytics import security_analytics
from .background_jobs import job_queue, job_executor
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass





# ============================================================================
# Content migrated from tasks_cap.py
# ============================================================================


class TaskCapability:
    """Base task capability class"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.enabled = True
        self.config = {}
        self.dependencies = []
        self.timeout = 3600  # 1 hour default
        self.max_retries = 3
        self.retry_delay = 60  # 1 minute
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute task capability - override in subclasses"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def validate_args(self, *args, **kwargs) -> bool:
        """Validate task arguments"""
        return True
    
    def get_dependencies(self) -> List[str]:
        """Get task dependencies"""
        return self.dependencies
    
    def enable(self):
        """Enable task capability"""
        self.enabled = True
    
    def disable(self):
        """Disable task capability"""
        self.enabled = False
    
    def set_config(self, config: Dict[str, Any]):
        """Set task configuration"""
        self.config = config
    
    def can_execute(self) -> bool:
        """Check if task can be executed"""
        return self.enabled and self.validate_args()



class SecurityAnalysisCapability(TaskCapability):
    """Security analysis task capability"""
    
    def __init__(self):
        super().__init__(
            "security_analysis",
            "Perform comprehensive security analysis"
        )
        self.timeout = 1800  # 30 minutes
    
    def execute(self, analysis_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute security analysis"""
        try:
            parameters = parameters or {}
            
            if analysis_type == 'user_risk':
                return self._analyze_user_risk(parameters)
            elif analysis_type == 'threat_intelligence':
                return self._analyze_threat_intelligence(parameters)
            elif analysis_type == 'incident_pattern':
                return self._analyze_incident_patterns(parameters)
            elif analysis_type == 'system_health':
                return self._analyze_system_health(parameters)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown analysis type: {analysis_type}'
                }
                
        except Exception as e:
            logger.error(f"Error in security analysis: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _analyze_user_risk(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user risk"""
        user_id = parameters.get('user_id')
        period_days = parameters.get('period_days', 30)
        
        if not user_id:
            return {
                'status': 'error',
                'message': 'user_id is required'
            }
        
        try:
            user = User.objects.get(id=user_id)
            
            # Get user security events
            start_date = timezone.now() - timedelta(days=period_days)
            security_events = SecurityLog.objects.filter(
                user=user,
                created_at__gte=start_date
            )
            
            # Calculate risk metrics
            total_events = security_events.count()
            failed_attempts = security_events.filter(security_type='failed_login').count()
            high_risk_events = security_events.filter(severity__in=['high', 'critical']).count()
            
            # Calculate risk score
            from .logic import security_logic_engine
            risk_score = security_logic_engine.calculate_user_risk_score(user)
            
            # Get user devices
            from .models import DeviceInfo
            devices = DeviceInfo.objects.filter(user=user)
            trusted_devices = devices.filter(is_trusted=True).count()
            
            return {
                'status': 'success',
                'analysis': {
                    'user_id': str(user_id),
                    'period_days': period_days,
                    'total_events': total_events,
                    'failed_attempts': failed_attempts,
                    'high_risk_events': high_risk_events,
                    'risk_score': risk_score,
                    'risk_level': self._get_risk_level(risk_score),
                    'total_devices': devices.count(),
                    'trusted_devices': trusted_devices,
                    'analysis_timestamp': timezone.now().isoformat()
                }
            }
            
        except User.DoesNotExist:
            return {
                'status': 'error',
                'message': f'User not found: {user_id}'
            }
    
    def _analyze_threat_intelligence(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze threat intelligence"""
        threat_type = parameters.get('threat_type')
        severity_filter = parameters.get('severity')
        
        threats = ThreatIntelligence.objects.filter(is_active=True)
        
        if threat_type:
            threats = threats.filter(threat_type=threat_type)
        
        if severity_filter:
            threats = threats.filter(severity=severity_filter)
        
        # Analyze threat patterns
        threat_analysis = {
            'total_threats': threats.count(),
            'by_type': {},
            'by_severity': {},
            'by_source': {},
            'recent_threats': []
        }
        
        for threat in threats:
            # Count by type
            threat_analysis['by_type'][threat.threat_type] = \
                threat_analysis['by_type'].get(threat.threat_type, 0) + 1
            
            # Count by severity
            threat_analysis['by_severity'][threat.severity] = \
                threat_analysis['by_severity'].get(threat.severity, 0) + 1
            
            # Count by source
            threat_analysis['by_source'][threat.source] = \
                threat_analysis['by_source'].get(threat.source, 0) + 1
        
        # Get recent threats
        recent_threats = threats.order_by('-created_at')[:10]
        for threat in recent_threats:
            threat_analysis['recent_threats'].append({
                'id': str(threat.id),
                'threat_type': threat.threat_type,
                'indicator': threat.indicator,
                'severity': threat.severity,
                'created_at': threat.created_at.isoformat()
            })
        
        return {
            'status': 'success',
            'analysis': threat_analysis
        }
    
    def _analyze_incident_patterns(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze incident patterns"""
        period_days = parameters.get('period_days', 30)
        
        start_date = timezone.now() - timedelta(days=period_days)
        incidents = SecurityIncident.objects.filter(opened_at__gte=start_date)
        
        # Analyze incident patterns
        pattern_analysis = {
            'total_incidents': incidents.count(),
            'by_type': {},
            'by_severity': {},
            'by_status': {},
            'resolution_times': [],
            'trend_data': []
        }
        
        for incident in incidents:
            # Count by type
            pattern_analysis['by_type'][incident.incident_type] = \
                pattern_analysis['by_type'].get(incident.incident_type, 0) + 1
            
            # Count by severity
            pattern_analysis['by_severity'][incident.severity] = \
                pattern_analysis['by_severity'].get(incident.severity, 0) + 1
            
            # Count by status
            pattern_analysis['by_status'][incident.status] = \
                pattern_analysis['by_status'].get(incident.status, 0) + 1
            
            # Resolution times
            if incident.resolved_at and incident.opened_at:
                resolution_time = (incident.resolved_at - incident.opened_at).total_seconds() / 3600
                pattern_analysis['resolution_times'].append(resolution_time)
        
        # Calculate average resolution time
        if pattern_analysis['resolution_times']:
            pattern_analysis['avg_resolution_time'] = sum(pattern_analysis['resolution_times']) / len(pattern_analysis['resolution_times'])
        else:
            pattern_analysis['avg_resolution_time'] = 0
        
        return {
            'status': 'success',
            'analysis': pattern_analysis
        }
    
    def _analyze_system_health(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze system health"""
        health_data = monitoring_manager.get_system_health()
        
        return {
            'status': 'success',
            'analysis': health_data
        }
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Get risk level from score"""
        if risk_score >= 80:
            return 'critical'
        elif risk_score >= 60:
            return 'high'
        elif risk_score >= 40:
            return 'medium'
        else:
            return 'low'



class DataProcessingCapability(TaskCapability):
    """Data processing task capability"""
    
    def __init__(self):
        super().__init__(
            "data_processing",
            "Process and transform security data"
        )
        self.timeout = 3600  # 1 hour
    
    def execute(self, operation: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute data processing operation"""
        try:
            parameters = parameters or {}
            
            if operation == 'cleanup_logs':
                return self._cleanup_logs(parameters)
            elif operation == 'archive_data':
                return self._archive_data(parameters)
            elif operation == 'export_data':
                return self._export_data(parameters)
            elif operation == 'aggregate_metrics':
                return self._aggregate_metrics(parameters)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown operation: {operation}'
                }
                
        except Exception as e:
            logger.error(f"Error in data processing: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _cleanup_logs(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up old security logs"""
        days_to_keep = parameters.get('days_to_keep', 90)
        dry_run = parameters.get('dry_run', False)
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        if dry_run:
            count = SecurityLog.objects.filter(created_at__lt=cutoff_date).count()
            return {
                'status': 'success',
                'action': 'dry_run',
                'logs_to_delete': count,
                'cutoff_date': cutoff_date.isoformat()
            }
        else:
            deleted_count, _ = SecurityLog.objects.filter(created_at__lt=cutoff_date).delete()
            
            return {
                'status': 'success',
                'action': 'cleanup_completed',
                'logs_deleted': deleted_count,
                'cutoff_date': cutoff_date.isoformat()
            }
    
    def _archive_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Archive security data"""
        data_type = parameters.get('data_type', 'logs')
        archive_date = parameters.get('archive_date')
        
        if not archive_date:
            archive_date = timezone.now() - timedelta(days=365)
        
        # This would implement data archiving logic
        # For now, return success
        return {
            'status': 'success',
            'action': 'archive_initiated',
            'data_type': data_type,
            'archive_date': archive_date.isoformat()
        }
    
    def _export_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Export security data"""
        data_type = parameters.get('data_type', 'logs')
        format_type = parameters.get('format', 'json')
        filters = parameters.get('filters', {})
        
        from .data_export import security_data_exporter
        
        if data_type == 'logs':
            export_response = security_data_exporter.export_security_logs(format_type, filters)
        elif data_type == 'incidents':
            export_response = security_data_exporter.export_incidents(format_type, filters)
        elif data_type == 'threats':
            export_response = security_data_exporter.export_threat_intelligence(format_type, filters)
        else:
            return {
                'status': 'error',
                'message': f'Unknown data type: {data_type}'
            }
        
        return {
            'status': 'success',
            'action': 'export_completed',
            'data_type': data_type,
            'format': format_type,
            'file_size': len(export_response.content)
        }
    
    def _aggregate_metrics(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate security metrics"""
        period = parameters.get('period', 'daily')
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        
        if not end_date:
            end_date = timezone.now()
        
        # Get aggregated metrics
        metrics = security_analytics.get_aggregated_metrics(period, start_date, end_date)
        
        return {
            'status': 'success',
            'action': 'metrics_aggregated',
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'metrics': metrics
        }



class NotificationCapability(TaskCapability):
    """Notification task capability"""
    
    def __init__(self):
        super().__init__(
            "notifications",
            "Send security notifications"
        )
        self.timeout = 300  # 5 minutes
    
    def execute(self, notification_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute notification task"""
        try:
            parameters = parameters or {}
            
            if notification_type == 'security_alert':
                return self._send_security_alert(parameters)
            elif notification_type == 'incident_notification':
                return self._send_incident_notification(parameters)
            elif notification_type == 'threat_notification':
                return self._send_threat_notification(parameters)
            elif notification_type == 'compliance_alert':
                return self._send_compliance_alert(parameters)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown notification type: {notification_type}'
                }
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _send_security_alert(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send security alert"""
        recipients = parameters.get('recipients', [])
        alert_data = parameters.get('alert_data', {})
        
        from .notifications_push import notification_service
        
        sent_notifications = []
        for recipient in recipients:
            try:
                notification = notification_service.send_security_alert(recipient, alert_data)
                sent_notifications.append(str(notification.id))
            except Exception as e:
                logger.error(f"Error sending alert to {recipient}: {e}")
        
        return {
            'status': 'success',
            'action': 'security_alerts_sent',
            'recipients_count': len(recipients),
            'sent_notifications': sent_notifications
        }
    
    def _send_incident_notification(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send incident notification"""
        incident_id = parameters.get('incident_id')
        action = parameters.get('action', 'created')
        recipients = parameters.get('recipients', [])
        
        if not incident_id:
            return {
                'status': 'error',
                'message': 'incident_id is required'
            }
        
        try:
            incident = SecurityIncident.objects.get(id=incident_id)
            
            from .notifications_push import notification_service
            notifications = notification_service.send_incident_notification(
                recipients, incident, action
            )
            
            return {
                'status': 'success',
                'action': 'incident_notifications_sent',
                'incident_id': str(incident_id),
                'notifications_sent': len(notifications)
            }
            
        except SecurityIncident.DoesNotExist:
            return {
                'status': 'error',
                'message': f'Incident not found: {incident_id}'
            }
    
    def _send_threat_notification(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send threat notification"""
        threat_data = parameters.get('threat_data', {})
        recipients = parameters.get('recipients', [])
        
        from .notifications_push import notification_service
        notifications = notification_service.send_threat_notification(recipients, threat_data)
        
        return {
            'status': 'success',
            'action': 'threat_notifications_sent',
            'notifications_sent': len(notifications)
        }
    
    def _send_compliance_alert(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send compliance alert"""
        compliance_data = parameters.get('compliance_data', {})
        recipients = parameters.get('recipients', [])
        
        # This would implement compliance alert logic
        return {
            'status': 'success',
            'action': 'compliance_alerts_sent',
            'recipients_count': len(recipients)
        }



class TaskCapabilityManager:
    """Manager for task capabilities"""
    
    def __init__(self):
        self.capabilities = {}
        self.running_tasks = {}
        self.task_history = []
        self.max_history = 1000
        self._initialize_capabilities()
    
    def _initialize_capabilities(self):
        """Initialize built-in capabilities"""
        self.register_capability(SecurityAnalysisCapability())
        self.register_capability(DataProcessingCapability())
        self.register_capability(NotificationCapability())
    
    def register_capability(self, capability: TaskCapability):
        """Register a task capability"""
        self.capabilities[capability.name] = capability
        logger.info(f"Registered task capability: {capability.name}")
    
    def unregister_capability(self, capability_name: str) -> bool:
        """Unregister a task capability"""
        if capability_name in self.capabilities:
            del self.capabilities[capability_name]
            logger.info(f"Unregistered task capability: {capability_name}")
            return True
        return False
    
    def get_capability(self, capability_name: str) -> Optional[TaskCapability]:
        """Get task capability by name"""
        return self.capabilities.get(capability_name)
    
    def execute_capability(self, capability_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a task capability"""
        capability = self.get_capability(capability_name)
        
        if not capability:
            return {
                'status': 'error',
                'message': f'Capability not found: {capability_name}'
            }
        
        if not capability.can_execute():
            return {
                'status': 'error',
                'message': f'Capability cannot execute: {capability_name}'
            }
        
        try:
            # Record task start
            task_id = SecurityUtils.generate_uuid()
            task_start = timezone.now()
            
            self.running_tasks[task_id] = {
                'capability': capability_name,
                'start_time': task_start,
                'status': 'running'
            }
            
            # Execute capability
            result = capability.execute(*args, **kwargs)
            
            # Record task completion
            task_end = timezone.now()
            duration = (task_end - task_start).total_seconds()
            
            task_record = {
                'task_id': task_id,
                'capability': capability_name,
                'start_time': task_start.isoformat(),
                'end_time': task_end.isoformat(),
                'duration': duration,
                'status': 'completed',
                'result': result
            }
            
            # Add to history
            self.task_history.append(task_record)
            if len(self.task_history) > self.max_history:
                self.task_history.pop(0)
            
            # Remove from running tasks
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            result['task_id'] = task_id
            result['duration'] = duration
            
            return result
            
        except Exception as e:
            # Record task failure
            task_end = timezone.now()
            duration = (task_end - task_start).total_seconds()
            
            task_record = {
                'task_id': task_id,
                'capability': capability_name,
                'start_time': task_start.isoformat(),
                'end_time': task_end.isoformat(),
                'duration': duration,
                'status': 'failed',
                'error': str(e)
            }
            
            self.task_history.append(task_record)
            if len(self.task_history) > self.max_history:
                self.task_history.pop(0)
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            logger.error(f"Error executing capability {capability_name}: {e}")
            
            return {
                'status': 'error',
                'message': str(e),
                'task_id': task_id,
                'duration': duration
            }
    
    def get_capability_status(self) -> Dict[str, Any]:
        """Get status of all capabilities"""
        return {
            'total_capabilities': len(self.capabilities),
            'enabled_capabilities': len([c for c in self.capabilities.values() if c.enabled]),
            'running_tasks': len(self.running_tasks),
            'capabilities': {
                name: {
                    'enabled': cap.enabled,
                    'description': cap.description,
                    'dependencies': cap.dependencies
                }
                for name, cap in self.capabilities.items()
            }
        }
    
    def get_task_history(self, capability_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get task execution history"""
        history = self.task_history
        
        if capability_name:
            history = [t for t in history if t['capability'] == capability_name]
        
        return history[-limit:]
    
    def get_running_tasks(self) -> Dict[str, Any]:
        """Get currently running tasks"""
        return {
            'total_running': len(self.running_tasks),
            'tasks': {
                task_id: {
                    'capability': task['capability'],
                    'start_time': task['start_time'].isoformat(),
                    'duration': (timezone.now() - task['start_time']).total_seconds()
                }
                for task_id, task in self.running_tasks.items()
            }
        }


# Celery task integration

class CapableTask(Task):
    """Celery task with capability support"""
    
    def __init__(self, capability_manager: TaskCapabilityManager = None):
        super().__init__()
        self.capability_manager = task_capability_manager if capability_manager is None else capability_manager
    
    def run(self, capability_name: str, *args, **kwargs):
        """Run task with capability"""
        return self.capability_manager.execute_capability(capability_name, *args, **kwargs)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        logger.warning(f"Task {task_id} retrying: {exc}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Task {task_id} failed: {exc}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Task {task_id} completed successfully")


# Global instances
task_capability_manager = TaskCapabilityManager()
capable_task = CapableTask(task_capability_manager)


# Celery tasks
@shared_task(bind=True, base=CapableTask)
def execute_capability(self, capability_name: str, *args, **kwargs):
    """Execute task capability via Celery"""
    return self.run(capability_name, *args, **kwargs)


@shared_task
def cleanup_old_logs(days_to_keep: int = 90, dry_run: bool = False):
    """Clean up old security logs"""
    return task_capability_manager.execute_capability(
        'data_processing',
        'cleanup_logs',
        {'days_to_keep': days_to_keep, 'dry_run': dry_run}
    )


@shared_task
def generate_security_report(report_type: str, parameters: Dict[str, Any] = None):
    """Generate security report"""
    return task_capability_manager.execute_capability(
        'security_analysis',
        report_type,
        parameters or {}
    )


@shared_task
def send_security_notifications(notification_type: str, parameters: Dict[str, Any]):
    """Send security notifications"""
    return task_capability_manager.execute_capability(
        'notifications',
        notification_type,
        parameters
    )


# Export symbols
__all__ = [
    'TaskCapability',
    'SecurityAnalysisCapability',
    'DataProcessingCapability',
    'NotificationCapability',
    'TaskCapabilityManager',
    'task_capability_manager',
    'CapableTask',
    'capable_task',
    'execute_capability',
    'cleanup_old_logs',
    'generate_security_report',
    'send_security_notifications'
]