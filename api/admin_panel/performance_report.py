# api/admin_panel/performance_report.py
"""System performance report generator."""
from __future__ import annotations
import logging
from typing import Dict
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class PerformanceReportGenerator:
    """Generate system performance reports."""

    @classmethod
    def generate(cls, days: int = 7) -> Dict:
        """Full performance report."""
        report = {
            'period_days': days,
            'generated_at': timezone.now().isoformat(),
        }

        # API performance
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.performance_monitor import perf_monitor
            report['api'] = perf_monitor.get_dashboard_summary()
        except Exception:
            report['api'] = {}

        # Platform metrics
        try:
            from api.admin_panel.analytics import get_admin_dashboard_analytics
            report['platform'] = get_admin_dashboard_analytics(days)
        except Exception:
            report['platform'] = {}

        # Health
        try:
            from api.admin_panel.monitoring import get_system_health_score
            report['health_score'] = get_system_health_score()
        except Exception:
            report['health_score'] = 100

        # Cache stats
        try:
            from api.admin_panel.caching import cache_manager
            report['cache'] = cache_manager.get_cache_stats()
        except Exception:
            report['cache'] = {}

        # SLA
        try:
            from api.admin_panel.monitoring import sla_monitor
            report['sla'] = {
                'uptime_24h': sla_monitor.get_uptime(24),
                'uptime_7d':  sla_monitor.get_uptime(24 * 7),
            }
        except Exception:
            report['sla'] = {}

        return report

    @classmethod
    def generate_and_cache(cls, days: int = 7) -> Dict:
        from django.core.cache import cache
        report = cls.generate(days)
        cache.set(f'admin_panel:performance_report:{days}', report, 3600)
        return report


perf_report_generator = PerformanceReportGenerator()