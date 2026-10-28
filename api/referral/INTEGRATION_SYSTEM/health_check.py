# api/referral/INTEGRATION_SYSTEM/health_check.py
# Health check for referral integration system
# Checks all connected modules + data consistency
# ============================================================

import logging
from datetime import timedelta
from typing import Dict, List, Optional
from django.utils import timezone
from .integ_constants import (
    HEALTH_STALE_TREE_DAYS, HEALTH_MIN_FRAUD_RULES,
    APP_WALLET, APP_NOTIFICATIONS, APP_FRAUD_DETECTION,
    APP_TASKS, APP_ANALYTICS, APP_AUDIT_LOGS,
)

logger = logging.getLogger(__name__)


class HealthStatus:
    OK       = 'ok'
    WARNING  = 'warning'
    CRITICAL = 'critical'
    UNKNOWN  = 'unknown'


class ReferralHealthCheck:
    """
    Comprehensive health check for the referral integration system.
    Called by:
      - GET /api/referral/health/
      - Celery monitoring task
      - Admin dashboard
    """

    def run_all(self) -> Dict:
        """Run all health checks and return consolidated report."""
        checks = {}
        start = timezone.now()

        checks['database']         = self.check_database()
        checks['cache']            = self.check_cache()
        checks['wallet_module']    = self.check_wallet_module()
        checks['notification_module'] = self.check_notification_module()
        checks['fraud_rules']      = self.check_fraud_rules()
        checks['stale_trees']      = self.check_stale_trees()
        checks['held_commissions'] = self.check_held_commissions()
        checks['pending_clawbacks'] = self.check_pending_clawbacks()
        checks['migration_state']  = self.check_migration_state()
        checks['settings']         = self.check_settings()
        checks['celery']           = self.check_celery()
        checks['integration_bus']  = self.check_event_bus()

        # Overall status
        statuses = [c['status'] for c in checks.values()]
        if HealthStatus.CRITICAL in statuses:
            overall = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.OK

        elapsed_ms = (timezone.now() - start).total_seconds() * 1000

        return {
            'status': overall,
            'timestamp': timezone.now().isoformat(),
            'elapsed_ms': round(elapsed_ms, 1),
            'checks': checks,
            'summary': {
                'ok': statuses.count(HealthStatus.OK),
                'warning': statuses.count(HealthStatus.WARNING),
                'critical': statuses.count(HealthStatus.CRITICAL),
                'unknown': statuses.count(HealthStatus.UNKNOWN),
            }
        }

    # ── Individual Checks ─────────────────────────────────────────────────────

    def check_database(self) -> Dict:
        """Can we read/write core referral tables?"""
        try:
            from api.referral.models import ReferralSettings, Referral
            count = Referral.objects.count()
            settings_ok = ReferralSettings.objects.exists()
            return {
                'status': HealthStatus.OK,
                'referral_count': count,
                'settings_configured': settings_ok,
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error': str(e),
                'message': 'Referral database tables inaccessible',
            }

    def check_cache(self) -> Dict:
        """Is Redis/cache working?"""
        try:
            from django.core.cache import cache
            test_key = 'referral:health:test'
            cache.set(test_key, 'ok', timeout=10)
            val = cache.get(test_key)
            if val == 'ok':
                return {'status': HealthStatus.OK, 'backend': str(cache.__class__.__name__)}
            return {'status': HealthStatus.WARNING, 'message': 'Cache read/write mismatch'}
        except Exception as e:
            return {
                'status': HealthStatus.WARNING,
                'error': str(e),
                'message': 'Cache unavailable — referral will use DB fallback',
            }

    def check_wallet_module(self) -> Dict:
        """Is api/wallet accessible?"""
        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet
            return {
                'status': HealthStatus.OK,
                'wallet_count': Wallet.objects.count(),
                'methods_available': [
                    'add_earnings', 'add_referral_commission', 'add_bonus'
                ],
            }
        except ImportError:
            return {
                'status': HealthStatus.CRITICAL,
                'message': 'api.wallet not found — commissions cannot be paid',
            }
        except Exception as e:
            return {'status': HealthStatus.WARNING, 'error': str(e)}

    def check_notification_module(self) -> Dict:
        """Is api/notifications accessible?"""
        try:
            from api.notifications.services import NotificationService
            return {'status': HealthStatus.OK, 'available': True}
        except ImportError:
            return {
                'status': HealthStatus.WARNING,
                'message': 'api.notifications not found — notifications disabled',
            }
        except Exception as e:
            return {'status': HealthStatus.WARNING, 'error': str(e)}

    def check_fraud_rules(self) -> Dict:
        """Are fraud detection rules configured?"""
        try:
            from api.referral.models import ReferralFraudRule
            active_rules = ReferralFraudRule.objects.filter(is_active=True).count()
            if active_rules == 0:
                return {
                    'status': HealthStatus.CRITICAL,
                    'active_rules': 0,
                    'message': 'No fraud rules! Run: python manage.py seed_referral_fraud_rules',
                }
            if active_rules < HEALTH_MIN_FRAUD_RULES:
                return {
                    'status': HealthStatus.WARNING,
                    'active_rules': active_rules,
                    'message': f'Only {active_rules} fraud rules — recommend at least {HEALTH_MIN_FRAUD_RULES}',
                }
            return {'status': HealthStatus.OK, 'active_rules': active_rules}
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}

    def check_stale_trees(self) -> Dict:
        """Are referral trees up to date?"""
        try:
            from api.referral.models import ReferralTree
            cutoff = timezone.now() - timedelta(days=HEALTH_STALE_TREE_DAYS)
            stale = ReferralTree.objects.filter(last_rebuilt_at__lt=cutoff).count()
            total = ReferralTree.objects.count()
            if stale > 0:
                pct = round(stale / total * 100, 1) if total > 0 else 0
                status = HealthStatus.WARNING if pct < 20 else HealthStatus.CRITICAL
                return {
                    'status': status,
                    'stale_trees': stale,
                    'total_trees': total,
                    'stale_pct': pct,
                    'message': f'{stale} trees not rebuilt in {HEALTH_STALE_TREE_DAYS}+ days',
                }
            return {'status': HealthStatus.OK, 'total_trees': total, 'stale_trees': 0}
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}

    def check_held_commissions(self) -> Dict:
        """Are there commissions stuck in held state too long?"""
        try:
            from api.referral.models import CommissionHold
            overdue = CommissionHold.objects.filter(
                is_released=False,
                release_at__lt=timezone.now() - timedelta(hours=1),
            ).count()
            pending = CommissionHold.objects.filter(is_released=False).count()
            if overdue > 0:
                return {
                    'status': HealthStatus.WARNING,
                    'overdue_holds': overdue,
                    'pending_holds': pending,
                    'message': f'{overdue} commissions overdue for release',
                }
            return {'status': HealthStatus.OK, 'pending_holds': pending}
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}

    def check_pending_clawbacks(self) -> Dict:
        """Are there approved clawbacks not yet processed?"""
        try:
            from api.referral.models import CommissionClawback
            approved = CommissionClawback.objects.filter(status='approved').count()
            pending = CommissionClawback.objects.filter(status='pending').count()
            if approved > 10:
                return {
                    'status': HealthStatus.WARNING,
                    'approved_unprocessed': approved,
                    'pending_review': pending,
                    'message': f'{approved} approved clawbacks not yet processed',
                }
            return {
                'status': HealthStatus.OK,
                'approved_unprocessed': approved,
                'pending_review': pending,
            }
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}

    def check_migration_state(self) -> Dict:
        """Are all referral migrations applied?"""
        try:
            from django.db.migrations.executor import MigrationExecutor
            from django.db import connections
            executor = MigrationExecutor(connections['default'])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            referral_pending = [
                str(m) for m in plan if 'referral' in str(m[0])
            ]
            if referral_pending:
                return {
                    'status': HealthStatus.CRITICAL,
                    'pending_migrations': referral_pending,
                    'message': 'Run: python manage.py migrate referral',
                }
            return {'status': HealthStatus.OK, 'pending_migrations': []}
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}

    def check_settings(self) -> Dict:
        """Are referral settings properly configured?"""
        try:
            from api.referral.models import ReferralSettings
            settings = ReferralSettings.objects.first()
            if not settings:
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': 'No ReferralSettings found — create one in admin',
                }
            issues = []
            if not settings.is_active:
                issues.append('Referral program is INACTIVE')
            if settings.level1_commission_rate <= 0:
                issues.append('L1 commission rate is 0%')
            if settings.commission_hold_days < 0:
                issues.append('Invalid hold days')

            if issues:
                return {
                    'status': HealthStatus.WARNING,
                    'issues': issues,
                    'is_active': settings.is_active,
                }
            return {
                'status': HealthStatus.OK,
                'is_active': settings.is_active,
                'l1_rate': float(settings.level1_commission_rate),
                'l2_rate': float(settings.level2_commission_rate),
                'l3_rate': float(settings.level3_commission_rate),
                'hold_days': settings.commission_hold_days,
                'active_campaign': bool(settings.active_campaign_id),
            }
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}

    def check_celery(self) -> Dict:
        """Is Celery available for async tasks?"""
        try:
            from celery import current_app
            inspect = current_app.control.inspect(timeout=2.0)
            active = inspect.active()
            if active is None:
                return {
                    'status': HealthStatus.WARNING,
                    'message': 'Celery workers not responding — async tasks disabled',
                }
            worker_count = len(active)
            return {'status': HealthStatus.OK, 'workers': worker_count}
        except ImportError:
            return {'status': HealthStatus.WARNING, 'message': 'Celery not installed'}
        except Exception as e:
            return {
                'status': HealthStatus.WARNING,
                'message': 'Celery check failed — may be offline',
                'error': str(e),
            }

    def check_event_bus(self) -> Dict:
        """Is the integration event bus operational?"""
        try:
            from api.referral.INTEGRATION_SYSTEM.event_bus import get_event_bus
            bus = get_event_bus()
            stats = bus.get_stats()
            dead_letters = stats.get('dead_letters', 0)
            if dead_letters > 100:
                return {
                    'status': HealthStatus.WARNING,
                    'dead_letters': dead_letters,
                    'message': f'{dead_letters} events in dead letter queue',
                    **stats,
                }
            return {'status': HealthStatus.OK, **stats}
        except Exception as e:
            return {'status': HealthStatus.UNKNOWN, 'error': str(e)}


# ── DRF View ──────────────────────────────────────────────────────────────────

def health_check_view(request):
    """
    GET /api/referral/health/
    Returns JSON health report.
    """
    from django.http import JsonResponse
    checker = ReferralHealthCheck()
    report = checker.run_all()
    status_code = 200 if report['status'] == HealthStatus.OK else (
        503 if report['status'] == HealthStatus.CRITICAL else 207
    )
    return JsonResponse(report, status=status_code)