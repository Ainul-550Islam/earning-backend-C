import json
from django.core.management.base import BaseCommand
from dr_integration.services import DRFailoverBridge, DRMonitoringBridge

class Command(BaseCommand):
    help = 'Run DR system health check'
    def add_arguments(self, parser):
        parser.add_argument('--output', choices=['text','json'], default='text')
        parser.add_argument('--fail-on-degraded', action='store_true')
    def handle(self, *args, **options):
        health = DRFailoverBridge().get_health_status()
        storage = DRMonitoringBridge().check_storage_health()
        overall = health.get('overall', 'unknown')
        if options['output'] == 'json':
            self.stdout.write(json.dumps({'health': health, 'storage': storage}, indent=2))
        else:
            self.stdout.write(f"\n=== DR HEALTH CHECK: {overall.upper()} ===")
            for name, comp in health.get('components', {}).items():
                s = str(comp.get('status','')).lower()
                icon = '✅' if s == 'healthy' else '⚠️' if s == 'degraded' else '❌'
                self.stdout.write(f"  {icon}  {name}: {s}")
        if overall == 'critical': raise SystemExit(2)
        if options.get('fail_on_degraded') and overall == 'degraded': raise SystemExit(1)
