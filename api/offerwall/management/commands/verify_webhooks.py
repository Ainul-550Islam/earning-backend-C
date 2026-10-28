"""
Management command: verify_webhooks
Test all registered webhook endpoints by sending dummy payloads.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify webhook endpoint health for all active providers'

    def add_arguments(self, parser):
        parser.add_argument('--provider', type=str, default=None,
                            help='Test only this provider type')

    def handle(self, *args, **options):
        import requests
        from django.conf import settings
        from api.offerwall.models import OfferProvider

        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        ptype    = options.get('provider')

        WEBHOOK_ENDPOINTS = {
            'tapjoy':   f'{base_url}/api/offerwall/webhooks/tapjoy/',
            'adgem':    f'{base_url}/api/offerwall/webhooks/adgem/',
            'adgate':   f'{base_url}/api/offerwall/webhooks/adgate/',
            'persona':  f'{base_url}/api/offerwall/webhooks/persona/',
            'offertoro':f'{base_url}/api/offerwall/webhooks/offertoro/',
            'monlix':   f'{base_url}/api/offerwall/webhooks/monlix/',
            'ogads':    f'{base_url}/api/offerwall/webhooks/ogads/',
            'fyber':    f'{base_url}/api/offerwall/webhooks/fyber/',
            'liftoff':  f'{base_url}/api/offerwall/webhooks/liftoff/',
            'applift':  f'{base_url}/api/offerwall/webhooks/applift/',
        }

        active = OfferProvider.objects.filter(status='active')
        if ptype:
            active = active.filter(provider_type=ptype)

        for provider in active:
            pt  = provider.provider_type
            url = WEBHOOK_ENDPOINTS.get(pt)
            if not url:
                self.stdout.write(f'  ⚠️  No webhook endpoint for {pt}')
                continue

            try:
                resp = requests.get(url, params={'test': '1'}, timeout=5)
                status = resp.status_code
                # 400 means we reached the endpoint (missing test params), that's OK
                ok = status in (200, 400)
                icon = '✅' if ok else '❌'
                self.stdout.write(f'  {icon} {pt}: HTTP {status} — {url}')
            except requests.ConnectionError:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ {pt}: CONNECTION ERROR — {url}'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ {pt}: {exc}'))

        self.stdout.write(self.style.SUCCESS('Webhook verification complete'))
