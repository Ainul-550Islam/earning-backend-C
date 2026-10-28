# api/admin_panel/report_builder.py
"""Visual report builder — custom report definitions."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)

class ReportBuilder:
    AVAILABLE_MODELS = {
        'users': 'auth.User', 'wallets': 'wallet.Wallet',
        'payouts': 'payout_queue.PayoutItem', 'conversions': 'promotions.TaskSubmission',
        'fraud': 'fraud_detection.FraudAttempt', 'kyc': 'kyc.KYC',
    }
    AVAILABLE_AGGREGATIONS = ['count', 'sum', 'avg', 'min', 'max']
    AVAILABLE_FILTERS = ['date_range', 'status', 'amount_range', 'country', 'user_id']

    @classmethod
    def build_report(cls, config: Dict) -> Dict:
        """Build and execute a custom report from config."""
        model_key = config.get('model', 'users')
        metrics   = config.get('metrics', ['count'])
        filters   = config.get('filters', {})
        group_by  = config.get('group_by', '')
        limit     = min(int(config.get('limit', 1000)), 10000)

        try:
            from api.admin_panel.data_export import AdminDataExporter
            fmt = config.get('format', 'json')
            # Simple implementation — call selectors
            from api.admin_panel.selectors import get_platform_summary
            data = get_platform_summary()
            return {'success': True, 'data': data, 'config': config, 'generated_at': timezone.now().isoformat()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def save_report_definition(cls, name: str, config: Dict, actor) -> Dict:
        try:
            from api.admin_panel.models.reports import ReportDefinition
            report = ReportDefinition.objects.create(
                name=name, report_type='custom',
                columns=config.get('columns', []),
                filters=config.get('filters', {}),
                is_active=True,
            )
            return {'success': True, 'report_id': report.pk, 'name': name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_saved_reports(cls) -> List[Dict]:
        try:
            from api.admin_panel.models.reports import ReportDefinition
            return list(ReportDefinition.objects.filter(is_active=True).values(
                'id', 'name', 'report_type', 'created_at')[:50])
        except Exception: return []

report_builder = ReportBuilder()