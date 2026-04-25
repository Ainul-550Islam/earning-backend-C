"""Event Type List API View

This module contains the API view for listing webhook event types.
"""

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from ..models import WebhookSubscription, WebhookDeliveryLog
from ..serializers import WebhookEventTypeSerializer, WebhookEventTypeDetailSerializer
from ..services.analytics import WebhookAnalyticsService


class EventTypeListAPIView(views.APIView):
    """API view for listing webhook event types."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """List all available event types."""
        try:
            # Get all unique event types from subscriptions
            event_types = WebhookSubscription.objects.filter(
                endpoint__owner=request.user
            ).values_list('event_type', flat=True).distinct()
            
            # Get additional event types from delivery logs
            delivery_event_types = WebhookDeliveryLog.objects.filter(
                endpoint__owner=request.user
            ).values_list('event_type', flat=True).distinct()
            
            # Combine both sets
            all_event_types = set(event_types) | set(delivery_event_types)
            
            # Sort event types
            sorted_event_types = sorted(list(all_event_types))
            
            return Response({
                'event_types': sorted_event_types,
                'total_count': len(sorted_event_types)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_details(self, request, *args, **kwargs):
        """Get detailed information about event types."""
        try:
            # Get all unique event types from subscriptions
            event_types = WebhookSubscription.objects.filter(
                endpoint__owner=request.user
            ).values_list('event_type', flat=True).distinct()
            
            event_type_details = []
            analytics_service = WebhookAnalyticsService()
            
            for event_type in event_types:
                # Get subscription count
                subscription_count = WebhookSubscription.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type
                ).count()
                
                # Get endpoint count
                endpoint_count = WebhookSubscription.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type
                ).values('endpoint').distinct().count()
                
                # Get last emitted time
                last_delivery = WebhookDeliveryLog.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type
                ).order_by('-created_at').first()
                
                last_emitted = last_delivery.created_at if last_delivery else None
                
                # Get description (could be from a config or database)
                description = self._get_event_type_description(event_type)
                
                event_type_details.append({
                    'event_type': event_type,
                    'description': description,
                    'subscription_count': subscription_count,
                    'endpoint_count': endpoint_count,
                    'last_emitted': last_emitted.isoformat() if last_emitted else None
                })
            
            # Sort by event type
            event_type_details.sort(key=lambda x: x['event_type'])
            
            return Response({
                'event_types': event_type_details,
                'total_count': len(event_type_details)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_statistics(self, request, *args, **kwargs):
        """Get statistics for event types."""
        try:
            # Get all unique event types from subscriptions
            event_types = WebhookSubscription.objects.filter(
                endpoint__owner=request.user
            ).values_list('event_type', flat=True).distinct()
            
            event_type_stats = []
            
            for event_type in event_types:
                # Get delivery statistics
                deliveries = WebhookDeliveryLog.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type
                )
                
                total_emits = deliveries.count()
                successful_emits = deliveries.filter(status='success').count()
                failed_emits = deliveries.filter(status='failed').count()
                success_rate = (successful_emits / total_emits * 100) if total_emits > 0 else 0
                
                # Get average response time
                successful_deliveries = deliveries.filter(status='success')
                avg_response_time = 0
                if successful_deliveries.exists():
                    avg_response_time = successful_deliveries.aggregate(
                        models.Avg('duration_ms')
                    )['duration_ms__avg'] or 0
                
                # Get last emitted time
                last_delivery = deliveries.order_by('-created_at').first()
                last_emitted = last_delivery.created_at if last_delivery else None
                
                event_type_stats.append({
                    'event_type': event_type,
                    'total_emits': total_emits,
                    'successful_emits': successful_emits,
                    'failed_emits': failed_emits,
                    'success_rate': round(success_rate, 2),
                    'avg_response_time': round(avg_response_time, 2),
                    'last_emitted': last_emitted.isoformat() if last_emitted else None
                })
            
            # Sort by total emits (descending)
            event_type_stats.sort(key=lambda x: x['total_emits'], reverse=True)
            
            return Response({
                'event_types': event_type_stats,
                'total_count': len(event_type_stats)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_popular(self, request, *args, **kwargs):
        """Get popular event types."""
        try:
            # Get event types with most emissions
            event_types = WebhookDeliveryLog.objects.filter(
                endpoint__owner=request.user
            ).values('event_type').annotate(
                emit_count=models.Count('id')
            ).order_by('-emit_count')[:10]
            
            popular_event_types = []
            
            for event_type_data in event_types:
                event_type = event_type_data['event_type']
                emit_count = event_type_data['emit_count']
                
                # Get subscription count
                subscription_count = WebhookSubscription.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type
                ).count()
                
                # Get success rate
                deliveries = WebhookDeliveryLog.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type
                )
                
                success_rate = 0
                if deliveries.exists():
                    success_count = deliveries.filter(status='success').count()
                    success_rate = (success_count / deliveries.count() * 100)
                
                popular_event_types.append({
                    'event_type': event_type,
                    'emit_count': emit_count,
                    'subscription_count': subscription_count,
                    'success_rate': round(success_rate, 2)
                })
            
            return Response({
                'event_types': popular_event_types,
                'total_count': len(popular_event_types)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_recent(self, request, *args, **kwargs):
        """Get recently used event types."""
        try:
            # Get event types used in the last 24 hours
            from datetime import timedelta
            since = timezone.now() - timedelta(hours=24)
            
            event_types = WebhookDeliveryLog.objects.filter(
                endpoint__owner=request.user,
                created_at__gte=since
            ).values('event_type').annotate(
                emit_count=models.Count('id')
            ).order_by('-emit_count')
            
            recent_event_types = []
            
            for event_type_data in event_types:
                event_type = event_type_data['event_type']
                emit_count = event_type_data['emit_count']
                
                # Get success rate for recent period
                recent_deliveries = WebhookDeliveryLog.objects.filter(
                    endpoint__owner=request.user,
                    event_type=event_type,
                    created_at__gte=since
                )
                
                success_rate = 0
                if recent_deliveries.exists():
                    success_count = recent_deliveries.filter(status='success').count()
                    success_rate = (success_count / recent_deliveries.count() * 100)
                
                # Get last emitted time
                last_delivery = recent_deliveries.order_by('-created_at').first()
                last_emitted = last_delivery.created_at if last_delivery else None
                
                recent_event_types.append({
                    'event_type': event_type,
                    'emit_count_24h': emit_count,
                    'success_rate_24h': round(success_rate, 2),
                    'last_emitted': last_emitted.isoformat() if last_emitted else None
                })
            
            return Response({
                'event_types': recent_event_types,
                'total_count': len(recent_event_types)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_trends(self, request, *args, **kwargs):
        """Get event type trends over time."""
        try:
            days = int(request.query_params.get('days', 7))
            since = timezone.now() - timedelta(days=days)
            
            # Get event types with trends
            event_types = WebhookDeliveryLog.objects.filter(
                endpoint__owner=request.user,
                created_at__gte=since
            ).values('event_type').annotate(
                emit_count=models.Count('id')
            ).order_by('-emit_count')[:10]
            
            event_type_trends = []
            
            for event_type_data in event_types:
                event_type = event_type_data['event_type']
                
                # Get daily trends
                daily_trends = []
                for day in range(days):
                    date = (timezone.now() - timedelta(days=day)).date()
                    
                    deliveries = WebhookDeliveryLog.objects.filter(
                        endpoint__owner=request.user,
                        event_type=event_type,
                        created_at__date=date
                    )
                    
                    emit_count = deliveries.count()
                    success_count = deliveries.filter(status='success').count()
                    success_rate = (success_count / emit_count * 100) if emit_count > 0 else 0
                    
                    avg_response_time = 0
                    successful_deliveries = deliveries.filter(status='success')
                    if successful_deliveries.exists():
                        avg_response_time = successful_deliveries.aggregate(
                            models.Avg('duration_ms')
                        )['duration_ms__avg'] or 0
                    
                    daily_trends.append({
                        'date': date.isoformat(),
                        'emit_count': emit_count,
                        'success_count': success_count,
                        'success_rate': round(success_rate, 2),
                        'avg_response_time': round(avg_response_time, 2)
                    })
                
                event_type_trends.append({
                    'event_type': event_type,
                    'trends': daily_trends
                })
            
            return Response({
                'event_types': event_type_trends,
                'total_count': len(event_type_trends),
                'days': days
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_event_type_description(self, event_type):
        """Get description for an event type."""
        # This could be enhanced with a database of event type descriptions
        descriptions = {
            'user.created': 'User account created',
            'user.updated': 'User account updated',
            'user.deleted': 'User account deleted',
            'user.login': 'User logged in',
            'user.logout': 'User logged out',
            'wallet.transaction.created': 'Wallet transaction created',
            'wallet.balance.updated': 'Wallet balance updated',
            'wallet.transaction.failed': 'Wallet transaction failed',
            'withdrawal.requested': 'Withdrawal requested',
            'withdrawal.approved': 'Withdrawal approved',
            'withdrawal.rejected': 'Withdrawal rejected',
            'withdrawal.completed': 'Withdrawal completed',
            'withdrawal.failed': 'Withdrawal failed',
            'offer.credited': 'Offer credited',
            'offer.completed': 'Offer completed',
            'offer.expired': 'Offer expired',
            'offer.cancelled': 'Offer cancelled',
            'payment.succeeded': 'Payment succeeded',
            'payment.failed': 'Payment failed',
            'payment.initiated': 'Payment initiated',
            'payment.cancelled': 'Payment cancelled',
            'payment.refunded': 'Payment refunded',
            'fraud.detected': 'Fraud detected',
            'fraud.flagged': 'Fraud flagged',
            'fraud.cleared': 'Fraud cleared',
            'kyc.submitted': 'KYC submitted',
            'kyc.verified': 'KYC verified',
            'kyc.rejected': 'KYC rejected',
            'webhook.test': 'Test webhook',
        }
        
        return descriptions.get(event_type, f'Event type: {event_type}')
