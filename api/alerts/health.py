"""
Production-grade health check system for alerts app
"""
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, DatabaseError
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.core.management import call_command
import redis
import json
import time
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HealthCheckStatus:
    """Health check status constants"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class HealthChecker:
    """Comprehensive health checker for alerts system"""
    
    def __init__(self):
        self.start_time = time.time()
        self.checks = []
        self.overall_status = HealthCheckStatus.HEALTHY
    
    def add_check(self, name: str, status: str, message: str = "", 
                  response_time: float = 0, details: Dict = None):
        """Add a health check result"""
        check = {
            "name": name,
            "status": status,
            "message": message,
            "response_time": round(response_time, 3),
            "timestamp": timezone.now().isoformat(),
            "details": details or {}
        }
        self.checks.append(check)
        
        # Update overall status
        if status == HealthCheckStatus.UNHEALTHY:
            self.overall_status = HealthCheckStatus.UNHEALTHY
        elif status == HealthCheckStatus.DEGRADED and self.overall_status == HealthCheckStatus.HEALTHY:
            self.overall_status = HealthCheckStatus.DEGRADED
    
    def check_database(self) -> bool:
        """Check database connectivity and performance"""
        start_time = time.time()
        try:
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result[0] != 1:
                    self.add_check(
                        "database", 
                        HealthCheckStatus.UNHEALTHY,
                        "Database query returned unexpected result",
                        time.time() - start_time
                    )
                    return False
                
                # Test table existence (alerts models). Uses Django's introspection
                # API rather than raw information_schema SQL - DATABASE() is a
                # MySQL-only function and doesn't exist in PostgreSQL, which made
                # this raise an error (and report the DB "unhealthy") on every
                # call in production. introspection.table_names() works the same
                # way across PostgreSQL, MySQL, and SQLite.
                existing_tables = set(connection.introspection.table_names())
                table_count = len(
                    existing_tables & {'alerts_alertlog', 'alerts_alertrule'}
                )
                
                # Server time - Django's own clock, no vendor-specific SQL needed
                db_time = timezone.now()
                
                self.add_check(
                    "database",
                    HealthCheckStatus.HEALTHY,
                    f"Database connected, {table_count} alert tables found",
                    time.time() - start_time,
                    {
                        "tables_found": table_count,
                        "server_time": str(db_time),
                        "connection_pool_stats": self._get_db_pool_stats()
                    }
                )
                return True
                
        except DatabaseError as e:
            self.add_check(
                "database",
                HealthCheckStatus.UNHEALTHY,
                f"Database connection failed: {str(e)}",
                time.time() - start_time,
                {"error_code": getattr(e, 'args', [None])[0]}
            )
            return False
        except Exception as e:
            self.add_check(
                "database",
                HealthCheckStatus.UNKNOWN,
                f"Database check failed: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def check_redis_cache(self) -> bool:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        try:
            # Test cache set/get
            test_key = "health_check_test"
            test_value = f"test_{int(time.time())}"
            
            # Set test value
            cache.set(test_key, test_value, timeout=10)
            
            # Get test value
            retrieved_value = cache.get(test_key)
            
            # Clean up
            cache.delete(test_key)
            
            if retrieved_value != test_value:
                self.add_check(
                    "redis_cache",
                    HealthCheckStatus.UNHEALTHY,
                    "Cache set/get operation failed",
                    time.time() - start_time
                )
                return False
            
            # Get Redis info if available
            redis_info = self._get_redis_info()
            
            self.add_check(
                "redis_cache",
                HealthCheckStatus.HEALTHY,
                "Redis cache working properly",
                time.time() - start_time,
                redis_info
            )
            return True
            
        except Exception as e:
            self.add_check(
                "redis_cache",
                HealthCheckStatus.UNHEALTHY,
                f"Redis cache check failed: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def check_celery_workers(self) -> bool:
        """Check Celery worker availability and status"""
        start_time = time.time()
        try:
            from .celery_tasks import app as celery_app
            
            # Check if Celery app is configured
            if not celery_app.conf.broker_url:
                self.add_check(
                    "celery_workers",
                    HealthCheckStatus.UNHEALTHY,
                    "Celery broker not configured",
                    time.time() - start_time
                )
                return False
            
            # Get active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            
            if not active_workers:
                self.add_check(
                    "celery_workers",
                    HealthCheckStatus.UNHEALTHY,
                    "No active Celery workers found",
                    time.time() - start_time
                )
                return False
            
            worker_count = len(active_workers)
            
            # Check worker stats
            stats = inspect.stats()
            
            self.add_check(
                "celery_workers",
                HealthCheckStatus.HEALTHY,
                f"{worker_count} active Celery workers",
                time.time() - start_time,
                {
                    "worker_count": worker_count,
                    "workers": list(active_workers.keys()),
                    "stats": stats
                }
            )
            return True
            
        except ImportError as e:
            self.add_check(
                "celery_workers",
                HealthCheckStatus.DEGRADED,
                f"Celery not available: {str(e)}",
                time.time() - start_time
            )
            return False
        except Exception as e:
            self.add_check(
                "celery_workers",
                HealthCheckStatus.UNHEALTHY,
                f"Celery worker check failed: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def check_celery_beat(self) -> bool:
        """Check Celery Beat scheduler status"""
        start_time = time.time()
        try:
            from .celery_tasks import app as celery_app
            
            # Check if beat schedule is configured
            beat_schedule = celery_app.conf.beat_schedule
            
            if not beat_schedule:
                self.add_check(
                    "celery_beat",
                    HealthCheckStatus.DEGRADED,
                    "No Celery beat schedule configured",
                    time.time() - start_time
                )
                return False
            
            scheduled_tasks = len(beat_schedule)
            
            # Check last beat execution (if available)
            last_beat_check = cache.get("celery_beat_last_check")
            
            self.add_check(
                "celery_beat",
                HealthCheckStatus.HEALTHY,
                f"{scheduled_tasks} tasks scheduled in beat",
                time.time() - start_time,
                {
                    "scheduled_tasks": scheduled_tasks,
                    "tasks": list(beat_schedule.keys()),
                    "last_check": last_beat_check
                }
            )
            return True
            
        except Exception as e:
            self.add_check(
                "celery_beat",
                HealthCheckStatus.UNHEALTHY,
                f"Celery beat check failed: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def check_alert_system(self) -> bool:
        """Check alerts-specific functionality"""
        start_time = time.time()
        try:
            from .models import AlertLog, AlertRule
            
            # Check alert models are accessible
            alert_count = AlertLog.objects.count()
            rule_count = AlertRule.objects.count()
            
            # Check recent alert activity
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_alerts = AlertLog.objects.filter(triggered_at__gte=recent_cutoff).count()
            
            # Check active rules
            active_rules = AlertRule.objects.filter(is_active=True).count()
            
            self.add_check(
                "alert_system",
                HealthCheckStatus.HEALTHY,
                f"Alert system operational: {alert_count} alerts, {rule_count} rules",
                time.time() - start_time,
                {
                    "total_alerts": alert_count,
                    "total_rules": rule_count,
                    "recent_alerts_1h": recent_alerts,
                    "active_rules": active_rules
                }
            )
            return True
            
        except Exception as e:
            self.add_check(
                "alert_system",
                HealthCheckStatus.UNHEALTHY,
                f"Alert system check failed: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def check_disk_space(self) -> bool:
        """Check disk space availability"""
        start_time = time.time()
        try:
            import shutil
            
            total, used, free = shutil.disk_usage("/")
            
            free_percent = (free / total) * 100
            
            if free_percent < 5:  # Less than 5% free
                status = HealthCheckStatus.UNHEALTHY
                message = f"Critical: Only {free_percent:.1f}% disk space free"
            elif free_percent < 10:  # Less than 10% free
                status = HealthCheckStatus.DEGRADED
                message = f"Warning: Only {free_percent:.1f}% disk space free"
            else:
                status = HealthCheckStatus.HEALTHY
                message = f"Disk space OK: {free_percent:.1f}% free"
            
            self.add_check(
                "disk_space",
                status,
                message,
                time.time() - start_time,
                {
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "free_percent": round(free_percent, 2)
                }
            )
            
            return status != HealthCheckStatus.UNHEALTHY
            
        except Exception as e:
            self.add_check(
                "disk_space",
                HealthCheckStatus.UNKNOWN,
                f"Disk space check failed: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def _get_db_pool_stats(self) -> Dict[str, Any]:
        """Get database connection pool statistics"""
        try:
            # This would depend on your database backend
            # For PostgreSQL with psycopg2, you might use connection.pool
            return {
                "pool_status": "active",
                "note": "Pool stats require specific DB driver implementation"
            }
        except:
            return {"pool_status": "unknown"}
    
    def _get_redis_info(self) -> Dict[str, Any]:
        """Get Redis server information"""
        try:
            # Try to get Redis info if redis-py is available
            try:
                import redis
                redis_client = redis.from_url(settings.CACHES['default']['LOCATION'])
                info = redis_client.info()
                return {
                    "redis_version": info.get('redis_version'),
                    "connected_clients": info.get('connected_clients'),
                    "used_memory": info.get('used_memory_human'),
                    "uptime_in_seconds": info.get('uptime_in_seconds')
                }
            except:
                return {"redis_info": "Redis info not available"}
        except:
            return {"redis_info": "Redis configuration not found"}
    
    def get_health_response(self) -> JsonResponse:
        """Generate comprehensive health response"""
        total_time = time.time() - self.start_time
        
        response_data = {
            "status": self.overall_status,
            "timestamp": timezone.now().isoformat(),
            "version": getattr(settings, 'ALERTS_VERSION', '1.0.0'),
            "environment": getattr(settings, 'ENVIRONMENT', 'development'),
            "total_response_time": round(total_time, 3),
            "checks": self.checks,
            "summary": {
                "total_checks": len(self.checks),
                "healthy": len([c for c in self.checks if c["status"] == HealthCheckStatus.HEALTHY]),
                "degraded": len([c for c in self.checks if c["status"] == HealthCheckStatus.DEGRADED]),
                "unhealthy": len([c for c in self.checks if c["status"] == HealthCheckStatus.UNHEALTHY]),
                "unknown": len([c for c in self.checks if c["status"] == HealthCheckStatus.UNKNOWN])
            }
        }
        
        # Set appropriate HTTP status code
        status_code = 200
        if self.overall_status == HealthCheckStatus.UNHEALTHY:
            status_code = 503
        elif self.overall_status == HealthCheckStatus.DEGRADED:
            status_code = 200  # Still serve but indicate degraded state
        
        return JsonResponse(response_data, status=status_code)


@require_http_methods(["GET", "HEAD"])
def health_check(request):
    """
    Comprehensive health check endpoint
    
    Returns detailed system health status including:
    - Database connectivity and performance
    - Redis cache status
    - Celery workers and beat scheduler
    - Alert system functionality
    - Disk space availability
    """
    checker = HealthChecker()
    
    # Run all health checks
    checker.check_database()
    checker.check_redis_cache()
    checker.check_celery_workers()
    checker.check_celery_beat()
    checker.check_alert_system()
    checker.check_disk_space()
    
    return checker.get_health_response()


@require_http_methods(["GET"])
def health_simple(request):
    """
    Simple health check endpoint for load balancers
    
    Returns minimal health status for quick checks
    """
    try:
        # Quick database check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Quick cache check
        cache.set("health_simple", "ok", timeout=10)
        cache.get("health_simple")
        
        return JsonResponse({
            "status": "healthy",
            "timestamp": timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Simple health check failed: {e}")
        return JsonResponse({
            "status": "unhealthy",
            "timestamp": timezone.now().isoformat(),
            "error": 'Internal server error'
        }, status=503)


@require_http_methods(["GET"])
def health_readiness(request):
    """
    Readiness probe for Kubernetes/container orchestration
    
    Checks if the application is ready to serve traffic
    """
    checker = HealthChecker()
    
    # Only check critical services for readiness
    db_ok = checker.check_database()
    cache_ok = checker.check_redis_cache()
    
    if db_ok and cache_ok:
        return JsonResponse({
            "status": "ready",
            "timestamp": timezone.now().isoformat()
        })
    else:
        return JsonResponse({
            "status": "not_ready",
            "timestamp": timezone.now().isoformat(),
            "checks": checker.checks
        }, status=503)


@require_http_methods(["GET"])
def health_liveness(request):
    """
    Liveness probe for Kubernetes/container orchestration
    
    Checks if the application is still alive and responsive
    """
    # Simple liveness check - if we can respond, we're alive
    return JsonResponse({
        "status": "alive",
        "timestamp": timezone.now().isoformat(),
        "uptime": time.time() - getattr(settings, 'START_TIME', time.time())
    })


@csrf_exempt
@require_http_methods(["POST"])
def health_heartbeat(request):
    """
    Heartbeat endpoint for external monitoring services
    
    Accepts heartbeat pings from monitoring systems
    """
    try:
        data = json.loads(request.body)
        service_name = data.get('service', 'unknown')
        service_status = data.get('status', 'unknown')
        
        # Store heartbeat in cache
        heartbeat_key = f"heartbeat_{service_name}"
        heartbeat_data = {
            "service": service_name,
            "status": service_status,
            "timestamp": timezone.now().isoformat(),
            "ip_address": request.META.get('REMOTE_ADDR')
        }
        
        cache.set(heartbeat_key, heartbeat_data, timeout=300)  # 5 minutes
        
        logger.info(f"Heartbeat received from {service_name}: {service_status}")
        
        return JsonResponse({
            "status": "received",
            "timestamp": timezone.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            "error": "Invalid JSON"
        }, status=400)
    except Exception as e:
        logger.error(f"Heartbeat processing failed: {e}")
        return JsonResponse({
            "error": 'Internal server error'
        }, status=500)
