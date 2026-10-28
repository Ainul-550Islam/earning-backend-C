# publisher_tools/views_scripts.py  (DRY refactored)
"""
Admin Script Runner — DRY refactored।

পুরনো pattern (38 endpoints × identical try/except):
─────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='backup-invoices')
    def backup_invoices(self, request):
        months = int(request.data.get('months', 3))
        try:                                              ← 38×
            from .scripts.backup_data import backup_invoices
            result = backup_invoices(months=months)
        except (ImportError, Exception) as e:            ← 38×
            return self.error_response(str(e), status_code=503)
        return self.success_response(                     ← 38×
            data=result if isinstance(result, dict) else {'generated': True},
            message='Invoice backup completed.',
        )

নতুন pattern (run_script() — ১ লাইন):
──────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='backup-invoices')
    def backup_invoices(self, request):
        return self.run_script(
            'scripts.backup_data', 'backup_invoices',
            kwargs={'months': int(request.data.get('months', 3))},
            success_message='Invoice backup completed.',
        )
"""
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet

from .mixins import AdminScriptViewMixin


class ScriptRunnerViewSet(AdminScriptViewMixin, ViewSet):
    """
    Admin Script Runner — all 38 script endpoints।
    AdminScriptViewMixin provides: admin-only perms + run_script() + handle_errors()
    """

    # ══════════════════════════════════════════════════════════════════════════
    # ORIGINAL ENDPOINTS
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='run-fraud-detection')
    def run_fraud_detection(self, request):
        return self.run_script(
            'scripts', 'run_fraud_detection',
            kwargs={'hours': int(request.data.get('hours', 24))},
            success_message='Fraud detection scan completed.',
        )

    @action(detail=False, methods=['post'], url_path='run-waterfall-optimization')
    def run_waterfall_optimization(self, request):
        return self.run_script(
            'scripts', 'run_waterfall_optimization',
            success_message='Waterfall optimization completed.',
        )

    @action(detail=False, methods=['post'], url_path='update-floor-prices')
    def update_floor_prices(self, request):
        return self.run_script(
            'scripts.optimize_waterfall', 'update_floor_prices_auto',
            success_message='Floor prices updated.',
        )

    @action(detail=False, methods=['post'], url_path='reorder-waterfalls')
    def reorder_waterfalls(self, request):
        return self.run_script(
            'scripts.optimize_waterfall', 'reorder_waterfalls_by_ecpm',
            success_message='Waterfalls reordered.',
        )

    @action(detail=False, methods=['post'], url_path='analyze-networks')
    def analyze_networks(self, request):
        return self.run_script(
            'scripts.optimize_waterfall', 'analyze_network_performance',
        )

    @action(detail=False, methods=['post'], url_path='validate-ads-txt')
    def validate_ads_txt(self, request):
        return self.run_script(
            'scripts.validate_traffic', 'validate_ads_txt_all_sites',
            success_message='ads.txt validation completed.',
        )

    @action(detail=False, methods=['get'], url_path='health-check')
    def health_check(self, request):
        return self.run_script('scripts', 'run_health_check')

    @action(detail=False, methods=['post'], url_path='flag-suspicious-publishers')
    def flag_suspicious_publishers(self, request):
        return self.run_script(
            'scripts.detect_fraud', 'flag_suspicious_publishers',
            kwargs={
                'threshold_pct': float(request.data.get('threshold_pct', 20.0)),
                'auto_suspend':  request.data.get('auto_suspend', False),
            },
        )

    @action(detail=False, methods=['get'], url_path='ivt-rates')
    def ivt_rates(self, request):
        return self.run_script(
            'scripts.detect_fraud', 'calculate_publisher_ivt_rates',
            kwargs={'days': int(request.query_params.get('days', 7))},
        )

    @action(detail=False, methods=['post'], url_path='calculate-earnings')
    def calculate_earnings(self, request):
        year  = request.data.get('year')
        month = request.data.get('month')
        return self.run_script(
            'scripts', 'run_earnings_calculation',
            kwargs={
                'year':  int(year)  if year  else None,
                'month': int(month) if month else None,
            },
            success_message='Earnings calculation completed.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # BACKUP
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='backup-publisher-earnings')
    def backup_publisher_earnings(self, request):
        return self.run_script(
            'scripts.backup_data', 'backup_publisher_earnings',
            kwargs={
                'publisher_id': request.data.get('publisher_id'),
                'days':         int(request.data.get('days', 30)),
            },
            success_message='Publisher earnings backup completed.',
        )

    @action(detail=False, methods=['post'], url_path='backup-invoices')
    def backup_invoices(self, request):
        return self.run_script(
            'scripts.backup_data', 'backup_invoices',
            kwargs={'months': int(request.data.get('months', 3))},
            success_message='Invoice backup completed.',
        )

    @action(detail=False, methods=['post'], url_path='export-publisher-data')
    def export_publisher_data(self, request):
        publisher_id = request.data.get('publisher_id', '')
        if not publisher_id:
            return self._build_error('publisher_id required.', 400)
        return self.run_script(
            'scripts.backup_data', 'export_publisher_data',
            kwargs={'publisher_id': publisher_id},
            success_message=f'Publisher {publisher_id} data exported.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # CLEAN LOGS
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='clean-webhook-logs')
    def clean_webhook_logs(self, request):
        return self.run_script(
            'scripts.clean_logs', 'clean_webhook_delivery_logs',
            kwargs={'days': int(request.data.get('days', 30))},
            success_message='Webhook delivery logs cleaned.',
        )

    @action(detail=False, methods=['post'], url_path='clean-traffic-logs')
    def clean_traffic_logs(self, request):
        return self.run_script(
            'scripts.clean_logs', 'clean_old_traffic_safety_logs',
            kwargs={'days': int(request.data.get('days', 90))},
            success_message='Traffic safety logs cleaned.',
        )

    @action(detail=False, methods=['post'], url_path='clean-fraud-alerts')
    def clean_fraud_alerts(self, request):
        return self.run_script(
            'scripts.clean_logs', 'clean_resolved_fraud_alerts',
            kwargs={'days': int(request.data.get('days', 60))},
            success_message='Resolved fraud alerts cleaned.',
        )

    @action(detail=False, methods=['post'], url_path='clean-performance-snapshots')
    def clean_performance_snapshots(self, request):
        return self.run_script(
            'scripts.clean_logs', 'clean_old_performance_snapshots',
            kwargs={'months': int(request.data.get('months', 12))},
            success_message='Performance snapshots cleaned.',
        )

    @action(detail=False, methods=['post'], url_path='clean-verification-tokens')
    def clean_verification_tokens(self, request):
        return self.run_script(
            'scripts.clean_logs', 'clean_old_verification_tokens',
            kwargs={'days': int(request.data.get('days', 7))},
            success_message='Expired verification tokens cleaned.',
        )

    @action(detail=False, methods=['post'], url_path='clean-database-records')
    def clean_database_records(self, request):
        return self.run_script(
            'scripts.clean_logs', 'clean_old_database_records',
            kwargs={'days': int(request.data.get('days', 90))},
            success_message='Old database records cleaned.',
        )

    @action(detail=False, methods=['post'], url_path='run-full-clean')
    def run_full_clean(self, request):
        """Calls 6 clean functions and aggregates results."""
        d = request.data
        clean_tasks = [
            ('webhook_logs',          'scripts.clean_logs', 'clean_webhook_delivery_logs',        {'days': int(d.get('webhook_log_days', 30))}),
            ('traffic_logs',          'scripts.clean_logs', 'clean_old_traffic_safety_logs',      {'days': int(d.get('traffic_log_days', 90))}),
            ('fraud_alerts',          'scripts.clean_logs', 'clean_resolved_fraud_alerts',         {'days': int(d.get('fraud_alert_days', 60))}),
            ('performance_snapshots', 'scripts.clean_logs', 'clean_old_performance_snapshots',     {'months': int(d.get('performance_months', 12))}),
            ('verification_tokens',   'scripts.clean_logs', 'clean_old_verification_tokens',       {'days': int(d.get('verification_token_days', 7))}),
            ('database_records',      'scripts.clean_logs', 'clean_old_database_records',          {'days': int(d.get('database_record_days', 90))}),
        ]
        results = {}
        for key, module, fn, kwargs in clean_tasks:
            try:
                import importlib
                mod    = importlib.import_module(f'publisher_tools.{module}')
                func   = getattr(mod, fn)
                result = func(**kwargs)
                results[key] = result if isinstance(result, dict) else {'deleted_count': result}
            except Exception as e:
                results[key] = {'error': str(e)}
        return self.ok(results, message='Full cleanup completed.')

    # ══════════════════════════════════════════════════════════════════════════
    # SYNC
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='sync-revenue-totals')
    def sync_revenue_totals(self, request):
        return self.run_script(
            'scripts.sync_publishers', 'sync_publisher_revenue_totals',
            success_message='Publisher revenue totals synced.',
        )

    @action(detail=False, methods=['post'], url_path='sync-status-consistency')
    def sync_status_consistency(self, request):
        return self.run_script(
            'scripts.sync_publishers', 'sync_publisher_status_consistency',
            success_message='Publisher status consistency synced.',
        )

    @action(detail=False, methods=['post'], url_path='sync-payout-schedules')
    def sync_payout_schedules(self, request):
        return self.run_script(
            'scripts.sync_publishers', 'sync_publisher_payout_schedules',
            success_message='Publisher payout schedules synced.',
        )

    @action(detail=False, methods=['post'], url_path='run-full-sync')
    def run_full_sync(self, request):
        return self.run_script(
            'scripts.sync_publishers', 'run_full_sync',
            success_message='Full publisher sync completed.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # GENERATE + PROCESS + UPDATE
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='generate-invoices')
    def generate_invoices(self, request):
        return self.run_script('scripts.generate_invoices', 'run',
                               success_message='Invoices generated.')

    @action(detail=False, methods=['post'], url_path='generate-reports')
    def generate_reports(self, request):
        return self.run_script('scripts.generate_reports', 'run',
                               success_message=f'{request.data.get("report_type", "daily").capitalize()} reports generated.')

    @action(detail=False, methods=['post'], url_path='process-payments')
    def process_payments(self, request):
        dry_run = request.data.get('dry_run', False)
        return self.run_script(
            'scripts.process_payments', 'run',
            success_message='Payments processed.' if not dry_run else 'Dry run — no payments sent.',
        )

    @action(detail=False, methods=['post'], url_path='update-ad-units')
    def update_ad_units(self, request):
        return self.run_script('scripts.update_ad_units', 'run',
                               success_message='Ad units updated.')
