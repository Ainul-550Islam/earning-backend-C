"""
api/ad_networks/monitoring.py
Monitoring and health checks for ad networks module
SaaS-ready with tenant support
"""

import logging
import psutil
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, transaction
from django.conf import settings

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, NetworkHealthCheck, NetworkAPILog
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== MONITORING METRICS ====================

class MonitoringMetrics:
    """Monitoring metrics definitions"""
    
    # System metrics
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    
    # Database metrics
    DB_CONNECTIONS = "db_connections"
    DB_QUERIES = "db_queries"
    DB_SLOW_QUERIES = "db_slow_queries"
    DB_LOCK_TIME = "db_lock_time"
    
    # Cache metrics
    CACHE_HITS = "cache_hits"
    CACHE_MISSES = "cache_misses"
    CACHE_HIT_RATE = "cache_hit_rate"
    CACHE_MEMORY_USAGE = "cache_memory_usage"
    
    # Application metrics
    ACTIVE_USERS = "active_users"
    OFFER_VIEWS = "offer_views"
    OFFER_CLICKS = "offer_clicks"
    CONVERSIONS = "conversions"
    REWARDS_PAID = "rewards_paid"
    API_REQUESTS = "api_requests"
    API_ERRORS = "api_errors"
    
    # Business metrics
    REVENUE = "revenue"
    USER_ACQUISITION = "user_acquisition"
    USER_RETENTION = "user_retention"
    CONVERSION_RATE = "conversion_rate"
    AVERAGE_REWARD = "average_reward"
    
    # Security metrics
    FAILED_LOGIN_ATTEMPTS = "failed_login_attempts"
    SUSPICIOUS_ACTIVITIES = "suspicious_activities"
    FRAUD_DETECTIONS = "fraud_detections"
    IP_BLACKLISTS = "ip_blacklists"


# ==================== HEALTH STATUS ====================

class HealthStatus:
    """Health status definitions"""
    
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ==================== BASE MONITOR ====================

class BaseMonitor:
    """Base monitor with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('monitoring', 300)
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key"""
        return get_cache_key(self.__class__.__name__, self.tenant_id, *args, **kwargs)
    
    def _get_from_cache(self, key: str) -> Any:
        """Get data from cache"""
        return cache.get(key)
    
    def _set_cache(self, key: str, data: Any, timeout: int = None) -> None:
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)


# ==================== SYSTEM MONITOR ====================

class SystemMonitor(BaseMonitor):
    """System resource monitoring"""
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()
            
            return {
                'timestamp': timezone.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency': {
                        'current': cpu_freq.current if cpu_freq else None,
                        'min': cpu_freq.min if cpu_freq else None,
                        'max': cpu_freq.max if cpu_freq else None,
                    } if cpu_freq else None,
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free,
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100,
                },
                'disk_io': {
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0,
                    'read_count': disk_io.read_count if disk_io else 0,
                    'write_count': disk_io.write_count if disk_io else 0,
                } if disk_io else None,
                'network_io': {
                    'bytes_sent': network_io.bytes_sent if network_io else 0,
                    'bytes_recv': network_io.bytes_recv if network_io else 0,
                    'packets_sent': network_io.packets_sent if network_io else 0,
                    'packets_recv': network_io.packets_recv if network_io else 0,
                } if network_io else None,
                'process': {
                    'memory_rss': process_memory.rss,
                    'memory_vms': process_memory.vms,
                    'cpu_percent': process_cpu,
                    'num_threads': process.num_threads,
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'status': HealthStatus.UNKNOWN,
            }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            metrics = self.get_system_metrics()
            
            # Determine health status
            status = HealthStatus.HEALTHY
            issues = []
            
            # Check CPU usage
            if metrics.get('cpu', {}).get('percent', 0) > 90:
                status = HealthStatus.CRITICAL
                issues.append("High CPU usage")
            elif metrics.get('cpu', {}).get('percent', 0) > 70:
                status = HealthStatus.WARNING
                issues.append("Moderate CPU usage")
            
            # Check memory usage
            if metrics.get('memory', {}).get('percent', 0) > 90:
                status = HealthStatus.CRITICAL
                issues.append("High memory usage")
            elif metrics.get('memory', {}).get('percent', 0) > 80:
                status = HealthStatus.WARNING
                issues.append("Moderate memory usage")
            
            # Check disk usage
            if metrics.get('disk', {}).get('percent', 0) > 90:
                status = HealthStatus.CRITICAL
                issues.append("High disk usage")
            elif metrics.get('disk', {}).get('percent', 0) > 80:
                status = HealthStatus.WARNING
                issues.append("Moderate disk usage")
            
            return {
                'status': status,
                'timestamp': timezone.now().isoformat(),
                'metrics': metrics,
                'issues': issues,
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {
                'status': HealthStatus.UNKNOWN,
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }


# ==================== DATABASE MONITOR ====================

class DatabaseMonitor(BaseMonitor):
    """Database monitoring"""
    
    def get_database_metrics(self) -> Dict[str, Any]:
        """Get database metrics"""
        try:
            # Get connection info
            with connection.cursor() as cursor:
                # Get database size
                cursor.execute("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as size,
                        pg_database_size(current_database()) as size_bytes
                """)
                db_size = cursor.fetchone()
                
                # Get connection count
                cursor.execute("""
                    SELECT count(*) as connection_count
                    FROM pg_stat_activity
                    WHERE state = 'active'
                """)
                connection_count = cursor.fetchone()
                
                # Get slow queries (if pg_stat_statements is available)
                try:
                    cursor.execute("""
                        SELECT 
                            count(*) as slow_queries,
                            avg(mean_exec_time) as avg_exec_time,
                            max(mean_exec_time) as max_exec_time
                        FROM pg_stat_statements
                        WHERE mean_exec_time > 1000
                    """)
                    slow_queries = cursor.fetchone()
                except:
                    slow_queries = (0, 0, 0)
                
                # Get table sizes
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """)
                table_sizes = cursor.fetchall()
            
            return {
                'timestamp': timezone.now().isoformat(),
                'database': {
                    'size': {
                        'pretty': db_size[0] if db_size else 'Unknown',
                        'bytes': db_size[1] if db_size else 0,
                    },
                    'connections': {
                        'active': connection_count[0] if connection_count else 0,
                    },
                    'slow_queries': {
                        'count': slow_queries[0],
                        'avg_time': slow_queries[1],
                        'max_time': slow_queries[2],
                    },
                    'tables': [
                        {
                            'schema': row[0],
                            'name': row[1],
                            'size': {
                                'pretty': row[2],
                                'bytes': row[3],
                            }
                        }
                        for row in table_sizes
                    ],
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting database metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'status': HealthStatus.UNKNOWN,
            }
    
    def get_database_health(self) -> Dict[str, Any]:
        """Get database health status"""
        try:
            metrics = self.get_database_metrics()
            
            # Determine health status
            status = HealthStatus.HEALTHY
            issues = []
            
            # Check connection count
            max_connections = getattr(settings, 'DATABASES', {}).get('default', {}).get('OPTIONS', {}).get('MAXCONNS', 100)
            active_connections = metrics.get('database', {}).get('connections', {}).get('active', 0)
            
            if active_connections > max_connections * 0.9:
                status = HealthStatus.CRITICAL
                issues.append("Too many active connections")
            elif active_connections > max_connections * 0.7:
                status = HealthStatus.WARNING
                issues.append("High connection count")
            
            # Check slow queries
            slow_query_count = metrics.get('database', {}).get('slow_queries', {}).get('count', 0)
            if slow_query_count > 100:
                status = HealthStatus.CRITICAL
                issues.append("Too many slow queries")
            elif slow_query_count > 50:
                status = HealthStatus.WARNING
                issues.append("High number of slow queries")
            
            return {
                'status': status,
                'timestamp': timezone.now().isoformat(),
                'metrics': metrics,
                'issues': issues,
            }
            
        except Exception as e:
            logger.error(f"Error getting database health: {str(e)}")
            return {
                'status': HealthStatus.UNKNOWN,
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }


# ==================== CACHE MONITOR ====================

class CacheMonitor(BaseMonitor):
    """Cache monitoring"""
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        try:
            # Test cache performance
            start_time = time.time()
            
            # Test cache set
            test_key = f"cache_test_{int(time.time())}"
            test_value = {"test": "data"}
            cache.set(test_key, test_value, timeout=60)
            
            # Test cache get
            cached_value = cache.get(test_key)
            
            # Test cache delete
            cache.delete(test_key)
            
            cache_response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Get Redis info if available
            cache_info = {}
            try:
                if hasattr(cache, 'client'):  # Redis cache
                    info = cache.client.info()
                    cache_info = {
                        'type': 'redis',
                        'version': info.get('redis_version'),
                        'used_memory': info.get('used_memory'),
                        'used_memory_human': info.get('used_memory_human'),
                        'connected_clients': info.get('connected_clients'),
                        'total_commands_processed': info.get('total_commands_processed'),
                        'keyspace_hits': info.get('keyspace_hits'),
                        'keyspace_misses': info.get('keyspace_misses'),
                        'hit_rate': self._calculate_hit_rate(
                            info.get('keyspace_hits', 0),
                            info.get('keyspace_misses', 0)
                        ),
                    }
                else:
                    cache_info = {'type': 'dummy'}
            except:
                cache_info = {'type': 'unknown'}
            
            return {
                'timestamp': timezone.now().isoformat(),
                'cache': {
                    'response_time_ms': cache_response_time,
                    'test_passed': cached_value == test_value,
                    'info': cache_info,
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting cache metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'status': HealthStatus.UNKNOWN,
            }
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100
    
    def get_cache_health(self) -> Dict[str, Any]:
        """Get cache health status"""
        try:
            metrics = self.get_cache_metrics()
            
            # Determine health status
            status = HealthStatus.HEALTHY
            issues = []
            
            # Check cache response time
            response_time = metrics.get('cache', {}).get('response_time_ms', 0)
            if response_time > 1000:  # 1 second
                status = HealthStatus.CRITICAL
                issues.append("Cache response time too high")
            elif response_time > 500:  # 500ms
                status = HealthStatus.WARNING
                issues.append("Cache response time high")
            
            # Check test passed
            if not metrics.get('cache', {}).get('test_passed', False):
                status = HealthStatus.CRITICAL
                issues.append("Cache test failed")
            
            # Check hit rate
            hit_rate = metrics.get('cache', {}).get('info', {}).get('hit_rate', 0)
            if hit_rate < 50:
                status = HealthStatus.WARNING
                issues.append("Low cache hit rate")
            
            return {
                'status': status,
                'timestamp': timezone.now().isoformat(),
                'metrics': metrics,
                'issues': issues,
            }
            
        except Exception as e:
            logger.error(f"Error getting cache health: {str(e)}")
            return {
                'status': HealthStatus.UNKNOWN,
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }


# ==================== APPLICATION MONITOR ====================

class ApplicationMonitor(BaseMonitor):
    """Application monitoring"""
    
    def get_application_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get application metrics"""
        try:
            start_time = timezone.now() - timedelta(hours=hours)
            
            # User metrics
            active_users = self._get_active_users_count(start_time)
            new_users = self._get_new_users_count(start_time)
            
            # Offer metrics
            offer_views = self._get_offer_views_count(start_time)
            offer_clicks = self._get_offer_clicks_count(start_time)
            
            # Conversion metrics
            conversions = self._get_conversions_count(start_time)
            conversion_rate = self._calculate_conversion_rate(offer_clicks, conversions)
            
            # Reward metrics
            rewards_paid = self._get_rewards_paid_count(start_time)
            total_rewards = self._get_total_rewards_amount(start_time)
            
            # API metrics
            api_requests = self._get_api_requests_count(start_time)
            api_errors = self._get_api_errors_count(start_time)
            
            return {
                'timestamp': timezone.now().isoformat(),
                'period_hours': hours,
                'users': {
                    'active': active_users,
                    'new': new_users,
                },
                'offers': {
                    'views': offer_views,
                    'clicks': offer_clicks,
                },
                'conversions': {
                    'count': conversions,
                    'rate': conversion_rate,
                },
                'rewards': {
                    'paid': rewards_paid,
                    'total_amount': float(total_rewards),
                },
                'api': {
                    'requests': api_requests,
                    'errors': api_errors,
                    'error_rate': self._calculate_error_rate(api_requests, api_errors),
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting application metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'status': HealthStatus.UNKNOWN,
            }
    
    def _get_active_users_count(self, start_time: datetime) -> int:
        """Get active users count"""
        # This would typically query user activity logs
        # For now, return a placeholder
        return 0
    
    def _get_new_users_count(self, start_time: datetime) -> int:
        """Get new users count"""
        return User.objects.filter(date_joined__gte=start_time).count()
    
    def _get_offer_views_count(self, start_time: datetime) -> int:
        """Get offer views count"""
        # This would typically query analytics logs
        # For now, return a placeholder
        return 0
    
    def _get_offer_clicks_count(self, start_time: datetime) -> int:
        """Get offer clicks count"""
        # This would typically query click logs
        # For now, return a placeholder
        return 0
    
    def _get_conversions_count(self, start_time: datetime) -> int:
        """Get conversions count"""
        return OfferConversion.objects.filter(
            tenant_id=self.tenant_id,
            created_at__gte=start_time
        ).count()
    
    def _calculate_conversion_rate(self, clicks: int, conversions: int) -> float:
        """Calculate conversion rate"""
        if clicks == 0:
            return 0.0
        return (conversions / clicks) * 100
    
    def _get_rewards_paid_count(self, start_time: datetime) -> int:
        """Get rewards paid count"""
        return OfferReward.objects.filter(
            tenant_id=self.tenant_id,
            status=RewardStatus.PAID,
            paid_at__gte=start_time
        ).count()
    
    def _get_total_rewards_amount(self, start_time: datetime) -> Decimal:
        """Get total rewards amount"""
        from django.db.models import Sum
        result = OfferReward.objects.filter(
            tenant_id=self.tenant_id,
            status=RewardStatus.PAID,
            paid_at__gte=start_time
        ).aggregate(total=Sum('amount'))['total']
        return result or 0
    
    def _get_api_requests_count(self, start_time: datetime) -> int:
        """Get API requests count"""
        # This would typically query API logs
        # For now, return a placeholder
        return 0
    
    def _get_api_errors_count(self, start_time: datetime) -> int:
        """Get API errors count"""
        # This would typically query error logs
        # For now, return a placeholder
        return 0
    
    def _calculate_error_rate(self, requests: int, errors: int) -> float:
        """Calculate error rate"""
        if requests == 0:
            return 0.0
        return (errors / requests) * 100
    
    def get_application_health(self) -> Dict[str, Any]:
        """Get application health status"""
        try:
            metrics = self.get_application_metrics(hours=1)
            
            # Determine health status
            status = HealthStatus.HEALTHY
            issues = []
            
            # Check error rate
            error_rate = metrics.get('api', {}).get('error_rate', 0)
            if error_rate > 10:
                status = HealthStatus.CRITICAL
                issues.append("High API error rate")
            elif error_rate > 5:
                status = HealthStatus.WARNING
                issues.append("Moderate API error rate")
            
            # Check conversion rate
            conversion_rate = metrics.get('conversions', {}).get('rate', 0)
            if conversion_rate < 1:
                status = HealthStatus.WARNING
                issues.append("Low conversion rate")
            
            return {
                'status': status,
                'timestamp': timezone.now().isoformat(),
                'metrics': metrics,
                'issues': issues,
            }
            
        except Exception as e:
            logger.error(f"Error getting application health: {str(e)}")
            return {
                'status': HealthStatus.UNKNOWN,
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }


# ==================== BUSINESS MONITOR ====================

class BusinessMonitor(BaseMonitor):
    """Business metrics monitoring"""
    
    def get_business_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get business metrics"""
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # Revenue metrics
            total_revenue = self._get_total_revenue(start_date)
            daily_revenue = self._get_daily_revenue(start_date, days)
            
            # User metrics
            total_users = User.objects.filter(date_joined__gte=start_date).count()
            user_retention = self._calculate_user_retention(start_date)
            
            # Offer metrics
            active_offers = Offer.objects.filter(
                tenant_id=self.tenant_id,
                status=OfferStatus.ACTIVE
            ).count()
            
            # Conversion metrics
            total_conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__gte=start_date
            ).count()
            
            # Average reward
            from django.db.models import Avg
            avg_reward = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__gte=start_date,
                status=ConversionStatus.APPROVED
            ).aggregate(avg=Avg('payout'))['avg'] or 0
            
            return {
                'timestamp': timezone.now().isoformat(),
                'period_days': days,
                'revenue': {
                    'total': float(total_revenue),
                    'daily': daily_revenue,
                    'average_daily': float(total_revenue / days) if days > 0 else 0,
                },
                'users': {
                    'total': total_users,
                    'retention_rate': user_retention,
                },
                'offers': {
                    'active': active_offers,
                },
                'conversions': {
                    'total': total_conversions,
                    'average_reward': float(avg_reward),
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting business metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'status': HealthStatus.UNKNOWN,
            }
    
    def _get_total_revenue(self, start_date: datetime) -> Decimal:
        """Get total revenue"""
        from django.db.models import Sum
        result = OfferConversion.objects.filter(
            tenant_id=self.tenant_id,
            created_at__gte=start_date,
            status=ConversionStatus.APPROVED
        ).aggregate(total=Sum('payout'))['total']
        return result or 0
    
    def _get_daily_revenue(self, start_date: datetime, days: int) -> List[Dict[str, Any]]:
        """Get daily revenue breakdown"""
        daily_revenue = []
        
        for i in range(days):
            date = start_date + timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            from django.db.models import Sum
            day_revenue = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[day_start, day_end],
                status=ConversionStatus.APPROVED
            ).aggregate(total=Sum('payout'))['total'] or 0
            
            daily_revenue.append({
                'date': date.isoformat(),
                'revenue': float(day_revenue),
            })
        
        return daily_revenue
    
    def _calculate_user_retention(self, start_date: datetime) -> float:
        """Calculate user retention rate"""
        # This is a simplified calculation
        # In practice, you'd want more sophisticated retention analysis
        total_users = User.objects.filter(date_joined__gte=start_date).count()
        
        if total_users == 0:
            return 0.0
        
        # Get users who had at least one conversion
        active_users = OfferConversion.objects.filter(
            engagement__user__date_joined__gte=start_date,
            tenant_id=self.tenant_id
        ).values('engagement__user').distinct().count()
        
        return (active_users / total_users) * 100
    
    def get_business_health(self) -> Dict[str, Any]:
        """Get business health status"""
        try:
            metrics = self.get_business_metrics(days=7)
            
            # Determine health status
            status = HealthStatus.HEALTHY
            issues = []
            
            # Check revenue
            avg_daily_revenue = metrics.get('revenue', {}).get('average_daily', 0)
            if avg_daily_revenue < 100:
                status = HealthStatus.WARNING
                issues.append("Low daily revenue")
            
            # Check user retention
            retention_rate = metrics.get('users', {}).get('retention_rate', 0)
            if retention_rate < 20:
                status = HealthStatus.WARNING
                issues.append("Low user retention")
            
            return {
                'status': status,
                'timestamp': timezone.now().isoformat(),
                'metrics': metrics,
                'issues': issues,
            }
            
        except Exception as e:
            logger.error(f"Error getting business health: {str(e)}")
            return {
                'status': HealthStatus.UNKNOWN,
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }


# ==================== COMPREHENSIVE MONITOR ====================

class ComprehensiveMonitor(BaseMonitor):
    """Comprehensive monitoring combining all monitors"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.system_monitor = SystemMonitor(tenant_id)
        self.database_monitor = DatabaseMonitor(tenant_id)
        self.cache_monitor = CacheMonitor(tenant_id)
        self.application_monitor = ApplicationMonitor(tenant_id)
        self.business_monitor = BusinessMonitor(tenant_id)
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        try:
            # Get health from all monitors
            system_health = self.system_monitor.get_system_health()
            database_health = self.database_monitor.get_database_health()
            cache_health = self.cache_monitor.get_cache_health()
            application_health = self.application_monitor.get_application_health()
            business_health = self.business_monitor.get_business_health()
            
            # Determine overall status
            all_statuses = [
                system_health.get('status'),
                database_health.get('status'),
                cache_health.get('status'),
                application_health.get('status'),
                business_health.get('status'),
            ]
            
            if HealthStatus.CRITICAL in all_statuses:
                overall_status = HealthStatus.CRITICAL
            elif HealthStatus.WARNING in all_statuses:
                overall_status = HealthStatus.WARNING
            elif HealthStatus.UNKNOWN in all_statuses:
                overall_status = HealthStatus.WARNING
            else:
                overall_status = HealthStatus.HEALTHY
            
            # Collect all issues
            all_issues = []
            for health in [system_health, database_health, cache_health, application_health, business_health]:
                all_issues.extend(health.get('issues', []))
            
            return {
                'overall_status': overall_status,
                'timestamp': timezone.now().isoformat(),
                'components': {
                    'system': system_health,
                    'database': database_health,
                    'cache': cache_health,
                    'application': application_health,
                    'business': business_health,
                },
                'issues': all_issues,
            }
            
        except Exception as e:
            logger.error(f"Error getting overall health: {str(e)}")
            return {
                'overall_status': HealthStatus.UNKNOWN,
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get metrics for monitoring dashboard"""
        try:
            return {
                'system': self.system_monitor.get_system_metrics(),
                'database': self.database_monitor.get_database_metrics(),
                'cache': self.cache_monitor.get_cache_metrics(),
                'application': self.application_monitor.get_application_metrics(hours=24),
                'business': self.business_monitor.get_business_metrics(days=30),
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
            }


# ==================== ALERTING ====================

class AlertManager(BaseMonitor):
    """Alert management for monitoring"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.monitor = ComprehensiveMonitor(tenant_id)
    
    def check_and_send_alerts(self) -> Dict[str, Any]:
        """Check health and send alerts if needed"""
        try:
            health = self.monitor.get_overall_health()
            
            alerts = []
            
            # Check for critical issues
            if health['overall_status'] == HealthStatus.CRITICAL:
                alerts.append({
                    'level': 'critical',
                    'message': 'System is in critical state',
                    'issues': health['issues'],
                    'timestamp': health['timestamp'],
                })
            
            # Check for warning issues
            elif health['overall_status'] == HealthStatus.WARNING:
                alerts.append({
                    'level': 'warning',
                    'message': 'System has warnings',
                    'issues': health['issues'],
                    'timestamp': health['timestamp'],
                })
            
            # Send alerts (this would integrate with notification service)
            for alert in alerts:
                self._send_alert(alert)
            
            return {
                'alerts_sent': len(alerts),
                'alerts': alerts,
                'health_status': health['overall_status'],
            }
            
        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")
            return {
                'error': str(e),
            }
    
    def _send_alert(self, alert: Dict[str, Any]):
        """Send alert notification"""
        # This would integrate with email, Slack, etc.
        logger.warning(f"ALERT: {alert['message']} - {alert['issues']}")


# ==================== EXPORTS ====================

__all__ = [
    # Metrics and status
    'MonitoringMetrics',
    'HealthStatus',
    
    # Monitors
    'BaseMonitor',
    'SystemMonitor',
    'DatabaseMonitor',
    'CacheMonitor',
    'ApplicationMonitor',
    'BusinessMonitor',
    'ComprehensiveMonitor',
    
    # Alerting
    'AlertManager',
]
