"""
tasks/management/commands/setup_tenant.py
Django management command to set up tenant configuration
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import logging

# Import tenant model safely
try:
    from tenants.models import Tenant
except ImportError:
    Tenant = None

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Set up tenant configuration for SaaS platform'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            required=True,
            help='Tenant ID'
        )
        parser.add_argument(
            '--tenant-name',
            type=str,
            required=True,
            help='Tenant name'
        )
        parser.add_argument(
            '--domain',
            type=str,
            required=True,
            help='Tenant domain'
        )
        parser.add_argument(
            '--subscription',
            type=str,
            default='basic',
            help='Subscription plan (basic/pro/enterprise)'
        )
        parser.add_argument(
            '--max-users',
            type=int,
            default=1000,
            help='Maximum users allowed'
        )
        parser.add_argument(
            '--features',
            nargs='+',
            default=['tasks', 'analytics', 'api'],
            help='Enabled features'
        )
    
    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        tenant_name = options['tenant_name']
        domain = options['domain']
        subscription = options['subscription']
        max_users = options['max_users']
        features = options['features']
        
        try:
            # Check if tenant model is available
            if Tenant is None:
                self.stdout.write(
                    self.style.ERROR("❌ Tenant model not available. Please ensure tenants app is properly configured.")
                )
                return
            
            # Check if tenant exists
            if Tenant.objects.filter(id=tenant_id).exists():
                self.stdout.write(
                    self.style.ERROR(f"Tenant {tenant_id} already exists")
                )
                return
            
            # Create tenant
            tenant = Tenant.objects.create(
                id=tenant_id,
                name=tenant_name,
                slug=tenant_name.lower().replace(' ', '-'),
                domain=domain,
                subscription_plan=subscription,
                max_users=max_users,
                is_active=True,
                settings={
                    'features': features,
                    'rate_limits': {
                        'api_requests_per_hour': 1000 if subscription == 'enterprise' else 500,
                        'file_upload_mb': 100 if subscription == 'enterprise' else 50,
                        'concurrent_tasks': 100 if subscription == 'enterprise' else 50,
                    },
                    'ui_config': {
                        'custom_branding': subscription == 'enterprise',
                        'custom_domain': subscription == 'enterprise',
                        'white_labeling': subscription == 'pro',
                    }
                }
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Tenant '{tenant_name}' ({tenant_id}) created successfully"
                )
            )
            
            # Create default admin user for tenant
            User = get_user_model()
            admin_user = User.objects.create_user(
                username=f"admin_{tenant_id}",
                email=f"admin@{domain}",
                is_staff=True,
                is_superuser=True,
                tenant_id=tenant_id
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Admin user created for tenant {tenant_id}"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error creating tenant: {e}")
            )
