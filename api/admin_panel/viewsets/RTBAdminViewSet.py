# api/admin_panel/viewsets/RTBAdminViewSet.py
"""
RTBAdminViewSet — Real-Time Bidding Admin Control.
Uses api.promotions.bidding models and api.ad_networks models.
admin_panel CALLS these, never duplicates.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class RTBAdminViewSet(viewsets.ViewSet):
    """RTB marketplace admin — bid floors, demand partners, auction analytics."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def rtb_overview(self, request):
        """RTB system overview from ad_networks and promotions.bidding."""
        try:
            from api.ad_networks.models import AdNetwork, Offer
            from api.promotions.bidding import models as bidding_models

            active_networks = AdNetwork.objects.filter(is_active=True).count()
            total_offers = Offer.objects.filter(is_active=True).count()

            return Response({'success': True, 'data': {
                'active_demand_networks': active_networks,
                'active_offers_in_rotation': total_offers,
                'rtb_enabled': True,
                'auction_type': cache.get('rtb:auction_type', 'first_price'),
                'avg_bid_floor': cache.get('rtb:avg_floor', 0.50),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {
                'active_demand_networks': 0,
                'active_offers_in_rotation': 0,
                'rtb_enabled': True,
                'note': str(e)[:100],
            }})

    @action(detail=False, methods=['get'])
    def bid_floor_settings(self, request):
        """Bid floor configuration by GEO/device/format (stored in SystemConfig)."""
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            floors_raw = SystemConfigService.get('rtb_bid_floors', default='{}')
            import json
            floors = json.loads(floors_raw) if isinstance(floors_raw, str) else floors_raw

            if not floors:
                floors = {
                    'US': {'mobile': {'banner': 0.50, 'interstitial': 2.00, 'rewarded': 5.00}},
                    'BD': {'mobile': {'banner': 0.10, 'interstitial': 0.30, 'rewarded': 0.50}},
                    'IN': {'mobile': {'banner': 0.20, 'interstitial': 0.60, 'rewarded': 1.50}},
                    'GB': {'mobile': {'banner': 0.80, 'interstitial': 3.00, 'rewarded': 7.00}},
                    'CA': {'mobile': {'banner': 0.70, 'interstitial': 2.50, 'rewarded': 6.00}},
                }
            return Response({'success': True, 'data': floors})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_bid_floor(self, request):
        """Update bid floor price — stored in SystemConfig."""
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            import json
            geo = request.data.get('geo', 'US')
            device = request.data.get('device_type', 'mobile')
            ad_format = request.data.get('ad_format', 'banner')
            floor_price = float(request.data.get('floor_price', 0))

            if floor_price <= 0:
                return Response({'error': 'floor_price must be > 0'}, status=400)

            floors_raw = SystemConfigService.get('rtb_bid_floors', default='{}')
            floors = json.loads(floors_raw) if isinstance(floors_raw, str) else {}
            floors.setdefault(geo, {}).setdefault(device, {})[ad_format] = floor_price
            SystemConfigService.set('rtb_bid_floors', json.dumps(floors), 'json')

            cache.delete(f'rtb:floor:{geo}:{device}:{ad_format}')
            return Response({'success': True, 'geo': geo, 'device': device,
                             'format': ad_format, 'floor_price': floor_price})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def demand_partners(self, request):
        """List all ad networks as demand partners."""
        try:
            from api.ad_networks.models import AdNetwork
            partners = list(AdNetwork.objects.values(
                'id', 'name', 'network_type', 'is_active',
                'api_key_set', 'total_revenue', 'total_impressions', 'fill_rate'
            ).order_by('-is_active', '-total_revenue'))
            return Response({'success': True, 'data': partners})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_demand_partner(self, request):
        """Enable/disable a demand partner network."""
        try:
            from api.ad_networks.models import AdNetwork
            partner_id = request.data.get('partner_id')
            network = AdNetwork.objects.get(pk=partner_id)
            network.is_active = not network.is_active
            network.save(update_fields=['is_active'])
            cache.delete(f'ad_network:{partner_id}')
            cache.delete('rtb:demand_partners')
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='toggle_rtb_partner',
                    model_name='AdNetwork', object_id=str(partner_id),
                    changes={'name': network.name, 'is_active': network.is_active},
                )
            except Exception:
                pass
            return Response({'success': True, 'network': network.name, 'is_active': network.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def set_auction_type(self, request):
        """Set RTB auction type: first_price or second_price."""
        auction_type = request.data.get('type', 'first_price')
        if auction_type not in ('first_price', 'second_price'):
            return Response({'error': 'type must be first_price or second_price'}, status=400)
        cache.set('rtb:auction_type', auction_type, 86400)
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            SystemConfigService.set('rtb_auction_type', auction_type, 'string')
        except Exception:
            pass
        return Response({'success': True, 'auction_type': auction_type})

    @action(detail=False, methods=['get'])
    def network_performance(self, request):
        """Ad network performance — revenue, fill rate, eCPM."""
        try:
            from api.ad_networks.models import AdNetwork
            last_7d = timezone.now() - timedelta(days=7)
            networks = list(AdNetwork.objects.filter(is_active=True).values(
                'id', 'name', 'network_type', 'total_revenue',
                'total_impressions', 'fill_rate', 'ecpm'
            ).order_by('-total_revenue'))
            return Response({'success': True, 'data': networks})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def set_network_priority(self, request):
        """Set waterfall priority order for ad networks."""
        try:
            from api.ad_networks.models import AdNetwork
            priorities = request.data.get('priorities', [])  # [{id, priority}]
            updated = 0
            for item in priorities:
                AdNetwork.objects.filter(pk=item['id']).update(priority=item.get('priority', 5))
                updated += 1
            cache.delete('rtb:network_waterfall')
            return Response({'success': True, 'updated': updated})
        except Exception as e:
            return Response({'error': str(e)}, status=400)