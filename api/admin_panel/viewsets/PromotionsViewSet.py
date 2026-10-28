# api/admin_panel/viewsets/PromotionsViewSet.py
"""
PromotionsViewSet — Admin control for CPAlead-style offers, campaigns,
content locking, CPA/CPI/CPS/CPL offers, advertiser management.
"""
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class PromotionsAdminViewSet(viewsets.ViewSet):
    """
    Master admin control for the Promotions app.
    Controls: Offers, Categories, Advertisers, Traffic Caps, Conversions.
    """
    permission_classes = [IsAdminUser]

    # ==================== OFFERS ====================

    @action(detail=False, methods=['get'])
    def offers_overview(self, request):
        """Get all offers with status, type, payout summary."""
        try:
            from api.promotions.models import Offer
            from django.db.models import Count, Sum, Avg
            
            qs = Offer.objects.all()
            
            # Filters
            status_filter = request.query_params.get('status')
            offer_type = request.query_params.get('type')
            search = request.query_params.get('search')
            
            if status_filter:
                qs = qs.filter(status=status_filter)
            if offer_type:
                qs = qs.filter(offer_type=offer_type)
            if search:
                qs = qs.filter(
                    Q(title__icontains=search) | Q(advertiser__icontains=search)
                )
            
            stats = qs.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(status='active')),
                paused=Count('id', filter=Q(status='paused')),
                total_budget=Sum('budget'),
                avg_payout=Avg('payout'),
            )
            
            # Top offers by conversion
            top_offers = list(qs.order_by('-total_conversions')[:20].values(
                'id', 'title', 'offer_type', 'payout', 'status',
                'total_conversions', 'budget', 'daily_cap', 'created_at'
            ))
            
            return Response({
                'success': True,
                'stats': stats,
                'top_offers': top_offers,
            })
        except Exception as e:
            logger.error(f"offers_overview error: {e}")
            return Response({'success': True, 'stats': {}, 'top_offers': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def bulk_pause_offers(self, request):
        """Bulk pause offers by IDs or filter criteria."""
        try:
            from api.promotions.models import Offer
            ids = request.data.get('ids', [])
            offer_type = request.data.get('offer_type')
            
            qs = Offer.objects.filter(status='active')
            if ids:
                qs = qs.filter(pk__in=ids)
            if offer_type:
                qs = qs.filter(offer_type=offer_type)
            
            count = qs.update(status='paused')
            return Response({'success': True, 'paused': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def bulk_activate_offers(self, request):
        """Bulk activate offers."""
        try:
            from api.promotions.models import Offer
            ids = request.data.get('ids', [])
            qs = Offer.objects.filter(status='paused')
            if ids:
                qs = qs.filter(pk__in=ids)
            count = qs.update(status='active')
            return Response({'success': True, 'activated': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def offer_types_stats(self, request):
        """Stats breakdown by offer type: CPA, CPI, CPL, CPS, CPC."""
        try:
            from api.promotions.models import Offer
            breakdown = list(
                Offer.objects.values('offer_type').annotate(
                    count=Count('id'),
                    active=Count('id', filter=Q(status='active')),
                    total_payout=Sum('total_payout_amount'),
                ).order_by('-count')
            )
            return Response({'success': True, 'data': breakdown})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== TRAFFIC CAPS ====================

    @action(detail=False, methods=['get'])
    def traffic_caps(self, request):
        """View and manage daily/total traffic caps."""
        try:
            from api.promotions.models import Offer
            # Offers hitting their cap
            near_cap = list(
                Offer.objects.filter(
                    status='active',
                    daily_cap__gt=0
                ).filter(
                    today_conversions__gte=0.8 * models.F('daily_cap')
                ).values('id', 'title', 'daily_cap', 'today_conversions', 'payout')[:20]
            )
            return Response({'success': True, 'near_cap': near_cap})
        except Exception as e:
            return Response({'success': True, 'near_cap': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def reset_daily_caps(self, request):
        """Reset daily conversion counters (run at midnight)."""
        try:
            from api.promotions.models import Offer
            count = Offer.objects.filter(daily_cap__gt=0).update(today_conversions=0)
            cache.delete('admin_panel:traffic_caps')
            return Response({'success': True, 'reset': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== CONVERSIONS ====================

    @action(detail=False, methods=['get'])
    def conversion_stats(self, request):
        """Real-time conversion statistics."""
        try:
            from api.promotions.models import TaskSubmission as Conversion
            from django.db.models import Count, Sum
            
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            last_7d = timezone.now() - timedelta(days=7)
            
            stats = {
                'today': Conversion.objects.filter(created_at__date=today).aggregate(
                    count=Count('id'), revenue=Sum('payout')
                ),
                'yesterday': Conversion.objects.filter(created_at__date=yesterday).aggregate(
                    count=Count('id'), revenue=Sum('payout')
                ),
                'last_7d': Conversion.objects.filter(created_at__gte=last_7d).aggregate(
                    count=Count('id'), revenue=Sum('payout')
                ),
                'pending_review': Conversion.objects.filter(status='QUEUED').count(),
                'flagged_fraud': Conversion.objects.filter(status='FAILED').count(),
            }
            return Response({'success': True, 'stats': stats})
        except Exception as e:
            return Response({'success': True, 'stats': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_conversions(self, request):
        """Bulk approve pending conversions."""
        try:
            from api.promotions.models import TaskSubmission as Conversion
            ids = request.data.get('ids', [])
            qs = Conversion.objects.filter(status='QUEUED')
            if ids:
                qs = qs.filter(pk__in=ids)
            count = qs.update(status='SUCCESS', reviewed_by=request.user)
            return Response({'success': True, 'approved': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_conversions(self, request):
        """Bulk reject conversions (mark as fraud)."""
        try:
            from api.promotions.models import TaskSubmission as Conversion
            ids = request.data.get('ids', [])
            reason = request.data.get('reason', 'Admin rejected')
            qs = Conversion.objects.filter(status='QUEUED')
            if ids:
                qs = qs.filter(pk__in=ids)
            count = qs.update(status='FAILED', reject_reason=reason, is_fraud=True)
            return Response({'success': True, 'rejected': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== CATEGORIES ====================

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """List all offer categories."""
        try:
            from api.promotions.models import PromotionCategory
            cats = list(PromotionCategory.objects.values(
                'id', 'name', 'category_type', 'is_active'
            ))
            return Response({'success': True, 'data': cats})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== CONTENT LOCKER ====================

    @action(detail=False, methods=['get'])
    def content_locker_stats(self, request):
        """CPAlead Content Locker stats — locked content, unlocks, revenue."""
        try:
            from api.promotions.content_locking import models as cl_models
            # Placeholder — actual models depend on promotions/content_locking/
            return Response({
                'success': True,
                'message': 'Content locker stats - integrate with api.promotions.content_locking',
                'stats': {}
            })
        except Exception as e:
            return Response({'success': True, 'stats': {}, 'note': str(e)})

    # ==================== REVENUE SUMMARY ====================

    @action(detail=False, methods=['get'])
    def revenue_summary(self, request):
        """Total revenue breakdown by offer type, geo, date."""
        try:
            from api.promotions.models import TaskSubmission as Conversion
            last_30d = timezone.now() - timedelta(days=30)
            
            by_type = list(
                Conversion.objects.filter(
                    created_at__gte=last_30d,
                    status='SUCCESS'
                ).values('campaign__name').annotate(
                    count=Count('id'),
                    revenue=Sum('payout')
                ).order_by('-revenue')
            )
            
            daily = list(
                Conversion.objects.filter(
                    created_at__gte=last_30d,
                    status='SUCCESS'
                ).extra(select={'day': 'DATE(created_at)'}).values('day').annotate(
                    count=Count('id'),
                    revenue=Sum('payout')
                ).order_by('day')
            )
            
            return Response({
                'success': True,
                'by_offer_type': by_type,
                'daily_revenue': daily,
            })
        except Exception as e:
            return Response({'success': True, 'by_offer_type': [], 'daily_revenue': [], 'error': str(e)})