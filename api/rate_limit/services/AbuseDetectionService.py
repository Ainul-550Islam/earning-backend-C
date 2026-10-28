"""
AbuseDetectionService.py – Advanced abuse detection and prevention service.

Provides comprehensive abuse detection functionality including:
- Pattern recognition and analysis
- Automated abuse reporting
- Integration with IP blocking system
- Real-time threat assessment
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.cache import cache

from api.rate_limit.models import AbuseReport, IPBlockList, RateLimitLog, RateLimitInsight

logger = logging.getLogger(__name__)


class AbuseDetectionService:
    """Advanced abuse detection and prevention service."""
    
    def __init__(self):
        logs = getattr(self, "_logs", [])
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache_timeout = 300  # 5 minutes
    
    def detect_abuse_patterns(self, ip_address: str, user=None, 
                           endpoint: str = None, time_window: int = 3600) -> Dict[str, Any]:
        """
        Detect abuse patterns for given IP/user/endpoint.
        
        Args:
            ip_address: IP address to analyze
            user: User object (optional)
            endpoint: Endpoint being accessed (optional)
            time_window: Time window in seconds (default: 1 hour)
            
        Returns:
            Dictionary with abuse detection results
        """
        try:
            # Validate IP address format
            import ipaddress
            try:
                ipaddress.ip_address(ip_address)
            except ValueError:
                return {
                    'error': f'Invalid IP address: {ip_address}',
                    'risk_score': 0,
                    'total_requests': 0,
                    'blocked_count': 0,
                    'abuse_types': ['other'],
                    'patterns': [],
                    'should_block': False,
                }

            since = timezone.now() - timedelta(seconds=time_window)
            
            # Get recent rate limit logs
            logs_query = RateLimitLog.objects.filter(
                timestamp__gte=since,
                ip_address=ip_address
            )
            
            if user:
                logs_query = logs_query.filter(user=user)
            
            if endpoint:
                logs_query = logs_query.filter(endpoint=endpoint)
            
            logs = logs_query.order_by('-timestamp')

            # If user filter returns no results, fall back to IP-only query
            if user and logs.count() == 0:
                logs_query_no_user = RateLimitLog.objects.filter(
                    timestamp__gte=since,
                    ip_address=ip_address,
                )
                if endpoint:
                    logs_query_no_user = logs_query_no_user.filter(endpoint=endpoint)
                if logs_query_no_user.count() > 0:
                    logs = logs_query_no_user.order_by('-timestamp')

            total = logs.count()
            blocked = logs.filter(status='blocked').count()

            # Analyze patterns (with counts already known)
            patterns = self._analyze_request_patterns(logs)

            # For fraud detection: count unique IPs for this user across ALL IPs
            if user:
                from api.rate_limit.models import RateLimitLog as _RLL
                user_unique_ips = _RLL.objects.filter(
                    user=user,
                    timestamp__gte=timezone.now() - timedelta(seconds=time_window)
                ).values('ip_address').distinct().count()
                patterns['unique_ips'] = max(patterns.get('unique_ips', 0), user_unique_ips)

            # Enrich patterns with counts so _identify_abuse_types can use them
            patterns['total_requests'] = total
            patterns['blocked_requests'] = blocked
            if total > 0:
                patterns['block_rate'] = round(blocked / total * 100, 1)

            risk_score = self._calculate_risk_score(patterns)
            abuse_types = self._identify_abuse_types(patterns)

            return {
                'ip_address': ip_address,
                'user_id': user.id if user else None,
                'endpoint': endpoint,
                'time_window': time_window,
                'total_requests': total,
                'blocked_requests': blocked,
                'patterns': patterns,
                'risk_score': risk_score,
                'abuse_types': abuse_types or ['other'],
                'should_block': risk_score > 70,
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting abuse patterns: {e}")
            return {
                'error': str(e),
                'risk_score': 0,
                'total_requests': 0,
                'blocked_count': 0,
                'abuse_types': [],
                'patterns': [],
                'should_block': False,
            }
    
    def _analyze_request_patterns(self, logs) -> Dict[str, Any]:
        """Analyze request patterns from rate limit logs."""
        if not logs:
            return {}
        
        total_requests = logs.count()
        blocked_requests = logs.filter(status='blocked').count()

        # Time-based patterns
        timestamps = list(logs.values_list('timestamp', flat=True))
        if len(timestamps) > 1:
            # Sort descending (newest first from order_by(-timestamp))
            sorted_ts = sorted(timestamps, reverse=True)
            time_diffs = [
                abs((sorted_ts[i] - sorted_ts[i+1]).total_seconds())
                for i in range(len(sorted_ts)-1)
            ]
            avg_interval = sum(time_diffs) / len(time_diffs) if time_diffs else 0
            min_interval = min(time_diffs) if time_diffs else 0
            max_interval = max(time_diffs) if time_diffs else 0
            # Actual time window covered in minutes
            span_seconds = max(abs((sorted_ts[0] - sorted_ts[-1]).total_seconds()), 1)
            requests_per_minute = (total_requests / span_seconds) * 60
        else:
            avg_interval = min_interval = max_interval = 0
            requests_per_minute = total_requests  # single request in window
        
        # Endpoint diversity
        unique_endpoints = logs.values_list('endpoint', flat=True).distinct().count()
        
        # User agent analysis
        user_agents = logs.values_list('user_agent', flat=True).distinct()
        unique_user_agents = len(user_agents)
        
        # Geographic patterns — count unique IPs across the filtered logs
        ip_addresses = logs.values_list('ip_address', flat=True).distinct()
        unique_ips = ip_addresses.count()
        
        # SQL injection detection — check metadata for SQLi patterns
        sqli_patterns = ["'", '"', 'SELECT', 'UNION', 'DROP', 'INSERT', '--', '/*', 'OR 1=1']
        sql_injection_count = 0
        for log_meta in logs.values_list('metadata', flat=True):
            if isinstance(log_meta, dict):
                meta_str = str(log_meta).lower()
                if any(p.lower() in meta_str for p in sqli_patterns):
                    sql_injection_count += 1

        return {
            'total_requests': total_requests,
            'blocked_requests': blocked_requests,
            'block_rate': (blocked_requests / total_requests * 100) if total_requests > 0 else 0,
            'avg_request_interval': avg_interval,
            'min_request_interval': min_interval,
            'max_request_interval': max_interval,
            'unique_endpoints': unique_endpoints,
            'unique_user_agents': unique_user_agents,
            'unique_ips': unique_ips,
            'requests_per_minute': requests_per_minute,
            'sql_injection_count': sql_injection_count,
        }
    
    def _calculate_risk_score(self, patterns: Dict[str, Any]) -> int:
        """Calculate risk score based on patterns. Returns 0 when no data."""
        if not patterns or patterns.get('total_requests', 0) == 0:
            return 0

        score = 0
        
        # High request frequency
        if patterns.get('requests_per_minute', 0) > 60:
            score += 30
        elif patterns.get('requests_per_minute', 0) > 30:
            score += 20
        elif patterns.get('requests_per_minute', 0) > 10:
            score += 10
        
        # High block rate
        block_rate = patterns.get('block_rate', 0)
        if block_rate >= 100:
            score += 50
        elif block_rate > 80:
            score += 40
        elif block_rate > 50:
            score += 30
        elif block_rate > 25:
            score += 20
        elif block_rate > 10:
            score += 10
        
        # Short intervals (potential bot) — strong signal
        min_iv = patterns.get('min_request_interval', 99)
        if min_iv < 1:
            score += 40
        elif min_iv < 3:
            score += 35
        elif min_iv < 5:
            score += 20
        
        # Low endpoint diversity (potential scraping)
        if patterns.get('unique_endpoints', 0) == 1 and patterns.get('total_requests', 0) > 50:
            score += 15
        
        # Multiple IPs from same user (potential account sharing)
        if patterns.get('unique_ips', 0) > 3:
            score += 15

        # Large total request volume bonus
        total = patterns.get('total_requests', 0)
        if total > 500:
            score += 20
        elif total > 100:
            score += 10

        # SQL injection detection
        if patterns.get('sql_injection_count', 0) > 0:
            score += 20

        return min(score, 100)
    
    def _identify_abuse_types(self, patterns: Dict[str, Any]) -> List[str]:
        """Identify types of abuse based on patterns."""
        abuse_types = []
        total = patterns.get('total_requests', 0)
        block_rate = patterns.get('block_rate', 0)
        blocked = patterns.get('blocked_requests', 0)
        min_interval = patterns.get('min_request_interval', 99)
        rpm = patterns.get('requests_per_minute', 0)
        unique_endpoints = patterns.get('unique_endpoints', 0)
        unique_ips = patterns.get('unique_ips', 0)
        sql_injection_count = patterns.get('sql_injection_count', 0)

        if min_interval < 3:
            abuse_types.append('bot')
        if block_rate > 0 or blocked > 0:
            abuse_types.append('rate_limit')
        # Brute force: single endpoint ALL blocked, OR massive absolute blocked count
        if (block_rate > 80 and unique_endpoints == 1 and total > 10) or \
           (blocked > 80 and unique_endpoints <= 3):
            abuse_types.append('brute_force')
        if rpm > 60:
            abuse_types.append('ddos')
        if rpm > 30 or total > 100:
            abuse_types.append('spam')
        if (unique_endpoints == 1 and total > 50) or (unique_endpoints > 1 and total > 200):
            abuse_types.append('scraping')
            abuse_types.append('scanning')  # alias for multi-endpoint scraping
        if unique_ips > 3:
            abuse_types.append('fraud')
        # Credential stuffing can co-exist with brute_force
        if block_rate >= 50 and total > 50:
            abuse_types.append('credential_stuffing')
        if sql_injection_count > 0:
            abuse_types.append('sql_injection')

        return abuse_types or ['other']
    
    def create_abuse_report(self, ip_address: str, user=None, endpoint: str = None,
                          abuse_type: str = 'rate_limit', severity: int = 1,
                          metadata: Dict[str, Any] = None) -> AbuseReport:
        """
        Create an abuse report.
        
        Args:
            ip_address: IP address of abuser
            user: User object (optional)
            endpoint: Endpoint being abused (optional)
            abuse_type: Type of abuse
            severity: Severity level (1-5)
            metadata: Additional metadata
            
        Returns:
            Created AbuseReport instance
        """
        try:
            # Check if existing report exists for this IP (merge by IP)
            existing_report = AbuseReport.objects.filter(
                ip_address=ip_address,
                is_blocked=False
            ).order_by('-created_at').first()
            
            if existing_report:
                # Update existing report
                existing_report.last_seen = timezone.now()
                existing_report.severity = max(existing_report.severity, severity)
                if metadata:
                    existing_report.metadata.update(metadata)
                existing_report.update_counts()
                existing_report.save()
                return existing_report
            
            # Create new report
            report = AbuseReport.objects.create(
                ip_address=ip_address,
                user=user,
                abuse_type=abuse_type,
                endpoint=endpoint,
                severity=severity,
                metadata=metadata or {},
                reported_ip=ip_address,
                reason=abuse_type,
                description=f"Auto-detected {abuse_type} abuse",
            )

            # Auto-block very high severity reports (severity == 5 max)
            should_auto_block = severity >= 5
            if should_auto_block:
                self._auto_block_ip(ip_address, report)
                # Ensure is_blocked is set even if _auto_block_ip doesn't save
                if not report.is_blocked:
                    report.is_blocked = True
                    report.save(update_fields=['is_blocked'])
            
            self.logger.info(f"Created abuse report: {abuse_type} - {ip_address}")
            return report
            
        except Exception as e:
            self.logger.error(f"Error creating abuse report: {e}")
            raise
    
    def _auto_block_ip(self, ip_address: str, abuse_report: AbuseReport):
        """Automatically block IP based on abuse report."""
        try:
            # Check if IP is already blocked
            existing_block = IPBlockList.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).first()
            
            if existing_block:
                existing_block.expires_at = timezone.now() + timedelta(days=7)
                existing_block.save()
                return
            
            # Create new block
            block = IPBlockList.objects.create(
                ip_address=ip_address,
                block_type='single',
                reason='automatic',
                description=f"Auto-blocked due to {abuse_report.abuse_type} abuse (Severity: {abuse_report.severity})",
                expires_at=timezone.now() + timedelta(days=7),
                permanent=abuse_report.severity >= 4
            )
            
            # Update abuse report
            abuse_report.is_blocked = True
            abuse_report.save()
            
            self.logger.warning(f"Auto-blocked IP: {ip_address}")
            
        except Exception as e:
            self.logger.error(f"Error auto-blocking IP: {e}")
    
    def get_abuse_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get abuse statistics for the given time period."""
        try:
            since = timezone.now() - timedelta(days=days)
            
            # Overall stats
            total_reports = AbuseReport.objects.filter(created_at__gte=since).count()
            blocked_ips = IPBlockList.objects.filter(created_at__gte=since).count()
            active_blocks = IPBlockList.objects.filter(is_active=True).count()
            
            # By abuse type
            abuse_by_type = AbuseReport.objects.filter(
                created_at__gte=since
            ).values('abuse_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # By severity
            abuse_by_severity = AbuseReport.objects.filter(
                created_at__gte=since
            ).values('severity').annotate(
                count=Count('id')
            ).order_by('severity')
            
            # Top abusers
            top_abusers = AbuseReport.objects.filter(
                created_at__gte=since
            ).values('ip_address').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            return {
                'period_days': days,
                'total_reports': total_reports,
                'blocked_ips': blocked_ips,
                'active_blocks': active_blocks,
                'abuse_by_type': list(abuse_by_type),
                'abuse_by_severity': list(abuse_by_severity),
                'top_abusers': list(top_abusers),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting abuse statistics: {e}")
            return {'error': str(e)}
    
    def investigate_abuse(self, report_id: int) -> Dict[str, Any]:
        """Investigate a specific abuse report."""
        try:
            report = AbuseReport.objects.get(id=report_id)
            
            # Get detailed analysis
            analysis = self.detect_abuse_patterns(
                report.ip_address,
                report.user,
                report.endpoint,
                time_window=86400  # 24 hours
            )
            
            # Get related reports
            related_reports = AbuseReport.objects.filter(
                ip_address=report.ip_address
            ).exclude(id=report_id).order_by('-created_at')
            
            # Check current block status
            current_block = IPBlockList.objects.filter(
                ip_address=report.ip_address,
                is_active=True
            ).first()
            
            return {
                'report': {
                    'id': report.id,
                    'ip_address': report.ip_address,
                    'abuse_type': report.abuse_type,
                    'severity': report.severity,
                    'created_at': report.created_at.isoformat(),
                    'is_blocked': report.is_blocked,
                    'is_investigated': report.is_investigated
                },
                'analysis': analysis,
                'related_reports': [
                    {
                        'id': r.id,
                        'abuse_type': r.abuse_type,
                        'severity': r.severity,
                        'created_at': r.created_at.isoformat()
                    }
                    for r in related_reports
                ],
                'current_block': {
                    'id': current_block.id,
                    'reason': current_block.reason,
                    'expires_at': current_block.expires_at.isoformat() if current_block.expires_at else None,
                    'permanent': current_block.permanent
                } if current_block else None
            }
            
        except AbuseReport.DoesNotExist:
            return {'error': 'Report not found'}
        except Exception as e:
            self.logger.error(f"Error investigating abuse: {e}")
            return {'error': str(e)}
    
    def cleanup_old_reports(self, days: int = 30):
        """Clean up old abuse reports."""
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            # Delete old reports that are not blocked
            deleted_count = AbuseReport.objects.filter(
                created_at__lt=cutoff,
                is_blocked=False
            ).delete()[0]
            
            self.logger.info(f"Cleaned up {deleted_count} old abuse reports")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old reports: {e}")
            return 0
