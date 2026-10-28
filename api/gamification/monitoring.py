"""
Gamification Monitoring — System monitoring and health checks.

This module provides comprehensive monitoring capabilities for the gamification
system, including health checks, performance metrics, alerting, and
system status reporting.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement,
    WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.repositories import (
    BadgeRepository, UserBadgeRepository, StreakRepository,
    UserAchievementRepository, WebhookDeliveryRepository
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.helpers import CacheHelper
from api.gamification.webhooks import WebhookService

logger = logging.getLogger(__name__)


class HealthCheck:
    """Represents a health check result."""
    
    def __init__(self, name: str, status: str, message: str, 
                 details: Optional[Dict[str, Any]] = None, 
                 duration: Optional[float] = None,
                 timestamp: Optional[datetime] = None):
        self.name = name
        self.status = status  # healthy, warning, critical, unknown
        self.message = message
        self.details = details or {}
        self.duration = duration
        self.timestamp = timestamp or timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert health check to dictionary."""
        return {
            'name': self.name,
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'duration': self.duration,
            'timestamp': self.timestamp.isoformat()
        }


class Metric:
    """Represents a system metric."""
    
    def __init__(self, name: str, value: Union[int, float, str], 
                 unit: Optional[str] = None, tags: Optional[Dict[str, str]] = None,
                 timestamp: Optional[datetime] = None):
        self.name = name
        self.value = value
        self.unit = unit
        self.tags = tags or {}
        self.timestamp = timestamp or timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'tags': self.tags,
            'timestamp': self.timestamp.isoformat()
        }


class Alert:
    """Represents a system alert."""
    
    def __init__(self, severity: str, title: str, message: str,
                 source: str, details: Optional[Dict[str, Any]] = None,
                 timestamp: Optional[datetime] = None):
        self.severity = severity  # info, warning, error, critical
        self.title = title
        self.message = message
        self.source = source
        self.details = details or {}
        self.timestamp = timestamp or timezone.now()
        self.id = f"{source}_{severity}_{title}_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            'id': self.id,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'source': self.source,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class BaseHealthChecker:
    """Base class for health checkers."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def check(self) -> HealthCheck:
        """Perform health check."""
        raise NotImplementedError("Subclasses must implement check method")


class DatabaseHealthChecker(BaseHealthChecker):
    """Health checker for database connectivity."""
    
    def check(self) -> HealthCheck:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Check table counts
            table_counts = {}
            tables = ['gamification_badge', 'gamification_userbadge', 'gamification_streak',
                     'gamification_dailychallenge', 'gamification_userdailychallenge',
                     'gamification_userachievement']
            
            for table in tables:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        table_counts[table] = count
                except Exception as e:
                    table_counts[table] = f"Error: {e}"
            
            # Check database size
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as size,
                        pg_database_size(current_database()) as size_bytes
                """)
                db_size = cursor.fetchone()
            
            duration = time.time() - start_time
            
            return HealthCheck(
                name="database",
                status="healthy",
                message="Database is responsive",
                details={
                    'table_counts': table_counts,
                    'database_size': db_size[0],
                    'database_size_bytes': db_size[1],
                    'query_time': duration
                },
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Database health check failed: {e}")
            
            return HealthCheck(
                name="database",
                status="critical",
                message=f"Database connection failed: {e}",
                details={'error': str(e)},
                duration=duration
            )


class CacheHealthChecker(BaseHealthChecker):
    """Health checker for cache connectivity."""
    
    def check(self) -> HealthCheck:
        """Check cache connectivity and performance."""
        start_time = time.time()
        
        try:
            # Test cache connectivity
            test_key = "health_check_test"
            test_value = {"test": True, "timestamp": timezone.now().isoformat()}
            
            # Write test
            cache.set(test_key, test_value, 60)
            
            # Read test
            cached_value = cache.get(test_key)
            
            # Clean up
            cache.delete(test_key)
            
            if cached_value != test_value:
                raise Exception("Cache read/write test failed")
            
            # Get cache info
            cache_info = {}
            try:
                # Try to get cache stats (Redis-specific)
                if hasattr(cache, 'client'):
                    info = cache.client.info()
                    cache_info = {
                        'used_memory': info.get('used_memory_human'),
                        'connected_clients': info.get('connected_clients'),
                        'keyspace_hits': info.get('keyspace_hits'),
                        'keyspace_misses': info.get('keyspace_misses'),
                        'hit_rate': info.get('keyspace_hits', 0) / max(1, info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0))
                    }
            except Exception:
                cache_info = {'message': 'Cache stats not available'}
            
            duration = time.time() - start_time
            
            return HealthCheck(
                name="cache",
                status="healthy",
                message="Cache is responsive",
                details={
                    'cache_info': cache_info,
                    'test_duration': duration
                },
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Cache health check failed: {e}")
            
            return HealthCheck(
                name="cache",
                status="critical",
                message=f"Cache connection failed: {e}",
                details={'error': str(e)},
                duration=duration
            )


class GamificationHealthChecker(BaseHealthChecker):
    """Health checker for gamification system components."""
    
    def check(self) -> HealthCheck:
        """Check gamification system health."""
        start_time = time.time()
        
        try:
            component_status = {}
            
            # Check badge system
            try:
                badge_count = Badge.objects.count()
                user_badge_count = UserBadge.objects.count()
                component_status['badges'] = {
                    'status': 'healthy',
                    'total_badges': badge_count,
                    'user_badges': user_badge_count
                }
            except Exception as e:
                component_status['badges'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check streak system
            try:
                streak_count = Streak.objects.count()
                active_streaks = Streak.objects.filter(is_active=True).count()
                component_status['streaks'] = {
                    'status': 'healthy',
                    'total_streaks': streak_count,
                    'active_streaks': active_streaks
                }
            except Exception as e:
                component_status['streaks'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check challenge system
            try:
                challenge_count = DailyChallenge.objects.count()
                user_challenge_count = UserDailyChallenge.objects.count()
                component_status['challenges'] = {
                    'status': 'healthy',
                    'total_challenges': challenge_count,
                    'user_challenges': user_challenge_count
                }
            except Exception as e:
                component_status['challenges'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check achievement system
            try:
                achievement_count = UserAchievement.objects.count()
                component_status['achievements'] = {
                    'status': 'healthy',
                    'total_achievements': achievement_count
                }
            except Exception as e:
                component_status['achievements'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check webhook system
            try:
                webhook_service = WebhookService()
                webhook_health = webhook_service.get_system_health()
                component_status['webhooks'] = webhook_health
            except Exception as e:
                component_status['webhooks'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Determine overall status
            error_count = sum(1 for comp in component_status.values() 
                             if comp.get('status') == 'error')
            
            if error_count == 0:
                overall_status = 'healthy'
                message = 'All gamification components are healthy'
            elif error_count <= 2:
                overall_status = 'warning'
                message = f'{error_count} gamification components have errors'
            else:
                overall_status = 'critical'
                message = f'Multiple ({error_count}) gamification components have errors'
            
            duration = time.time() - start_time
            
            return HealthCheck(
                name="gamification",
                status=overall_status,
                message=message,
                details=component_status,
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Gamification health check failed: {e}")
            
            return HealthCheck(
                name="gamification",
                status="critical",
                message=f"Gamification system check failed: {e}",
                details={'error': str(e)},
                duration=duration
            )


class PerformanceHealthChecker(BaseHealthChecker):
    """Health checker for system performance."""
    
    def check(self) -> HealthCheck:
        """Check system performance metrics."""
        start_time = time.time()
        
        try:
            performance_metrics = {}
            
            # Database query performance
            try:
                db_start = time.time()
                Badge.objects.count()
                UserBadge.objects.count()
                Streak.objects.count()
                db_time = time.time() - db_start
                
                performance_metrics['database_queries'] = {
                    'status': 'healthy' if db_time < 0.5 else 'warning',
                    'query_time': db_time,
                    'queries_per_second': 3 / db_time
                }
            except Exception as e:
                performance_metrics['database_queries'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Cache performance
            try:
                cache_start = time.time()
                for i in range(10):
                    cache.set(f"perf_test_{i}", f"value_{i}", 60)
                    cache.get(f"perf_test_{i}")
                cache_time = time.time() - cache_start
                
                performance_metrics['cache_operations'] = {
                    'status': 'healthy' if cache_time < 0.1 else 'warning',
                    'cache_time': cache_time,
                    'operations_per_second': 20 / cache_time
                }
            except Exception as e:
                performance_metrics['cache_operations'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Memory usage (simplified check)
            try:
                import psutil
                memory = psutil.virtual_memory()
                performance_metrics['memory'] = {
                    'status': 'healthy' if memory.percent < 80 else 'warning',
                    'usage_percent': memory.percent,
                    'available_gb': round(memory.available / (1024**3), 2)
                }
            except ImportError:
                performance_metrics['memory'] = {
                    'status': 'unknown',
                    'message': 'psutil not available'
                }
            
            # Determine overall status
            warning_count = sum(1 for metric in performance_metrics.values() 
                              if metric.get('status') == 'warning')
            error_count = sum(1 for metric in performance_metrics.values() 
                             if metric.get('status') == 'error')
            
            if error_count > 0:
                overall_status = 'critical'
                message = f'{error_count} performance metrics have errors'
            elif warning_count > 0:
                overall_status = 'warning'
                message = f'{warning_count} performance metrics show warnings'
            else:
                overall_status = 'healthy'
                message = 'All performance metrics are healthy'
            
            duration = time.time() - start_time
            
            return HealthCheck(
                name="performance",
                status=overall_status,
                message=message,
                details=performance_metrics,
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Performance health check failed: {e}")
            
            return HealthCheck(
                name="performance",
                status="critical",
                message=f"Performance check failed: {e}",
                details={'error': str(e)},
                duration=duration
            )


class MonitoringService:
    """Main monitoring service for the gamification system."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.health_checkers = {
            'database': DatabaseHealthChecker(),
            'cache': CacheHealthChecker(),
            'gamification': GamificationHealthChecker(),
            'performance': PerformanceHealthChecker()
        }
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
    
    def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_status = 'healthy'
        
        for name, checker in self.health_checkers.items():
            try:
                result = checker.check()
                results[name] = result.to_dict()
                
                # Update overall status
                if result.status == 'critical':
                    overall_status = 'critical'
                elif result.status == 'warning' and overall_status == 'healthy':
                    overall_status = 'warning'
                    
            except Exception as e:
                self.logger.error(f"Health check '{name}' failed: {e}")
                results[name] = {
                    'name': name,
                    'status': 'critical',
                    'message': f"Health check failed: {e}",
                    'details': {'error': str(e)},
                    'timestamp': timezone.now().isoformat()
                }
                overall_status = 'critical'
        
        # Create overall health summary
        health_summary = {
            'overall_status': overall_status,
            'checks': results,
            'checked_at': timezone.now().isoformat(),
            'total_checks': len(results),
            'healthy_checks': len([r for r in results.values() if r['status'] == 'healthy']),
            'warning_checks': len([r for r in results.values() if r['status'] == 'warning']),
            'critical_checks': len([r for r in results.values() if r['status'] == 'critical'])
        }
        
        # Store health status
        cache.set('gamification_health_status', health_summary, 300)  # 5 minutes
        
        return health_summary
    
    def get_system_metrics(self, time_range: str = '1h') -> List[Metric]:
        """Get system metrics for the specified time range."""
        return self.metrics_collector.collect_metrics(time_range)
    
    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        """Get active alerts."""
        return self.alert_manager.get_active_alerts(severity)
    
    def create_alert(self, severity: str, title: str, message: str,
                    source: str, details: Optional[Dict[str, Any]] = None) -> Alert:
        """Create a new alert."""
        alert = Alert(severity, title, message, source, details)
        self.alert_manager.add_alert(alert)
        return alert
    
    def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard data."""
        # Health checks
        health_status = self.run_health_checks()
        
        # Recent metrics
        metrics = self.get_system_metrics('1h')
        
        # Active alerts
        alerts = self.get_active_alerts()
        
        # System statistics
        stats = self._get_system_statistics()
        
        return {
            'health_status': health_status,
            'metrics': [m.to_dict() for m in metrics],
            'alerts': [a.to_dict() for a in alerts],
            'system_statistics': stats,
            'generated_at': timezone.now().isoformat()
        }
    
    def _get_system_statistics(self) -> Dict[str, Any]:
        """Get system statistics."""
        try:
            stats = {}
            
            # User statistics
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            stats['users'] = {
                'total_users': User.objects.count(),
                'active_users_today': User.objects.filter(
                    last_login__gte=timezone.now() - timedelta(days=1)
                ).count(),
                'active_users_week': User.objects.filter(
                    last_login__gte=timezone.now() - timedelta(days=7)
                ).count()
            }
            
            # Gamification statistics
            stats['gamification'] = {
                'total_badges': Badge.objects.count(),
                'total_user_badges': UserBadge.objects.count(),
                'total_streaks': Streak.objects.count(),
                'active_streaks': Streak.objects.filter(is_active=True).count(),
                'total_challenges': DailyChallenge.objects.count(),
                'total_user_challenges': UserDailyChallenge.objects.count(),
                'total_achievements': UserAchievement.objects.count()
            }
            
            # Performance statistics
            stats['performance'] = {
                'database_size': self._get_database_size(),
                'cache_hit_rate': self._get_cache_hit_rate(),
                'average_response_time': self._get_average_response_time()
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting system statistics: {e}")
            return {'error': str(e)}
    
    def _get_database_size(self) -> str:
        """Get database size."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                return cursor.fetchone()[0]
        except Exception:
            return "Unknown"
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        try:
            if hasattr(cache, 'client'):
                info = cache.client.info()
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                total = hits + misses
                return (hits / total * 100) if total > 0 else 0.0
        except Exception:
            pass
        return 0.0
    
    def _get_average_response_time(self) -> float:
        """Get average response time (simplified)."""
        try:
            start_time = time.time()
            Badge.objects.count()
            return time.time() - start_time
        except Exception:
            return 0.0


class MetricsCollector:
    """Collector for system metrics."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def collect_metrics(self, time_range: str = '1h') -> List[Metric]:
        """Collect system metrics."""
        metrics = []
        
        # Database metrics
        metrics.extend(self._collect_database_metrics())
        
        # Cache metrics
        metrics.extend(self._collect_cache_metrics())
        
        # Gamification metrics
        metrics.extend(self._collect_gamification_metrics())
        
        # Performance metrics
        metrics.extend(self._collect_performance_metrics())
        
        return metrics
    
    def _collect_database_metrics(self) -> List[Metric]:
        """Collect database metrics."""
        metrics = []
        
        try:
            # Connection count
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = cursor.fetchone()[0]
            
            metrics.append(Metric(
                name="database.active_connections",
                value=active_connections,
                unit="connections"
            ))
            
            # Table sizes
            tables = ['gamification_badge', 'gamification_userbadge', 'gamification_streak']
            for table in tables:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f"""
                            SELECT pg_size_pretty(pg_total_relation_size('{table}')) as size,
                                   pg_total_relation_size('{table}') as size_bytes
                        """)
                        size_info = cursor.fetchone()
                        
                        metrics.append(Metric(
                            name=f"database.table_size_bytes",
                            value=size_info[1],
                            unit="bytes",
                            tags={'table': table}
                        ))
                except Exception as e:
                    self.logger.error(f"Error getting size for table {table}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {e}")
        
        return metrics
    
    def _collect_cache_metrics(self) -> List[Metric]:
        """Collect cache metrics."""
        metrics = []
        
        try:
            if hasattr(cache, 'client'):
                info = cache.client.info()
                
                metrics.append(Metric(
                    name="cache.used_memory",
                    value=info.get('used_memory', 0),
                    unit="bytes"
                ))
                
                metrics.append(Metric(
                    name="cache.connected_clients",
                    value=info.get('connected_clients', 0),
                    unit="clients"
                ))
                
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                total = hits + misses
                hit_rate = (hits / total * 100) if total > 0 else 0.0
                
                metrics.append(Metric(
                    name="cache.hit_rate",
                    value=hit_rate,
                    unit="percent"
                ))
        
        except Exception as e:
            self.logger.error(f"Error collecting cache metrics: {e}")
        
        return metrics
    
    def _collect_gamification_metrics(self) -> List[Metric]:
        """Collect gamification-specific metrics."""
        metrics = []
        
        try:
            # Badge metrics
            total_badges = Badge.objects.count()
            user_badges = UserBadge.objects.count()
            
            metrics.append(Metric(
                name="gamification.total_badges",
                value=total_badges,
                unit="badges"
            ))
            
            metrics.append(Metric(
                name="gamification.user_badges",
                value=user_badges,
                unit="user_badges"
            ))
            
            # Streak metrics
            total_streaks = Streak.objects.count()
            active_streaks = Streak.objects.filter(is_active=True).count()
            
            metrics.append(Metric(
                name="gamification.total_streaks",
                value=total_streaks,
                unit="streaks"
            ))
            
            metrics.append(Metric(
                name="gamification.active_streaks",
                value=active_streaks,
                unit="streaks"
            ))
            
            # Challenge metrics
            total_challenges = DailyChallenge.objects.count()
            completed_challenges = UserDailyChallenge.objects.filter(is_completed=True).count()
            
            metrics.append(Metric(
                name="gamification.total_challenges",
                value=total_challenges,
                unit="challenges"
            ))
            
            metrics.append(Metric(
                name="gamification.completed_challenges",
                value=completed_challenges,
                unit="challenges"
            ))
            
            # Achievement metrics
            total_achievements = UserAchievement.objects.count()
            
            metrics.append(Metric(
                name="gamification.total_achievements",
                value=total_achievements,
                unit="achievements"
            ))
        
        except Exception as e:
            self.logger.error(f"Error collecting gamification metrics: {e}")
        
        return metrics
    
    def _collect_performance_metrics(self) -> List[Metric]:
        """Collect performance metrics."""
        metrics = []
        
        try:
            # Response time metrics
            start_time = time.time()
            Badge.objects.count()
            badge_query_time = time.time() - start_time
            
            metrics.append(Metric(
                name="performance.badge_query_time",
                value=badge_query_time,
                unit="seconds"
            ))
            
            # Cache performance
            cache_start = time.time()
            cache.set("perf_test", "test_value", 60)
            cache.get("perf_test")
            cache_time = time.time() - cache_start
            
            metrics.append(Metric(
                name="performance.cache_operation_time",
                value=cache_time,
                unit="seconds"
            ))
            
            # Memory usage
            try:
                import psutil
                memory = psutil.virtual_memory()
                
                metrics.append(Metric(
                    name="system.memory_usage_percent",
                    value=memory.percent,
                    unit="percent"
                ))
                
                metrics.append(Metric(
                    name="system.memory_available_gb",
                    value=memory.available / (1024**3),
                    unit="gigabytes"
                ))
            except ImportError:
                pass
        
        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {e}")
        
        return metrics


class AlertManager:
    """Manager for system alerts."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.alerts_cache_key = "gamification_alerts"
        self.alerts_cache_timeout = 3600  # 1 hour
    
    def add_alert(self, alert: Alert) -> None:
        """Add an alert."""
        try:
            # Get existing alerts
            existing_alerts = cache.get(self.alerts_cache_key, [])
            
            # Add new alert
            existing_alerts.append(alert.to_dict())
            
            # Keep only recent alerts (last 100)
            if len(existing_alerts) > 100:
                existing_alerts = existing_alerts[-100:]
            
            # Update cache
            cache.set(self.alerts_cache_key, existing_alerts, self.alerts_cache_timeout)
            
            self.logger.warning(f"Alert created: {alert.title} - {alert.message}")
            
        except Exception as e:
            self.logger.error(f"Error adding alert: {e}")
    
    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        """Get active alerts."""
        try:
            alerts_data = cache.get(self.alerts_cache_key, [])
            
            # Filter by severity if specified
            if severity:
                alerts_data = [a for a in alerts_data if a['severity'] == severity]
            
            # Convert to Alert objects
            alerts = []
            for alert_data in alerts_data:
                alert = Alert(
                    severity=alert_data['severity'],
                    title=alert_data['title'],
                    message=alert_data['message'],
                    source=alert_data['source'],
                    details=alert_data.get('details', {}),
                    timestamp=datetime.fromisoformat(alert_data['timestamp'])
                )
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting active alerts: {e}")
            return []
    
    def clear_alerts(self, severity: Optional[str] = None) -> int:
        """Clear alerts."""
        try:
            if severity:
                # Clear alerts of specific severity
                existing_alerts = cache.get(self.alerts_cache_key, [])
                filtered_alerts = [a for a in existing_alerts if a['severity'] != severity]
                cache.set(self.alerts_cache_key, filtered_alerts, self.alerts_cache_timeout)
                cleared_count = len(existing_alerts) - len(filtered_alerts)
            else:
                # Clear all alerts
                cleared_count = len(cache.get(self.alerts_cache_key, []))
                cache.delete(self.alerts_cache_key)
            
            self.logger.info(f"Cleared {cleared_count} alerts")
            return cleared_count
            
        except Exception as e:
            self.logger.error(f"Error clearing alerts: {e}")
            return 0


# Global monitoring service instance
monitoring_service = MonitoringService()


# Convenience functions
def run_health_checks() -> Dict[str, Any]:
    """Run all health checks."""
    return monitoring_service.run_health_checks()


def get_system_health() -> Dict[str, Any]:
    """Get overall system health status."""
    return cache.get('gamification_health_status', {'status': 'unknown'})


def get_monitoring_dashboard() -> Dict[str, Any]:
    """Get monitoring dashboard data."""
    return monitoring_service.get_monitoring_dashboard()


def create_alert(severity: str, title: str, message: str, 
                source: str, details: Optional[Dict[str, Any]] = None) -> Alert:
    """Create a system alert."""
    return monitoring_service.create_alert(severity, title, message, source, details)


def get_active_alerts(severity: Optional[str] = None) -> List[Alert]:
    """Get active alerts."""
    return monitoring_service.get_active_alerts(severity)


def clear_alerts(severity: Optional[str] = None) -> int:
    """Clear alerts."""
    return monitoring_service.alert_manager.clear_alerts(severity)
