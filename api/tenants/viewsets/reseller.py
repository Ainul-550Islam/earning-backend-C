"""
Reseller Viewsets

This module contains viewsets for reseller-related models including
ResellerConfig and ResellerInvoice.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models.reseller import ResellerConfig, ResellerInvoice
from ..serializers.reseller import (
    ResellerConfigSerializer, ResellerConfigCreateSerializer,
    ResellerInvoiceSerializer
)


class ResellerConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reseller configurations.
    """
    serializer_class = ResellerConfigSerializer
    queryset = ResellerConfig.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['parent_tenant', 'status', 'commission_type', 'support_level']
    search_fields = ['company_name', 'contact_email', 'reseller_id']
    ordering_fields = ['company_name', 'created_at']
    ordering = ['company_name']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ResellerConfigCreateSerializer
        return ResellerConfigSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        if self.request.user.is_superuser:
            return ResellerConfig.objects.all()
        return ResellerConfig.objects.filter(parent_tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify reseller configuration."""
        reseller = self.get_object()
        
        if reseller.is_verified:
            return Response(
                {'error': 'Reseller is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reseller.is_verified = True
        reseller.verified_at = timezone.now()
        reseller.save(update_fields=['is_verified', 'verified_at'])
        
        return Response({'message': 'Reseller verified successfully'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate reseller."""
        reseller = self.get_object()
        
        if not reseller.is_verified:
            return Response(
                {'error': 'Reseller must be verified before activation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reseller.status = 'active'
        reseller.save(update_fields=['status'])
        
        return Response({'message': 'Reseller activated successfully'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate reseller."""
        reseller = self.get_object()
        reseller.status = 'inactive'
        reseller.save(update_fields=['status'])
        
        return Response({'message': 'Reseller deactivated successfully'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def complete_training(self, request, pk=None):
        """Mark training as completed."""
        reseller = self.get_object()
        
        if not reseller.training_required:
            return Response(
                {'error': 'Training is not required for this reseller'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reseller.training_completed_at = timezone.now()
        reseller.save(update_fields=['training_completed_at'])
        
        return Response({'message': 'Training marked as completed'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def referral_stats(self, request, pk=None):
        """Get referral statistics."""
        reseller = self.get_object()
        
        # Get child tenants
        from ..models import Tenant
        child_tenants = Tenant.objects.filter(parent_tenant=reseller.parent_tenant)
        
        stats = {
            'total_referrals': child_tenants.count(),
            'active_referrals': child_tenants.filter(status='active').count(),
            'trial_referrals': child_tenants.filter(status='trial').count(),
            'suspended_referrals': child_tenants.filter(status='suspended').count(),
            'referral_details': [
                {
                    'id': str(tenant.id),
                    'name': tenant.name,
                    'status': tenant.status,
                    'created_at': tenant.created_at,
                    'plan': tenant.plan.name if tenant.plan else None,
                }
                for tenant in child_tenants.order_by('-created_at')
            ]
        }
        
        return Response(stats, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def commission_summary(self, request, pk=None):
        """Get commission summary."""
        reseller = self.get_object()
        
        # Get all invoices for this reseller's referrals
        from ..models import Tenant
        child_tenants = Tenant.objects.filter(parent_tenant=reseller.parent_tenant)
        
        invoices = ResellerInvoice.objects.filter(
            reseller=reseller
        )
        
        summary = {
            'total_commission_earned': reseller.total_commission_earned,
            'total_invoices': invoices.count(),
            'paid_invoices': invoices.filter(status='paid').count(),
            'pending_invoices': invoices.filter(status='pending').count(),
            'overdue_invoices': invoices.filter(status='overdue').count(),
            'recent_invoices': [
                {
                    'id': str(invoice.id),
                    'invoice_number': invoice.invoice_number,
                    'period_start': invoice.period_start,
                    'period_end': invoice.period_end,
                    'commission_amount': float(invoice.commission_amount),
                    'total_amount': float(invoice.total_amount),
                    'status': invoice.status,
                }
                for invoice in invoices.order_by('-created_at')[:10]
            ]
        }
        
        return Response(summary, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def calculate_commission(self, request, pk=None):
        """Calculate commission for period."""
        reseller = self.get_object()
        
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        
        if not period_start or not period_end:
            return Response(
                {'error': 'period_start and period_end are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            period_start = datetime.fromisoformat(period_start.replace('Z', '+00:00')).date()
            period_end = datetime.fromisoformat(period_end.replace('Z', '+00:00')).date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # This would calculate actual commission based on referral activity
        # For now, return placeholder calculation
        commission_data = {
            'period_start': period_start,
            'period_end': period_end,
            'referral_count': 0,
            'commission_amount': 0.0,
            'details': []
        }
        
        return Response(commission_data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get reseller dashboard data."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get overall reseller statistics
        total_resellers = ResellerConfig.objects.count()
        active_resellers = ResellerConfig.objects.filter(status='active').count()
        verified_resellers = ResellerConfig.objects.filter(is_verified=True).count()
        
        # Commission statistics
        total_commission = ResellerConfig.objects.aggregate(
            total=models.Sum('total_commission_earned')
        )['total'] or 0
        
        dashboard = {
            'total_resellers': total_resellers,
            'active_resellers': active_resellers,
            'verified_resellers': verified_resellers,
            'total_commission_earned': float(total_commission),
            'by_status': {},
            'by_commission_type': {},
        }
        
        # By status
        from django.db.models import Count
        status_counts = ResellerConfig.objects.values('status').annotate(count=Count('id'))
        dashboard['by_status'] = {s['status']: s['count'] for s in status_counts}
        
        # By commission type
        commission_counts = ResellerConfig.objects.values('commission_type').annotate(count=Count('id'))
        dashboard['by_commission_type'] = {c['commission_type']: c['count'] for c in commission_counts}
        
        return Response(dashboard, status=status.HTTP_200_OK)


class ResellerInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reseller invoices.
    """
    serializer_class = ResellerInvoiceSerializer
    queryset = ResellerInvoice.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['reseller', 'status', 'period_start', 'period_end']
    search_fields = ['invoice_number', 'notes']
    ordering_fields = ['period_start', 'due_date', 'total_amount']
    ordering = ['-period_start']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        if self.request.user.is_superuser:
            return ResellerInvoice.objects.all()
        return ResellerInvoice.objects.filter(reseller__parent_tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve reseller invoice."""
        invoice = self.get_object()
        
        if invoice.status != 'pending':
            return Response(
                {'error': 'Invoice is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invoice.status = 'approved'
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save(update_fields=['status', 'approved_by', 'approved_at'])
        
        return Response({'message': 'Invoice approved'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject reseller invoice."""
        invoice = self.get_object()
        
        if invoice.status != 'pending':
            return Response(
                {'error': 'Invoice is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rejection_reason = request.data.get('rejection_reason')
        
        invoice.status = 'rejected'
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.rejection_reason = rejection_reason
        invoice.save(update_fields=['status', 'approved_by', 'approved_at', 'rejection_reason'])
        
        return Response({'message': 'Invoice rejected'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """Mark invoice as paid."""
        invoice = self.get_object()
        
        if invoice.status != 'approved':
            return Response(
                {'error': 'Invoice must be approved before marking as paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method')
        transaction_id = request.data.get('transaction_id')
        
        invoice.status = 'paid'
        invoice.paid_date = timezone.now()
        invoice.payment_method = payment_method
        invoice.transaction_id = transaction_id
        invoice.save(update_fields=['status', 'paid_date', 'payment_method', 'transaction_id'])
        
        return Response({'message': 'Invoice marked as paid'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def calculate_commission(self, request, pk=None):
        """Calculate commission details for invoice."""
        invoice = self.get_object()
        
        # This would calculate detailed commission breakdown
        # For now, return basic info
        commission_details = {
            'commission_amount': float(invoice.commission_amount),
            'bonus_amount': float(invoice.bonus_amount),
            'tax_amount': float(invoice.tax_amount),
            'total_amount': float(invoice.total_amount),
            'referral_count': invoice.referral_count,
            'active_referrals': invoice.active_referrals,
            'commission_rate': 0.0,  # Would calculate based on reseller config
            'details': []
        }
        
        return Response(commission_details, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def referral_details(self, request, pk=None):
        """Get referral details for invoice period."""
        invoice = self.get_object()
        
        # Get tenants that were referred during this period
        from ..models import Tenant
        referred_tenants = Tenant.objects.filter(
            parent_tenant=invoice.reseller.parent_tenant,
            created_at__date__gte=invoice.period_start,
            created_at__date__lte=invoice.period_end
        )
        
        details = {
            'period_start': invoice.period_start,
            'period_end': invoice.period_end,
            'referral_count': referred_tenants.count(),
            'referrals': [
                {
                    'id': str(tenant.id),
                    'name': tenant.name,
                    'email': tenant.contact_email,
                    'plan': tenant.plan.name if tenant.plan else None,
                    'created_at': tenant.created_at,
                    'status': tenant.status,
                }
                for tenant in referred_tenants.order_by('-created_at')
            ]
        }
        
        return Response(details, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get invoices pending approval."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset().filter(status='pending')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def commission_report(self, request):
        """Generate commission report."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        
        if period_start and period_end:
            try:
                from datetime import datetime
                period_start = datetime.fromisoformat(period_start.replace('Z', '+00:00')).date()
                period_end = datetime.fromisoformat(period_end.replace('Z', '+00:00')).date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Default to last month
            from datetime import timedelta
            end_date = timezone.now().date()
            start_date = end_date.replace(day=1) - timedelta(days=1)
            period_start = start_date.replace(day=1)
            period_end = end_date
        
        # Get invoices for the period
        invoices = ResellerInvoice.objects.filter(
            period_start__gte=period_start,
            period_end__lte=period_end
        )
        
        report = {
            'period_start': period_start,
            'period_end': period_end,
            'total_invoices': invoices.count(),
            'total_commission': float(invoices.aggregate(
                total=models.Sum('commission_amount')
            )['total'] or 0),
            'total_bonus': float(invoices.aggregate(
                total=models.Sum('bonus_amount')
            )['total'] or 0),
            'total_amount': float(invoices.aggregate(
                total=models.Sum('total_amount')
            )['total'] or 0),
            'by_status': {},
            'by_reseller': {},
        }
        
        # By status
        from django.db.models import Count
        status_counts = invoices.values('status').annotate(count=Count('id'))
        report['by_status'] = {s['status']: s['count'] for s in status_counts}
        
        # By reseller
        reseller_counts = invoices.values('reseller__company_name').annotate(
            count=Count('id'),
            commission=models.Sum('commission_amount'),
            total=models.Sum('total_amount')
        )
        report['by_reseller'] = {
            r['reseller__company_name']: {
                'count': r['count'],
                'commission': float(r['commission'] or 0),
                'total': float(r['total'] or 0)
            }
            for r in reseller_counts
        }
        
        return Response(report, status=status.HTTP_200_OK)
