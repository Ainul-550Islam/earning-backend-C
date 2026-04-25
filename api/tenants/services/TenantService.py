"""
Tenant Service

This service handles core tenant operations including creation,
updates, deletion, and business logic for tenant management.
"""

import uuid
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..models.plan import Plan, PlanUpgrade
from ..models.security import TenantAuditLog

User = get_user_model()


class TenantService:
    """
    Service class for tenant management operations.
    
    This service encapsulates business logic for tenant
    creation, updates, validation, and related operations.
    """
    
    @staticmethod
    def create_tenant(data, created_by=None):
        """
        Create a new tenant with all related objects.
        
        Args:
            data (dict): Tenant creation data
            created_by (User): User creating the tenant
            
        Returns:
            Tenant: Created tenant instance
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Validate required fields
            required_fields = ['name', 'slug', 'owner', 'plan']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(_(f'{field} is required.'))
            
            # Check if slug is available
            if Tenant.objects.filter(slug=data['slug']).exists():
                raise ValidationError(_('Tenant slug already exists.'))
            
            # Get plan
            try:
                plan = Plan.objects.get(id=data['plan'], is_active=True)
            except Plan.DoesNotExist:
                raise ValidationError(_('Invalid or inactive plan.'))
            
            # Get owner
            try:
                owner = User.objects.get(id=data['owner'])
            except User.DoesNotExist:
                raise ValidationError(_('Invalid owner user.'))
            
            # Create tenant
            tenant_data = {
                'name': data['name'],
                'slug': data['slug'],
                'plan': plan,
                'owner': owner,
                'contact_email': data.get('contact_email', owner.email),
                'contact_phone': data.get('contact_phone'),
                'timezone': data.get('timezone', 'UTC'),
                'country_code': data.get('country_code'),
                'currency_code': data.get('currency_code', 'USD'),
                'data_region': data.get('data_region', 'us-east-1'),
                'domain': data.get('domain'),
                'parent_tenant': data.get('parent_tenant'),
                'trial_ends_at': data.get('trial_ends_at'),
                'billing_cycle_start': data.get('billing_cycle_start', timezone.now().date().day),
                'metadata': data.get('metadata', {}),
                'created_by': created_by,
            }
            
            # Set trial end date if plan has trial
            if plan.has_trial and not tenant_data.get('trial_ends_at'):
                trial_end = timezone.now() + timedelta(days=plan.trial_days)
                tenant_data['trial_ends_at'] = trial_end
                tenant_data['status'] = 'trial'
            else:
                tenant_data['status'] = 'active'
            
            tenant = Tenant.objects.create(**tenant_data)
            
            # Create related objects
            TenantService._create_tenant_settings(tenant, data)
            TenantService._create_tenant_billing(tenant, data, plan)
            
            # Log creation
            if created_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='create',
                    actor=created_by,
                    model_name='Tenant',
                    object_id=str(tenant.id),
                    object_repr=str(tenant),
                    description=f"Tenant {tenant.name} created"
                )
            
            return tenant
    
    @staticmethod
    def _create_tenant_settings(tenant, data):
        """Create tenant settings."""
        settings_data = {
            'tenant': tenant,
            'enable_smartlink': data.get('enable_smartlink', True),
            'enable_ai_engine': data.get('enable_ai_engine', True),
            'enable_publisher_tools': data.get('enable_publisher_tools', True),
            'enable_advertiser_portal': data.get('enable_advertiser_portal', True),
            'enable_coalition': data.get('enable_coalition', False),
            'max_withdrawal_per_day': data.get('max_withdrawal_per_day', 1000.00),
            'require_kyc_for_withdrawal': data.get('require_kyc_for_withdrawal', True),
            'max_users': data.get('max_users', tenant.plan.max_users),
            'max_publishers': data.get('max_publishers', tenant.plan.max_publishers),
            'max_smartlinks': data.get('max_smartlinks', tenant.plan.max_smartlinks),
            'api_calls_per_day': data.get('api_calls_per_day', tenant.plan.api_calls_per_day),
            'storage_gb': data.get('storage_gb', tenant.plan.storage_gb),
            'default_language': data.get('default_language', 'en'),
            'default_currency': data.get('default_currency', 'USD'),
            'default_timezone': data.get('default_timezone', 'UTC'),
            'email_from_name': data.get('email_from_name', 'Support'),
            'email_from_address': data.get('email_from_address'),
            'enable_two_factor_auth': data.get('enable_two_factor_auth', False),
            'session_timeout_minutes': data.get('session_timeout_minutes', 480),
            'password_min_length': data.get('password_min_length', 8),
            'enable_email_notifications': data.get('enable_email_notifications', True),
            'enable_push_notifications': data.get('enable_push_notifications', True),
            'enable_sms_notifications': data.get('enable_sms_notifications', False),
        }
        
        return TenantSettings.objects.create(**settings_data)
    
    @staticmethod
    def _create_tenant_billing(tenant, data, plan):
        """Create tenant billing configuration."""
        billing_data = {
            'tenant': tenant,
            'stripe_customer_id': data.get('stripe_customer_id'),
            'billing_cycle': data.get('billing_cycle', 'monthly'),
            'billing_cycle_start': data.get('billing_cycle_start', timezone.now().date().day),
            'payment_method': data.get('payment_method', 'card'),
            'base_price': plan.price_monthly,
            'discount_pct': data.get('discount_pct', 0),
            'final_price': plan.price_monthly,
            'billing_email': data.get('billing_email', tenant.contact_email),
            'billing_phone': data.get('billing_phone', tenant.contact_phone),
            'billing_address': data.get('billing_address', {}),
            'tax_id': data.get('tax_id'),
            'tax_exempt': data.get('tax_exempt', False),
            'vat_number': data.get('vat_number'),
            'metadata': data.get('billing_metadata', {}),
        }
        
        # Calculate next billing date
        from datetime import date
        today = date.today()
        if billing_data['billing_cycle_start'] > today.day:
            next_month = today.replace(month=today.month + 1 if today.month < 12 else 1)
            billing_data['next_billing_date'] = next_month.replace(day=billing_data['billing_cycle_start'])
        else:
            next_month = today.replace(month=today.month + 2 if today.month < 11 else 1)
            billing_data['next_billing_date'] = next_month.replace(day=billing_data['billing_cycle_start'])
        
        billing = TenantBilling.objects.create(**billing_data)
        billing.calculate_final_price()
        billing.save()
        
        return billing
    
    @staticmethod
    def update_tenant(tenant, data, updated_by=None):
        """
        Update an existing tenant.
        
        Args:
            tenant (Tenant): Tenant to update
            data (dict): Update data
            updated_by (User): User making the update
            
        Returns:
            Tenant: Updated tenant instance
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Store old values for audit
            old_values = {}
            for field in ['name', 'slug', 'domain', 'status', 'plan', 'timezone', 'country_code']:
                if hasattr(tenant, field):
                    old_values[field] = getattr(tenant, field)
            
            # Update fields
            updatable_fields = [
                'name', 'domain', 'timezone', 'country_code', 'currency_code',
                'data_region', 'contact_email', 'contact_phone', 'metadata'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(tenant, field, data[field])
            
            # Handle plan change
            if 'plan' in data and data['plan'] != tenant.plan:
                new_plan = Plan.objects.get(id=data['plan'], is_active=True)
                TenantService._handle_plan_change(tenant, new_plan, updated_by)
            
            # Handle status change
            if 'status' in data and data['status'] != tenant.status:
                TenantService._handle_status_change(tenant, data['status'], updated_by)
            
            tenant.save()
            
            # Log update
            if updated_by:
                changes = {}
                for field, old_value in old_values.items():
                    new_value = getattr(tenant, field)
                    if old_value != new_value:
                        changes[field] = {'old': str(old_value), 'new': str(new_value)}
                
                if changes:
                    TenantAuditLog.log_action(
                        tenant=tenant,
                        action='update',
                        actor=updated_by,
                        model_name='Tenant',
                        object_id=str(tenant.id),
                        object_repr=str(tenant),
                        changes=changes,
                        description=f"Tenant {tenant.name} updated"
                    )
            
            return tenant
    
    @staticmethod
    def _handle_plan_change(tenant, new_plan, changed_by=None):
        """Handle tenant plan change."""
        old_plan = tenant.plan
        
        # Create plan upgrade record
        PlanUpgrade.objects.create(
            tenant=tenant,
            from_plan=old_plan,
            to_plan=new_plan,
            upgraded_at=timezone.now(),
            effective_from=timezone.now(),
            old_price=old_plan.price_monthly,
            new_price=new_plan.price_monthly,
            processed_by=changed_by,
            reason="Plan change requested"
        )
        
        # Update tenant plan
        tenant.plan = new_plan
        
        # Update tenant settings limits
        settings = tenant.settings
        settings.max_users = new_plan.max_users
        settings.max_publishers = new_plan.max_publishers
        settings.max_smartlinks = new_plan.max_smartlinks
        settings.api_calls_per_day = new_plan.api_calls_per_day
        settings.storage_gb = new_plan.storage_gb
        settings.save()
        
        # Update billing
        billing = tenant.billing
        billing.base_price = new_plan.price_monthly
        billing.calculate_final_price()
        billing.save()
    
    @staticmethod
    def _handle_status_change(tenant, new_status, changed_by=None):
        """Handle tenant status change."""
        old_status = tenant.status
        
        if new_status == 'suspended' and old_status != 'suspended':
            tenant.suspend(reason="Status changed to suspended")
        elif new_status == 'active' and old_status == 'suspended':
            tenant.unsuspend()
        elif new_status == 'cancelled':
            tenant.is_deleted = True
            tenant.deleted_at = timezone.now()
        
        tenant.status = new_status
    
    @staticmethod
    def delete_tenant(tenant, deleted_by=None, reason=None):
        """
        Soft delete a tenant.
        
        Args:
            tenant (Tenant): Tenant to delete
            deleted_by (User): User deleting the tenant
            reason (str): Reason for deletion
            
        Returns:
            bool: True if successful
        """
        with transaction.atomic():
            # Log deletion
            if deleted_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='delete',
                    actor=deleted_by,
                    model_name='Tenant',
                    object_id=str(tenant.id),
                    object_repr=str(tenant),
                    description=f"Tenant {tenant.name} deleted: {reason or 'No reason provided'}"
                )
            
            # Soft delete
            tenant.is_deleted = True
            tenant.deleted_at = timezone.now()
            tenant.save()
            
            return True
    
    @staticmethod
    def restore_tenant(tenant, restored_by=None):
        """
        Restore a soft deleted tenant.
        
        Args:
            tenant (Tenant): Tenant to restore
            restored_by (User): User restoring the tenant
            
        Returns:
            Tenant: Restored tenant instance
        """
        with transaction.atomic():
            tenant.is_deleted = False
            tenant.deleted_at = None
            tenant.save()
            
            # Log restoration
            if restored_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='create',  # Using create for restoration
                    actor=restored_by,
                    model_name='Tenant',
                    object_id=str(tenant.id),
                    object_repr=str(tenant),
                    description=f"Tenant {tenant.name} restored"
                )
            
            return tenant
    
    @staticmethod
    def get_tenant_statistics(tenant):
        """
        Get comprehensive tenant statistics.
        
        Args:
            tenant (Tenant): Tenant to get statistics for
            
        Returns:
            dict: Tenant statistics
        """
        from ..models.analytics import TenantMetric
        from ..models.security import TenantAPIKey
        from django.db.models import Count, Sum
        
        stats = {
            'basic_info': {
                'id': str(tenant.id),
                'name': tenant.name,
                'slug': tenant.slug,
                'status': tenant.status,
                'tier': tenant.tier,
                'created_at': tenant.created_at,
                'last_activity_at': tenant.last_activity_at,
            },
            'plan_info': {
                'plan_name': tenant.plan.name,
                'plan_type': tenant.plan.plan_type,
                'price_monthly': float(tenant.plan.price_monthly),
                'trial_ends_at': tenant.trial_ends_at,
                'is_trial_expired': tenant.is_trial_expired,
                'days_until_trial_expiry': tenant.days_until_trial_expiry,
            },
            'usage_stats': {},
            'security_stats': {},
            'billing_stats': {},
        }
        
        # Usage statistics
        try:
            latest_metrics = TenantMetric.objects.filter(
                tenant=tenant
            ).order_by('-date').first()
            
            if latest_metrics:
                stats['usage_stats'] = {
                    'mau': float(latest_metrics.value) if latest_metrics.metric_type == 'mau' else 0,
                    'dau': float(latest_metrics.value) if latest_metrics.metric_type == 'dau' else 0,
                    'api_calls': float(latest_metrics.value) if latest_metrics.metric_type == 'api_calls' else 0,
                    'storage_used': float(latest_metrics.value) if latest_metrics.metric_type == 'storage_used' else 0,
                    'last_updated': latest_metrics.date,
                }
        except:
            pass
        
        # Security statistics
        api_keys = TenantAPIKey.objects.filter(tenant=tenant, is_deleted=False)
        stats['security_stats'] = {
            'active_api_keys': api_keys.filter(status='active').count(),
            'total_api_keys': api_keys.count(),
            'recent_usage': api_keys.aggregate(
                total_usage=Sum('usage_count')
            )['total_usage'] or 0,
        }
        
        # Billing statistics
        invoices = TenantInvoice.objects.filter(tenant=tenant)
        stats['billing_stats'] = {
            'total_invoices': invoices.count(),
            'paid_invoices': invoices.filter(status='paid').count(),
            'overdue_invoices': invoices.filter(status='overdue').count(),
            'total_revenue': float(invoices.filter(status='paid').aggregate(
                total=Sum('total_amount')
            )['total'] or 0),
        }
        
        return stats
    
    @staticmethod
    def validate_tenant_data(data, tenant=None):
        """
        Validate tenant data.
        
        Args:
            data (dict): Data to validate
            tenant (Tenant): Existing tenant (for updates)
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate required fields
        if not tenant:  # Creation validation
            required_fields = ['name', 'slug', 'owner', 'plan']
            for field in required_fields:
                if field not in data or not data[field]:
                    errors.append(f'{field} is required.')
        
        # Validate slug uniqueness
        if 'slug' in data:
            slug = data['slug']
            queryset = Tenant.objects.filter(slug=slug)
            if tenant:
                queryset = queryset.exclude(pk=tenant.pk)
            if queryset.exists():
                errors.append('Tenant slug already exists.')
        
        # Validate email format
        if 'contact_email' in data and data['contact_email']:
            from django.core.validators import validate_email
            try:
                validate_email(data['contact_email'])
            except ValidationError:
                errors.append('Invalid email format.')
        
        # Validate timezone
        if 'timezone' in data and data['timezone']:
            try:
                import pytz
                pytz.timezone(data['timezone'])
            except:
                errors.append('Invalid timezone.')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_tenant_by_slug(slug):
        """
        Get tenant by slug.
        
        Args:
            slug (str): Tenant slug
            
        Returns:
            Tenant: Tenant instance or None
        """
        try:
            return Tenant.objects.get(slug=slug, is_deleted=False)
        except Tenant.DoesNotExist:
            return None
    
    @staticmethod
    def search_tenants(query, filters=None):
        """
        Search tenants with filters.
        
        Args:
            query (str): Search query
            filters (dict): Additional filters
            
        Returns:
            QuerySet: Filtered tenant queryset
        """
        queryset = Tenant.objects.filter(is_deleted=False)
        
        if query:
            queryset = queryset.filter(
                models.Q(name__icontains=query) |
                models.Q(slug__icontains=query) |
                models.Q(contact_email__icontains=query)
            )
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'tier' in filters:
                queryset = queryset.filter(tier=filters['tier'])
            if 'plan' in filters:
                queryset = queryset.filter(plan__id=filters['plan'])
            if 'owner' in filters:
                queryset = queryset.filter(owner__id=filters['owner'])
        
        return queryset.select_related('plan', 'owner').order_by('-created_at')
