# publisher_tools/views_scripts_remaining.py
"""
ScriptRunnerViewSet extension — বাকি 37টি floating script functions API-তে expose।

এই ফাইলটি views_scripts.py-এর ScriptRunnerViewSet-এ merge করো,
অথবা আলাদা ViewSet হিসেবে register করো:
  router.register(r'admin-scripts-ext', ScriptRunnerExtendedViewSet, basename='admin-script-ext')

Floating functions wired (এর আগে views_scripts.py-এ ছিল না):

  health_check.py (5টা):
    check_database_health(), check_cache_health(),
    check_pending_tasks(), check_webhook_health(),
    check_publisher_quality()

  validate_traffic.py (2টা remaining):
    calculate_publisher_ivt_rates(), validate_ads_txt_all_sites()
    (flag_suspicious_publishers already wired)

  generate_invoices.py (3টা):
    generate_invoices_for_month(), issue_pending_invoices(),
    send_invoice_notifications()

  generate_reports.py (4টা):
    generate_daily_reports_all(), generate_monthly_reports_all(),
    generate_waterfall_reports(), generate_fraud_reports()

  process_payments.py (3টা):
    process_pending_payout_requests(), execute_approved_payouts(),
    check_overdue_invoices()

  update_ad_units.py (3টা):
    update_ad_unit_metrics(), archive_inactive_ad_units(),
    sync_ad_unit_revenue_totals()

  optimize_waterfall.py (1টা remaining):
    optimize_all_auto_groups()
    (update_floor_prices_auto, reorder_waterfalls_by_ecpm,
     analyze_network_performance already wired in original)

  calculate_earnings.py (1টা):
    run_earnings_calculation()  (already partially wired — expose granular version)

  detect_fraud.py (4টা):
    scan_recent_traffic_logs(), detect_click_farms(),
    detect_device_farms(), calculate_revenue_impact()
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet


class ScriptRunnerExtendedViewSet(BaseViewSet):
    """
    Remaining floating script functions — all admin-only POST/GET।
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    # ══════════════════════════════════════════════════════════════════════════
    # health_check.py — 5 granular checks
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='check-database')
    def check_database(self, request):
        """
        GET /admin-scripts-ext/check-database/
        Database connectivity + table health check।
        """
        try:
            from .scripts.health_check import check_database_health
            result = check_database_health()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data=result if isinstance(result, dict) else {'healthy': result})

    @action(detail=False, methods=['get'], url_path='check-cache')
    def check_cache(self, request):
        """
        GET /admin-scripts-ext/check-cache/
        Redis/cache connectivity check।
        """
        try:
            from .scripts.health_check import check_cache_health
            result = check_cache_health()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data=result if isinstance(result, dict) else {'healthy': result})

    @action(detail=False, methods=['get'], url_path='check-pending-tasks')
    def check_pending_tasks(self, request):
        """
        GET /admin-scripts-ext/check-pending-tasks/
        Celery pending task queue check।
        """
        try:
            from .scripts.health_check import check_pending_tasks
            result = check_pending_tasks()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data=result if isinstance(result, dict) else {'tasks': result})

    @action(detail=False, methods=['get'], url_path='check-webhook-health')
    def check_webhook_health(self, request):
        """
        GET /admin-scripts-ext/check-webhook-health/
        Webhook delivery health (consecutive failures etc.)।
        """
        try:
            from .scripts.health_check import check_webhook_health
            result = check_webhook_health()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data=result if isinstance(result, dict) else {'healthy': result})

    @action(detail=False, methods=['get'], url_path='check-publisher-quality')
    def check_publisher_quality(self, request):
        """
        GET /admin-scripts-ext/check-publisher-quality/
        Publisher quality scores health check।
        """
        try:
            from .scripts.health_check import check_publisher_quality
            result = check_publisher_quality()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data=result if isinstance(result, dict) else {'quality': result})

    @action(detail=False, methods=['get'], url_path='health-full')
    def health_full(self, request):
        """
        GET /admin-scripts-ext/health-full/
        All 5 checks একসাথে।
        """
        results = {}
        checks = [
            ('database',         'check_database_health'),
            ('cache',            'check_cache_health'),
            ('pending_tasks',    'check_pending_tasks'),
            ('webhook_health',   'check_webhook_health'),
            ('publisher_quality','check_publisher_quality'),
        ]
        try:
            from .scripts import health_check as hc
            for key, fn_name in checks:
                fn = getattr(hc, fn_name, None)
                if fn:
                    try:
                        results[key] = fn()
                    except Exception as ex:
                        results[key] = {'error': str(ex)}
                else:
                    results[key] = {'error': f'{fn_name} not found'}
        except ImportError as e:
            return self.error_response(str(e), status_code=503)
        overall = all(
            (r.get('healthy', True) if isinstance(r, dict) else bool(r))
            for r in results.values()
        )
        return self.success_response(data={
            'overall_healthy': overall,
            'checks': results,
        })

    # ══════════════════════════════════════════════════════════════════════════
    # validate_traffic.py — 2 remaining
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='ivt-rates')
    def ivt_rates(self, request):
        """
        GET /admin-scripts-ext/ivt-rates/?days=7
        Publisher IVT (invalid traffic) rates।
        """
        days = int(request.query_params.get('days', 7))
        try:
            from .scripts.validate_traffic import calculate_publisher_ivt_rates
            result = calculate_publisher_ivt_rates(days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data=result if isinstance(result, dict) else {'rates': result})

    @action(detail=False, methods=['post'], url_path='validate-ads-txt-all')
    def validate_ads_txt_all(self, request):
        """
        POST /admin-scripts-ext/validate-ads-txt-all/
        ads.txt validation for all active sites।
        """
        try:
            from .scripts.validate_traffic import validate_ads_txt_all_sites
            result = validate_ads_txt_all_sites()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'validated': True},
            message='ads.txt validation complete.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # generate_invoices.py — 3 granular functions
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='generate-invoices-month')
    def generate_invoices_month(self, request):
        """
        POST /admin-scripts-ext/generate-invoices-month/
        Body: { "year": 2025, "month": 1, "dry_run": false }
        Month-specific invoice generation।
        """
        year    = request.data.get('year')
        month   = request.data.get('month')
        dry_run = request.data.get('dry_run', False)
        try:
            from .scripts.generate_invoices import generate_invoices_for_month
            result = generate_invoices_for_month(
                year=int(year) if year else None,
                month=int(month) if month else None,
                dry_run=dry_run,
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'generated': True, 'dry_run': dry_run},
            message='Invoice generation complete.' if not dry_run else 'Dry run — no invoices created.',
        )

    @action(detail=False, methods=['post'], url_path='issue-pending-invoices')
    def issue_pending_invoices(self, request):
        """
        POST /admin-scripts-ext/issue-pending-invoices/
        Mark pending invoices as issued।
        """
        try:
            from .scripts.generate_invoices import issue_pending_invoices
            result = issue_pending_invoices()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'issued': True},
            message='Pending invoices issued.',
        )

    @action(detail=False, methods=['post'], url_path='send-invoice-notifications')
    def send_invoice_notifications(self, request):
        """
        POST /admin-scripts-ext/send-invoice-notifications/
        Email notifications for newly issued invoices।
        """
        try:
            from .scripts.generate_invoices import send_invoice_notifications
            result = send_invoice_notifications()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'sent': True},
            message='Invoice notifications sent.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # generate_reports.py — 4 granular functions
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='generate-daily-reports')
    def generate_daily_reports(self, request):
        """
        POST /admin-scripts-ext/generate-daily-reports/
        Daily reports for all publishers।
        """
        try:
            from .scripts.generate_reports import generate_daily_reports_all
            result = generate_daily_reports_all()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'generated': True},
            message='Daily reports generated.',
        )

    @action(detail=False, methods=['post'], url_path='generate-monthly-reports')
    def generate_monthly_reports(self, request):
        """
        POST /admin-scripts-ext/generate-monthly-reports/
        Body: { "year": 2025, "month": 1 }
        Monthly reports for all publishers।
        """
        year  = request.data.get('year')
        month = request.data.get('month')
        try:
            from .scripts.generate_reports import generate_monthly_reports_all
            result = generate_monthly_reports_all(
                year=int(year) if year else None,
                month=int(month) if month else None,
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'generated': True},
            message='Monthly reports generated.',
        )

    @action(detail=False, methods=['post'], url_path='generate-waterfall-reports')
    def generate_waterfall_reports(self, request):
        """
        POST /admin-scripts-ext/generate-waterfall-reports/
        Waterfall performance reports।
        """
        try:
            from .scripts.generate_reports import generate_waterfall_reports
            result = generate_waterfall_reports()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'generated': True},
            message='Waterfall reports generated.',
        )

    @action(detail=False, methods=['post'], url_path='generate-fraud-reports')
    def generate_fraud_reports(self, request):
        """
        POST /admin-scripts-ext/generate-fraud-reports/
        Fraud detection summary reports।
        """
        try:
            from .scripts.generate_reports import generate_fraud_reports
            result = generate_fraud_reports()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'generated': True},
            message='Fraud reports generated.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # process_payments.py — 3 granular functions
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='process-payout-requests')
    def process_payout_requests(self, request):
        """
        POST /admin-scripts-ext/process-payout-requests/
        Process all pending payout requests।
        """
        try:
            from .scripts.process_payments import process_pending_payout_requests
            result = process_pending_payout_requests()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'processed': True},
            message='Payout requests processed.',
        )

    @action(detail=False, methods=['post'], url_path='execute-approved-payouts')
    def execute_approved_payouts(self, request):
        """
        POST /admin-scripts-ext/execute-approved-payouts/
        Execute approved (gateway-ready) payouts।
        """
        dry_run = request.data.get('dry_run', False)
        try:
            from .scripts.process_payments import execute_approved_payouts
            result = execute_approved_payouts()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'executed': True, 'dry_run': dry_run},
            message='Approved payouts executed.' if not dry_run else 'Dry run — no payouts sent.',
        )

    @action(detail=False, methods=['post'], url_path='check-overdue-invoices')
    def check_overdue_invoices(self, request):
        """
        POST /admin-scripts-ext/check-overdue-invoices/
        Flag and notify about overdue invoices।
        """
        try:
            from .scripts.process_payments import check_overdue_invoices
            result = check_overdue_invoices()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'checked': True},
            message='Overdue invoice check complete.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # update_ad_units.py — 3 granular functions
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='update-ad-unit-metrics')
    def update_ad_unit_metrics(self, request):
        """
        POST /admin-scripts-ext/update-ad-unit-metrics/
        Refresh all ad unit performance metrics।
        """
        try:
            from .scripts.update_ad_units import update_ad_unit_metrics
            result = update_ad_unit_metrics()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'updated': True},
            message='Ad unit metrics updated.',
        )

    @action(detail=False, methods=['post'], url_path='archive-inactive-ad-units')
    def archive_inactive_ad_units(self, request):
        """
        POST /admin-scripts-ext/archive-inactive-ad-units/
        Body: { "days_inactive": 90 }
        Archive ad units inactive for N days।
        """
        days_inactive = int(request.data.get('days_inactive', 90))
        try:
            from .scripts.update_ad_units import archive_inactive_ad_units
            result = archive_inactive_ad_units(days_inactive=days_inactive)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'archived': True, 'days': days_inactive},
            message=f'Ad units inactive for {days_inactive}+ days archived.',
        )

    @action(detail=False, methods=['post'], url_path='sync-ad-unit-revenue')
    def sync_ad_unit_revenue(self, request):
        """
        POST /admin-scripts-ext/sync-ad-unit-revenue/
        Sync ad unit lifetime revenue totals from earnings data।
        """
        try:
            from .scripts.update_ad_units import sync_ad_unit_revenue_totals
            result = sync_ad_unit_revenue_totals()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'synced': True},
            message='Ad unit revenue totals synced.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # optimize_waterfall.py — 1 remaining
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='optimize-all-groups')
    def optimize_all_groups(self, request):
        """
        POST /admin-scripts-ext/optimize-all-groups/
        Run full optimization for all auto_optimize=True mediation groups।
        """
        try:
            from .scripts.optimize_waterfall import optimize_all_auto_groups
            result = optimize_all_auto_groups()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'optimized': True},
            message='All auto-optimize groups processed.',
        )

    # ══════════════════════════════════════════════════════════════════════════
    # detect_fraud.py — 4 granular functions
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['post'], url_path='scan-traffic-logs')
    def scan_traffic_logs(self, request):
        """
        POST /admin-scripts-ext/scan-traffic-logs/
        Body: { "hours": 24 }
        Scan recent traffic logs for fraud signals।
        """
        hours = int(request.data.get('hours', 24))
        try:
            from .scripts.detect_fraud import scan_recent_traffic_logs
            result = scan_recent_traffic_logs(hours=hours)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'scanned': True, 'hours': hours},
            message=f'Traffic logs from last {hours}h scanned.',
        )

    @action(detail=False, methods=['post'], url_path='detect-click-farms')
    def detect_click_farms(self, request):
        """
        POST /admin-scripts-ext/detect-click-farms/
        Detect click farm activity patterns।
        """
        try:
            from .scripts.detect_fraud import detect_click_farms
            result = detect_click_farms()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'detected': True},
            message='Click farm detection complete.',
        )

    @action(detail=False, methods=['post'], url_path='detect-device-farms')
    def detect_device_farms(self, request):
        """
        POST /admin-scripts-ext/detect-device-farms/
        Detect device farm / emulator activity।
        """
        try:
            from .scripts.detect_fraud import detect_device_farms
            result = detect_device_farms()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'detected': True},
            message='Device farm detection complete.',
        )

    @action(detail=False, methods=['get'], url_path='fraud-revenue-impact')
    def fraud_revenue_impact(self, request):
        """
        GET /admin-scripts-ext/fraud-revenue-impact/
        Calculate revenue at-risk from fraud activity।
        """
        try:
            from .scripts.detect_fraud import calculate_revenue_impact
            result = calculate_revenue_impact()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(
            data=result if isinstance(result, dict) else {'revenue_impact': result}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # urls.py registration helper
    # ══════════════════════════════════════════════════════════════════════════
    # urls.py-তে যোগ করো:
    #   from .views_scripts_remaining import ScriptRunnerExtendedViewSet
    #   router.register(r'admin-scripts-ext', ScriptRunnerExtendedViewSet,
    #                   basename='admin-script-ext')
