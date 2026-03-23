from django.core.management.base import BaseCommand
from api.tenants.models import Tenant
import os

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'earning-backend-c-production.up.railway.app')
        t, created = Tenant.objects.get_or_create(
            domain=domain,
            defaults={
                'name': 'Production Client',
                'slug': 'production-client',
                'plan': 'basic',
                'max_users': 100,
                'is_active': True
            }
        )
        self.stdout.write(f'Tenant: {t.name}')
        self.stdout.write(f'API Key: {t.api_key}')
        self.stdout.write(f'Created: {created}')
