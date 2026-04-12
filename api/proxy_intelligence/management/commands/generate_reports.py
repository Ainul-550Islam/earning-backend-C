"""
Management Command: generate_reports
Usage: python manage.py generate_reports --type <type> [--days <n>] [--output <file>] [--email]
"""
import json
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate and output proxy intelligence analytics reports'

    REPORT_TYPES = [
        'executive', 'fraud', 'geo', 'proxy_usage',
        'provider_risk', 'risk_trend', 'daily', 'all',
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            choices=self.REPORT_TYPES,
            default='executive',
            help=(
                'Report type to generate:\n'
                '  executive    — High-level KPI summary (default)\n'
                '  fraud        — Fraud attempt analysis\n'
                '  geo          — Geographic risk heatmap\n'
                '  proxy_usage  — VPN/proxy/Tor usage trends\n'
                '  provider_risk — ISP/ASN risk breakdown\n'
                '  risk_trend   — Risk score trends over time\n'
                '  daily        — Daily risk digest\n'
                '  all          — All of the above'
            )
        )
        parser.add_argument(
            '--days', type=int, default=30,
            help='Number of days to include in the report (default: 30)'
        )
        parser.add_argument(
            '--output', type=str, default=None,
            help='Output JSON file path (default: print to stdout)'
        )
        parser.add_argument(
            '--email', action='store_true',
            help='Send the daily summary report via email to PI_ADMIN_EMAILS'
        )
        parser.add_argument(
            '--pretty', action='store_true',
            help='Pretty-print JSON output (indent=2)'
        )
        parser.add_argument(
            '--tenant-id', type=int, default=None,
            help='Generate report for a specific tenant ID only'
        )

    def handle(self, *args, **options):
        report_type = options['type']
        days        = options['days']
        output_file = options['output']
        send_email  = options['email']
        pretty      = options['pretty']
        tenant_id   = options['tenant_id']

        tenant = None
        if tenant_id:
            try:
                from tenants.models import Tenant
                tenant = Tenant.objects.get(pk=tenant_id)
                self.stdout.write(self.style.NOTICE(f'Tenant: {tenant}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Tenant not found: {e}'))
                return

        self.stdout.write(self.style.NOTICE(
            f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M")}] '
            f'Generating {report_type} report (last {days} days)...\n'
        ))

        # ── Email mode ───────────────────────────────────────────────────
        if send_email:
            self._send_email_report(days, tenant)
            return

        # ── Report generation ────────────────────────────────────────────
        if report_type == 'all':
            report = self._generate_all(days, tenant)
        else:
            report = self._generate_single(report_type, days, tenant)

        if report is None:
            self.stdout.write(self.style.ERROR('Report generation failed.'))
            return

        # Add metadata
        report['_meta'] = {
            'report_type': report_type,
            'period_days': days,
            'tenant_id':   tenant_id,
            'generated_at': timezone.now().isoformat(),
        }

        # Output
        indent  = 2 if pretty else None
        output  = json.dumps(report, indent=indent, default=str)

        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(output)
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Report saved to: {output_file}'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed to write file: {e}'))
        else:
            self.stdout.write(output)
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'✓ {report_type} report generated successfully.'
            ))

    def _generate_single(self, report_type: str, days: int, tenant) -> dict:
        """Generate a single report type."""
        generators = {
            'executive':     self._executive,
            'fraud':         self._fraud,
            'geo':           self._geo,
            'proxy_usage':   self._proxy_usage,
            'provider_risk': self._provider_risk,
            'risk_trend':    self._risk_trend,
            'daily':         self._daily,
        }
        gen = generators.get(report_type)
        if not gen:
            return {}
        try:
            return gen(days, tenant)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ {report_type} failed: {e}'))
            logger.exception(f'Report generation failed: {report_type}')
            return {'error': str(e)}

    def _generate_all(self, days: int, tenant) -> dict:
        """Generate all report types."""
        report = {}
        for report_type in self.REPORT_TYPES:
            if report_type == 'all':
                continue
            self.stdout.write(f'  Generating {report_type}...')
            try:
                result = self._generate_single(report_type, days, tenant)
                report[report_type] = result
                self.stdout.write(self.style.SUCCESS(f'    ✓ Done'))
            except Exception as e:
                report[report_type] = {'error': str(e)}
                self.stdout.write(self.style.ERROR(f'    ✗ Failed: {e}'))
        return report

    def _executive(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.executive_dashboard import ExecutiveDashboard
        return ExecutiveDashboard(tenant=tenant, days=days).get_kpis()

    def _fraud(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.fraud_attempt_analytics import FraudAttemptAnalytics
        return FraudAttemptAnalytics(tenant=tenant, days=days).full_report()

    def _geo(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.geo_risk_heatmap import GeoRiskHeatmap
        return GeoRiskHeatmap(tenant=tenant).full_report(days=days)

    def _proxy_usage(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.proxy_usage_analytics import ProxyUsageAnalytics
        analytics = ProxyUsageAnalytics(tenant=tenant, days=days)
        return {
            'summary':           analytics.summary(),
            'daily_trend':       analytics.daily_trend(),
            'top_vpn_providers': analytics.top_vpn_providers(),
        }

    def _provider_risk(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.provider_risk_report import ProviderRiskReport
        return ProviderRiskReport(tenant=tenant, days=days).full_report()

    def _risk_trend(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.risk_trend_analytics import RiskTrendAnalytics
        return RiskTrendAnalytics(tenant=tenant, days=days).full_report()

    def _daily(self, days: int, tenant) -> dict:
        from api.proxy_intelligence.analytics_reporting.daily_risk_summary import DailyRiskSummary
        return DailyRiskSummary().generate()

    def _send_email_report(self, days: int, tenant):
        """Send daily summary via email."""
        from api.proxy_intelligence.analytics_reporting.daily_risk_summary import DailyRiskSummary
        from api.proxy_intelligence.config import PIConfig

        recipients = PIConfig.admin_emails()
        if not recipients:
            self.stdout.write(self.style.WARNING(
                '⚠️  No admin emails configured. Set PI_ADMIN_EMAILS in settings.'
            ))
            return

        self.stdout.write(f'  Sending to: {recipients}')
        success = DailyRiskSummary().send_email(recipients)
        if success:
            self.stdout.write(self.style.SUCCESS(f'✓ Email sent to {len(recipients)} recipients'))
        else:
            self.stdout.write(self.style.ERROR('✗ Email send failed'))
