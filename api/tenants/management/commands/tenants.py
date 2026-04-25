"""
Tenant Management Commands

This module contains Django management commands for tenant operations
including creation, listing, suspension, and deletion.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

from ...models import Tenant
from ...services import TenantService, TenantSuspensionService

User = get_user_model()


class Command(BaseCommand):
    """Base command with common tenant utilities."""
    
    def get_tenant_by_id_or_name(self, identifier):
        """Get tenant by ID or name."""
        try:
            # Try by ID first
            return Tenant.objects.get(id=identifier)
        except (Tenant.DoesNotExist, ValueError):
            try:
                # Try by name
                return Tenant.objects.get(name=identifier)
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant '{identifier}' not found")
    
    def get_user_by_email(self, email):
        """Get user by email."""
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"User with email '{email}' not found")


class CreateTenantCommand(Command):
    """
    Create a new tenant.
    
    Usage:
        python manage.py create_tenant <name> <owner_email> [--plan=<plan_id>] [--tier=<tier>]
    """
    
    help = "Create a new tenant"
    
    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Tenant name')
        parser.add_argument('owner_email', type=str, help='Owner email address')
        parser.add_argument('--plan', type=str, help='Plan ID or name')
        parser.add_argument('--tier', type=str, choices=['basic', 'professional', 'enterprise'], default='basic')
        parser.add_argument('--trial-days', type=int, default=30, help='Trial period in days')
        parser.add_argument('--contact-email', type=str, help='Contact email')
        parser.add_argument('--contact-phone', type=str, help='Contact phone')
        parser.add_argument('--timezone', type=str, default='UTC', help='Timezone')
    
    def handle(self, *args, **options):
        name = options['name']
        owner_email = options['owner_email']
        tier = options['tier']
        trial_days = options['trial_days']
        
        self.stdout.write(f"Creating tenant: {name}")
        
        # Get owner
        owner = self.get_user_by_email(owner_email)
        
        # Get plan
        plan_id = options.get('plan')
        if plan_id:
            try:
                from ...models.plan import Plan
                plan = Plan.objects.get(id=plan_id)
            except (Plan.DoesNotExist, ValueError):
                try:
                    plan = Plan.objects.get(name=plan_id)
                except Plan.DoesNotExist:
                    raise CommandError(f"Plan '{plan_id}' not found")
        else:
            # Get default plan for tier
            from ...models.plan import Plan
            plan = Plan.objects.filter(plan_type=tier, is_active=True).first()
            if not plan:
                raise CommandError(f"No active plan found for tier '{tier}'")
        
        # Create tenant
        tenant = TenantService.create_tenant(
            name=name,
            owner=owner,
            plan=plan,
            trial_days=trial_days,
            contact_email=options.get('contact_email', owner_email),
            contact_phone=options.get('contact_phone'),
            timezone=options['timezone'],
            tier=tier,
        )
        
        self.stdout.write(
            self.style.SUCCESS(f"Tenant '{name}' created successfully (ID: {tenant.id})")
        )
        
        # Display tenant info
        self.stdout.write(f"  Plan: {plan.name}")
        self.stdout.write(f"  Trial ends: {tenant.trial_ends_at}")
        self.stdout.write(f"  Owner: {owner.get_full_name() or owner.username}")


class ListTenantsCommand(Command):
    """
    List all tenants with optional filtering.
    
    Usage:
        python manage.py list_tenants [--status=<status>] [--tier=<tier>] [--format=<format>]
    """
    
    help = "List all tenants"
    
    def add_arguments(self, parser):
        parser.add_argument('--status', type=str, help='Filter by status')
        parser.add_argument('--tier', type=str, help='Filter by tier')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
        parser.add_argument('--limit', type=int, help='Limit number of results')
    
    def handle(self, *args, **options):
        queryset = Tenant.objects.filter(is_deleted=False)
        
        # Apply filters
        if options['status']:
            queryset = queryset.filter(status=options['status'])
        
        if options['tier']:
            queryset = queryset.filter(tier=options['tier'])
        
        # Apply limit
        if options['limit']:
            queryset = queryset[:options['limit']]
        
        if options['format'] == 'json':
            self._output_json(queryset)
        else:
            self._output_table(queryset)
    
    def _output_table(self, queryset):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("Tenants:"))
        self.stdout.write("-" * 80)
        self.stdout.write(f"{'ID':<6} {'Name':<20} {'Status':<10} {'Tier':<12} {'Plan':<15} {'Owner':<15}")
        self.stdout.write("-" * 80)
        
        for tenant in queryset.select_related('plan', 'owner'):
            self.stdout.write(
                f"{str(tenant.id):<6} "
                f"{tenant.name[:19]:<20} "
                f"{tenant.status:<10} "
                f"{tenant.tier:<12} "
                f"{(tenant.plan.name if tenant.plan else 'None')[:14]:<15} "
                f"{(tenant.owner.get_full_name() or tenant.owner.username)[:14]:<15}"
            )
    
    def _output_json(self, queryset):
        """Output in JSON format."""
        tenants = []
        for tenant in queryset.select_related('plan', 'owner'):
            tenants.append({
                'id': str(tenant.id),
                'name': tenant.name,
                'slug': tenant.slug,
                'status': tenant.status,
                'tier': tenant.tier,
                'plan': tenant.plan.name if tenant.plan else None,
                'owner': tenant.owner.get_full_name() or tenant.owner.username,
                'created_at': tenant.created_at.isoformat(),
                'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            })
        
        self.stdout.write(json.dumps(tenants, indent=2))


class SuspendTenantCommand(Command):
    """
    Suspend a tenant.
    
    Usage:
        python manage.py suspend_tenant <tenant_id_or_name> [--reason=<reason>]
    """
    
    help = "Suspend a tenant"
    
    def add_arguments(self, parser):
        parser.add_argument('tenant', type=str, help='Tenant ID or name')
        parser.add_argument('--reason', type=str, default='Admin suspension', help='Suspension reason')
    
    def handle(self, *args, **options):
        tenant = self.get_tenant_by_id_or_name(options['tenant'])
        reason = options['reason']
        
        self.stdout.write(f"Suspending tenant: {tenant.name}")
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()
        
        TenantSuspensionService.suspend_tenant(tenant, reason, admin_user)
        
        self.stdout.write(
            self.style.SUCCESS(f"Tenant '{tenant.name}' suspended successfully")
        )


class UnsuspendTenantCommand(Command):
    """
    Unsuspend a tenant.
    
    Usage:
        python manage.py unsuspend_tenant <tenant_id_or_name>
    """
    
    help = "Unsuspend a tenant"
    
    def add_arguments(self, parser):
        parser.add_argument('tenant', type=str, help='Tenant ID or name')
    
    def handle(self, *args, **options):
        tenant = self.get_tenant_by_id_or_name(options['tenant'])
        
        self.stdout.write(f"Unsuspending tenant: {tenant.name}")
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()
        
        TenantSuspensionService.unsuspend_tenant(tenant, admin_user)
        
        self.stdout.write(
            self.style.SUCCESS(f"Tenant '{tenant.name}' unsuspended successfully")
        )


class DeleteTenantCommand(Command):
    """
    Soft delete a tenant.
    
    Usage:
        python manage.py delete_tenant <tenant_id_or_name> [--force]
    """
    
    help = "Soft delete a tenant"
    
    def add_arguments(self, parser):
        parser.add_argument('tenant', type=str, help='Tenant ID or name')
        parser.add_argument('--force', action='store_true', help='Force deletion without confirmation')
    
    def handle(self, *args, **options):
        tenant = self.get_tenant_by_id_or_name(options['tenant'])
        
        if not options['force']:
            confirm = input(f"Are you sure you want to delete tenant '{tenant.name}'? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("Deletion cancelled.")
                return
        
        self.stdout.write(f"Deleting tenant: {tenant.name}")
        
        # Soft delete
        tenant.is_deleted = True
        tenant.deleted_at = timezone.now()
        tenant.save()
        
        self.stdout.write(
            self.style.WARNING(f"Tenant '{tenant.name}' deleted (soft delete)")
        )


class TenantInfoCommand(Command):
    """
    Show detailed information about a tenant.
    
    Usage:
        python manage.py tenant_info <tenant_id_or_name>
    """
    
    help = "Show detailed tenant information"
    
    def add_arguments(self, parser):
        parser.add_argument('tenant', type=str, help='Tenant ID or name')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        tenant = self.get_tenant_by_id_or_name(options['tenant'])
        
        if options['format'] == 'json':
            self._output_json(tenant)
        else:
            self._output_table(tenant)
    
    def _output_table(self, tenant):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS(f"Tenant Information: {tenant.name}"))
        self.stdout.write("=" * 50)
        
        # Basic info
        self.stdout.write(f"ID: {tenant.id}")
        self.stdout.write(f"Slug: {tenant.slug}")
        self.stdout.write(f"Status: {tenant.status}")
        self.stdout.write(f"Tier: {tenant.tier}")
        self.stdout.write(f"Is Suspended: {tenant.is_suspended}")
        self.stdout.write(f"Created: {tenant.created_at}")
        self.stdout.write(f"Last Activity: {tenant.last_activity_at}")
        
        # Trial info
        self.stdout.write(f"\nTrial Information:")
        self.stdout.write(f"Trial Ends: {tenant.trial_ends_at}")
        self.stdout.write(f"Days Until Expiry: {tenant.days_until_trial_expiry}")
        self.stdout.write(f"Is Trial Expired: {tenant.is_trial_expired}")
        
        # Plan info
        if tenant.plan:
            self.stdout.write(f"\nPlan Information:")
            self.stdout.write(f"Plan: {tenant.plan.name}")
            self.stdout.write(f"Plan Type: {tenant.plan.plan_type}")
            self.stdout.write(f"Monthly Price: ${tenant.plan.price_monthly}")
        
        # Owner info
        if tenant.owner:
            self.stdout.write(f"\nOwner Information:")
            self.stdout.write(f"Owner: {tenant.owner.get_full_name() or tenant.owner.username}")
            self.stdout.write(f"Email: {tenant.owner.email}")
        
        # Contact info
        self.stdout.write(f"\nContact Information:")
        self.stdout.write(f"Contact Email: {tenant.contact_email}")
        self.stdout.write(f"Contact Phone: {tenant.contact_phone}")
        self.stdout.write(f"Timezone: {tenant.timezone}")
        self.stdout.write(f"Country: {tenant.country_code}")
        
        # Usage stats
        from ...models.plan import PlanUsage
        usage = PlanUsage.objects.filter(tenant=tenant, period='monthly').first()
        if usage:
            self.stdout.write(f"\nUsage Information:")
            self.stdout.write(f"API Calls: {usage.api_calls_used}/{usage.api_calls_limit} ({usage.api_calls_percentage:.1f}%)")
            self.stdout.write(f"Storage: {usage.storage_used_gb:.1f}/{usage.storage_limit_gb} GB ({usage.storage_percentage:.1f}%)")
            self.stdout.write(f"Users: {usage.users_used}/{usage.users_limit} ({usage.users_percentage:.1f}%)")
    
    def _output_json(self, tenant):
        """Output in JSON format."""
        info = {
            'id': str(tenant.id),
            'name': tenant.name,
            'slug': tenant.slug,
            'status': tenant.status,
            'tier': tenant.tier,
            'is_suspended': tenant.is_suspended,
            'created_at': tenant.created_at.isoformat(),
            'last_activity_at': tenant.last_activity_at.isoformat() if tenant.last_activity_at else None,
            'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            'days_until_trial_expiry': tenant.days_until_trial_expiry,
            'is_trial_expired': tenant.is_trial_expired,
            'plan': {
                'id': str(tenant.plan.id),
                'name': tenant.plan.name,
                'plan_type': tenant.plan.plan_type,
                'price_monthly': tenant.plan.price_monthly,
            } if tenant.plan else None,
            'owner': {
                'id': str(tenant.owner.id),
                'name': tenant.owner.get_full_name() or tenant.owner.username,
                'email': tenant.owner.email,
            } if tenant.owner else None,
            'contact': {
                'email': tenant.contact_email,
                'phone': tenant.contact_phone,
                'timezone': tenant.timezone,
                'country_code': tenant.country_code,
            },
        }
        
        self.stdout.write(json.dumps(info, indent=2))
