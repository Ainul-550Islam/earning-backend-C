"""
Billing ViewSets

This module contains viewsets for billing-related operations including
tenant billing, invoices, and payment processing.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend

from ..models.core import TenantBilling, TenantInvoice
from ..serializers.billing import (
    TenantBillingSerializer, TenantInvoiceSerializer,
    InvoiceCreateSerializer, InvoiceUpdateSerializer
)
from ..services import TenantBillingService
from ..viewsets.base import BaseTenantViewSet


class TenantBillingViewSet(BaseTenantViewSet):
    """
    ViewSet for tenant billing operations.
    
    Provides endpoints for:
    - Billing configuration management
    - Billing status updates
    - Payment method management
    - Billing analytics and reporting
    """
    
    queryset = TenantBilling.objects.all()
    serializer_class = TenantBillingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'billing_cycle', 'payment_method']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            # Non-staff users can only see their own billing
            queryset = queryset.filter(tenant__owner=self.request.user)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def update_payment_method(self, request, pk=None):
        """Update payment method for billing."""
        billing = self.get_object()
        payment_method = request.data.get('payment_method')
        payment_details = request.data.get('payment_details', {})
        
        try:
            updated_billing = TenantBillingService.update_payment_method(
                billing, payment_method, payment_details
            )
            
            serializer = self.get_serializer(updated_billing)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_billing_cycle(self, request, pk=None):
        """Update billing cycle."""
        billing = self.get_object()
        billing_cycle = request.data.get('billing_cycle')
        
        try:
            updated_billing = TenantBillingService.update_billing_cycle(
                billing, billing_cycle
            )
            
            serializer = self.get_serializer(updated_billing)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def calculate_prorated_amount(self, request, pk=None):
        """Calculate prorated amount for billing cycle change."""
        billing = self.get_object()
        new_cycle = request.data.get('new_billing_cycle')
        
        try:
            result = TenantBillingService.calculate_prorated_amount(
                billing, new_cycle
            )
            
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def billing_summary(self, request, pk=None):
        """Get billing summary for tenant."""
        billing = self.get_object()
        
        try:
            summary = TenantBillingService.get_billing_summary(billing.tenant)
            return Response(summary)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def payment_history(self, request, pk=None):
        """Get payment history for billing."""
        billing = self.get_object()
        days = request.query_params.get('days', 30)
        
        try:
            history = TenantBillingService.get_payment_history(billing.tenant, days)
            return Response(history)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def billing_analytics(self, request):
        """Get billing analytics for all tenants."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        days = request.query_params.get('days', 30)
        
        try:
            analytics = TenantBillingService.get_billing_analytics(days)
            return Response(analytics)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TenantInvoiceViewSet(BaseTenantViewSet):
    """
    ViewSet for tenant invoice operations.
    
    Provides endpoints for:
    - Invoice creation and management
    - Invoice payment processing
    - Invoice analytics and reporting
    - Invoice export functionality
    """
    
    queryset = TenantInvoice.objects.all()
    serializer_class = TenantInvoiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'type', 'tenant']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            # Non-staff users can only see their own invoices
            queryset = queryset.filter(tenant__owner=self.request.user)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return InvoiceCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return InvoiceUpdateSerializer
        return self.serializer_class
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid."""
        invoice = self.get_object()
        payment_amount = request.data.get('payment_amount')
        payment_method = request.data.get('payment_method')
        transaction_id = request.data.get('transaction_id')
        
        try:
            updated_invoice = TenantBillingService.mark_invoice_paid(
                invoice, payment_amount, payment_method, transaction_id
            )
            
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def mark_overdue(self, request, pk=None):
        """Mark invoice as overdue."""
        invoice = self.get_object()
        
        try:
            updated_invoice = TenantBillingService.mark_invoice_overdue(invoice)
            
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel_invoice(self, request, pk=None):
        """Cancel an invoice."""
        invoice = self.get_object()
        reason = request.data.get('reason', '')
        
        try:
            updated_invoice = TenantBillingService.cancel_invoice(invoice, reason)
            
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None):
        """Send payment reminder for invoice."""
        invoice = self.get_object()
        
        try:
            result = TenantBillingService.send_payment_reminder(invoice)
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def invoice_pdf(self, request, pk=None):
        """Generate PDF for invoice."""
        invoice = self.get_object()
        
        try:
            pdf_url = TenantBillingService.generate_invoice_pdf(invoice)
            return Response({'pdf_url': pdf_url})
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_generate(self, request):
        """Generate invoices in bulk."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tenant_ids = request.data.get('tenant_ids', [])
        period = request.data.get('period', 'monthly')
        
        try:
            result = TenantBillingService.bulk_generate_invoices(tenant_ids, period)
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_mark_paid(self, request):
        """Mark multiple invoices as paid."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        invoice_ids = request.data.get('invoice_ids', [])
        payment_method = request.data.get('payment_method')
        
        try:
            result = TenantBillingService.bulk_mark_paid(invoice_ids, payment_method)
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def invoice_analytics(self, request):
        """Get invoice analytics."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        days = request.query_params.get('days', 30)
        
        try:
            analytics = TenantBillingService.get_invoice_analytics(days)
            return Response(analytics)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def revenue_report(self, request):
        """Get revenue report."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        try:
            report = TenantBillingService.get_revenue_report(start_date, end_date)
            return Response(report)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def dunning_report(self, request):
        """Get dunning report."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        days = request.query_params.get('days', 30)
        
        try:
            report = TenantBillingService.get_dunning_report(days)
            return Response(report)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def apply_discount(self, request, pk=None):
        """Apply discount to invoice."""
        invoice = self.get_object()
        discount_amount = request.data.get('discount_amount')
        discount_percentage = request.data.get('discount_percentage')
        reason = request.data.get('reason', '')
        
        try:
            updated_invoice = TenantBillingService.apply_discount(
                invoice, discount_amount, discount_percentage, reason
            )
            
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def add_line_item(self, request, pk=None):
        """Add line item to invoice."""
        invoice = self.get_object()
        line_item = request.data.get('line_item')
        
        try:
            updated_invoice = TenantBillingService.add_line_item(invoice, line_item)
            
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def remove_line_item(self, request, pk=None):
        """Remove line item from invoice."""
        invoice = self.get_object()
        line_item_index = request.data.get('line_item_index')
        
        try:
            updated_invoice = TenantBillingService.remove_line_item(invoice, line_item_index)
            
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def payment_schedule(self, request, pk=None):
        """Get payment schedule for invoice."""
        invoice = self.get_object()
        
        try:
            schedule = TenantBillingService.get_payment_schedule(invoice)
            return Response(schedule)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
