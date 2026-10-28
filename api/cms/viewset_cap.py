from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewset_cap.py
"""CPAlead Publisher (CAP) ViewSets — offerwall, postback test, publisher stats."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from .viewsets.cms_viewset_base import CMSViewSetMixin, CMSSmallPagination
from .throttling import CMSPostbackThrottle


class CAPPublisherViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    CPAlead Publisher stats and tools.
    GET /api/cms/publisher/stats/        — Publisher revenue stats
    GET /api/cms/publisher/conversions/  — Conversion breakdown
    GET /api/cms/publisher/offers/       — Available offers
    POST /api/cms/publisher/test_postback/ — Test postback (sandbox)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = CMSSmallPagination

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.models_new.cpalead import ConversionLog, ClickLog, OfferWallConfig
        from django.db.models import Sum, Count, Q, Avg
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timedelta(days=days)

        conv_stats = ConversionLog.objects.filter(created_at__gte=cutoff).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status__in=['rejected','fraud','duplicate'])),
            total_payout=Sum('payout_usd', filter=Q(status='approved')),
            avg_payout=Avg('payout_usd', filter=Q(status='approved')),
        )
        click_stats = ClickLog.objects.filter(created_at__gte=cutoff).aggregate(
            total_clicks=Count('id'),
            converted=Count('id', filter=Q(has_converted=True)),
            fraud_clicks=Count('id', filter=Q(is_fraud=True)),
        )
        conversion_rate = 0
        if click_stats['total_clicks']:
            conversion_rate = round(
                click_stats['converted'] / click_stats['total_clicks'] * 100, 2
            )
        return Response({
            'period_days': days,
            'conversions': {
                'total': conv_stats['total'] or 0,
                'approved': conv_stats['approved'] or 0,
                'rejected': conv_stats['rejected'] or 0,
                'approval_rate': round((conv_stats['approved'] or 0) /
                                       max(conv_stats['total'] or 1, 1) * 100, 1),
                'total_payout_usd': float(conv_stats['total_payout'] or 0),
                'avg_payout_usd': float(conv_stats['avg_payout'] or 0),
            },
            'clicks': {
                'total': click_stats['total_clicks'] or 0,
                'converted': click_stats['converted'] or 0,
                'fraud': click_stats['fraud_clicks'] or 0,
                'conversion_rate_pct': conversion_rate,
            },
        })

    @action(detail=False, methods=['get'])
    def top_offers(self, request):
        from api.cms.models_new.cpalead import ConversionLog
        from django.db.models import Count, Sum
        top = (ConversionLog.objects
               .filter(status='approved')
               .values('campaign_id')
               .annotate(count=Count('id'), total=Sum('payout_usd'))
               .order_by('-total')[:10])
        return Response(list(top))

    @action(detail=False, methods=['post'])
    def test_postback(self, request):
        """
        Test CPAlead postback in sandbox mode.
        Does NOT award real coins — just validates the postback flow.
        """
        DataValidator = None
        try:
            from api.cms.INTEGRATION_SYSTEM.data_validator import DataValidator
        except ImportError:
            pass
        import uuid
        data = {
            'subid': str(request.user.id),
            'payout': request.data.get('payout', '0.50'),
            'lead_id': f"TEST_{uuid.uuid4().hex[:8]}",
            'password': request.data.get('password', ''),
            'campaign_id': request.data.get('campaign_id', 'TEST'),
        }
        cleaned, errors = DataValidator.validate_cpalead_postback(data)
        if errors:
            return Response({'valid': False, 'errors': errors}, status=400)
        return Response({
            'valid': True,
            'message': 'Postback validation successful (sandbox — no coins awarded)',
            'params_received': {k: v for k, v in cleaned.items() if k != 'password'},
            'postback_url_format': (
                'https://yoursite.com/api/cms/webhooks/cpalead/'
                '?subid={subid}&payout={payout}&lead_id={lead_id}&password={password}'
            ),
        })


class CAPOfferwallViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    Offerwall management ViewSet.
    GET /api/cms/offerwall-admin/configs/   — List configs (admin)
    POST /api/cms/offerwall-admin/sync/     — Force sync offer cache
    GET /api/cms/offerwall-admin/embed-code/ — Get embed code
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def configs(self, request):
        from api.cms.models_new.cpalead import OfferWallConfig
        configs = OfferWallConfig.objects.select_related('currency').all()
        return Response([{
            'id': c.id, 'name': c.name, 'offerwall_title': c.offerwall_title,
            'publisher_id': c.publisher_id, 'is_active': c.is_active,
            'currency_name': c.currency if c.currency else 'Coins',
            'total_views': c.total_views, 'total_completions': c.total_completions,
        } for c in configs])

    @action(detail=False, methods=['post'])
    def sync(self, request):
        from api.cms.services_new.CPALeadService import CPALeadService
        ip = request.data.get('test_ip', '8.8.8.8')
        offers = CPALeadService.fetch_offers(user_ip=ip, limit=100)
        return Response({
            'synced': len(offers),
            'message': f'Synced {len(offers)} offers to cache',
        })

    @action(detail=False, methods=['get'])
    def embed_code(self, request):
        from api.cms.services_new.CPALeadService import CPALeadService
        data = CPALeadService.generate_offerwall_embed(user=request.user)
        return Response(data)
