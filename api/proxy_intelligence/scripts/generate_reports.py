#!/usr/bin/env python3
"""
Script: generate_reports.py
============================
Standalone script to generate proxy intelligence analytics reports.
Outputs JSON to stdout or to a file.

Usage:
    python scripts/generate_reports.py
    python scripts/generate_reports.py --type fraud --days 7
    python scripts/generate_reports.py --type all --output /tmp/pi_report.json
    python scripts/generate_reports.py --type geo --pretty
    python scripts/generate_reports.py --type daily --email

Requires Django to be configured.
"""
import os
import sys
import json
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

logging.basicConfig(level=logging.WARNING)

from django.utils import timezone

REPORT_TYPES = ['executive', 'fraud', 'geo', 'proxy_usage',
                'provider_risk', 'risk_trend', 'daily', 'all']


def generate(report_type: str, days: int, tenant=None) -> dict:
    """Generate a single report."""
    generators = {
        'executive': _executive,
        'fraud':     _fraud,
        'geo':       _geo,
        'proxy_usage': _proxy_usage,
        'provider_risk': _provider_risk,
        'risk_trend': _risk_trend,
        'daily':     _daily,
    }

    if report_type == 'all':
        result = {}
        for rtype in REPORT_TYPES:
            if rtype == 'all':
                continue
            try:
                result[rtype] = generators[rtype](days, tenant)
                print(f'  ✓ {rtype}', file=sys.stderr)
            except Exception as e:
                result[rtype] = {'error': str(e)}
                print(f'  ✗ {rtype}: {e}', file=sys.stderr)
        return result

    gen = generators.get(report_type)
    if not gen:
        return {'error': f'Unknown report type: {report_type}'}
    return gen(days, tenant)


def _executive(days, tenant):
    from api.proxy_intelligence.analytics_reporting.executive_dashboard import ExecutiveDashboard
    return ExecutiveDashboard(tenant=tenant, days=days).get_kpis()

def _fraud(days, tenant):
    from api.proxy_intelligence.analytics_reporting.fraud_attempt_analytics import FraudAttemptAnalytics
    return FraudAttemptAnalytics(tenant=tenant, days=days).full_report()

def _geo(days, tenant):
    from api.proxy_intelligence.analytics_reporting.geo_risk_heatmap import GeoRiskHeatmap
    return GeoRiskHeatmap(tenant=tenant).full_report(days=days)

def _proxy_usage(days, tenant):
    from api.proxy_intelligence.analytics_reporting.proxy_usage_analytics import ProxyUsageAnalytics
    a = ProxyUsageAnalytics(tenant=tenant, days=days)
    return {
        'summary': a.summary(),
        'daily_trend': a.daily_trend(),
        'top_vpn_providers': a.top_vpn_providers(),
    }

def _provider_risk(days, tenant):
    from api.proxy_intelligence.analytics_reporting.provider_risk_report import ProviderRiskReport
    return ProviderRiskReport(tenant=tenant, days=days).full_report()

def _risk_trend(days, tenant):
    from api.proxy_intelligence.analytics_reporting.risk_trend_analytics import RiskTrendAnalytics
    return RiskTrendAnalytics(tenant=tenant, days=days).full_report()

def _daily(days, tenant):
    from api.proxy_intelligence.analytics_reporting.daily_risk_summary import DailyRiskSummary
    return DailyRiskSummary().generate()


def main():
    parser = argparse.ArgumentParser(
        description='Proxy Intelligence Report Generator'
    )
    parser.add_argument('--type', choices=REPORT_TYPES, default='executive',
                        help='Report type (default: executive)')
    parser.add_argument('--days', type=int, default=30,
                        help='Period in days (default: 30)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file path (default: stdout)')
    parser.add_argument('--pretty', action='store_true',
                        help='Pretty-print JSON')
    parser.add_argument('--email', action='store_true',
                        help='Send daily summary via email')
    parser.add_argument('--tenant-id', type=int, default=None,
                        help='Filter by tenant ID')

    args = parser.parse_args()

    # ── Email mode ───────────────────────────────────────────────────────
    if args.email:
        from api.proxy_intelligence.analytics_reporting.daily_risk_summary import DailyRiskSummary
        from api.proxy_intelligence.config import PIConfig
        recipients = PIConfig.admin_emails()
        if not recipients:
            print('✗ No PI_ADMIN_EMAILS configured in settings.', file=sys.stderr)
            sys.exit(1)
        success = DailyRiskSummary().send_email(recipients)
        if success:
            print(f'✓ Email sent to: {recipients}')
        else:
            print('✗ Email send failed', file=sys.stderr)
            sys.exit(1)
        return

    # ── Tenant lookup ────────────────────────────────────────────────────
    tenant = None
    if args.tenant_id:
        try:
            from tenants.models import Tenant
            tenant = Tenant.objects.get(pk=args.tenant_id)
        except Exception as e:
            print(f'✗ Tenant not found: {e}', file=sys.stderr)
            sys.exit(1)

    print(f'[{timezone.now().strftime("%Y-%m-%d %H:%M")}] '
          f'Generating {args.type} report...', file=sys.stderr)

    report = generate(args.type, args.days, tenant)

    # Add metadata
    report['_meta'] = {
        'report_type':  args.type,
        'period_days':  args.days,
        'generated_at': timezone.now().isoformat(),
        'tenant_id':    args.tenant_id,
    }

    indent = 2 if args.pretty else None
    output = json.dumps(report, indent=indent, default=str)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f'✓ Report saved to: {args.output}', file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
