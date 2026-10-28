# api/admin_panel/viewsets/ContentLockerOfferwallAdminViewSet.py
"""
ContentLocker & Offerwall Admin — CPAlead core features.
ContentLocker is a service (uses cache), OfferProvider uses DB.
admin_panel only CALLS their methods — no duplicate code.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class ContentLockerAdminViewSet(viewsets.ViewSet):
    """
    CPAlead-style Content Locker Admin.
    Calls api.promotions.content_locking service classes.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Content locker system stats from cache/analytics."""
        try:
            from api.promotions.content_locking.locker_analytics import LockerAnalytics
            stats = LockerAnalytics.get_global_stats()
            return Response({'success': True, 'data': stats})
        except Exception as e:
            # Fallback: read from cache keys
            total_locks = cache.get('content_locker:total_locks', 0)
            total_unlocks = cache.get('content_locker:total_unlocks', 0)
            return Response({'success': True, 'data': {
                'total_locks': total_locks,
                'total_unlocks': total_unlocks,
                'unlock_rate': round(total_unlocks / max(total_locks, 1) * 100, 2),
                'active_sessions': len([k for k in (cache.get('content_locker:sessions') or [])]),
                'note': str(e)[:100],
            }})

    @action(detail=False, methods=['get'])
    def locker_types(self, request):
        """Available locker types and their config."""
        try:
            from api.promotions.content_locking.content_locker import ContentLocker
            from api.promotions.content_locking.file_locker import FileLocker
            from api.promotions.content_locking.link_locker import LinkLocker
            return Response({'success': True, 'data': {
                'content_locker': {
                    'types': ContentLocker.LOCKER_TYPES,
                    'description': 'Gate HTML content behind CPA offers',
                },
                'file_locker': {
                    'description': 'Gate file downloads behind CPA offers',
                    'max_file_size_mb': getattr(FileLocker, 'MAX_FILE_SIZE_MB', 100),
                },
                'link_locker': {
                    'description': 'Gate URLs behind CPA offers (CPAlead signature)',
                },
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Content locker performance analytics."""
        try:
            from api.promotions.content_locking.locker_analytics import LockerAnalytics
            days = int(request.query_params.get('days', 7))
            data = LockerAnalytics.get_daily_stats(days=days)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def clear_locker_session(self, request):
        """Clear a user's active locker session (admin override)."""
        try:
            from api.promotions.content_locking.content_locker import ContentLocker
            user_id = request.data.get('user_id')
            locker_key = request.data.get('locker_key', '')
            cache_key = f"{ContentLocker.UNLOCK_PREFIX}{user_id}:{locker_key}"
            cache.delete(cache_key)
            return Response({'success': True, 'cleared': True, 'user_id': user_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def epc_stats(self, request):
        """EPC (Earnings Per Click) stats for content lockers."""
        try:
            from api.promotions.content_locking.locker_analytics import LockerAnalytics
            epc_data = LockerAnalytics.get_epc_breakdown()
            return Response({'success': True, 'data': epc_data})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})


class OfferwallAdminViewSet(viewsets.ViewSet):
    """
    Offerwall Admin — calls api.offerwall models directly.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.offerwall.models import OfferProvider, Offer
            from django.db.models import Count, Sum
            last_24h = timezone.now() - timedelta(hours=24)
            return Response({'success': True, 'data': {
                'total_providers': OfferProvider.objects.count(),
                'active_providers': OfferProvider.objects.filter(is_active=True).count(),
                'total_offers': Offer.objects.count(),
                'active_offers': Offer.objects.filter(is_active=True).count(),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def providers(self, request):
        """List all offerwall providers (Adscend, Fyber, etc.)."""
        try:
            from api.offerwall.models import OfferProvider
            providers = list(OfferProvider.objects.values(
                'id', 'name', 'provider_type', 'is_active',
                'api_key_set', 'total_offers', 'last_sync'
            ).order_by('-is_active', 'name'))
            return Response({'success': True, 'data': providers})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_provider(self, request):
        try:
            from api.offerwall.models import OfferProvider
            provider_id = request.data.get('provider_id')
            p = OfferProvider.objects.get(pk=provider_id)
            p.is_active = not p.is_active
            p.save(update_fields=['is_active'])
            cache.delete(f'offerwall:provider:{provider_id}')
            return Response({'success': True, 'provider': p.name, 'is_active': p.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def top_offers(self, request):
        """Top performing offerwall offers."""
        try:
            from api.offerwall.models import Offer
            offers = list(Offer.objects.filter(is_active=True).values(
                'id', 'name', 'offer_type', 'payout', 'currency',
                'provider__name', 'countries', 'platforms', 'total_completions'
            ).order_by('-total_completions')[:50])
            return Response({'success': True, 'data': offers})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def sync_provider_offers(self, request):
        """Trigger offer sync from a provider's API."""
        try:
            provider_id = request.data.get('provider_id')
            from celery import current_app
            current_app.send_task(
                'api.offerwall.tasks.sync_provider_offers',
                args=[provider_id]
            )
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='sync_offerwall_provider',
                    model_name='OfferProvider', object_id=str(provider_id),
                )
            except Exception:
                pass
            return Response({'success': True, 'queued': True, 'provider_id': provider_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def category_breakdown(self, request):
        """Offers broken down by category."""
        try:
            from api.offerwall.models import Offer
            from django.db.models import Count, Avg
            breakdown = list(Offer.objects.filter(is_active=True).values(
                'category__name'
            ).annotate(
                total=Count('id'),
                avg_payout=Avg('payout'),
            ).order_by('-total'))
            return Response({'success': True, 'data': breakdown})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})