# api/cms/viewsets_new/RealTimeOfferViewSet.py
"""
API ViewSets for Real-time Offer Updates System
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models_new.realtime_offers import (
    RealTimeOfferUpdate, UserOfferSubscription, OfferUpdateQueue
)
from ..services_new.RealTimeOfferService import RealTimeOfferService


class RealTimeOfferUpdateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for real-time offer updates
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['update_type', 'is_active']
    
    def get_queryset(self):
        """Get updates relevant to current user"""
        user = self.request.user
        queryset = RealTimeOfferUpdate.objects.filter(
            is_active=True
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).order_by('-priority', '-created_at')
        
        # Filter for user relevance
        relevant_updates = []
        for update in queryset:
            if update.is_relevant_for_user(user):
                relevant_updates.append(update)
        
        return relevant_updates
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent updates for user"""
        limit = min(int(request.query_params.get('limit', 20)), 100)
        updates = RealTimeOfferService.get_user_updates(request.user, limit)
        return Response({'updates': updates})
    
    @action(detail=False, methods=['post'])
    def mark_read(self, request):
        """Mark updates as read"""
        update_ids = request.data.get('update_ids', [])
        # This would require a read tracking model
        return Response({'marked_read': len(update_ids)})


class UserOfferSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user offer subscription preferences
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserOfferSubscription.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create subscription for user"""
        obj, created = UserOfferSubscription.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get', 'patch'])
    def preferences(self, request):
        """Get or update subscription preferences"""
        if request.method == 'GET':
            subscription = self.get_object()
            data = {
                'subscribe_new_offers': subscription.subscribe_new_offers,
                'subscribe_updated_offers': subscription.subscribe_updated_offers,
                'subscribe_expired_offers': subscription.subscribe_expired_offers,
                'subscribe_payout_changes': subscription.subscribe_payout_changes,
                'min_payout': float(subscription.min_payout),
                'max_payout': float(subscription.max_payout),
                'preferred_countries': subscription.preferred_countries,
                'preferred_categories': subscription.preferred_categories,
                'notification_sound': subscription.notification_sound,
                'notification_desktop': subscription.notification_desktop,
                'notification_email': subscription.notification_email,
            }
            return Response(data)
        else:
            subscription = self.get_object()
            for field, value in request.data.items():
                if hasattr(subscription, field):
                    setattr(subscription, field, value)
            subscription.save()
            return Response({'message': 'Preferences updated'})


class OfferUpdateQueueViewSet(viewsets.ModelViewSet):
    """
    ViewSet for offer update queue (admin only)
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if not self.request.user.is_staff:
            return OfferUpdateQueue.objects.none()
        return OfferUpdateQueue.objects.all().order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def process_batch(self, request):
        """Process batch of updates"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        batch_data = request.data.get('batch_data', {})
        queue_item = OfferUpdateQueue.objects.create(
            batch_data=batch_data,
            status='pending'
        )
        
        # Trigger processing
        RealTimeOfferService._queue_update_processing(queue_item)
        
        return Response({
            'queue_id': str(queue_item.uuid),
            'message': 'Batch queued for processing'
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get queue statistics"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        from ..services_new.RealTimeOfferService import RealTimeOfferAnalyticsService
        
        stats = RealTimeOfferAnalyticsService.get_update_statistics(days=30)
        return Response(stats)

# Alias: external code imports RealTimeOfferViewSet from this module
RealTimeOfferViewSet = RealTimeOfferUpdateViewSet
