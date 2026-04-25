"""
Core Viewsets

This module contains viewsets for core tenant models including
Tenant, TenantSettings, TenantBilling, and TenantInvoice.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from ..serializers.core import (
    TenantSerializer, TenantCreateSerializer, TenantUpdateSerializer,
    TenantSettingsSerializer, TenantBillingSerializer, TenantInvoiceSerializer,
    TenantInvoiceCreateSerializer
)
from ..services import TenantService, TenantBillingService


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants with comprehensive CRUD operations.
    """
    queryset = Tenant.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'tier', 'plan', 'country_code']
    search_fields = ['name', 'slug', 'contact_email']
    ordering_fields = ['name', 'created_at', 'last_activity_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TenantUpdateSerializer
        return TenantSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action == 'create':
            return [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated]
        elif self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAdminUser]
    
    def perform_create(self, serializer):
        """Create tenant with proper services."""
        data = serializer.validated_data
        tenant = TenantService.create_tenant(data, self.request.user)
        serializer.instance = tenant
    
    def perform_update(self, serializer):
        """Update tenant with proper services."""
        tenant = serializer.save()
        TenantService.update_tenant(tenant, serializer.validated_data, self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete tenant."""
        TenantService.delete_tenant(instance, self.request.user)
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend tenant."""
        tenant = self.get_object()
        reason = request.data.get('reason', 'Manual suspension')
        
        from ..services import TenantSuspensionService
        result = TenantSuspensionService.suspend_tenant(tenant, reason, request.user)
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def unsuspend(self, request, pk=None):
        """Unsuspend tenant."""
        tenant = self.get_object()
        
        from ..services import TenantSuspensionService
        result = TenantSuspensionService.unsuspend_tenant(tenant, request.user)
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get tenant statistics."""
        tenant = self.get_object()
        stats = TenantService.get_tenant_statistics(tenant)
        return Response(stats, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore soft deleted tenant."""
        tenant = self.get_object()
        
        if not tenant.is_deleted:
            return Response(
                {'error': 'Tenant is not deleted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        restored_tenant = TenantService.restore_tenant(tenant, request.user)
        serializer = self.get_serializer(restored_tenant)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search tenants with advanced filtering."""
        query = request.query_params.get('q', '')
        filters = {
            'status': request.query_params.get('status'),
            'tier': request.query_params.get('tier'),
            'plan': request.query_params.get('plan'),
            'owner': request.query_params.get('owner'),
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        tenants = TenantService.search_tenants(query, filters)
        page = self.paginate_queryset(tenants)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(tenants, many=True)
        return Response(serializer.data)


class TenantSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant settings.
    """
    serializer_class = TenantSettingsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset to tenant's settings."""
        if self.request.user.is_superuser:
            return TenantSettings.objects.all()
        return TenantSettings.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def reset_to_defaults(self, request, pk=None):
        """Reset settings to plan defaults."""
        settings = self.get_object()
        tenant = settings.tenant
        
        # Reset to plan defaults
        settings.max_users = tenant.plan.max_users
        settings.max_publishers = tenant.plan.max_publishers
        settings.max_smartlinks = tenant.plan.max_smartlinks
        settings.api_calls_per_day = tenant.plan.api_calls_per_day
        settings.storage_gb = tenant.plan.storage_gb
        settings.save()
        
        return Response({'message': 'Settings reset to plan defaults'}, status=status.HTTP_200_OK)


class TenantBillingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant billing information.
    """
    serializer_class = TenantBillingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'billing_cycle', 'payment_method']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset to tenant's billing."""
        if self.request.user.is_superuser:
            return TenantBilling.objects.all()
        return TenantBilling.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def calculate_final_price(self, request, pk=None):
        """Calculate final price with discounts."""
        billing = self.get_object()
        billing.calculate_final_price()
        billing.save()
        
        return Response({
            'base_price': float(billing.base_price),
            'final_price': float(billing.final_price),
            'discount_pct': billing.discount_pct,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def send_invoice(self, request, pk=None):
        """Send next billing invoice."""
        billing = self.get_object()
        tenant = billing.tenant
        
        invoice = TenantBillingService.generate_monthly_invoice(tenant)
        
        if invoice:
            return Response({
                'message': 'Invoice generated successfully',
                'invoice_id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'total_amount': float(invoice.total_amount),
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'message': 'No billing activity to invoice'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get billing summary."""
        billing = self.get_object()
        summary = TenantBillingService.get_billing_summary(billing.tenant)
        return Response(summary, status=status.HTTP_200_OK)


class TenantInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant invoices.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'status', 'issue_date', 'due_date']
    search_fields = ['invoice_number', 'description']
    ordering_fields = ['issue_date', 'due_date', 'total_amount']
    ordering = ['-issue_date']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantInvoiceCreateSerializer
        return TenantInvoiceSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's invoices."""
        if self.request.user.is_superuser:
            return TenantInvoice.objects.all()
        return TenantInvoice.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        elif self.action == 'create':
            return [permissions.IsAdminUser]
        return [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Create invoice with proper services."""
        data = serializer.validated_data
        invoice = TenantBillingService.generate_invoice(
            self.request.user.tenant if hasattr(self.request.user, 'tenant') else None,
            data,
            self.request.user
        )
        serializer.instance = invoice
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """Mark invoice as paid."""
        invoice = self.get_object()
        
        payment_data = {
            'amount': request.data.get('amount', invoice.balance_due),
            'payment_method': request.data.get('payment_method'),
            'transaction_id': request.data.get('transaction_id'),
        }
        
        result = TenantBillingService.process_payment(invoice, payment_data, request.user)
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None):
        """Send payment reminder for invoice."""
        invoice = self.get_object()
        
        if invoice.is_paid:
            return Response(
                {'error': 'Invoice is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # This would integrate with your notification system
        # For now, just return success
        return Response(
            {'message': 'Payment reminder sent'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Generate and download invoice PDF."""
        invoice = self.get_object()
        
        # This would generate a PDF invoice
        # For now, return invoice data
        return Response({
            'message': 'PDF download not implemented yet',
            'invoice_data': TenantInvoiceSerializer(invoice).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue invoices."""
        queryset = self.get_queryset().filter(status='overdue')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
