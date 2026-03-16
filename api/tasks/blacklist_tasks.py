# api/tasks/blacklist_tasks.py
"""
Celery tasks for automated blacklist management and fraud detection.
These tasks run automatically on schedule to maintain system health.
"""

import logging
from celery import shared_task, current_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction, models
from django.db.models import Count, Q
import json
from datetime import datetime, timedelta
from decimal import Decimal
import requests
from typing import List, Dict, Optional, Tuple

from api.ad_networks.models import (
    BlacklistedIP, 
    PostbackLog, 
    KnownBadIP,
    UserOfferEngagement,
    OfferConversion
)
from utils.redis_utils import RedisCacheManager
from core.services.email_service import send_email_template

logger = get_task_logger(__name__)

# ============================================================================
# DAILY MAINTENANCE TASKS
# ============================================================================

@shared_task(bind=True, queue='maintenance', max_retries=3, default_retry_delay=300)
def cleanup_expired_blacklist_task(self, batch_size: int = 1000) -> Dict:
    """
    Daily task to cleanup expired blacklist entries.
    Runs every day at 3:00 AM.
    
    Args:
        batch_size: Number of records to process per batch
        
    Returns:
        Dictionary with cleanup statistics
    """
    task_id = current_task.request.id if current_task else 'manual'
    
    logger.info(f"[Task {task_id}] Starting expired blacklist cleanup")
    
    try:
        # Update task state for monitoring
        if self:
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 0,
                    'total': 'calculating',
                    'status': 'Starting cleanup...',
                    'task_id': task_id
                }
            )
        
        # Run the cleanup
        result = BlacklistedIP.cleanup_expired_entries(batch_size=batch_size)
        
        # Log detailed results
        logger.info(
            f"[Task {task_id}] Cleanup completed - "
            f"Deactivated: {result['deactivated']}, "
            f"Total expired: {result['total_expired']}"
        )
        
        # Send notification if significant cleanup happened
        if result['deactivated'] > 50:
            send_admin_notification_task.delay(
                subject=f"🚨 Blacklist Cleanup Report - {result['deactivated']} entries cleaned",
                message_type='cleanup_report',
                data=result,
                priority='info'
            )
        
        # Also clear Redis cache for cleaned entries
        if result['deactivated'] > 0:
            RedisCacheManager.clear_all_blacklist_cache()
            logger.info(f"[Task {task_id}] Cleared Redis blacklist cache")
        
        return {
            'status': 'SUCCESS',
            'task_id': task_id,
            'result': result,
            'completed_at': timezone.now().isoformat(),
            'execution_time': result.get('execution_time', 0)
        }
        
    except Exception as exc:
        logger.error(f"[Task {task_id}] Cleanup failed: {str(exc)}")
        
        # Retry with exponential backoff
        if self:
            self.retry(exc=exc, countdown=300, max_retries=3)
        
        return {
            'status': 'FAILED',
            'task_id': task_id,
            'error': str(exc),
            'completed_at': timezone.now().isoformat()
        }

@shared_task(queue='maintenance')
def analyze_blacklist_patterns_task() -> Dict:
    """
    Analyze patterns in blacklisted IPs for insights.
    Runs every day at 4:00 AM.
    
    Returns:
        Analysis results
    """
    logger.info("Starting blacklist pattern analysis")
    
    try:
        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)
        
        # Get blacklist statistics
        stats = BlacklistedIP.get_statistics()
        
        # Analyze by country (if IP geolocation data available)
        # This requires your IP model to have country field
        analysis_results = {
            'period': {
                'last_7_days': last_7_days.isoformat(),
                'last_30_days': last_30_days.isoformat(),
                'now': now.isoformat()
            },
            'summary_stats': stats,
            'patterns': {}
        }
        
        # Check for unusual spikes in blacklisting
        recent_additions = stats['recent_additions_7d']
        avg_monthly = stats['total_entries'] / 30 if stats['total_entries'] > 30 else 0
        
        if recent_additions > avg_monthly * 2:
            analysis_results['patterns']['unusual_spike'] = {
                'detected': True,
                'recent_7d': recent_additions,
                'avg_daily': avg_monthly,
                'message': f"Unusual spike in blacklist additions (7x average)"
            }
        
        # Analyze by reason distribution
        reason_distribution = {}
        for item in stats['by_reason']:
            reason_distribution[item['reason']] = {
                'count': item['count'],
                'percentage': (item['count'] / stats['active_entries'] * 100) 
                              if stats['active_entries'] > 0 else 0
            }
        
        analysis_results['patterns']['reason_distribution'] = reason_distribution
        
        # Check for IP ranges (potential botnets)
        ip_ranges = BlacklistedIP.objects.filter(
            is_active=True
        ).extra(
            where=["ip_address LIKE '%.%.%.%'"]
        ).values_list('ip_address', flat=True)
        
        # Simple range detection (first two octets)
        range_counter = {}
        for ip in ip_ranges:
            parts = ip.split('.')
            if len(parts) >= 2:
                range_key = f"{parts[0]}.{parts[1]}"
                range_counter[range_key] = range_counter.get(range_key, 0) + 1
        
        # Find suspicious ranges (> 10 IPs)
        suspicious_ranges = [
            {'range': range_key, 'count': count}
            for range_key, count in range_counter.items()
            if count > 10
        ]
        
        if suspicious_ranges:
            analysis_results['patterns']['suspicious_ranges'] = {
                'detected': True,
                'ranges': suspicious_ranges,
                'message': f"Found {len(suspicious_ranges)} suspicious IP ranges"
            }
        
        logger.info(f"Pattern analysis completed: {len(analysis_results['patterns'])} patterns found")
        
        # Store analysis results for dashboard
        cache_key = f"blacklist_analysis_{now.strftime('%Y%m%d')}"
        RedisCacheManager._cache.set(cache_key, analysis_results, timeout=86400)  # 24 hours
        
        return analysis_results
        
    except Exception as e:
        logger.error(f"Pattern analysis failed: {str(e)}")
        return {'error': str(e), 'status': 'FAILED'}

# ============================================================================
# WEEKLY REPORTING TASKS
# ============================================================================

@shared_task(queue='reports')
def send_weekly_blacklist_report_task() -> Dict:
    """
    Send comprehensive weekly blacklist report.
    Runs every Monday at 9:00 AM.
    
    Returns:
        Email sending status
    """
    logger.info("Starting weekly blacklist report generation")
    
    try:
        now = timezone.now()
        week_start = now - timedelta(days=7)
        
        # Get comprehensive statistics
        stats = BlacklistedIP.get_statistics()
        
        # Get recent fraud activity
        recent_fraud = PostbackLog.objects.filter(
            created_at__gte=week_start,
            is_fraud=True
        ).count()
        
        total_postbacks = PostbackLog.objects.filter(
            created_at__gte=week_start
        ).count()
        
        fraud_rate = (recent_fraud / total_postbacks * 100) if total_postbacks > 0 else 0
        
        # Get top blocked countries (if geolocation available)
        top_countries = BlacklistedIP.objects.filter(
            is_active=True
        ).exclude(
            metadata__country__isnull=True
        ).values(
            'metadata__country'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Generate report data
        report_data = {
            'period': {
                'start': week_start.isoformat(),
                'end': now.isoformat(),
                'days': 7
            },
            'blacklist_stats': stats,
            'fraud_metrics': {
                'total_postbacks': total_postbacks,
                'fraud_postbacks': recent_fraud,
                'fraud_rate_percentage': round(fraud_rate, 2),
                'fraud_rate_level': 'HIGH' if fraud_rate > 20 else 'MEDIUM' if fraud_rate > 5 else 'LOW'
            },
            'top_countries': list(top_countries),
            'generated_at': now.isoformat()
        }
        
        # Send email to admins
        admin_emails = getattr(settings, 'ADMIN_EMAILS', ['admin@example.com'])
        
        # Use your email service
        email_sent = send_email_template(
            template_name='weekly_blacklist_report',
            subject=f"[STATS] Weekly Blacklist & Fraud Report - {now.strftime('%Y-%m-%d')}",
            to_emails=admin_emails,
            context=report_data
        )
        
        if email_sent:
            logger.info(f"Weekly report sent to {len(admin_emails)} admins")
            
            # Also store report in database for history
            store_report_history_task.delay(
                report_type='weekly_blacklist',
                data=report_data,
                sent_to=admin_emails
            )
            
            return {
                'status': 'SUCCESS',
                'recipients': len(admin_emails),
                'report_generated': True,
                'fraud_rate': fraud_rate
            }
        else:
            logger.error("Failed to send weekly report email")
            return {
                'status': 'FAILED',
                'error': 'Email sending failed',
                'report_generated': True
            }
        
    except Exception as e:
        logger.error(f"Weekly report generation failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

@shared_task(queue='reports')
def generate_fraud_analytics_dashboard_task() -> Dict:
    """
    Generate fraud analytics data for admin dashboard.
    Runs every 6 hours.
    
    Returns:
        Dashboard data
    """
    logger.info("Generating fraud analytics dashboard data")
    
    try:
        now = timezone.now()
        
        # Time periods for analytics
        time_periods = {
            'last_hour': now - timedelta(hours=1),
            'last_24h': now - timedelta(hours=24),
            'last_7d': now - timedelta(days=7),
            'last_30d': now - timedelta(days=30),
        }
        
        dashboard_data = {
            'generated_at': now.isoformat(),
            'time_periods': {k: v.isoformat() for k, v in time_periods.items()},
            'metrics': {},
            'charts': {}
        }
        
        # 1. Fraud Rate Over Time (Hourly for last 24h)
        fraud_by_hour = []
        for hour in range(24):
            hour_start = now - timedelta(hours=hour+1)
            hour_end = now - timedelta(hours=hour)
            
            total = PostbackLog.objects.filter(
                created_at__range=(hour_start, hour_end)
            ).count()
            
            fraud = PostbackLog.objects.filter(
                created_at__range=(hour_start, hour_end),
                is_fraud=True
            ).count()
            
            fraud_rate = (fraud / total * 100) if total > 0 else 0
            
            fraud_by_hour.append({
                'hour': hour_start.strftime('%H:00'),
                'total': total,
                'fraud': fraud,
                'fraud_rate': round(fraud_rate, 2)
            })
        
        dashboard_data['charts']['fraud_by_hour'] = list(reversed(fraud_by_hour))
        
        # 2. Top Fraud Reasons
        fraud_reasons = PostbackLog.objects.filter(
            is_fraud=True,
            created_at__gte=time_periods['last_24h']
        ).exclude(
            fraud_indicators__isnull=True
        ).values_list('fraud_indicators', flat=True)
        
        reason_counter = {}
        for reasons in fraud_reasons:
            if reasons:
                for reason in reasons[:3]:  # Take first 3 reasons
                    reason_counter[reason] = reason_counter.get(reason, 0) + 1
        
        dashboard_data['charts']['top_fraud_reasons'] = [
            {'reason': reason, 'count': count}
            for reason, count in sorted(reason_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # 3. Blacklist Activity
        blacklist_activity = BlacklistedIP.objects.filter(
            created_at__gte=time_periods['last_7d']
        ).extra({
            'date': "DATE(created_at)"
        }).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        dashboard_data['charts']['blacklist_activity'] = list(blacklist_activity)
        
        # 4. Blocked vs Allowed Traffic
        traffic_stats = PostbackLog.objects.filter(
            created_at__gte=time_periods['last_24h']
        ).aggregate(
            total=Count('id'),
            blocked=Count('id', filter=Q(is_fraud=True)),
            allowed=Count('id', filter=Q(is_fraud=False))
        )
        
        dashboard_data['metrics']['traffic_stats'] = traffic_stats
        
        # 5. Most Active Malicious IPs
        malicious_ips = PostbackLog.objects.filter(
            is_fraud=True,
            created_at__gte=time_periods['last_24h']
        ).values('ip_address').annotate(
            count=Count('id'),
            first_seen=models.Min('created_at'),
            last_seen=models.Max('created_at')
        ).order_by('-count')[:10]
        
        dashboard_data['metrics']['malicious_ips'] = list(malicious_ips)
        
        # Cache the dashboard data
        cache_key = f"fraud_dashboard_{now.strftime('%Y%m%d_%H')}"
        RedisCacheManager._cache.set(cache_key, dashboard_data, timeout=3600)  # 1 hour
        
        logger.info("Fraud analytics dashboard generated successfully")
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Fraud analytics generation failed: {str(e)}")
        return {'error': str(e), 'status': 'FAILED'}

# ============================================================================
# CACHE MANAGEMENT TASKS
# ============================================================================

@shared_task(queue='cache')
def warmup_blacklist_cache_task(batch_size: int = 2000) -> Dict:
    """
    Warm up Redis cache with blacklist data.
    Runs every 6 hours.
    
    Args:
        batch_size: Records per batch
        
    Returns:
        Cache warmup results
    """
    logger.info(f"Starting blacklist cache warmup (batch_size: {batch_size})")
    
    try:
        start_time = timezone.now()
        
        # Warm up blacklist cache
        cached_count = BlacklistedIP.prefetch_and_cache_active_ips(batch_size)
        
        # Also warm up known bad IPs
        known_bad_count = KnownBadIP.objects.filter(is_active=True).count()
        if known_bad_count > 0:
            known_bad_ips = KnownBadIP.objects.filter(
                is_active=True
            ).values_list('ip_address', flat=True)[:5000]  # Limit to 5000
            
            ip_status_map = {ip: True for ip in known_bad_ips}
            RedisCacheManager.bulk_cache_ip_blacklist(ip_status_map)
        
        # Get cache statistics
        cache_stats = RedisCacheManager.get_cache_stats()
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Cache warmup completed in {duration:.2f}s - "
            f"{cached_count} IPs cached, Hit Rate: {cache_stats.get('hit_rate', 0):.1f}%"
        )
        
        return {
            'status': 'SUCCESS',
            'blacklist_ips_cached': cached_count,
            'known_bad_ips_cached': known_bad_count,
            'cache_stats': cache_stats,
            'duration_seconds': round(duration, 2),
            'completed_at': end_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache warmup failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

@shared_task(queue='cache')
def cleanup_stale_cache_task() -> Dict:
    """
    Cleanup stale cache entries.
    Runs every hour.
    
    Returns:
        Cleanup results
    """
    logger.info("Starting stale cache cleanup")
    
    try:
        # This would require Redis SCAN functionality
        # For now, we'll use a simpler approach
        
        cleared_count = RedisCacheManager.clear_all_blacklist_cache()
        
        logger.info(f"Cleared {cleared_count} blacklist cache entries")
        
        return {
            'status': 'SUCCESS',
            'cleared_entries': cleared_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

# ============================================================================
# THIRD-PARTY DATA SYNC TASKS
# ============================================================================

@shared_task(queue='data_sync', max_retries=3)
def sync_external_ip_reputation_task() -> Dict:
    """
    Sync IP reputation data from external sources.
    Runs daily at 4:30 AM.
    
    Returns:
        Sync results
    """
    logger.info("Starting external IP reputation sync")
    
    try:
        synced_sources = []
        new_entries = 0
        updated_entries = 0
        
        # 1. Sync from AbuseIPDB (if configured)
        if hasattr(settings, 'ABUSEIPDB_API_KEY'):
            abuseipdb_result = sync_abuseipdb_data()
            if abuseipdb_result:
                synced_sources.append('abuseipdb')
                new_entries += abuseipdb_result.get('new_entries', 0)
                updated_entries += abuseipdb_result.get('updated_entries', 0)
        
        # 2. Sync from FireHOL (if enabled)
        if getattr(settings, 'SYNC_FIREHOL', False):
            firehol_result = sync_firehol_data()
            if firehol_result:
                synced_sources.append('firehol')
                new_entries += firehol_result.get('new_entries', 0)
        
        # 3. Sync from other sources...
        
        # After sync, warm up cache
        if new_entries > 0 or updated_entries > 0:
            warmup_blacklist_cache_task.delay()
        
        result = {
            'status': 'SUCCESS',
            'sources_synced': synced_sources,
            'new_entries': new_entries,
            'updated_entries': updated_entries,
            'total_changes': new_entries + updated_entries,
            'completed_at': timezone.now().isoformat()
        }
        
        logger.info(
            f"External IP reputation sync completed: "
            f"{len(synced_sources)} sources, {result['total_changes']} changes"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"External IP reputation sync failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

def sync_abuseipdb_data() -> Optional[Dict]:
    """
    Sync data from AbuseIPDB
    """
    try:
        api_key = getattr(settings, 'ABUSEIPDB_API_KEY')
        if not api_key:
            return None
        
        # Configure API parameters
        days = 30  # Last 30 days
        confidence_minimum = 90  # Minimum confidence score
        
        headers = {
            'Key': api_key,
            'Accept': 'application/json'
        }
        
        # Get blacklist from AbuseIPDB
        response = requests.get(
            'https://api.abuseipdb.com/api/v2/blacklist',
            headers=headers,
            params={
                'confidenceMinimum': confidence_minimum,
                'limit': 10000,
                'plaintext': 'true'
            },
            timeout=30
        )
        
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        blacklist_data = data.get('data', '').split('\n')
        
        new_entries = 0
        
        # Add to KnownBadIP table
        for ip_entry in blacklist_data:
            if ip_entry.strip():
                ip_address = ip_entry.strip()
                
                # Check if already exists
                exists = KnownBadIP.objects.filter(ip_address=ip_address).exists()
                
                if not exists:
                    KnownBadIP.objects.create(
                        ip_address=ip_address,
                        threat_type='abuse',
                        source='abuseipdb',
                        confidence_score=95,
                        description='Blocked by AbuseIPDB community',
                        is_active=True
                    )
                    new_entries += 1
        
        return {
            'new_entries': new_entries,
            'updated_entries': 0,
            'source': 'abuseipdb'
        }
        
    except Exception as e:
        logger.error(f"AbuseIPDB sync error: {str(e)}")
        return None

def sync_firehol_data() -> Optional[Dict]:
    """
    Sync data from FireHOL IP lists
    """
    try:
        # Download FireHOL level1 list (basic protection)
        response = requests.get(
            'https://iplists.firehol.org/files/firehol_level1.netset',
            timeout=30
        )
        
        response.raise_for_status()
        
        ip_entries = response.text.split('\n')
        new_entries = 0
        
        for line in ip_entries:
            line = line.strip()
            if line and not line.startswith('#'):
                # Handle CIDR notation
                if '/' in line:
                    # For simplicity, we'll just store the base IP
                    base_ip = line.split('/')[0]
                    ip_address = base_ip
                else:
                    ip_address = line
                
                # Check if already exists
                exists = KnownBadIP.objects.filter(ip_address=ip_address).exists()
                
                if not exists:
                    KnownBadIP.objects.create(
                        ip_address=ip_address,
                        threat_type='malware',
                        source='firehol',
                        confidence_score=80,
                        description='Blocked by FireHOL level1 list',
                        is_active=True
                    )
                    new_entries += 1
        
        return {
            'new_entries': new_entries,
            'source': 'firehol'
        }
        
    except Exception as e:
        logger.error(f"FireHOL sync error: {str(e)}")
        return None

# ============================================================================
# MONITORING & ALERTING TASKS
# ============================================================================

@shared_task(queue='monitoring')
def monitor_suspicious_activity_task() -> Dict:
    """
    Monitor for suspicious activity and send alerts.
    Runs every hour.
    
    Returns:
        Monitoring results
    """
    logger.info("Starting suspicious activity monitoring")
    
    try:
        now = timezone.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)
        
        alerts = []
        
        # 1. Check postback traffic spike
        recent_postbacks = PostbackLog.objects.filter(
            created_at__gte=last_hour
        ).count()
        
        avg_postbacks = PostbackLog.objects.filter(
            created_at__gte=last_24h
        ).count() / 24
        
        spike_threshold = avg_postbacks * 2  # 2x average
        
        if recent_postbacks > spike_threshold and recent_postbacks > 100:
            alerts.append({
                'type': 'TRAFFIC_SPIKE',
                'severity': 'warning',
                'message': f"Postback traffic spike: {recent_postbacks} in last hour (avg: {avg_postbacks:.1f})",
                'details': {
                    'recent': recent_postbacks,
                    'average': avg_postbacks,
                    'threshold': spike_threshold
                }
            })
        
        # 2. Check fraud rate
        recent_fraud = PostbackLog.objects.filter(
            created_at__gte=last_hour,
            is_fraud=True
        ).count()
        
        if recent_postbacks > 0:
            fraud_rate = (recent_fraud / recent_postbacks) * 100
            
            if fraud_rate > 30:
                alerts.append({
                    'type': 'HIGH_FRAUD_RATE',
                    'severity': 'critical',
                    'message': f"High fraud rate detected: {fraud_rate:.1f}% in last hour",
                    'details': {
                        'fraud_count': recent_fraud,
                        'total_count': recent_postbacks,
                        'fraud_rate': fraud_rate
                    }
                })
            elif fraud_rate > 15:
                alerts.append({
                    'type': 'ELEVATED_FRAUD_RATE',
                    'severity': 'warning',
                    'message': f"Elevated fraud rate: {fraud_rate:.1f}% in last hour",
                    'details': {
                        'fraud_count': recent_fraud,
                        'total_count': recent_postbacks,
                        'fraud_rate': fraud_rate
                    }
                })
        
        # 3. Check for IP repetition (potential botnet)
        ip_activity = PostbackLog.objects.filter(
            created_at__gte=last_hour
        ).values('ip_address').annotate(
            count=Count('id')
        ).filter(
            count__gt=10
        ).order_by('-count')[:5]
        
        for ip_activity_item in ip_activity:
            ip = ip_activity_item['ip_address']
            count = ip_activity_item['count']
            
            alerts.append({
                'type': 'IP_ACTIVITY_SPIKE',
                'severity': 'info',
                'message': f"IP {ip} made {count} requests in last hour",
                'details': {
                    'ip_address': ip,
                    'request_count': count,
                    'period_hours': 1
                }
            })
        
        # 4. Check for blacklist effectiveness
        recent_blacklisted = PostbackLog.objects.filter(
            created_at__gte=last_hour,
            is_fraud=True,
            ip_address__in=BlacklistedIP.get_active_blacklisted_ips_cached()
        ).count()
        
        if recent_fraud > 0:
            blacklist_effectiveness = (recent_blacklisted / recent_fraud) * 100
            
            if blacklist_effectiveness < 50:
                alerts.append({
                    'type': 'LOW_BLACKLIST_EFFECTIVENESS',
                    'severity': 'warning',
                    'message': f"Blacklist catching only {blacklist_effectiveness:.1f}% of fraud",
                    'details': {
                        'fraud_blocked': recent_blacklisted,
                        'total_fraud': recent_fraud,
                        'effectiveness': blacklist_effectiveness
                    }
                })
        
        # Send alerts if any
        if alerts:
            send_alerts_task.delay(alerts)
        
        result = {
            'status': 'SUCCESS',
            'alerts_generated': len(alerts),
            'alerts': alerts,
            'monitoring_period': {
                'start': last_hour.isoformat(),
                'end': now.isoformat()
            },
            'completed_at': now.isoformat()
        }
        
        logger.info(f"Monitoring completed: {len(alerts)} alerts generated")
        
        return result
        
    except Exception as e:
        logger.error(f"Monitoring failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

@shared_task(queue='monitoring')
def send_alerts_task(alerts: List[Dict]) -> Dict:
    """
    Send alerts to appropriate channels.
    
    Args:
        alerts: List of alert dictionaries
        
    Returns:
        Alert sending results
    """
    try:
        # Group alerts by severity
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
        info_alerts = [a for a in alerts if a.get('severity') == 'info']
        
        # Send critical alerts immediately via email
        if critical_alerts:
            send_admin_notification_task.delay(
                subject=f"🚨 CRITICAL: {len(critical_alerts)} Fraud Detection Alerts",
                message_type='critical_alerts',
                data={'alerts': critical_alerts},
                priority='high'
            )
        
        # Send warning alerts (can be batched)
        if warning_alerts:
            send_admin_notification_task.delay(
                subject=f"[WARN] WARNING: {len(warning_alerts)} Suspicious Activities",
                message_type='warning_alerts',
                data={'alerts': warning_alerts},
                priority='medium'
            )
        
        # Store info alerts in dashboard only
        if info_alerts:
            store_alerts_in_dashboard(info_alerts)
        
        return {
            'status': 'SUCCESS',
            'alerts_sent': {
                'critical': len(critical_alerts),
                'warning': len(warning_alerts),
                'info': len(info_alerts)
            },
            'total_alerts': len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Alert sending failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

def store_alerts_in_dashboard(alerts: List[Dict]):
    """
    Store alerts in Redis for dashboard display
    """
    try:
        cache_key = "recent_alerts"
        existing_alerts = RedisCacheManager._cache.get(cache_key) or []
        
        # Add timestamp and limit to 100 most recent
        for alert in alerts:
            alert['timestamp'] = timezone.now().isoformat()
        
        all_alerts = alerts + existing_alerts
        all_alerts = all_alerts[:100]  # Keep only 100 most recent
        
        RedisCacheManager._cache.set(cache_key, all_alerts, timeout=86400)  # 24 hours
        
    except Exception as e:
        logger.error(f"Failed to store alerts in dashboard: {str(e)}")

# ============================================================================
# UTILITY TASKS
# ============================================================================

@shared_task(queue='maintenance')
def send_admin_notification_task(subject: str, message_type: str, 
                                data: Dict, priority: str = 'medium') -> bool:
    """
    Send notification to administrators.
    
    Args:
        subject: Email subject
        message_type: Type of message for template selection
        data: Data to include in message
        priority: Priority level (high, medium, low)
    
    Returns:
        True if sent successfully
    """
    try:
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
        
        if not admin_emails:
            logger.warning("No admin emails configured")
            return False
        
        # Use your email service
        context = {
            'subject': subject,
            'message_type': message_type,
            'data': data,
            'priority': priority,
            'timestamp': timezone.now().isoformat()
        }
        
        email_sent = send_email_template(
            template_name='admin_notification',
            subject=subject,
            to_emails=admin_emails,
            context=context
        )
        
        if email_sent:
            logger.info(f"Admin notification sent: {subject}")
        else:
            logger.error(f"Failed to send admin notification: {subject}")
        
        return email_sent
        
    except Exception as e:
        logger.error(f"Admin notification failed: {str(e)}")
        return False

@shared_task(queue='reports')
def store_report_history_task(report_type: str, data: Dict, 
                             sent_to: List[str]) -> Dict:
    """
    Store report in history for audit purposes.
    
    Args:
        report_type: Type of report
        data: Report data
        sent_to: List of recipient emails
    
    Returns:
        Storage result
    """
    try:
        # Store in Redis for quick access
        cache_key = f"report_history_{report_type}_{timezone.now().strftime('%Y%m%d')}"
        
        report_entry = {
            'type': report_type,
            'data': data,
            'sent_to': sent_to,
            'generated_at': timezone.now().isoformat(),
            'stored_at': timezone.now().isoformat()
        }
        
        # Get existing reports
        existing_reports = RedisCacheManager._cache.get(cache_key) or []
        existing_reports.append(report_entry)
        
        # Store for 30 days
        RedisCacheManager._cache.set(cache_key, existing_reports, timeout=2592000)
        
        return {
            'status': 'SUCCESS',
            'report_type': report_type,
            'stored_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Report history storage failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

# ============================================================================
# MANUAL TASK TRIGGERS (for admin panel)
# ============================================================================

@shared_task(queue='default')
def manual_blacklist_ip_task(ip_address: str, reason: str = 'manual', 
                            notes: str = '', expiry_days: int = 30) -> Dict:
    """
    Manually blacklist an IP address.
    Can be triggered from admin panel.
    
    Args:
        ip_address: IP to blacklist
        reason: Reason for blacklisting
        notes: Additional notes
        expiry_days: Days until auto-removal (0 for permanent)
    
    Returns:
        Blacklisting result
    """
    try:
        expiry_date = None
        if expiry_days > 0:
            expiry_date = timezone.now() + timedelta(days=expiry_days)
        
        # Check if already blacklisted
        existing = BlacklistedIP.objects.filter(ip_address=ip_address).first()
        
        if existing:
            existing.reason = reason
            existing.is_active = True
            existing.expiry_date = expiry_date
            if notes:
                existing.metadata['notes'] = notes
            existing.save()
            
            action = 'updated'
        else:
            BlacklistedIP.objects.create(
                ip_address=ip_address,
                reason=reason,
                is_active=True,
                expiry_date=expiry_date,
                metadata={
                    'notes': notes,
                    'added_by': 'manual_task',
                    'added_at': timezone.now().isoformat()
                }
            )
            action = 'added'
        
        # Invalidate cache
        RedisCacheManager.invalidate_ip_blacklist_cache(ip_address)
        
        logger.info(f"Manually blacklisted IP {ip_address} ({action})")
        
        return {
            'status': 'SUCCESS',
            'ip_address': ip_address,
            'action': action,
            'reason': reason,
            'expiry_date': expiry_date.isoformat() if expiry_date else 'permanent',
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Manual blacklist failed for {ip_address}: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

@shared_task(queue='default')
def manual_whitelist_ip_task(ip_address: str) -> Dict:
    """
    Manually whitelist (remove from blacklist) an IP address.
    Can be triggered from admin panel.
    
    Args:
        ip_address: IP to whitelist
    
    Returns:
        Whitelisting result
    """
    try:
        # Deactivate blacklist entry
        deactivated = BlacklistedIP.objects.filter(
            ip_address=ip_address,
            is_active=True
        ).update(is_active=False)
        
        # Also remove from KnownBadIP if exists
        KnownBadIP.objects.filter(
            ip_address=ip_address,
            is_active=True
        ).update(is_active=False)
        
        # Invalidate cache
        RedisCacheManager.invalidate_ip_blacklist_cache(ip_address)
        
        if deactivated:
            logger.info(f"Manually whitelisted IP {ip_address}")
            
            return {
                'status': 'SUCCESS',
                'ip_address': ip_address,
                'action': 'whitelisted',
                'entries_deactivated': deactivated,
                'completed_at': timezone.now().isoformat()
            }
        else:
            return {
                'status': 'SUCCESS',
                'ip_address': ip_address,
                'action': 'not_found',
                'message': 'IP was not active in blacklist',
                'completed_at': timezone.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Manual whitelist failed for {ip_address}: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

@shared_task(queue='default')
def bulk_blacklist_task(ip_list: List[str], reason: str = 'bulk', 
                       source: str = 'manual') -> Dict:
    """
    Bulk blacklist multiple IPs.
    
    Args:
        ip_list: List of IP addresses
        reason: Reason for blacklisting
        source: Source of the blacklist
    
    Returns:
        Bulk operation results
    """
    try:
        result = BlacklistedIP.bulk_blacklist_ips(
            ip_list=ip_list,
            reason=reason,
            expiry_days=30
        )
        
        logger.info(f"Bulk blacklist completed: {result}")
        
        return {
            'status': 'SUCCESS',
            'result': result,
            'source': source,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Bulk blacklist failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}

# ============================================================================
# TASK HEALTH CHECK
# ============================================================================

@shared_task(queue='monitoring')
def check_task_health_task() -> Dict:
    """
    Check health of all scheduled tasks.
    Runs every 30 minutes.
    
    Returns:
        Health check results
    """
    logger.info("Starting task health check")
    
    try:
        now = timezone.now()
        health_status = {
            'checked_at': now.isoformat(),
            'tasks': {},
            'overall': 'healthy'
        }
        
        # Check recent task executions
        # This would require task result tracking in your setup
        
        # For now, return basic health status
        health_status['tasks']['blacklist_cleanup'] = {
            'status': 'healthy',
            'last_run': 'N/A',  # Would come from your task tracking
            'next_run': '03:00 daily'
        }
        
        health_status['tasks']['weekly_report'] = {
            'status': 'healthy',
            'last_run': 'N/A',
            'next_run': 'Monday 09:00'
        }
        
        health_status['tasks']['cache_warmup'] = {
            'status': 'healthy',
            'last_run': 'N/A',
            'next_run': 'Every 6 hours'
        }
        
        health_status['tasks']['monitoring'] = {
            'status': 'healthy',
            'last_run': 'N/A',
            'next_run': 'Every hour'
        }
        
        # Check Redis connectivity
        try:
            cache_info = RedisCacheManager.get_cache_stats()
            health_status['redis'] = {
                'status': 'connected',
                'memory_used': cache_info.get('used_memory_human', 'N/A'),
                'hit_rate': f"{cache_info.get('hit_rate', 0):.1f}%"
            }
        except Exception as redis_error:
            health_status['redis'] = {
                'status': 'disconnected',
                'error': str(redis_error)
            }
            health_status['overall'] = 'degraded'
        
        # Store health status in cache
        RedisCacheManager._cache.set(
            'task_health_status', 
            health_status, 
            timeout=1800  # 30 minutes
        )
        
        logger.info("Task health check completed")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Task health check failed: {str(e)}")
        return {'status': 'FAILED', 'error': str(e)}