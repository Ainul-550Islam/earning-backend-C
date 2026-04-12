"""
Billing Management Views

This module contains Django REST Framework ViewSets for managing
billing operations, payments, invoices, and financial transactions.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.billing_model import BillingProfile, PaymentMethod, Invoice, PaymentTransaction
from ..database_models.advertiser_model import Advertiser
from .services import (
    BillingService, PaymentService, InvoiceService, TransactionService
)
from .serializers import *
from ..exceptions import *
from ..utils import *


class BillingProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing billing profiles."""
    
    queryset = BillingProfile.objects.all()
    serializer_class = BillingProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'status', 'is_verified', 'billing_cycle']
    search_fields = ['company_name', 'trade_name', 'billing_email']
    ordering_fields = ['created_at', 'company_name', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show profiles from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no profiles
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new billing profile."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            billing_profile = BillingService.create_billing_profile(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = BillingProfileDetailSerializer(billing_profile)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating billing profile: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update billing profile."""
        try:
            billing_profile = self.get_object()
            
            serializer = self.get_serializer(billing_profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_profile = BillingService.update_billing_profile(
                billing_profile.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = BillingProfileDetailSerializer(updated_profile)
            return Response(response_serializer.data)
            
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating billing profile: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify billing profile."""
        try:
            billing_profile = self.get_object()
            
            success = BillingService.verify_billing_profile(
                billing_profile.id,
                verified_by=request.user
            )
            
            if success:
                response_serializer = BillingProfileDetailSerializer(billing_profile)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to verify billing profile'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error verifying billing profile: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def calculate_tax(self, request, pk=None):
        """Calculate tax amount."""
        try:
            billing_profile = self.get_object()
            
            amount = Decimal(str(request.data.get('amount', 0)))
            if amount <= 0:
                return Response(
                    {'error': 'Amount must be positive'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tax_amount = BillingService.calculate_tax(billing_profile.id, amount)
            
            return Response({
                'amount': float(amount),
                'tax_amount': float(tax_amount),
                'total_amount': float(amount + tax_amount),
                'tax_rate': float(billing_profile.tax_rate)
            })
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error calculating tax: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_credit(self, request, pk=None):
        """Update credit available."""
        try:
            billing_profile = self.get_object()
            
            amount = Decimal(str(request.data.get('amount', 0)))
            transaction_type = request.data.get('transaction_type', 'spend')
            
            if not amount:
                return Response(
                    {'error': 'Amount is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = BillingService.update_credit_available(
                billing_profile.id,
                amount,
                transaction_type
            )
            
            if success:
                response_serializer = BillingProfileDetailSerializer(billing_profile)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to update credit available'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating credit available: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get billing summary for advertiser."""
        try:
            if not hasattr(request.user, 'advertiser'):
                return Response(
                    {'error': 'User is not associated with an advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            summary = BillingService.get_billing_summary(request.user.advertiser.id)
            return Response(summary)
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting billing summary: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet for managing payment methods."""
    
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['billing_profile', 'method_type', 'status', 'is_default']
    search_fields = ['method_name', 'cardholder_name', 'paypal_email']
    ordering_fields = ['created_at', 'method_name', 'is_default']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show methods from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(billing_profile__advertiser=self.request.user.advertiser)
            else:
                # Other users see no methods
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new payment method."""
        try:
            # Add billing profile ID to data if not present
            if hasattr(request.user, 'advertiser'):
                billing_profile = request.user.advertiser.get_billing_profile()
                if billing_profile:
                    request.data['billing_profile'] = billing_profile.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            payment_method = PaymentService.create_payment_method(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = PaymentMethodDetailSerializer(payment_method)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating payment method: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update payment method."""
        try:
            payment_method = self.get_object()
            
            serializer = self.get_serializer(payment_method, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_method = PaymentService.update_payment_method(
                payment_method.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = PaymentMethodDetailSerializer(updated_method)
            return Response(response_serializer.data)
            
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating payment method: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify payment method."""
        try:
            payment_method = self.get_object()
            
            success = PaymentService.verify_payment_method(
                payment_method.id,
                verified_by=request.user
            )
            
            if success:
                response_serializer = PaymentMethodDetailSerializer(payment_method)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to verify payment method'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error verifying payment method: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def process_payment(self, request):
        """Process payment transaction."""
        try:
            payment_data = request.data
            
            # Add advertiser ID if not present
            if hasattr(request.user, 'advertiser'):
                payment_data['advertiser_id'] = request.user.advertiser.id
            
            result = PaymentService.process_payment(
                payment_data,
                processed_by=request.user
            )
            
            return Response(result)
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def by_profile(self, request):
        """Get payment methods by billing profile."""
        try:
            billing_profile_id = request.query_params.get('billing_profile_id')
            
            if not billing_profile_id:
                if hasattr(request.user, 'advertiser'):
                    billing_profile = request.user.advertiser.get_billing_profile()
                    if billing_profile:
                        billing_profile_id = billing_profile.id
            
            if not billing_profile_id:
                return Response(
                    {'error': 'billing_profile_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            payment_methods = PaymentService.get_payment_methods_by_profile(UUID(billing_profile_id))
            serializer = PaymentMethodDetailSerializer(payment_methods, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting payment methods by profile: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get default payment method for advertiser."""
        try:
            if not hasattr(request.user, 'advertiser'):
                return Response(
                    {'error': 'User is not associated with an advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            billing_profile = request.user.advertiser.get_billing_profile()
            if not billing_profile:
                return Response(
                    {'error': 'No billing profile found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            default_method = PaymentService.get_default_payment_method(billing_profile.id)
            if default_method:
                serializer = PaymentMethodDetailSerializer(default_method)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'No default payment method found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Error getting default payment method: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing invoices."""
    
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'billing_profile', 'status', 'currency']
    search_fields = ['invoice_number', 'recipient_name', 'recipient_email']
    ordering_fields = ['created_at', 'invoice_number', 'due_date', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show invoices from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no invoices
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new invoice."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
                billing_profile = request.user.advertiser.get_billing_profile()
                if billing_profile:
                    request.data['billing_profile'] = billing_profile.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            invoice = InvoiceService.create_invoice(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = InvoiceDetailSerializer(invoice)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update invoice."""
        try:
            invoice = self.get_object()
            
            serializer = self.get_serializer(invoice, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_invoice = InvoiceService.update_invoice(
                invoice.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = InvoiceDetailSerializer(updated_invoice)
            return Response(response_serializer.data)
            
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating invoice: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send invoice to recipient."""
        try:
            invoice = self.get_object()
            
            success = InvoiceService.send_invoice(
                invoice.id,
                sent_by=request.user
            )
            
            if success:
                response_serializer = InvoiceDetailSerializer(invoice)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to send invoice'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error sending invoice: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid."""
        try:
            invoice = self.get_object()
            
            payment_transaction_id = request.data.get('payment_transaction_id')
            if payment_transaction_id:
                payment_transaction_id = UUID(payment_transaction_id)
            
            success = InvoiceService.mark_as_paid(
                invoice.id,
                payment_transaction_id,
                paid_by=request.user
            )
            
            if success:
                response_serializer = InvoiceDetailSerializer(invoice)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to mark invoice as paid'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except BillingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error marking invoice as paid: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get invoice summary."""
        try:
            invoice = self.get_object()
            summary = InvoiceService.get_invoice_summary(invoice.id)
            return Response(summary)
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting invoice summary: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing payment transactions."""
    
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'billing_profile', 'payment_method', 'status', 'transaction_type']
    search_fields = ['transaction_id', 'gateway_transaction_id']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show transactions from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no transactions
                queryset = queryset.none()
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get transaction summary."""
        try:
            transaction = self.get_object()
            summary = TransactionService.get_transaction_summary(transaction.id)
            return Response(summary)
            
        except BillingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting transaction summary: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingAlertViewSet(viewsets.ViewSet):
    """ViewSet for managing billing alerts."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Get billing alerts for advertiser."""
        try:
            if not hasattr(request.user, 'advertiser'):
                return Response(
                    {'error': 'User is not associated with an advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get billing alerts
            alerts = []
            
            # Check credit limit
            billing_profile = request.user.advertiser.get_billing_profile()
            if billing_profile and billing_profile.credit_available < 0:
                alerts.append({
                    'type': 'credit_limit_exceeded',
                    'severity': 'high',
                    'message': f'Credit limit exceeded. Available: ${billing_profile.credit_available}',
                    'created_at': timezone.now().isoformat()
                })
            
            # Check auto-charge threshold
            if billing_profile and billing_profile.auto_charge and billing_profile.auto_charge_threshold > 0:
                credit_utilization = (billing_profile.credit_limit - billing_profile.credit_available) / billing_profile.credit_limit * 100
                if credit_utilization >= billing_profile.auto_charge_threshold:
                    alerts.append({
                        'type': 'auto_charge_threshold',
                        'severity': 'medium',
                        'message': f'Auto-charge threshold reached. Credit utilization: {credit_utilization:.1f}%',
                        'created_at': timezone.now().isoformat()
                    })
            
            # Check overdue invoices
            overdue_invoices = Invoice.objects.filter(
                advertiser=request.user.advertiser,
                status='sent',
                due_date__lt=timezone.now().date()
            ).count()
            
            if overdue_invoices > 0:
                alerts.append({
                    'type': 'overdue_invoices',
                    'severity': 'high',
                    'message': f'You have {overdue_invoices} overdue invoice(s)',
                    'created_at': timezone.now().isoformat()
                })
            
            return Response({
                'alerts': alerts,
                'has_alerts': len(alerts) > 0
            })
            
        except Exception as e:
            logger.error(f"Error getting billing alerts: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
