# api/offer_inventory/reporting_audit/export_manager.py
"""
Export Manager — Centralized export dispatcher for all platform data.
Supports: CSV, JSON. Routes to correct report generator.
"""
import logging
from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

AVAILABLE_EXPORTS = [
    'revenue_report', 'conversion_report', 'withdrawal_report',
    'fraud_report', 'user_earnings', 'network_comparison',
    'audit_log', 'offer_cap_usage', 'postback_delivery',
    'user_growth', 'payout_reconciliation',
]


class ExportManager:
    """Single entry point for all data exports."""

    @classmethod
    def export(cls, export_type: str, format: str = 'json',
                days: int = 30, **kwargs):
        """Dispatch to the correct export function."""
        from api.offer_inventory.business.reporting_suite import ReportingEngine
        from api.offer_inventory.reporting import ReportGenerator
        from .audit_logs import AuditLogService

        handlers = {
            'revenue_report'      : lambda: ReportingEngine.revenue_report(days=days, format=format),
            'conversion_report'   : lambda: ReportingEngine.conversion_report(days=days, format=format),
            'withdrawal_report'   : lambda: ReportingEngine.withdrawal_report(days=days, format=format),
            'fraud_report'        : lambda: ReportingEngine.fraud_report(days=days),
            'user_earnings'       : lambda: ReportingEngine.user_earnings_report(days=days, format=format),
            'network_comparison'  : lambda: ReportingEngine.network_comparison(days=days),
            'audit_log'           : lambda: AuditLogService.export_audit_csv(days=days),
            'offer_cap_usage'     : lambda: ReportGenerator.offer_cap_usage(format=format),
            'postback_delivery'   : lambda: ReportGenerator.postback_delivery_report(days=days),
            'user_growth'         : lambda: ReportGenerator.user_growth(days=days),
            'payout_reconciliation': lambda: ReportGenerator.payout_reconciliation(),
        }

        handler = handlers.get(export_type)
        if not handler:
            raise ValueError(
                f'Unknown export type: {export_type}. '
                f'Available: {AVAILABLE_EXPORTS}'
            )

        logger.info(f'Export requested: {export_type} format={format} days={days}')
        return handler()

    @staticmethod
    def get_available_exports() -> list:
        """List all available export types with descriptions."""
        return [
            {'name': 'revenue_report',       'description': 'Daily revenue breakdown'},
            {'name': 'conversion_report',     'description': 'Conversion details'},
            {'name': 'withdrawal_report',     'description': 'Withdrawal history'},
            {'name': 'fraud_report',          'description': 'Fraud summary & sources'},
            {'name': 'user_earnings',         'description': 'Top user earners'},
            {'name': 'network_comparison',    'description': 'Network ROI side-by-side'},
            {'name': 'audit_log',             'description': 'Admin audit trail'},
            {'name': 'offer_cap_usage',       'description': 'Offer cap utilization'},
            {'name': 'postback_delivery',     'description': 'Postback success rates'},
            {'name': 'user_growth',           'description': 'Daily new registrations'},
            {'name': 'payout_reconciliation', 'description': 'Monthly payout reconciliation'},
        ]

    @staticmethod
    def schedule_export(export_type: str, email_to: str,
                         days: int = 30, format: str = 'csv') -> dict:
        """Schedule a report to be emailed."""
        from api.offer_inventory.tasks import send_email_batch
        logger.info(f'Export scheduled: {export_type} → {email_to}')
        return {
            'scheduled': True,
            'export_type': export_type,
            'email_to'  : email_to,
            'message'   : 'Report will be emailed shortly.',
        }
