# api/admin_panel/viewsets/SmartlinkAdminViewSet.py
"""
SmartlinkAdminViewSet — Full admin control for Smartlink engine.
Controls: Smartlinks, offer pools, routing rules, geo-targeting, click/conversion analytics.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class SmartlinkAdminViewSet(viewsets.ViewSet):
    """
    Admin control for Smartlink engine.
    CPAlead SmartLink: routes traffic to best-converting offer by GEO+Device+OS+Browser.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Smartlink system overview — total links, clicks, conversions, EPC."""
        try:
            from api.smartlink.models.smartlink import Smartlink
            from api.smartlink.models.click import Click
            
            last_24h = timezone.now() - timedelta(hours=24)
            last_7d = timezone.now() - timedelta(days=7)
            
            total_links = Smartlink.objects.count()
            active_links = Smartlink.objects.filter(is_active=True).count()
            
            clicks_24h = Click.objects.filter(created_at__gte=last_24h).count()
            clicks_7d = Click.objects.filter(created_at__gte=last_7d).count()
            
            return Response({
                'success': True,
                'data': {
                    'total_smartlinks': total_links,
                    'active_smartlinks': active_links,
                    'clicks_24h': clicks_24h,
                    'clicks_7d': clicks_7d,
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def all_links(self, request):
        """List all smartlinks with performance metrics."""
        try:
            from api.smartlink.models.smartlink import Smartlink
            
            qs = Smartlink.objects.all()
            
            search = request.query_params.get('search')
            is_active = request.query_params.get('is_active')
            
            if search:
                qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search))
            if is_active is not None:
                qs = qs.filter(is_active=is_active.lower() == 'true')
            
            page_size = int(request.query_params.get('page_size', 25))
            links = list(qs.values(
                'id', 'name', 'slug', 'is_active', 'total_clicks',
                'total_conversions', 'created_at'
            )[:page_size])
            
            return Response({'success': True, 'data': links, 'total': qs.count()})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_link(self, request):
        """Enable/disable a smartlink."""
        try:
            from api.smartlink.models.smartlink import Smartlink
            link_id = request.data.get('link_id')
            link = Smartlink.objects.get(pk=link_id)
            link.is_active = not link.is_active
            link.save(update_fields=['is_active'])
            return Response({'success': True, 'is_active': link.is_active, 'id': link_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def geo_performance(self, request):
        """Click/conversion performance by country."""
        try:
            from api.smartlink.models.click import Click
            last_7d = timezone.now() - timedelta(days=7)
            
            geo_stats = list(
                Click.objects.filter(created_at__gte=last_7d).values('country').annotate(
                    clicks=Count('id'),
                    conversions=Count('id', filter=Q(is_converted=True)),
                ).order_by('-clicks')[:30]
            )
            
            # Calculate conversion rate
            for item in geo_stats:
                clicks = item['clicks'] or 1
                item['cvr'] = round((item['conversions'] / clicks) * 100, 2)
            
            return Response({'success': True, 'data': geo_stats})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def device_performance(self, request):
        """Performance breakdown by device type (Mobile/Desktop/Tablet)."""
        try:
            from api.smartlink.models.click import Click
            last_7d = timezone.now() - timedelta(days=7)
            
            device_stats = list(
                Click.objects.filter(created_at__gte=last_7d).values('device_type').annotate(
                    clicks=Count('id'),
                    conversions=Count('id', filter=Q(is_converted=True)),
                ).order_by('-clicks')
            )
            return Response({'success': True, 'data': device_stats})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def offer_pool(self, request):
        """View active offers in the smartlink rotation pool."""
        try:
            from api.smartlink.models.offer_pool import OfferPool
            pool = list(OfferPool.objects.filter(is_active=True).values(
                'id', 'offer_name', 'weight', 'geo_targets',
                'device_targets', 'daily_cap', 'total_clicks', 'is_active'
            )[:50])
            return Response({'success': True, 'data': pool})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_routing_rules(self, request):
        """Update smartlink routing weights and rules."""
        try:
            from api.smartlink.models.offer_pool import OfferPool
            rules = request.data.get('rules', [])
            updated = 0
            for rule in rules:
                pool_id = rule.get('id')
                weight = rule.get('weight')
                if pool_id and weight is not None:
                    OfferPool.objects.filter(pk=pool_id).update(weight=weight)
                    updated += 1
            cache.delete('admin_panel:smartlink_routing')
            return Response({'success': True, 'updated': updated})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def click_timeline(self, request):
        """Hourly click volume for last 24 hours."""
        try:
            from api.smartlink.models.click import Click
            from django.db.models.functions import TruncHour
            last_24h = timezone.now() - timedelta(hours=24)
            
            hourly = list(
                Click.objects.filter(created_at__gte=last_24h).annotate(
                    hour=TruncHour('created_at')
                ).values('hour').annotate(
                    clicks=Count('id'),
                    conversions=Count('id', filter=Q(is_converted=True)),
                ).order_by('hour')
            )
            return Response({'success': True, 'data': hourly})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def top_performing_links(self, request):
        """Top smartlinks by EPC (Earnings Per Click)."""
        try:
            from api.smartlink.models.smartlink import Smartlink
            links = list(Smartlink.objects.filter(
                is_active=True, total_clicks__gt=0
            ).values('id', 'name', 'total_clicks', 'total_revenue', 'total_conversions')
            .order_by('-total_revenue')[:20])
            
            for link in links:
                clicks = link.get('total_clicks') or 1
                revenue = float(link.get('total_revenue') or 0)
                link['epc'] = round(revenue / clicks, 4)
            
            return Response({'success': True, 'data': links})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})