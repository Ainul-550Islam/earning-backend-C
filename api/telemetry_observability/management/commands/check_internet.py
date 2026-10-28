"""
Management command: check_internet

Run the internet connectivity check on demand and print a detailed report.
Useful for debugging connectivity in production containers, CI environments,
or when diagnosing why the Celery task is firing alerts.

Usage
─────
  python manage.py check_internet
  python manage.py check_internet --format json
  python manage.py check_internet --probe tcp
  python manage.py check_internet --probe http --timeout 10
  python manage.py check_internet --threshold 0.8
  python manage.py check_internet --no-save

Exit codes
──────────
  0  — internet reachable (all or enough probes passed)
  1  — internet unreachable or degraded (below pass threshold)
  2  — command error (bad arguments, import failure, etc.)
"""
import json
import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = (
        'Run the internet connectivity check immediately and print a report. '
        'Exits 0 if reachable, 1 if not.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--probe',
            choices=['tcp', 'dns', 'http', 'all'],
            default='all',
            help='Which probe type(s) to run (default: all).',
        )
        parser.add_argument(
            '--timeout',
            type=float,
            default=None,
            help='Per-probe timeout in seconds. Overrides INTERNET_CHECK_TIMEOUT setting.',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=None,
            help=(
                'Fraction of probes that must pass to be considered reachable (0.0–1.0). '
                'Overrides INTERNET_CHECK_PASS_THRESHOLD setting.'
            ),
        )
        parser.add_argument(
            '--format',
            choices=['table', 'json'],
            default='table',
            dest='output_format',
            help='Output format (default: table).',
        )
        parser.add_argument(
            '--no-save',
            action='store_true',
            help='Do not write results to HealthStatus or emit MetricEvent records.',
        )

    def handle(self, *args, **options):
        try:
            from api.telemetry_observability.services.internet_check_service import (
                InternetCheckService,
            )
        except ImportError as exc:
            raise CommandError(f'Could not import InternetCheckService: {exc}') from exc

        # ── Build filtered target list ─────────────────────────────────────────
        probe_filter = options['probe']
        timeout      = options['timeout']
        threshold    = options['threshold']

        base_targets = getattr(settings, 'INTERNET_CHECK_TARGETS', [])
        if probe_filter != 'all':
            targets = [t for t in base_targets if t.get('type') == probe_filter]
            if not targets:
                raise CommandError(
                    f'No configured targets with probe type "{probe_filter}". '
                    f'Check INTERNET_CHECK_TARGETS in settings.'
                )
        else:
            targets = base_targets

        # Apply timeout override
        if timeout is not None:
            targets = [{**t, 'timeout': timeout} for t in targets]

        # ── Run the check ─────────────────────────────────────────────────────
        svc = InternetCheckService(
            targets=targets,
            pass_threshold=threshold,   # None → uses setting default
        )

        self.stdout.write('Running internet connectivity check…\n')
        result = svc.check()

        # ── Output ────────────────────────────────────────────────────────────
        if options['output_format'] == 'json':
            self._print_json(result)
        else:
            self._print_table(result)

        # ── Persist (unless --no-save) ────────────────────────────────────────
        if not options['no_save']:
            self._save(result)

        # ── Exit code ─────────────────────────────────────────────────────────
        sys.exit(0 if result.reachable else 1)

    # ── Output helpers ────────────────────────────────────────────────────────

    def _print_table(self, result):
        w = self.stdout.write
        style_ok  = self.style.SUCCESS
        style_err = self.style.ERROR
        style_dim = self.style.WARNING

        # Header
        w('\n' + '─' * 65 + '\n')
        w(f'  Internet Connectivity Check — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        w('─' * 65 + '\n')

        # Probes table
        w(f'  {"TYPE":<6}  {"TARGET":<48}  {"RESULT":<12}  {"LATENCY":>10}\n')
        w(f'  {"────":<6}  {"──────":<48}  {"──────":<12}  {"───────":>10}\n')
        for p in result.probes:
            status  = style_ok('PASS') if p.reachable else style_err('FAIL')
            latency = f'{p.latency_ms:.1f} ms' if p.latency_ms is not None else '—'
            target  = p.target[:48]
            w(f'  {p.probe_type.upper():<6}  {target:<48}  {status:<12}  {latency:>10}\n')
            if p.error:
                w(style_dim(f'          ↳ {p.error}\n'))

        # Summary
        w('─' * 65 + '\n')
        passed = len(result.probes) - result.error_count
        status_label = (
            style_ok('REACHABLE')
            if result.reachable
            else style_err('UNREACHABLE')
        )
        w(f'\n  Status       : {status_label}\n')
        w(f'  Health score : {result.health_score}/100\n')
        w(f'  Probes       : {passed}/{len(result.probes)} passed\n')
        if result.avg_latency_ms is not None:
            w(f'  Avg latency  : {result.avg_latency_ms:.1f} ms\n')
        else:
            w(f'  Avg latency  : — (all probes failed)\n')
        w('\n')

    def _print_json(self, result):
        payload = {
            'reachable':      result.reachable,
            'health_score':   result.health_score,
            'avg_latency_ms': (
                round(result.avg_latency_ms, 2) if result.avg_latency_ms else None
            ),
            'probes_passed':  len(result.probes) - result.error_count,
            'probes_total':   len(result.probes),
            'checked_at':     result.checked_at,
            'probes': [
                {
                    'type':        p.probe_type,
                    'target':      p.target,
                    'reachable':   p.reachable,
                    'latency_ms':  round(p.latency_ms, 2) if p.latency_ms else None,
                    'http_status': p.http_status,
                    'error':       p.error,
                }
                for p in result.probes
            ],
        }
        self.stdout.write(json.dumps(payload, indent=2) + '\n')

    # ── Persistence helper ────────────────────────────────────────────────────

    def _save(self, result):
        """
        Write HealthStatus + MetricEvent records, exactly as the Celery task does.
        Allows ops to trigger a manual check and have it reflected in dashboards.
        """
        try:
            from api.telemetry_observability.models.health_status import HealthStatus
            from api.telemetry_observability.models.metric_event  import MetricEvent

            status_value = (
                'healthy'   if result.health_score >= 80
                else 'degraded' if result.health_score >= 40
                else 'unhealthy'
            )
            env = getattr(settings, 'INTERNET_CHECK_ENVIRONMENT', 'production')

            HealthStatus.objects.update_or_create(
                service_name='internet',
                component_name='connectivity',
                defaults={
                    'status':           status_value,
                    'health_score':     result.health_score,
                    'response_time_ms': result.avg_latency_ms,
                    'error_rate': (
                        result.error_count / len(result.probes) * 100
                        if result.probes else 0.0
                    ),
                    'metadata':    result.as_metadata(),
                    'environment': env,
                },
            )

            MetricEvent.objects.create(
                name='internet.connectivity.health_score',
                metric_type='gauge',
                value=float(result.health_score),
                unit='score',
                source='management-command',
                service='internet',
                environment=env,
            )
            if result.avg_latency_ms is not None:
                MetricEvent.objects.create(
                    name='internet.connectivity.latency_ms',
                    metric_type='gauge',
                    value=round(result.avg_latency_ms, 2),
                    unit='ms',
                    source='management-command',
                    service='internet',
                    environment=env,
                )

            self.stdout.write(
                self.style.SUCCESS('Results saved to HealthStatus and MetricEvent.\n')
            )
        except Exception as exc:
            self.stderr.write(
                self.style.WARNING(f'Could not save results: {exc}\n')
            )
