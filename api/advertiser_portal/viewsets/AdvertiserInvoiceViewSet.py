"""
Advertiser Invoice ViewSet

ViewSet for advertiser invoice management,
including listing and PDF download.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse
from django.core.files.storage import default_storage

from ..models.billing import AdvertiserInvoice
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
from ..serializers import AdvertiserInvoiceSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser invoice management.
    
    Handles invoice listing, viewing, and PDF download.
    """
    
    queryset = AdvertiserInvoice.objects.all()
    serializer_class = AdvertiserInvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all invoices
            return AdvertiserInvoice.objects.all()
        else:
            # Advertisers can only see their own invoices
            return AdvertiserInvoice.objects.filter(advertiser__user=user)
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """
        Download invoice PDF.
        
        Generates and returns PDF file for the invoice.
        """
        invoice = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or invoice.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Generate PDF content
            pdf_content = self._generate_invoice_pdf(invoice)
            
            # Create response
            response = HttpResponse(
                pdf_content,
                content_type='application/pdf'
            )
            
            filename = f"invoice_{invoice.invoice_number}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(pdf_content)
            
            return response
            
        except Exception as e:
            logger.error(f"Error downloading invoice PDF: {e}")
            return Response(
                {'detail': 'Failed to download invoice PDF'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get invoice preview.
        
        Returns invoice details and preview information.
        """
        invoice = self.get_object()
        
        try:
            preview_data = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'advertiser_id': invoice.advertiser.id,
                'advertiser_name': invoice.advertiser.company_name,
                'period': invoice.period,
                'start_date': invoice.start_date.isoformat(),
                'end_date': invoice.end_date.isoformat(),
                'subtotal': float(invoice.subtotal),
                'tax_amount': float(invoice.tax_amount),
                'fee_amount': float(invoice.fee_amount),
                'total_amount': float(invoice.total_amount),
                'currency': invoice.currency,
                'status': invoice.status,
                'due_date': invoice.due_date.isoformat(),
                'created_at': invoice.created_at.isoformat(),
                'updated_at': invoice.updated_at.isoformat(),
                'sent_at': invoice.sent_at.isoformat() if invoice.sent_at else None,
                'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
                'file_path': invoice.file_path,
                'metadata': invoice.metadata,
            }
            
            return Response(preview_data)
            
        except Exception as e:
            logger.error(f"Error getting invoice preview: {e}")
            return Response(
                {'detail': 'Failed to get invoice preview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """
        Mark invoice as paid.
        
        Only staff members can mark invoices as paid.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        invoice = self.get_object()
        
        if invoice.status == 'paid':
            return Response(
                {'detail': 'Invoice is already marked as paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method')
        payment_reference = request.data.get('payment_reference')
        notes = request.data.get('notes', '')
        
        try:
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
            
            # Update metadata with payment information
            metadata = invoice.metadata or {}
            metadata['payment_info'] = {
                'payment_method': payment_method,
                'payment_reference': payment_reference,
                'paid_by': request.user.id,
                'notes': notes,
            }
            invoice.metadata = metadata
            
            invoice.save()
            
            return Response({
                'detail': 'Invoice marked as paid successfully',
                'status': invoice.status,
                'paid_at': invoice.paid_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error marking invoice as paid: {e}")
            return Response(
                {'detail': 'Failed to mark invoice as paid'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def send_invoice(self, request, pk=None):
        """
        Send invoice to advertiser.
        
        Triggers invoice delivery via email.
        """
        invoice = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or invoice.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # This would implement actual invoice sending
            # For now, just update the sent timestamp
            invoice.sent_at = timezone.now()
            invoice.save()
            
            return Response({
                'detail': 'Invoice sent successfully',
                'sent_at': invoice.sent_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error sending invoice: {e}")
            return Response(
                {'detail': 'Failed to send invoice'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def regenerate_pdf(self, request, pk=None):
        """
        Regenerate invoice PDF.
        
        Creates new PDF file for the invoice.
        """
        invoice = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or invoice.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Generate new PDF
            pdf_content = self._generate_invoice_pdf(invoice)
            
            # Save PDF file
            filename = f"invoice_{invoice.invoice_number}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            file_path = f"invoices/{invoice.advertiser.id}/{filename}"
            
            # Save to storage
            from django.core.files.base import ContentFile
            invoice.file_path.save(file_path, ContentFile(pdf_content))
            
            return Response({
                'detail': 'Invoice PDF regenerated successfully',
                'file_path': invoice.file_path.name
            })
            
        except Exception as e:
            logger.error(f"Error regenerating invoice PDF: {e}")
            return Response(
                {'detail': 'Failed to regenerate invoice PDF'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def invoice_history(self, request):
        """
        Get invoice history for advertiser.
        
        Returns list of invoices with filtering.
        """
        try:
            billing_service = AdvertiserBillingService()
            
            filters = {}
            
            # Apply filters from query parameters
            status = request.query_params.get('status')
            period = request.query_params.get('period')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            min_amount = request.query_params.get('min_amount')
            max_amount = request.query_params.get('max_amount')
            
            if status:
                filters['status'] = status
            if period:
                filters['period'] = period
            if date_from:
                filters['date_from'] = date_from
            if date_to:
                filters['date_to'] = date_to
            if min_amount:
                filters['min_amount'] = float(min_amount)
            if max_amount:
                filters['max_amount'] = float(max_amount)
            
            invoices = billing_service.get_invoice_history(request.user.advertiser, filters)
            
            serializer = self.get_serializer(invoices, many=True)
            
            return Response({
                'invoices': serializer.data,
                'count': len(invoices),
                'filters': filters
            })
            
        except Exception as e:
            logger.error(f"Error getting invoice history: {e}")
            return Response(
                {'detail': 'Failed to get invoice history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def outstanding_invoices(self, request):
        """
        Get outstanding invoices.
        
        Returns list of unpaid invoices.
        """
        try:
            outstanding_invoices = AdvertiserInvoice.objects.filter(
                advertiser=request.user.advertiser,
                status__in=['sent', 'overdue']
            ).order_by('-due_date')
            
            serializer = self.get_serializer(outstanding_invoices, many=True)
            
            return Response({
                'outstanding_invoices': serializer.data,
                'count': outstanding_invoices.count(),
                'total_outstanding': float(
                    outstanding_invoices.aggregate(
                        total=models.Sum('total_amount')
                    )['total'] or 0
                )
            })
            
        except Exception as e:
            logger.error(f"Error getting outstanding invoices: {e}")
            return Response(
                {'detail': 'Failed to get outstanding invoices'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def invoice_summary(self, request):
        """
        Get invoice summary.
        
        Returns financial summary of invoices.
        """
        try:
            days = int(request.query_params.get('days', 90))
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            invoices = AdvertiserInvoice.objects.filter(
                advertiser=request.user.advertiser,
                created_at__gte=start_date
            )
            
            summary = invoices.aggregate(
                total_invoices=models.Count('id'),
                total_invoiced=models.Sum('total_amount'),
                total_paid=models.Sum(
                    models.Case(
                        When(status='paid', then=models.F('total_amount')),
                        default=0,
                    )
                ),
                total_outstanding=models.Sum(
                    models.Case(
                        When(status__in=['sent', 'overdue'], then=models.F('total_amount')),
                        default=0,
                    )
                )
            )
            
            # Fill missing values
            for key, value in summary.items():
                if value is None:
                    summary[key] = 0
            
            # Get status breakdown
            status_breakdown = invoices.values('status').annotate(
                count=models.Count('id'),
                amount=models.Sum('total_amount')
            ).order_by('-amount')
            
            # Get monthly breakdown
            monthly_breakdown = invoices.extra(
                select={'month': 'strftime("%%Y-%%m", created_at)'}
            ).values('month').annotate(
                count=models.Count('id'),
                amount=models.Sum('total_amount')
            ).order_by('month')
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': timezone.now().date().isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_invoices': summary['total_invoices'],
                    'total_invoiced': float(summary['total_invoiced']),
                    'total_paid': float(summary['total_paid']),
                    'total_outstanding': float(summary['total_outstanding']),
                    'payment_rate': float((summary['total_paid'] / summary['total_invoiced'] * 100) if summary['total_invoiced'] > 0 else 0),
                },
                'status_breakdown': [
                    {
                        'status': item['status'],
                        'count': item['count'],
                        'amount': float(item['amount']),
                    }
                    for item in status_breakdown
                ],
                'monthly_breakdown': [
                    {
                        'month': item['month'],
                        'count': item['count'],
                        'amount': float(item['amount']),
                    }
                    for item in monthly_breakdown
                ],
            })
            
        except Exception as e:
            logger.error(f"Error getting invoice summary: {e}")
            return Response(
                {'detail': 'Failed to get invoice summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def invoice_periods(self, request):
        """
        Get available invoice periods.
        
        Returns list of supported billing periods.
        """
        try:
            periods = {
                'daily': {
                    'name': 'Daily',
                    'description': 'Daily billing',
                    'common_for': 'High-volume accounts',
                },
                'weekly': {
                    'name': 'Weekly',
                    'description': 'Weekly billing',
                    'common_for': 'Medium-volume accounts',
                },
                'bi_weekly': {
                    'name': 'Bi-Weekly',
                    'description': 'Bi-weekly billing',
                    'common_for': 'Regular billing cycles',
                },
                'monthly': {
                    'name': 'Monthly',
                    'description': 'Monthly billing',
                    'common_for': 'Standard accounts',
                },
                'quarterly': {
                    'name': 'Quarterly',
                    'description': 'Quarterly billing',
                    'common_for': 'Enterprise accounts',
                },
                'yearly': {
                    'name': 'Yearly',
                    'description': 'Yearly billing',
                    'common_for': 'Annual contracts',
                },
            }
            
            return Response(periods)
            
        except Exception as e:
            logger.error(f"Error getting invoice periods: {e}")
            return Response(
                {'detail': 'Failed to get invoice periods'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def generate_invoice(self, request):
        """
        Generate new invoice.
        
        Creates invoice for specified period.
        """
        try:
            billing_service = AdvertiserBillingService()
            
            period = request.data.get('period')
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            items = request.data.get('items', [])
            
            if not all([period, start_date, end_date]):
                return Response(
                    {'detail': 'Period, start date, and end date are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Convert dates
            if isinstance(start_date, str):
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if isinstance(end_date, str):
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            
            invoice = billing_service.create_invoice(
                request.user.advertiser,
                period,
                start_date,
                end_date,
                items
            )
            
            serializer = self.get_serializer(invoice)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error generating invoice: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_invoice_pdf(self, invoice):
        """
        Generate PDF content for invoice.
        
        This would implement actual PDF generation using a library
        like ReportLab or WeasyPrint.
        """
        # This is a placeholder implementation
        # In a real implementation, you would:
        # 1. Use a PDF generation library
        # 2. Create a template with invoice details
        # 3. Include company information, line items, totals
        # 4. Add proper formatting and styling
        # 5. Return the PDF bytes
        
        # For now, return a simple PDF content
        from io import BytesIO
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Add invoice header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, f"INVOICE #{invoice.invoice_number}")
        
        # Add advertiser information
        p.setFont("Helvetica", 12)
        p.drawString(100, 720, f"Bill To: {invoice.advertiser.company_name}")
        p.drawString(100, 700, f"Period: {invoice.period}")
        p.drawString(100, 680, f"Date: {invoice.created_at.strftime('%B %d, %Y')}")
        
        # Add totals
        p.setFont("Helvetica-Bold", 12)
        p.drawString(400, 600, f"Subtotal: ${invoice.subtotal:.2f}")
        p.drawString(400, 580, f"Tax: ${invoice.tax_amount:.2f}")
        p.drawString(400, 560, f"Fee: ${invoice.fee_amount:.2f}")
        p.drawString(400, 540, f"Total: ${invoice.total_amount:.2f}")
        
        p.save()
        
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        status = request.query_params.get('status')
        period = request.query_params.get('period')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        min_amount = request.query_params.get('min_amount')
        max_amount = request.query_params.get('max_amount')
        search = request.query_params.get('search')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if period:
            queryset = queryset.filter(period=period)
        
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(end_date__lte=date_to)
        
        if min_amount:
            queryset = queryset.filter(total_amount__gte=float(min_amount))
        
        if max_amount:
            queryset = queryset.filter(total_amount__lte=float(max_amount))
        
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(advertiser__company_name__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
