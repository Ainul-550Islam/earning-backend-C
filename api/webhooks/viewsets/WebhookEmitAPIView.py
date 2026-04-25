"""Webhook Emit API View

This module contains the API view for webhook emit operations.
"""

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from ..models import WebhookEndpoint
from ..serializers import (
    WebhookEmitSerializer,
    WebhookEmitBatchSerializer,
    WebhookEmitTestSerializer,
    WebhookEmitResultSerializer,
    WebhookEmitBatchResultSerializer,
    WebhookEmitStatsSerializer
)
from ..services.core import DispatchService
from ..permissions import IsOwnerOrReadOnly


class WebhookEmitAPIView(views.APIView):
    """API view for webhook emit operations."""
    
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def post(self, request, *args, **kwargs):
        """Emit a webhook event."""
        serializer = WebhookEmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_id = serializer.validated_data['endpoint_id']
        event_type = serializer.validated_data['event_type']
        payload = serializer.validated_data['payload']
        async_emit = serializer.validated_data['async_emit']
        
        try:
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
            
            # Emit webhook
            dispatch_service = DispatchService()
            start_time = timezone.now()
            
            if async_emit:
                result = dispatch_service.emit_async(
                    endpoint=endpoint,
                    event_type=event_type,
                    payload=payload
                )
            else:
                result = dispatch_service.emit(
                    endpoint=endpoint,
                    event_type=event_type,
                    payload=payload
                )
            
            end_time = timezone.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Return result
            result_data = {
                'success': result,
                'endpoint_id': str(endpoint_id),
                'event_type': event_type,
                'processing_time': processing_time,
                'emitted_at': end_time.isoformat()
            }
            
            if result and not async_emit:
                # Get delivery log ID for synchronous emits
                from ..models import WebhookDeliveryLog
                delivery_log = WebhookDeliveryLog.objects.filter(
                    endpoint=endpoint,
                    event_type=event_type,
                    created_at__gte=start_time
                ).first()
                if delivery_log:
                    result_data['delivery_log_id'] = str(delivery_log.id)
            elif not result:
                result_data['error'] = 'Failed to emit webhook'
            
            return Response(result_data, status=status.HTTP_200_OK)
            
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post_batch(self, request, *args, **kwargs):
        """Emit multiple webhook events in batch."""
        serializer = WebhookEmitBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_id = serializer.validated_data['endpoint_id']
        event_type = serializer.validated_data['event_type']
        events = serializer.validated_data['events']
        async_emit = serializer.validated_data['async_emit']
        
        try:
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
            
            # Emit webhooks in batch
            dispatch_service = DispatchService()
            start_time = timezone.now()
            
            results = []
            successful_events = 0
            failed_events = 0
            
            for i, event in enumerate(events):
                try:
                    if async_emit:
                        result = dispatch_service.emit_async(
                            endpoint=endpoint,
                            event_type=event_type,
                            payload=event
                        )
                    else:
                        result = dispatch_service.emit(
                            endpoint=endpoint,
                            event_type=event_type,
                            payload=event
                        )
                    
                    if result:
                        successful_events += 1
                    else:
                        failed_events += 1
                    
                    results.append({
                        'index': i,
                        'success': result
                    })
                    
                except Exception as e:
                    failed_events += 1
                    results.append({
                        'index': i,
                        'success': False,
                        'error': str(e)
                    })
            
            end_time = timezone.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Return result
            result_data = {
                'success': failed_events == 0,
                'endpoint_id': str(endpoint_id),
                'event_type': event_type,
                'total_events': len(events),
                'processed_events': len(results),
                'successful_events': successful_events,
                'failed_events': failed_events,
                'processing_time': processing_time,
                'emitted_at': end_time.isoformat()
            }
            
            if failed_events > 0:
                errors = []
                for result in results:
                    if not result['success'] and 'error' in result:
                        errors.append(f"Event {result['index']}: {result['error']}")
                result_data['errors'] = errors
            
            return Response(result_data, status=status.HTTP_200_OK)
            
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post_test(self, request, *args, **kwargs):
        """Test webhook emit with sample payload."""
        serializer = WebhookEmitTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_id = serializer.validated_data['endpoint_id']
        test_payload = serializer.validated_data['test_payload']
        
        try:
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
            
            # Emit test webhook
            dispatch_service = DispatchService()
            start_time = timezone.now()
            
            result = dispatch_service.emit(
                endpoint=endpoint,
                event_type='webhook.test',
                payload=test_payload
            )
            
            end_time = timezone.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Return result
            result_data = {
                'success': result,
                'endpoint_id': str(endpoint_id),
                'event_type': 'webhook.test',
                'processing_time': processing_time,
                'emitted_at': end_time.isoformat(),
                'payload': test_payload
            }
            
            if result:
                # Get delivery log ID
                from ..models import WebhookDeliveryLog
                delivery_log = WebhookDeliveryLog.objects.filter(
                    endpoint=endpoint,
                    event_type='webhook.test',
                    created_at__gte=start_time
                ).first()
                if delivery_log:
                    result_data['delivery_log_id'] = str(delivery_log.id)
            else:
                result_data['error'] = 'Test webhook failed'
            
            return Response(result_data, status=status.HTTP_200_OK)
            
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_statistics(self, request, *args, **kwargs):
        """Get webhook emit statistics."""
        try:
            from ..models import WebhookDeliveryLog
            from django.db.models import Avg, Count
            
            # Get user's endpoints
            endpoints = WebhookEndpoint.objects.filter(owner=request.user)
            
            # Get overall statistics
            deliveries = WebhookDeliveryLog.objects.filter(endpoint__in=endpoints)
            
            total_emits = deliveries.count()
            successful_emits = deliveries.filter(status='success').count()
            failed_emits = deliveries.filter(status='failed').count()
            success_rate = (successful_emits / total_emits * 100) if total_emits > 0 else 0
            
            # Get average processing time
            successful_deliveries = deliveries.filter(status='success')
            avg_processing_time = 0
            if successful_deliveries.exists():
                avg_processing_time = successful_deliveries.aggregate(
                    avg_time=Avg('duration_ms')
                )['avg_time'] or 0
            
            # Get last emit time
            last_emit = deliveries.order_by('-created_at').first()
            last_emit_at = last_emit.created_at if last_emit else None
            
            return Response({
                'total_emits': total_emits,
                'successful_emits': successful_emits,
                'failed_emits': failed_emits,
                'success_rate': round(success_rate, 2),
                'avg_processing_time': round(avg_processing_time, 2),
                'last_emit_at': last_emit_at.isoformat() if last_emit_at else None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_preview(self, request, *args, **kwargs):
        """Preview webhook emit without actually sending."""
        endpoint_id = request.query_params.get('endpoint_id')
        event_type = request.query_params.get('event_type')
        payload = request.query_params.get('payload')
        
        if not all([endpoint_id, event_type, payload]):
            return Response({
                'error': 'endpoint_id, event_type, and payload parameters are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
            
            # Parse payload
            import json
            try:
                payload_data = json.loads(payload)
            except json.JSONDecodeError:
                return Response({
                    'error': 'Invalid JSON payload'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate preview
            from ..services.signature_engine import SignatureEngine
            
            signature_engine = SignatureEngine()
            signature = signature_engine.generate_signature(
                payload_data,
                endpoint.secret_key
            )
            
            # Generate headers
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Signature': signature,
                'X-Webhook-Event': event_type,
                'X-Webhook-Timestamp': timezone.now().isoformat()
            }
            
            # Add custom headers
            if endpoint.headers:
                headers.update(endpoint.headers)
            
            # Calculate estimated size
            import json
            payload_size = len(json.dumps(payload_data))
            estimated_size = payload_size + len(json.dumps(headers))
            
            return Response({
                'endpoint_id': str(endpoint_id),
                'endpoint_url': endpoint.url,
                'event_type': event_type,
                'payload': payload_data,
                'headers': headers,
                'signature': signature,
                'estimated_size': estimated_size,
                'payload_size': payload_size
            }, status=status.HTTP_200_OK)
            
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
