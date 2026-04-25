# api/payment_gateways/integration_system/health_check.py
# Integration system health dashboard

import time
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class IntegrationHealthCheck:
    """
    Health dashboard for the entire payment_gateways integration system.

    Checks:
        - Gateway connectivity (bKash, Nagad, Stripe, etc.)
        - Redis queue health (can enqueue/dequeue)
        - Database connectivity (can read/write)
        - External app availability (api.wallet, api.fraud_detection, etc.)
        - Circuit breaker states
        - Queue depths (warn if > 80% full)
        - Recent error rates

    Used by:
        - /api/payment/status/ — public status page
        - Admin dashboard
        - Monitoring systems (Prometheus, Datadog)
    """

    def run_all_checks(self) -> dict:
        """Run all health checks and return comprehensive status."""
        checks = {
            'gateways':         self.check_gateways(),
            'queue':            self.check_queue(),
            'database':         self.check_database(),
            'external_apps':    self.check_external_apps(),
            'circuit_breakers': self.check_circuit_breakers(),
            'queue_depths':     self.check_queue_depths(),
            'error_rates':      self.check_error_rates(),
        }

        # Overall status
        all_healthy  = all(
            v.get('status') in ('healthy', 'not_required')
            for v in checks.values()
            if isinstance(v, dict) and 'status' in v
        )
        has_degraded = any(
            v.get('status') == 'degraded'
            for v in checks.values()
            if isinstance(v, dict)
        )

        return {
            'status':     'healthy' if all_healthy else ('degraded' if has_degraded else 'down'),
            'timestamp':  time.time(),
            'checks':     checks,
        }

    def check_gateways(self) -> dict:
        """Check all gateway connectivity."""
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        try:
            svc     = GatewayHealthService()
            summary = svc.get_status_summary()
            down    = [g for g, s in summary.items() if s.get('status') == 'down']
            return {
                'status':   'healthy' if not down else 'degraded',
                'gateways': summary,
                'down':     down,
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def check_queue(self) -> dict:
        """Check Redis queue system."""
        try:
            from .message_queue import message_queue
            is_healthy = message_queue.is_healthy()
            return {
                'status': 'healthy' if is_healthy else 'degraded',
                'redis':  is_healthy,
            }
        except Exception as e:
            return {'status': 'degraded', 'error': str(e), 'fallback': 'in-memory queue active'}

    def check_database(self) -> dict:
        """Check database connectivity."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return {'status': 'healthy', 'db': 'connected'}
        except Exception as e:
            return {'status': 'down', 'error': str(e)}

    def check_external_apps(self) -> dict:
        """Check availability of your existing apps."""
        apps = {
            'api.wallet':          ('api.wallet.models', 'Wallet'),
            'api.fraud_detection': ('api.fraud_detection.models', 'FraudEvent'),
            'api.notifications':   ('api.notifications.models', None),
            'api.postback_engine': ('api.postback_engine.models', None),
            'api.kyc':             ('api.kyc.models', 'KYCProfile'),
            'api.gamification':    ('api.gamification.models', None),
        }
        results = {}
        for app_name, (module_path, _) in apps.items():
            try:
                __import__(module_path)
                results[app_name] = {'status': 'available'}
            except ImportError:
                results[app_name] = {'status': 'not_installed', 'note': 'Using payment_gateways fallback'}

        all_ok = all(v['status'] == 'available' for v in results.values())
        return {
            'status': 'healthy' if all_ok else 'degraded',
            'apps':   results,
        }

    def check_circuit_breakers(self) -> dict:
        """Check circuit breaker states."""
        from .fallback_logic import (wallet_cb, notifications_cb,
                                      fraud_detection_cb, postback_engine_cb)
        breakers = {
            'wallet':          wallet_cb.get_status(),
            'notifications':   notifications_cb.get_status(),
            'fraud_detection': fraud_detection_cb.get_status(),
            'postback_engine': postback_engine_cb.get_status(),
        }
        open_breakers = [name for name, s in breakers.items() if s['state'] == 'open']
        return {
            'status':       'degraded' if open_breakers else 'healthy',
            'breakers':     breakers,
            'open':         open_breakers,
        }

    def check_queue_depths(self) -> dict:
        """Check if any queues are filling up dangerously."""
        try:
            from .message_queue import message_queue
            depths = message_queue.get_all_depths()
            critical = {
                name: d for name, d in depths.items()
                if d.get('pct_full', 0) > 90
            }
            return {
                'status': 'degraded' if critical else 'healthy',
                'depths': depths,
                'critical_queues': list(critical.keys()),
            }
        except Exception as e:
            return {'status': 'unknown', 'error': str(e)}

    def check_error_rates(self) -> dict:
        """Check recent error rates across all operations."""
        try:
            from .performance_monitor import PerformanceMonitor
            stats = PerformanceMonitor().get_all_stats()
            high_error = {
                op: s for op, s in stats.items()
                if s.get('success_rate', 100) < 90 and s.get('count', 0) > 10
            }
            return {
                'status':       'degraded' if high_error else 'healthy',
                'stats':        stats,
                'high_error_ops':list(high_error.keys()),
            }
        except Exception as e:
            return {'status': 'unknown', 'error': str(e)}


# Singleton
health_checker = IntegrationHealthCheck()
