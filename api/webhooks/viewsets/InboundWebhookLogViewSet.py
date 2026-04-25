"""Inbound Webhook Log ViewSet

This module contains the ViewSet for inbound webhook log management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import InboundWebhookLog, InboundWebhook
from ..serializers import (
    InboundWebhookLogSerializer,
    InboundWebhookLogListSerializer,
    InboundWebhookLogDetailSerializer,
    InboundWebhookLogStatsSerializer,
    InboundWebhookLogProcessSerializer,
    InboundWebhookLogFilterSerializer,
    InboundWebhookLogBatchSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import InboundWebhookLogFilter


class InboundWebhookLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for inbound webhook log management (read-only)."""
    
    queryset = InboundWebhookLog.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = InboundWebhookLogFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'retrieve':
            return InboundWebhookLogDetailSerializer
        elif self.action == 'list':
            return InboundWebhookLogListSerializer
        else:
            return InboundWebhookLogSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own inbound webhook logs."""
        return super().get_queryset().filter(inbound__created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process an inbound webhook log."""
        log = self.get_object()
        
        if log.processed:
            return Response({
                'error': 'Log is already processed',
                'processed_at': log.processed_at
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = InboundWebhookLogProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Process the log
            from ..services.inbound import InboundWebhookService
            service = InboundWebhookService()
            
            result = service.process_inbound_webhook_log(
                log=log,
                processed=serializer.validated_data['processed'],
                error_message=serializer.validated_data.get('error_message', '')
            )
            
            return Response({
                'success': result['success'],
                'log_id': str(log.id),
                'processed': result.get('processed', False),
                'message': result.get('message', 'Log processed successfully')
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Log processing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Get detailed information about an inbound webhook log."""
        log = self.get_object()
        
        # Get detailed payload and headers
        raw_payload = log.raw_payload
        headers = log.headers
        signature = log.signature
        
        return Response({
            'id': str(log.id),
            'inbound': {
                'id': str(log.inbound.id),
                'source': log.inbound.source,
                'url_token': log.inbound.url_token
            },
            'raw_payload': raw_payload,
            'headers': headers,
            'signature': signature,
            'signature_valid': log.signature_valid,
            'processed': log.processed,
            'processed_at': log.processed_at,
            'error_message': log.error_message,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'created_at': log.created_at,
            'updated_at': log.updated_at
        })
    
    @action(detail=True, methods=['get'])
    def validation_result(self, request, pk=None):
        """Get validation result for an inbound webhook log."""
        log = self.get_object()
        
        # Get validation details
        validation_result = {
            'signature_valid': log.signature_valid,
            'processed': log.processed,
            'error_message': log.error_message
        }
        
        # Re-validate signature if possible
        if log.signature and log.raw_payload:
            try:
                from ..services.signature_engine import SignatureEngine
                signature_engine = SignatureEngine()
                
                is_valid = signature_engine.verify_signature(
                    log.signature,
                    log.raw_payload,
                    log.inbound.secret
                )
                
                validation_result['current_signature_valid'] = is_valid
            except Exception as e:
                validation_result['validation_error'] = str(e)
        
        return Response(validation_result)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get inbound webhook log statistics."""
        queryset = self.get_queryset()
        
        # Get overall statistics
        total_count = queryset.count()
        processed_count = queryset.filter(processed=True).count()
        unprocessed_count = queryset.filter(processed=False).count()
        signature_valid_count = queryset.filter(signature_valid=True).count()
        signature_invalid_count = queryset.filter(signature_valid=False).count()
        
        success_rate = (processed_count / total_count * 100) if total_count > 0 else 0
        
        return Response({
            'total_count': total_count,
            'processed_count': processed_count,
            'unprocessed_count': unprocessed_count,
            'signature_valid_count': signature_valid_count,
            'signature_invalid_count': signature_invalid_count,
            'success_rate': round(success_rate, 2)
        })
    
    @action(detail=False, methods=['get'])
    def by_inbound(self, request):
        """Get logs by inbound webhook ID."""
        inbound_id = request.query_params.get('inbound_id')
        if not inbound_id:
            return Response({
                'error': 'inbound_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            inbound = InboundWebhook.objects.get(id=inbound_id, created_by=request.user)
        except InboundWebhook.DoesNotExist:
            return Response({
                'error': 'Inbound webhook not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        logs = self.get_queryset().filter(inbound=inbound)
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_source(self, request):
        """Get logs by source."""
        source = request.query_params.get('source')
        if not source:
            return Response({
                'error': 'source parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logs = self.get_queryset().filter(inbound__source=source)
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Get logs by processing status."""
        processed = request.query_params.get('processed')
        if processed is not None:
            logs = self.get_queryset().filter(processed=processed.lower() == 'true')
        else:
            logs = self.get_queryset()
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_signature_validity(self, request):
        """Get logs by signature validity."""
        signature_valid = request.query_params.get('signature_valid')
        if signature_valid is not None:
            logs = self.get_queryset().filter(signature_valid=signature_valid.lower() == 'true')
        else:
            logs = self.get_queryset()
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent inbound webhook logs."""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        logs = self.get_queryset().filter(created_at__gte=since)
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unprocessed(self, request):
        """Get unprocessed inbound webhook logs."""
        logs = self.get_queryset().filter(processed=False)
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def invalid_signatures(self, request):
        """Get logs with invalid signatures."""
        logs = self.get_queryset().filter(signature_valid=False)
        
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_process(self, request):
        """Process multiple inbound webhook logs."""
        log_ids = request.data.get('log_ids', [])
        processed = request.data.get('processed', True)
        error_message = request.data.get('error_message', '')
        
        if not log_ids:
            return Response({
                'error': 'log_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logs = self.get_queryset().filter(id__in=log_ids, processed=False)
        
        processed_count = 0
        from ..services.inbound import InboundWebhookService
        service = InboundWebhookService()
        
        for log in logs:
            try:
                result = service.process_inbound_webhook_log(
                    log=log,
                    processed=processed,
                    error_message=error_message
                )
                if result['success']:
                    processed_count += 1
            except Exception as e:
                continue
        
        return Response({
            'message': f'Processed {processed_count} logs',
            'processed_count': processed_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_revalidate(self, request):
        """Revalidate signatures for multiple logs."""
        log_ids = request.data.get('log_ids', [])
        
        if not log_ids:
            return Response({
                'error': 'log_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logs = self.get_queryset().filter(id__in=log_ids)
        
        revalidated_count = 0
        signature_valid_count = 0
        signature_invalid_count = 0
        
        for log in logs:
            try:
                from ..services.signature_engine import SignatureEngine
                signature_engine = SignatureEngine()
                
                is_valid = signature_engine.verify_signature(
                    log.signature,
                    log.raw_payload,
                    log.inbound.secret
                )
                
                # Update log's signature validity
                log.signature_valid = is_valid
                log.save()
                
                revalidated_count += 1
                if is_valid:
                    signature_valid_count += 1
                else:
                    signature_invalid_count += 1
            except Exception as e:
                continue
        
        return Response({
            'message': f'Revalidated {revalidated_count} logs',
            'revalidated_count': revalidated_count,
            'signature_valid_count': signature_valid_count,
            'signature_invalid_count': signature_invalid_count
        })
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Get inbound webhook log trends."""
        days = int(request.query_params.get('days', 7))
        since = timezone.now() - timezone.timedelta(days=days)
        
        # Get daily trends
        trends = []
        for day in range(days):
            date = (timezone.now() - timezone.timedelta(days=day)).date()
            
            day_logs = self.get_queryset().filter(created_at__date=date)
            total_count = day_logs.count()
            processed_count = day_logs.filter(processed=True).count()
            signature_valid_count = day_logs.filter(signature_valid=True).count()
            
            trends.append({
                'date': date.isoformat(),
                'total_count': total_count,
                'processed_count': processed_count,
                'unprocessed_count': total_count - processed_count,
                'signature_valid_count': signature_valid_count,
                'signature_invalid_count': total_count - signature_valid_count
            })
        
        return Response({
            'trends': trends,
            'days': days
        })
    
    @action(detail=False, methods=['get'])
    def error_analysis(self, request):
        """Get error analysis for inbound webhook logs."""
        # Get logs with errors
        error_logs = self.get_queryset().filter(error_message__isnull=False)
        
        # Group by error type
        error_types = {}
        for log in error_logs:
            error_message = log.error_message or 'Unknown error'
            if error_message not in error_types:
                error_types[error_message] = 0
            error_types[error_message] += 1
        
        # Sort by frequency
        sorted_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        
        return Response({
            'total_error_logs': error_logs.count(),
            'error_types': [
                {
                    'error_message': error,
                    'count': count
                }
                for error, count in sorted_errors[:10]  # Top 10 errors
            ]
        })
    
    @action(detail=False, methods=['get'])
    def ip_analysis(self, request):
        """Get IP address analysis for inbound webhook logs."""
        # Get logs with IP addresses
        logs_with_ip = self.get_queryset().filter(ip_address__isnull=False)
        
        # Group by IP address
        ip_stats = {}
        for log in logs_with_ip:
            ip = log.ip_address
            if ip not in ip_stats:
                ip_stats[ip] = {
                    'total_count': 0,
                    'processed_count': 0,
                    'signature_valid_count': 0
                }
            
            ip_stats[ip]['total_count'] += 1
            if log.processed:
                ip_stats[ip]['processed_count'] += 1
            if log.signature_valid:
                ip_stats[ip]['signature_valid_count'] += 1
        
        # Calculate rates and sort by total count
        ip_analysis = []
        for ip, stats in ip_stats.items():
            total = stats['total_count']
            processed_rate = (stats['processed_count'] / total * 100) if total > 0 else 0
            signature_valid_rate = (stats['signature_valid_count'] / total * 100) if total > 0 else 0
            
            ip_analysis.append({
                'ip_address': ip,
                'total_count': total,
                'processed_count': stats['processed_count'],
                'signature_valid_count': stats['signature_valid_count'],
                'processed_rate': round(processed_rate, 2),
                'signature_valid_rate': round(signature_valid_rate, 2)
            })
        
        ip_analysis.sort(key=lambda x: x['total_count'], reverse=True)
        
        return Response({
            'ip_analysis': ip_analysis[:20],  # Top 20 IPs
            'total_unique_ips': len(ip_stats)
        })
