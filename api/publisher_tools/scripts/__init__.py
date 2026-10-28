# publisher_tools/scripts/__init__.py
# ============================================================
# Exports management script runners.
# Each script has a run() or run_*() entry point.
# Can be called from management commands or Celery tasks.
#
# Usage:
#   from .scripts import run_fraud_detection, run_earnings_calculation
#   from .scripts import run_health_check, run_reports
# ============================================================

def run_fraud_detection(hours: int = 24):
    """Scan recent traffic logs for fraud patterns."""
    from .detect_fraud import run
    return run()

def run_earnings_calculation(year: int = None, month: int = None):
    """Calculate earnings for all publishers for given period."""
    from .calculate_earnings import run_earnings_calculation
    return run_earnings_calculation(year=year, month=month)

def run_reports(report_type: str = 'daily'):
    """Generate reports: 'daily', 'monthly', 'waterfall', 'fraud'."""
    from .generate_reports import run
    return run(report_type=report_type)

def run_health_check():
    """Check database, cache, pending tasks, webhook health."""
    from .health_check import (
        check_database_health,
        check_cache_health,
        check_pending_tasks,
        check_webhook_health,
        check_publisher_quality,
    )
    return {
        'database':  check_database_health(),
        'cache':     check_cache_health(),
        'tasks':     check_pending_tasks(),
        'webhooks':  check_webhook_health(),
        'quality':   check_publisher_quality(),
    }

def run_invoice_generation():
    """Generate invoices for eligible publishers."""
    from .generate_invoices import run
    return run()

def run_payment_processing():
    """Process pending payouts."""
    from .process_payments import run
    return run()

def run_waterfall_optimization():
    """Optimize waterfalls for all auto-optimize groups."""
    from .optimize_waterfall import run
    return run()

def run_traffic_validation():
    """Validate recent traffic against IVT rules."""
    from .validate_traffic import run
    return run()

def run_publisher_sync():
    """Sync publisher data with external systems."""
    from .sync_publishers import run_full_sync as run
    return run()

def run_ad_unit_update():
    """Update ad unit performance stats."""
    from .update_ad_units import run
    return run()

def run_backup():
    """Backup critical publisher data."""
    from .backup_data import run
    return run()

def run_log_cleanup():
    """Clean old logs per retention policy."""
    from .clean_logs import run
    return run()

__all__ = [
    'run_fraud_detection',
    'run_earnings_calculation',
    'run_reports',
    'run_health_check',
    'run_invoice_generation',
    'run_payment_processing',
    'run_waterfall_optimization',
    'run_traffic_validation',
    'run_publisher_sync',
    'run_ad_unit_update',
    'run_backup',
    'run_log_cleanup',
]
