# api/payment_gateways/tracking/views.py
# Tracking endpoints: postback receiver, click redirect, stats API

from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.views import BaseViewSet
from .models import Click, Conversion, PostbackLog, PublisherDailyStats
from .serializers import (ClickSerializer, ConversionSerializer,
                           PostbackLogSerializer, PublisherStatsSerializer)
from .PostbackEngine import PostbackEngine
from .ClickTracker import ClickTracker


# ── Postback receiver ────────────────────────────────────────────────────────
@csrf_exempt
@require_http_methods(['GET', 'POST'])
def postback(request, offer_id=None):
    """
    S2S Postback endpoint.
    Advertiser fires this URL after a conversion.

    GET /tracking/postback/?click_id={click_id}&payout={payout}&status=approved

    Standard params:
        click_id  — Our tracking ID (required)
        payout    — Publisher payout amount (optional, uses offer default)
        cost      — Advertiser cost (optional)
        status    — approved | rejected | pending (default: approved)
        order_id  — Advertiser's order/transaction ID
        sale_amount — Actual sale value (for CPS offers)
    """
    params     = request.GET.dict() if request.method == 'GET' else {**request.GET.dict(), **request.POST.dict()}
    raw_url    = request.build_absolute_uri()
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                 or request.META.get('REMOTE_ADDR', '')

    engine = PostbackEngine()
    result = engine.process(params, raw_url, ip_address)

    if result['success']:
        return HttpResponse('OK', status=200)
    return HttpResponse(result['message'], status=400)


# ── Click redirect ────────────────────────────────────────────────────────────
def click_redirect(request, offer_id):
    """
    Publisher click tracking redirect.
    Publisher sends traffic to: /tracking/click/{offer_id}/?sub1=xxx&sub2=yyy

    Records click → redirects to advertiser URL with click_id appended.
    """
    from offers.models import Offer

    try:
        offer = Offer.objects.get(id=offer_id, status='active')
    except Exception:
        return HttpResponse('Offer not found', status=404)

    publisher = request.user if request.user.is_authenticated else None
    if not publisher:
        return HttpResponse('Authentication required', status=401)

    extra = {
        'sub1':       request.GET.get('sub1', ''),
        'sub2':       request.GET.get('sub2', ''),
        'sub3':       request.GET.get('sub3', ''),
        'sub4':       request.GET.get('sub4', ''),
        'sub5':       request.GET.get('sub5', ''),
        'traffic_id': request.GET.get('traffic_id', ''),
    }

    tracker = ClickTracker()
    click, redirect_url = tracker.track(offer, publisher, request, extra)

    return HttpResponseRedirect(redirect_url)


# ── Stats API ─────────────────────────────────────────────────────────────────
class ClickViewSet(BaseViewSet):
    """Admin: view all clicks with filtering."""
    queryset           = Click.objects.all().order_by('-created_at')
    serializer_class   = ClickSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['offer', 'publisher', 'is_converted', 'is_fraud',
                          'country_code', 'device_type']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(publisher=self.request.user)


class ConversionViewSet(BaseViewSet):
    """Conversion management."""
    queryset           = Conversion.objects.all().order_by('-created_at')
    serializer_class   = ConversionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['status', 'offer', 'publisher', 'conversion_type', 'publisher_paid']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(publisher=self.request.user)

    def perform_update(self, serializer):
        """Admin: approve/reject conversions."""
        if 'status' in serializer.validated_data:
            if serializer.validated_data['status'] == 'approved':
                serializer.save(approved_by=self.request.user, approved_at=timezone.now())
            else:
                serializer.save()
        else:
            serializer.save()


class PostbackLogViewSet(BaseViewSet):
    """Admin: postback log viewer."""
    queryset           = PostbackLog.objects.all().order_by('-created_at')
    serializer_class   = PostbackLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status', 'offer']


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_stats(request):
    """
    Publisher real-time earnings stats.

    GET /tracking/stats/?days=7&offer_id=1
    """
    days     = int(request.GET.get('days', 7))
    offer_id = request.GET.get('offer_id')
    since    = timezone.now().date() - timedelta(days=days)

    from django.db.models import Sum, Count

    qs = PublisherDailyStats.objects.filter(
        publisher=request.user,
        date__gte=since,
    )
    if offer_id:
        qs = qs.filter(offer_id=offer_id)

    agg = qs.aggregate(
        total_clicks=Sum('clicks'),
        total_conversions=Sum('conversions'),
        total_revenue=Sum('revenue'),
        total_impressions=Sum('impressions'),
    )

    # Today's numbers from live DB
    today = timezone.now().date()
    today_clicks = Click.objects.filter(
        publisher=request.user,
        created_at__date=today,
        is_bot=False,
    ).count()
    today_revenue = Conversion.objects.filter(
        publisher=request.user,
        status='approved',
        created_at__date=today,
    ).aggregate(r=Sum('payout'))['r'] or Decimal('0')

    # Daily breakdown
    daily = list(qs.values('date').annotate(
        clicks=Sum('clicks'),
        conversions=Sum('conversions'),
        revenue=Sum('revenue'),
    ).order_by('date'))

    return Response({
        'success': True,
        'data': {
            'period_days':         days,
            'total_clicks':        agg['total_clicks'] or 0,
            'total_conversions':   agg['total_conversions'] or 0,
            'total_revenue':       float(agg['total_revenue'] or 0),
            'total_impressions':   agg['total_impressions'] or 0,
            'today_clicks':        today_clicks,
            'today_revenue':       float(today_revenue),
            'ctr': round(
                (agg['total_clicks'] or 0) / max(agg['total_impressions'] or 1, 1) * 100, 2
            ),
            'cr': round(
                (agg['total_conversions'] or 0) / max(agg['total_clicks'] or 1, 1) * 100, 2
            ),
            'daily': daily,
        }
    })
