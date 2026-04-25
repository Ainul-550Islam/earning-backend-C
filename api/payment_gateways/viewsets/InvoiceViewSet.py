# api/payment_gateways/viewsets/InvoiceViewSet.py
# Advertiser invoice generation

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from rest_framework import serializers


class InvoiceSerializer(serializers.Serializer):
    invoice_number   = serializers.CharField()
    advertiser_email = serializers.EmailField()
    period           = serializers.CharField()
    total_spend      = serializers.FloatField()
    total_conversions= serializers.IntegerField()
    gateway_breakdown= serializers.DictField()
    issued_at        = serializers.DateTimeField()


class InvoiceViewSet(BaseViewSet):
    """
    Advertiser invoice generation and management.
    Generates detailed invoices for campaign spend.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List invoices for current advertiser."""
        from django.utils import timezone
        from datetime import timedelta
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum, Count

        months = []
        now = timezone.now()
        for i in range(6):
            month_start = (now.replace(day=1) - timedelta(days=i*30)).replace(
                day=1, hour=0, minute=0, second=0
            )
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

            agg = Conversion.objects.filter(
                advertiser=request.user,
                status='approved',
                created_at__gte=month_start,
                created_at__lte=month_end,
            ).aggregate(spend=Sum('cost'), convs=Count('id'))

            if agg['spend']:
                months.append({
                    'period':          month_start.strftime('%B %Y'),
                    'total_spend':     float(agg['spend'] or 0),
                    'total_conversions': agg['convs'],
                    'invoice_url':     f'/api/payment/invoices/generate/?period={month_start.strftime("%Y-%m")}',
                })

        return self.success_response(data=months)

    @action(detail=False, methods=['get'])
    def generate(self, request):
        """Generate a detailed invoice for a specific period."""
        from django.utils import timezone
        from datetime import datetime
        from api.payment_gateways.tracking.models import Conversion
        from api.payment_gateways.services.ReceiptGenerator import ReceiptGenerator
        from django.db.models import Sum, Count

        period = request.GET.get('period', timezone.now().strftime('%Y-%m'))
        try:
            year, month = map(int, period.split('-'))
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end = datetime(year+1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(year, month+1, 1, tzinfo=timezone.utc)
        except Exception:
            return self.error_response(message='Invalid period format. Use YYYY-MM', status_code=400)

        convs = Conversion.objects.filter(
            advertiser=request.user,
            status='approved',
            created_at__gte=start, created_at__lt=end,
        )
        agg = convs.aggregate(spend=Sum('cost'), convs=Count('id'))

        # By gateway
        by_gateway = {}
        for c in convs.values('offer__payout_model').annotate(
            spend=Sum('cost'), count=Count('id')
        ):
            key = c.get('offer__payout_model', 'cpa')
            by_gateway[key] = {
                'spend': float(c['spend'] or 0),
                'conversions': c['count'],
            }

        gen = ReceiptGenerator()
        invoice = {
            'invoice_number':   f'INV-{request.user.id}-{period}',
            'advertiser_email': request.user.email,
            'company':          gen.COMPANY_INFO,
            'period':           period,
            'period_start':     start.date().isoformat(),
            'period_end':       (end - timezone.timedelta(seconds=1)).date().isoformat(),
            'total_spend':      float(agg['spend'] or 0),
            'total_conversions':agg['convs'],
            'gateway_breakdown':by_gateway,
            'issued_at':        timezone.now().isoformat(),
            'due_date':         (timezone.now() + timezone.timedelta(days=30)).date().isoformat(),
            'status':           'paid',
        }

        return self.success_response(data=invoice)
