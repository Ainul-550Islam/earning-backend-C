"""Management Command: pi_health_check — validates the proxy intelligence module."""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Run health checks on the proxy intelligence module'

    def handle(self, *args, **options):
        checks = []

        # 1. DB connectivity
        try:
            from api.proxy_intelligence.models import IPIntelligence
            count = IPIntelligence.objects.count()
            checks.append(('DB: IPIntelligence', True, f'{count} records'))
        except Exception as e:
            checks.append(('DB: IPIntelligence', False, str(e)))

        # 2. Cache
        try:
            from django.core.cache import cache
            cache.set('pi:health', 'ok', 10)
            val = cache.get('pi:health')
            checks.append(('Cache (Redis)', val == 'ok', 'Connected' if val == 'ok' else 'Failed'))
        except Exception as e:
            checks.append(('Cache (Redis)', False, str(e)))

        # 3. Tor list
        try:
            from api.proxy_intelligence.models import TorExitNode
            tor_count = TorExitNode.objects.filter(is_active=True).count()
            checks.append(('Tor Exit Nodes', tor_count > 0, f'{tor_count} active nodes'))
        except Exception as e:
            checks.append(('Tor Exit Nodes', False, str(e)))

        # 4. Integration credentials
        try:
            from api.proxy_intelligence.models import IntegrationCredential
            cred_count = IntegrationCredential.objects.filter(is_active=True).count()
            checks.append(('Integration Credentials', True, f'{cred_count} configured'))
        except Exception as e:
            checks.append(('Integration Credentials', False, str(e)))

        # 5. ML Models
        try:
            from api.proxy_intelligence.models import MLModelMetadata
            active = MLModelMetadata.objects.filter(is_active=True).count()
            checks.append(('ML Models', True, f'{active} active models'))
        except Exception as e:
            checks.append(('ML Models', False, str(e)))

        self.stdout.write('\n=== Proxy Intelligence Health Check ===\n')
        all_ok = True
        for name, ok, detail in checks:
            style = self.style.SUCCESS if ok else self.style.ERROR
            symbol = '✓' if ok else '✗'
            self.stdout.write(style(f'  {symbol} {name}: {detail}'))
            if not ok: all_ok = False

        self.stdout.write('')
        if all_ok:
            self.stdout.write(self.style.SUCCESS('All checks passed.'))
        else:
            self.stdout.write(self.style.WARNING('Some checks failed. Review above.'))
