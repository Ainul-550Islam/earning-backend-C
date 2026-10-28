"""
Management command: check_provider_health
Ping each active provider API and report status + latency.
"""
import time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Check health of all active offer providers'

    def add_arguments(self, parser):
        parser.add_argument('--provider', type=str, default=None)
        parser.add_argument('--timeout', type=int, default=10,
                            help='Request timeout in seconds')

    def handle(self, *args, **options):
        import requests
        from api.offerwall.models import OfferProvider

        timeout = options['timeout']
        ptype   = options.get('provider')

        qs = OfferProvider.objects.filter(status='active')
        if ptype:
            qs = qs.filter(provider_type=ptype)

        self.stdout.write(f'Checking {qs.count()} active providers…\n')

        for provider in qs:
            url = provider.api_base_url
            if not url:
                self.stdout.write(f'  ⚠️  {provider.name}: no api_base_url configured')
                continue

            start = time.time()
            try:
                resp = requests.get(url, timeout=timeout)
                ms   = int((time.time() - start) * 1000)
                icon = '✅' if resp.status_code < 500 else '⚠️ '
                self.stdout.write(
                    f'  {icon} {provider.name} ({provider.provider_type}): '
                    f'HTTP {resp.status_code} — {ms}ms')
            except requests.Timeout:
                self.stdout.write(self.style.WARNING(
                    f'  ⏱️  {provider.name}: TIMEOUT after {timeout}s'))
            except requests.ConnectionError as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ {provider.name}: CONNECTION ERROR — {exc}'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ {provider.name}: {exc}'))

        self.stdout.write(self.style.SUCCESS('\nHealth check complete'))
