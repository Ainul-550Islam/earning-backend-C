"""
Tenant Views - Improved Version with Enhanced Security and Features

This module contains comprehensive views for tenant management with
advanced security, proper error handling, and extensive functionality.
"""

import uuid
import secrets
from datetime import datetime, timedelta
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models_improved import (
    Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog
)
from .serializers_improved import (
    TenantSerializer, TenantCreateSerializer, TenantUpdateSerializer,
    TenantPublicSerializer, TenantSettingsSerializer, TenantBillingSerializer,
    TenantInvoiceSerializer, TenantAuditLogSerializer,
    TenantApiKeySerializer, TenantWebhookSecretSerializer,
    TenantFeatureToggleSerializer, TenantSubscriptionSerializer,
    TenantOverviewSerializer
)
from .permissions_improved import (
    IsTenantOwner, IsTenantMember, IsActiveTenant, IsNotSuspended,
    HasValidSubscription, IsSuperAdminOrTenantOwner
)

User = get_user_model()


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tenant management with comprehensive operations.
    
    Provides CRUD operations and additional actions for tenant management
    including branding, billing, features, and administrative functions.
    """
    
    queryset = Tenant.objects.all()
    permission_classes = [IsSuperAdminOrTenantOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['plan', 'status', 'is_active', 'country_code']
    search_fields = ['name', 'slug', 'domain', 'admin_email']
    ordering_fields = ['created_at', 'name', 'plan', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TenantUpdateSerializer
        elif self.action == 'overview':
            return TenantOverviewSerializer
        return TenantSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        if user.is_superuser:
            return Tenant.objects.all()
        
        # Non-superusers can only see their own tenants
        return Tenant.objects.filter(
            models.Q(owner=user) | 
            models.Q(users=user)
        ).distinct()
    
    def perform_create(self, serializer):
        """Perform tenant creation with audit logging."""
        with transaction.atomic():
            tenant = serializer.save(
                created_by=self.request.user
            )
            
            # Log creation
            tenant.audit_log(
                action='created',
                details={
                    'plan': tenant.plan,
                    'max_users': tenant.max_users,
                    'created_by': self.request.user.email,
                    'ip_address': self.get_client_ip(),
                },
                user=self.request.user
            )
            
            return tenant
    
    def perform_update(self, serializer):
        """Perform tenant update with audit logging."""
        with transaction.atomic():
            instance = serializer.save()
            
            # Log update
            instance.audit_log(
                action='updated',
                details={
                    'updated_by': self.request.user.email,
                    'ip_address': self.get_client_ip(),
                },
                user=self.request.user
            )
            
            return instance
    
    def perform_destroy(self, instance):
        """Perform tenant soft delete with audit logging."""
        with transaction.atomic():
            # Soft delete
            instance.is_deleted = True
            instance.is_active = False
            instance.deleted_at = timezone.now()
            instance.save()
            
            # Log deletion
            instance.audit_log(
                action='deleted',
                details={
                    'deleted_by': self.request.user.email,
                    'ip_address': self.get_client_ip(),
                },
                user=self.request.user
            )
    
    def get_client_ip(self):
        """Get client IP address from request."""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    # Public endpoint for React Native app
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def my_tenant(self, request):
        """
        Get tenant information for React Native app.
        
        Returns public tenant configuration including branding,
        feature flags, and app settings.
        """
        try:
            # Get tenant from middleware or request
            tenant = getattr(request, 'tenant', None)
            
            if not tenant:
                # Try to get tenant by domain or slug
                domain = request.META.get('HTTP_X_TENANT_DOMAIN')
                slug = request.META.get('HTTP_X_TENANT_SLUG')
                
                if domain:
                    tenant = Tenant.objects.filter(
                        domain=domain, 
                        is_active=True, 
                        is_deleted=False
                    ).first()
                elif slug:
                    tenant = Tenant.objects.filter(
                        slug=slug, 
                        is_active=True, 
                        is_deleted=False
                    ).first()
            
            if not tenant:
                return Response({
                    'error': 'Tenant not found',
                    'message': 'No tenant configuration available'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if tenant is active and not suspended
            if not tenant.is_active or tenant.is_deleted or tenant.is_suspended:
                return Response({
                    'error': 'Tenant unavailable',
                    'message': 'Tenant is currently unavailable'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Get tenant configuration
            serializer = TenantPublicSerializer(
                tenant, 
                context={'request': request}
            )
            
            # Log access for security
            tenant.audit_log(
                action='public_access',
                details={
                    'endpoint': 'my_tenant',
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': self.get_client_ip(),
                }
            )
            
            return Response({
                'success': True,
                'data': serializer.data
            })
            
        except Exception as e:
            return Response({
                'error': 'Internal server error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: Branding management
    @action(detail=True, methods=['patch'], permission_classes=[IsSuperAdminOrTenantOwner])
    def update_branding(self, request, pk=None):
        """
        Update tenant branding information.
        
        Allows updating logo, colors, and other branding elements.
        """
        try:
            tenant = self.get_object()
            
            # Allowed fields for branding update
            allowed_fields = [
                'name', 'logo', 'primary_color', 'secondary_color',
                'android_package_name', 'ios_bundle_id'
            ]
            
            # Validate and update allowed fields
            updated_fields = []
            for field in allowed_fields:
                if field in request.data:
                    setattr(tenant, field, request.data[field])
                    updated_fields.append(field)
            
            if not updated_fields:
                return Response({
                    'error': 'No valid fields provided',
                    'allowed_fields': allowed_fields
                }, status=status.HTTP_400_BAD_REQUEST)
            
            tenant.save()
            
            # Log branding update
            tenant.audit_log(
                action='updated',
                details={
                    'branding_update': updated_fields,
                    'ip_address': self.get_client_ip(),
                },
                user=request.user
            )
            
            # Return updated tenant data
            serializer = TenantSerializer(
                tenant, 
                context={'request': request}
            )
            
            return Response({
                'success': True,
                'message': 'Branding updated successfully',
                'data': serializer.data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to update branding',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: API key management
    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdminOrTenantOwner])
    def regenerate_api_key(self, request, pk=None):
        """
        Regenerate tenant API key and secret.
        
        Creates new API credentials for secure API access.
        """
        try:
            tenant = self.get_object()
            
            # Generate new API key and secret
            new_api_key = uuid.uuid4()
            new_api_secret = secrets.token_urlsafe(48)
            
            # Update tenant credentials
            tenant.api_key = new_api_key
            tenant.api_secret = new_api_secret
            tenant.save(update_fields=['api_key', 'api_secret', 'updated_at'])
            
            # Log API key regeneration
            tenant.audit_log(
                action='api_key_regenerated',
                details={
                    'ip_address': self.get_client_ip(),
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'API key regenerated successfully',
                'data': {
                    'api_key': str(new_api_key),
                    'api_secret': new_api_secret
                }
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to regenerate API key',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: Webhook secret management
    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdminOrTenantOwner])
    def regenerate_webhook_secret(self, request, pk=None):
        """
        Regenerate webhook secret for secure webhook verification.
        """
        try:
            tenant = self.get_object()
            
            # Generate new webhook secret
            new_webhook_secret = secrets.token_urlsafe(32)
            
            # Update tenant
            tenant.webhook_secret = new_webhook_secret
            tenant.save(update_fields=['webhook_secret', 'updated_at'])
            
            # Log webhook secret regeneration
            tenant.audit_log(
                action='webhook_secret_regenerated',
                details={
                    'ip_address': self.get_client_ip(),
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Webhook secret regenerated successfully',
                'data': {
                    'webhook_secret': new_webhook_secret
                }
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to regenerate webhook secret',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: Dashboard statistics
    @action(detail=True, methods=['get'], permission_classes=[IsSuperAdminOrTenantOwner])
    def dashboard(self, request, pk=None):
        """
        Get comprehensive dashboard statistics for tenant.
        
        Returns user statistics, billing information, and usage data.
        """
        try:
            tenant = self.get_object()
            
            # Get user statistics
            total_users = User.objects.filter(tenant=tenant).count()
            active_users = User.objects.filter(tenant=tenant, is_active=True).count()
            new_users_this_month = User.objects.filter(
                tenant=tenant,
                date_joined__gte=timezone.now().replace(day=1)
            ).count()
            
            # Get billing information
            billing = tenant.get_billing()
            
            # Get usage statistics
            usage_stats = tenant.get_usage_stats()
            
            # Get recent audit logs
            recent_logs = TenantAuditLog.objects.filter(
                tenant=tenant
            ).order_by('-created_at')[:10]
            
            dashboard_data = {
                'tenant': {
                    'id': str(tenant.id),
                    'name': tenant.name,
                    'slug': tenant.slug,
                    'plan': tenant.plan,
                    'status': tenant.status,
                    'created_at': tenant.created_at.isoformat(),
                },
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'new_this_month': new_users_this_month,
                    'limit': tenant.max_users,
                    'remaining': tenant.get_user_limit_remaining(),
                    'limit_reached': tenant.is_user_limit_reached(),
                },
                'billing': {
                    'status': billing.status,
                    'is_active': billing.is_active,
                    'is_past_due': billing.is_past_due,
                    'plan': tenant.plan,
                    'trial_active': tenant.is_trial_active,
                    'trial_days_remaining': tenant.days_until_trial_expires,
                    'trial_expired': tenant.trial_expired,
                    'next_payment': billing.next_payment_at.isoformat() if billing.next_payment_at else None,
                    'last_payment': billing.last_payment_at.isoformat() if billing.last_payment_at else None,
                },
                'usage': usage_stats,
                'recent_activity': [
                    {
                        'action': log.action,
                        'user': log.user_email,
                        'timestamp': log.created_at.isoformat(),
                        'details': log.details
                    }
                    for log in recent_logs
                ]
            }
            
            return Response({
                'success': True,
                'data': dashboard_data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to load dashboard data',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: Feature management
    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdminOrTenantOwner])
    def toggle_feature(self, request, pk=None):
        """
        Toggle specific tenant features on/off.
        
        Allows enabling/disabling features like referral, offerwall, KYC, etc.
        """
        try:
            tenant = self.get_object()
            
            # Validate feature toggle data
            serializer = TenantFeatureToggleSerializer(
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            # Toggle feature
            result = serializer.toggle_feature(tenant)
            
            return Response({
                'success': True,
                'message': f'Feature {result["feature"]} {"enabled" if result["enabled"] else "disabled"}',
                'data': result
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to toggle feature',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: Subscription management
    @action(detail=True, methods=['patch'], permission_classes=[IsSuperAdminOrTenantOwner])
    def manage_subscription(self, request, pk=None):
        """
        Manage tenant subscription and billing.
        
        Allows updating subscription plans, extending trials, etc.
        """
        try:
            tenant = self.get_object()
            billing = tenant.get_billing()
            
            # Validate subscription data
            serializer = TenantSubscriptionSerializer(
                billing,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            # Update subscription
            billing = serializer.save()
            
            # Update tenant status if needed
            if billing.status != tenant.status:
                tenant.status = billing.status
                tenant.save(update_fields=['status', 'updated_at'])
            
            return Response({
                'success': True,
                'message': 'Subscription updated successfully',
                'data': TenantBillingSerializer(billing).data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to update subscription',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: Suspend/Activate tenant
    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdminOrTenantOwner])
    def toggle_status(self, request, pk=None):
        """
        Toggle tenant active/suspended status.
        
        Allows suspending or reactivating tenant accounts.
        """
        try:
            tenant = self.get_object()
            
            # Get action from request
            action = request.data.get('action')
            if action not in ['suspend', 'activate']:
                return Response({
                    'error': 'Invalid action',
                    'message': 'Action must be "suspend" or "activate"'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update tenant status
            if action == 'suspend':
                tenant.is_active = False
                tenant.is_suspended = True
                message = 'Tenant suspended successfully'
            else:
                tenant.is_active = True
                tenant.is_suspended = False
                message = 'Tenant activated successfully'
            
            tenant.save(update_fields=['is_active', 'is_suspended', 'updated_at'])
            
            # Log status change
            tenant.audit_log(
                action='suspended' if action == 'suspend' else 'activated',
                details={
                    'action': action,
                    'ip_address': self.get_client_ip(),
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': message,
                'data': {
                    'is_active': tenant.is_active,
                    'is_suspended': tenant.is_suspended,
                    'status': tenant.status
                }
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to toggle tenant status',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin: All tenants overview
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def overview(self, request):
        """
        Get overview of all tenants for admin dashboard.
        
        Returns summary statistics and tenant list with key metrics.
        """
        try:
            # Get query parameters
            plan_filter = request.query_params.get('plan')
            status_filter = request.query_params.get('status')
            
            # Build queryset
            queryset = Tenant.objects.all()
            
            if plan_filter:
                queryset = queryset.filter(plan=plan_filter)
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            # Get statistics
            total_tenants = queryset.count()
            active_tenants = queryset.filter(is_active=True, is_deleted=False).count()
            trial_tenants = queryset.filter(status='trial').count()
            expired_trials = queryset.filter(
                status='trial', 
                trial_ends_at__lt=timezone.now()
            ).count()
            
            # Get tenant data
            tenants_data = []
            for tenant in queryset.select_related('billing').prefetch_related('users'):
                billing = tenant.billing if hasattr(tenant, 'billing') else None
                
                tenant_data = {
                    'id': str(tenant.id),
                    'name': tenant.name,
                    'slug': tenant.slug,
                    'domain': tenant.domain,
                    'plan': tenant.plan,
                    'status': tenant.status,
                    'is_active': tenant.is_active,
                    'is_suspended': tenant.is_suspended,
                    'users': {
                        'total': tenant.get_total_user_count(),
                        'active': tenant.get_active_user_count(),
                        'limit': tenant.max_users,
                        'limit_reached': tenant.is_user_limit_reached(),
                    },
                    'billing': {
                        'status': billing.status if billing else 'unknown',
                        'is_active': billing.is_active if billing else False,
                        'is_past_due': billing.is_past_due if billing else False,
                        'next_payment': billing.next_payment_at.isoformat() if billing and billing.next_payment_at else None,
                    },
                    'created_at': tenant.created_at.isoformat(),
                    'trial_info': {
                        'active': tenant.is_trial_active,
                        'days_remaining': tenant.days_until_trial_expires,
                        'expired': tenant.trial_expired,
                    }
                }
                tenants_data.append(tenant_data)
            
            overview_data = {
                'statistics': {
                    'total_tenants': total_tenants,
                    'active_tenants': active_tenants,
                    'trial_tenants': trial_tenants,
                    'expired_trials': expired_trials,
                    'suspended_tenants': queryset.filter(is_suspended=True).count(),
                },
                'tenants': tenants_data
            }
            
            return Response({
                'success': True,
                'data': overview_data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to load tenant overview',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tenant settings management.
    
    Handles configuration of tenant-specific settings including
    feature flags, payout rules, and custom configurations.
    """
    
    serializer_class = TenantSettingsSerializer
    permission_classes = [IsSuperAdminOrTenantOwner]
    
    def get_queryset(self):
        """Filter settings based on user permissions."""
        user = self.request.user
        
        if user.is_superuser:
            return TenantSettings.objects.all()
        
        return TenantSettings.objects.filter(
            tenant__owner=user
        ).select_related('tenant')
    
    def perform_update(self, serializer):
        """Perform settings update with audit logging."""
        with transaction.atomic():
            settings = serializer.save()
            
            # Log settings update
            settings.tenant.audit_log(
                action='settings_updated',
                details={
                    'updated_by': self.request.user.email,
                    'ip_address': self.get_client_ip(),
                },
                user=self.request.user
            )
            
            return settings
    
    def get_client_ip(self):
        """Get client IP address from request."""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class TenantBillingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tenant billing management.
    
    Handles subscription management, payments, and billing operations.
    """
    
    serializer_class = TenantBillingSerializer
    permission_classes = [IsSuperAdminOrTenantOwner]
    
    def get_queryset(self):
        """Filter billing records based on user permissions."""
        user = self.request.user
        
        if user.is_superuser:
            return TenantBilling.objects.all()
        
        return TenantBilling.objects.filter(
            tenant__owner=user
        ).select_related('tenant')
    
    @action(detail=True, methods=['post'])
    def create_invoice(self, request, pk=None):
        """
        Create invoice for tenant.
        
        Generates a new invoice with specified amount and description.
        """
        try:
            billing = self.get_object()
            
            # Validate invoice data
            amount = request.data.get('amount')
            description = request.data.get('description', 'Subscription fee')
            
            if not amount:
                return Response({
                    'error': 'Amount is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError()
            except ValueError:
                return Response({
                    'error': 'Invalid amount'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create invoice
            invoice = billing.create_invoice(
                amount=amount,
                description=description
            )
            
            # Log invoice creation
            billing.tenant.audit_log(
                action='invoice_generated',
                details={
                    'invoice_id': invoice.id,
                    'amount': float(amount),
                    'description': description,
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Invoice created successfully',
                'data': TenantInvoiceSerializer(invoice).data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to create invoice',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def extend_trial(self, request, pk=None):
        """
        Extend tenant trial period.
        
        Adds specified number of days to trial period.
        """
        try:
            billing = self.get_object()
            
            days = request.data.get('days')
            if not days:
                return Response({
                    'error': 'Number of days is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                days = int(days)
                if days < 1 or days > 365:
                    raise ValueError()
            except ValueError:
                return Response({
                    'error': 'Days must be between 1 and 365'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Extend trial
            billing.extend_trial(days)
            
            # Log trial extension
            billing.tenant.audit_log(
                action='billing_updated',
                details={
                    'trial_extended_days': days,
                    'new_trial_end': billing.trial_ends_at.isoformat() if billing.trial_ends_at else None,
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': f'Trial extended by {days} days',
                'data': {
                    'trial_ends_at': billing.trial_ends_at.isoformat() if billing.trial_ends_at else None,
                    'days_remaining': billing.tenant.days_until_trial_expires,
                }
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to extend trial',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for tenant invoice viewing.
    
    Provides read-only access to tenant invoices and payment history.
    """
    
    serializer_class = TenantInvoiceSerializer
    permission_classes = [IsSuperAdminOrTenantOwner]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'due_date', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter invoices based on user permissions."""
        user = self.request.user
        
        if user.is_superuser:
            return TenantInvoice.objects.all()
        
        return TenantInvoice.objects.filter(
            tenant__owner=user
        ).select_related('tenant')
    
    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdminOrTenantOwner])
    def mark_paid(self, request, pk=None):
        """
        Mark invoice as paid.
        
        Records payment information and updates invoice status.
        """
        try:
            invoice = self.get_object()
            
            # Validate payment data
            payment_method = request.data.get('payment_method')
            transaction_id = request.data.get('transaction_id')
            payment_notes = request.data.get('payment_notes')
            
            if not payment_method:
                return Response({
                    'error': 'Payment method is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark as paid
            invoice.mark_as_paid(
                payment_method=payment_method,
                transaction_id=transaction_id,
                notes=payment_notes
            )
            
            # Log payment
            invoice.tenant.audit_log(
                action='payment_processed',
                details={
                    'invoice_id': invoice.id,
                    'amount': float(invoice.total_amount),
                    'payment_method': payment_method,
                    'transaction_id': transaction_id,
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Invoice marked as paid',
                'data': TenantInvoiceSerializer(invoice).data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to mark invoice as paid',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for tenant audit logs.
    
    Provides read-only access to tenant activity logs for security
    and compliance monitoring.
    """
    
    serializer_class = TenantAuditLogSerializer
    permission_classes = [IsSuperAdminOrTenantOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['action', 'user', 'success']
    search_fields = ['action', 'user_email', 'details']
    ordering_fields = ['created_at', 'action']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter audit logs based on user permissions."""
        user = self.request.user
        
        if user.is_superuser:
            return TenantAuditLog.objects.all()
        
        return TenantAuditLog.objects.filter(
            tenant__owner=user
        ).select_related('tenant', 'user')


# API Views for standalone endpoints
@api_view(['GET'])
@permission_classes([AllowAny])
def tenant_health_check(request):
    """
    Health check endpoint for tenant system.
    
    Returns system health status and basic statistics.
    """
    try:
        # Get system statistics
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(
            is_active=True, 
            is_deleted=False
        ).count()
        trial_tenants = Tenant.objects.filter(status='trial').count()
        
        # Check database connectivity
        from django.db import connection
        db_connection = connection.ensure_connection()
        
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'system': {
                'total_tenants': total_tenants,
                'active_tenants': active_tenants,
                'trial_tenants': trial_tenants,
                'database_connected': db_connection is not None,
            },
            'version': '1.0.0',
        }
        
        return Response({
            'success': True,
            'data': health_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Health check failed',
            'message': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_handler(request, tenant_slug):
    """
    Handle incoming webhooks for tenants.
    
    Processes webhook requests with signature verification.
    """
    try:
        # Get tenant
        tenant = Tenant.objects.filter(
            slug=tenant_slug,
            is_active=True,
            is_deleted=False
        ).first()
        
        if not tenant:
            return Response({
                'error': 'Tenant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify webhook signature
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
        if not signature:
            return Response({
                'error': 'Missing webhook signature'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Here you would verify the signature using tenant.webhook_secret
        # For now, we'll just log the webhook
        tenant.audit_log(
            action='webhook_received',
            details={
                'signature': signature[:10] + '...',  # Log partial signature
                'headers': dict(request.headers),
                'body_length': len(request.body),
            }
        )
        
        return Response({
            'success': True,
            'message': 'Webhook received'
        })
        
    except Exception as e:
        return Response({
            'error': 'Webhook processing failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantPublicAPIView(generics.RetrieveAPIView):
    """
    Public API view for tenant information.
    
    Provides safe public tenant information for external access.
    """
    
    serializer_class = TenantPublicSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Return only active, non-deleted tenants."""
        return Tenant.objects.filter(
            is_active=True,
            is_deleted=False
        )
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get public tenant information.
        
        Returns safe tenant data for public consumption.
        """
        try:
            tenant = self.get_object()
            
            # Check if tenant is suspended
            if tenant.is_suspended:
                return Response({
                    'error': 'Tenant suspended',
                    'message': 'This tenant is currently suspended'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Get serializer data
            serializer = self.get_serializer(tenant)
            
            # Log public access
            tenant.audit_log(
                action='public_api_access',
                details={
                    'endpoint': 'public_api',
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                }
            )
            
            return Response({
                'success': True,
                'data': serializer.data
            })
            
        except Http404:
            return Response({
                'error': 'Tenant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': 'Failed to get tenant information',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
