"""
Django Management Command: Check System Health
"""
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone
from datetime import timedelta
import logging

from api.alerts.models.core import AlertRule, AlertLog, SystemMetrics
from api.alerts.models.channel import AlertChannel, ChannelHealthLog
from api.alerts.models.incident import Incident

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check system health and generate health report'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='Check health for last N hours (default: 24)')
        parser.add_argument('--verbose', action='store_true', help='Show detailed health information')
        parser.add_argument('--component', type=str, choices=['alerts', 'channels', 'incidents', 'all'],
                             default='all', help='Which component(s) to check (default: all)')
        parser.add_argument('--format', type=str, choices=['text', 'json', 'csv'], default='text',
                             help='Output format (default: text)')
        parser.add_argument('--warning-threshold', type=float, default=70.0,
                             help='Warning health threshold, percent (default: 70)')
        parser.add_argument('--critical-threshold', type=float, default=50.0,
                             help='Critical health threshold, percent (default: 50)')
        parser.add_argument('--save', action='store_true', help='Save health check results to database')

    def handle(self, *args, **options):
        hours = options['hours']
        verbose = options['verbose']
        component = options['component']
        output_format = options['format']
        warning_threshold = options['warning_threshold']
        critical_threshold = options['critical_threshold']
        save_results = options['save']

        self.stdout.write(self.style.SUCCESS('Checking system health'))
        self.stdout.write(f'Component: {component}')
        self.stdout.write(f'Time period: {hours} hours')
        self.stdout.write(f'Warning threshold: {warning_threshold}')
        self.stdout.write(f'Critical threshold: {critical_threshold}')
        if verbose:
            self.stdout.write('Verbose: Yes')
        self.stdout.write(f'Format: {output_format}')

        check_alerts = component in ('alerts', 'all')
        check_channels = component in ('channels', 'all')
        check_incidents = component in ('incidents', 'all')

        cutoff_time = timezone.now() - timedelta(hours=hours)

        no_data = (
            not AlertRule.objects.exists()
            and not SystemMetrics.objects.exists()
            and not AlertChannel.objects.exists()
            and not Incident.objects.exists()
        )
        if no_data:
            self.stdout.write(self.style.WARNING('No data available'))
            self.stdout.write('Health Status: Unknown')
            return

        health_data = {'timestamp': timezone.now(), 'period_hours': hours}

        if check_alerts:
            health_data['alerts'] = self.check_alert_system_health(cutoff_time)
        if check_channels:
            health_data['channels'] = self._check_channels_health(cutoff_time)
        if check_incidents:
            health_data['incidents'] = self._check_incidents_health(cutoff_time)

        health_data['overall_health'] = self._calculate_overall_health(health_data)

        if output_format == 'json':
            self._output_json(health_data)
        elif output_format == 'csv':
            self._output_csv(health_data)
        else:
            self._output_text(health_data, verbose, warning_threshold, critical_threshold)

        if save_results:
            self._save_results(health_data, warning_threshold)

        overall_pct = health_data['overall_health']
        if overall_pct >= warning_threshold:
            self.stdout.write(self.style.SUCCESS(f'Overall Health: {overall_pct:.1f}% (GOOD)'))
        elif overall_pct >= critical_threshold:
            self.stdout.write(self.style.WARNING(f'Overall Health: {overall_pct:.1f}% (WARNING)'))
        else:
            self.stdout.write(self.style.ERROR(f'Overall Health: {overall_pct:.1f}% (CRITICAL)'))

    def check_alert_system_health(self, cutoff_time):
        total_rules = AlertRule.objects.count()
        active_rules = AlertRule.objects.filter(is_active=True).count()

        total_alerts = AlertLog.objects.filter(triggered_at__gte=cutoff_time).count()
        resolved_alerts = AlertLog.objects.filter(triggered_at__gte=cutoff_time, is_resolved=True).count()

        active_pct = (active_rules / total_rules * 100) if total_rules > 0 else 100.0
        resolution_pct = (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 100.0

        return {
            'rules': {'total': total_rules, 'active': active_rules, 'active_percentage': active_pct},
            'logs': {'total': total_alerts, 'resolved': resolved_alerts, 'resolution_rate': resolution_pct},
            'health_score': (active_pct + resolution_pct) / 2,
        }

    def _check_channels_health(self, cutoff_time):
        total_channels = AlertChannel.objects.count()
        healthy_channels = AlertChannel.objects.filter(status='active').count()
        health_pct = (healthy_channels / total_channels * 100) if total_channels > 0 else 100.0

        recent_checks = ChannelHealthLog.objects.filter(checked_at__gte=cutoff_time).count()

        return {
            'status': {'total': total_channels, 'healthy': healthy_channels, 'health_percentage': health_pct},
            'health_checks': {'total': recent_checks},
            'health_score': health_pct,
        }

    def _check_incidents_health(self, cutoff_time):
        total_incidents = Incident.objects.filter(detected_at__gte=cutoff_time).count()
        resolved_incidents = Incident.objects.filter(detected_at__gte=cutoff_time, status='resolved').count()
        resolution_pct = (resolved_incidents / total_incidents * 100) if total_incidents > 0 else 100.0

        resolved_qs = Incident.objects.filter(
            detected_at__gte=cutoff_time, status='resolved', resolved_at__isnull=False
        )
        if resolved_qs.exists():
            avg_resolution_time = sum(
                (i.resolved_at - i.detected_at).total_seconds() / 60 for i in resolved_qs
            ) / resolved_qs.count()
        else:
            avg_resolution_time = 0

        return {
            'status': {'total': total_incidents, 'resolved': resolved_incidents, 'resolution_rate': resolution_pct},
            'avg_resolution_time': avg_resolution_time,
            'health_score': resolution_pct,
        }

    def _calculate_overall_health(self, health_data):
        scores = [health_data[k]['health_score'] for k in ('alerts', 'channels', 'incidents') if k in health_data]
        return sum(scores) / len(scores) if scores else 0.0

    def _output_text(self, health_data, verbose, warning_threshold, critical_threshold):
        if 'alerts' in health_data:
            alerts = health_data['alerts']
            self.stdout.write(self.style.SUCCESS('Alert System Health:'))
            self.stdout.write(f'  Rules: {alerts["rules"]["active"]}/{alerts["rules"]["total"]} active')
            self.stdout.write(f'  Resolution Rate: {alerts["logs"]["resolution_rate"]:.1f}%')
            self.stdout.write(f'  Health Score: {alerts["health_score"]:.1f}%')
            if verbose:
                self.stdout.write('  Detailed metrics:')
                self.stdout.write(f'    {alerts}')

        if 'channels' in health_data:
            channels = health_data['channels']
            self.stdout.write(self.style.SUCCESS('Channel Health:'))
            self.stdout.write(f'  Channels: {channels["status"]["healthy"]}/{channels["status"]["total"]} healthy')
            self.stdout.write(f'  Health Score: {channels["health_score"]:.1f}%')
            if verbose:
                self.stdout.write('  Detailed metrics:')
                self.stdout.write(f'    {channels}')

        if 'incidents' in health_data:
            incidents = health_data['incidents']
            self.stdout.write(self.style.SUCCESS('Incident System Health:'))
            self.stdout.write(f'  Resolution Rate: {incidents["status"]["resolution_rate"]:.1f}%')
            self.stdout.write(f'  Avg Resolution Time: {incidents["avg_resolution_time"]:.1f} minutes')
            self.stdout.write(f'  Health Score: {incidents["health_score"]:.1f}%')
            if verbose:
                self.stdout.write('  Detailed metrics:')
                self.stdout.write(f'    {incidents}')

    def _output_json(self, health_data):
        import json
        self.stdout.write(json.dumps(health_data, indent=2, default=str))

    def _output_csv(self, health_data):
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Timestamp', health_data['timestamp']])
        writer.writerow(['Overall Health', f"{health_data['overall_health']:.1f}%"])

        for key, label in (('alerts', 'Alerts'), ('channels', 'Channels'), ('incidents', 'Incidents')):
            if key in health_data:
                writer.writerow([f'{label} Health Score', f"{health_data[key]['health_score']:.1f}%"])

        self.stdout.write(output.getvalue())

    def _save_results(self, health_data, warning_threshold):
        try:
            from api.alerts.models.core import SystemHealthCheck

            overall = health_data['overall_health']
            health_check = SystemHealthCheck.objects.create(
                check_name=f'Management Command Health Check {timezone.now().isoformat()}',
                check_type='api',
                status='healthy' if overall >= warning_threshold else 'warning',
                response_time_ms=0,
                status_message=f'Overall health: {overall:.1f}%',
                last_checked=timezone.now(),
            )
            self.stdout.write(f'Save results: Yes')
            self.stdout.write(f'Results saved to: SystemHealthCheck #{health_check.id}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to save health check results: {str(e)}'))
