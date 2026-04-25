"""Admin Webhook ViewSet

This module contains the ViewSet for admin webhook operations.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ..serializers import (
    AdminWebhookEndpointSerializer,
    AdminWebhookSubscriptionSerializer,
    AdminWebhookDeliveryLogSerializer,
    AdminWebhookBatchOperationSerializer,
    AdminWebhookStatsSerializer,
    AdminWebhookHealthCheckSerializer,
    AdminWebhookHealthCheckResultSerializer,
    AdminWebhookCleanupSerializer,
    AdminWebhookExportSerializer,
    AdminWebhookImportSerializer,
    AdminWebhookTestSerializer,
    AdminWebhookTestResultSerializer
)
from ..permissions import IsSuperUser
from ..filters import AdminWebhookFilter


class AdminWebhookViewSet(viewsets.ModelViewSet):
    """ViewSet for admin webhook operations (superadmin only)."""
    
    queryset = WebhookEndpoint.objects.all()
    permission_classes = [IsAuthenticated, IsSuperUser]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AdminWebhookFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action in ['create', 'update', 'partial_update']:
            return AdminWebhookEndpointSerializer
        elif self.action == 'retrieve':
            return AdminWebhookEndpointSerializer
        elif self.action == 'list':
            return AdminWebhookEndpointSerializer
        else:
            return AdminWebhookEndpointSerializer
    
    @action(detail=False, methods=['get'])
    def global_statistics(self, request):
        """Get global webhook statistics."""
        # Get overall statistics
        total_endpoints = WebhookEndpoint.objects.count()
        active_endpoints = WebhookEndpoint.objects.filter(status='active').count()
        inactive_endpoints = WebhookEndpoint.objects.filter(status='inactive').count()
        suspended_endpoints = WebhookEndpoint.objects.filter(status='suspended').count()
        
        # Get subscription statistics
        total_subscriptions = WebhookSubscription.objects.count()
        active_subscriptions = WebhookSubscription.objects.filter(is_active=True).count()
        
        # Get delivery statistics
        total_deliveries = WebhookDeliveryLog.objects.count()
        successful_deliveries = WebhookDeliveryLog.objects.filter(status='success').count()
        failed_deliveries = WebhookDeliveryLog.objects.filter(status='failed').count()
        success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Get performance statistics
        successful_deliveries = WebhookDeliveryLog.objects.filter(status='success')
        avg_response_time = 0
        if successful_deliveries.exists():
            avg_response_time = successful_deliveries.aggregate(
                models.Avg('duration_ms')
            )['duration_ms__avg'] or 0
        
        return Response({
            'total_endpoints': total_endpoints,
            'active_endpoints': active_endpoints,
            'inactive_endpoints': inactive_endpoints,
            'suspended_endpoints': suspended_endpoints,
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'total_deliveries': total_deliveries,
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': round(success_rate, 2),
            'avg_response_time': round(avg_response_time, 2)
        })
    
    @action(detail=False, methods=['post'])
    def batch_operation(self, request):
        """Perform batch operations on endpoints."""
        serializer = AdminWebhookBatchOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_ids = serializer.validated_data['endpoint_ids']
        operation = serializer.validated_data['operation']
        
        try:
            endpoints = WebhookEndpoint.objects.filter(id__in=endpoint_ids)
            
            if operation == 'activate':
                updated_count = endpoints.update(status='active')
                message = f'Activated {updated_count} endpoints'
            elif operation == 'deactivate':
                updated_count = endpoints.update(status='inactive')
                message = f'Deactivated {updated_count} endpoints'
            elif operation == 'suspend':
                updated_count = endpoints.update(status='suspended')
                message = f'Suspended {updated_count} endpoints'
            elif operation == 'test':
                # Test endpoints
                from ..services.core import DispatchService
                dispatch_service = DispatchService()
                
                results = []
                for endpoint in endpoints:
                    try:
                        result = dispatch_service.emit(
                            endpoint=endpoint,
                            event_type='webhook.admin.test',
                            payload={'admin_test': True, 'timestamp': timezone.now().isoformat()}
                        )
                        results.append(f"{endpoint.label or endpoint.url}: {'Success' if result else 'Failed'}")
                    except Exception as e:
                        results.append(f"{endpoint.label or endpoint.url}: Error - {str(e)}")
                
                return Response({
                    'success': True,
                    'message': 'Test results',
                    'results': results
                })
            elif operation == 'rotate_secret':
                # Rotate secrets
                from ..services.core import SecretRotationService
                rotation_service = SecretRotationService()
                
                rotated_count = 0
                for endpoint in endpoints:
                    try:
                        new_secret = rotation_service.rotate_secret(endpoint)
                        rotated_count += 1
                    except Exception as e:
                        continue
                
                message = f'Rotated secrets for {rotated_count} endpoints'
            elif operation == 'check_health':
                # Check health
                from ..services.analytics import HealthMonitorService
                health_service = HealthMonitorService()
                
                results = []
                for endpoint in endpoints:
                    try:
                        health = health_service.check_endpoint_health(endpoint)
                        status = "Healthy" if health['is_healthy'] else "Unhealthy"
                        results.append(f"{endpoint.label or endpoint.url}: {status}")
                    except Exception as e:
                        results.append(f"{endpoint.label or endpoint.url}: Error - {str(e)}")
                
                return Response({
                    'success': True,
                    'message': 'Health check results',
                    'results': results
                })
            else:
                return Response({
                    'error': f'Unknown operation: {operation}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': message,
                'updated_count': updated_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': f'Batch operation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def health_check_all(self, request):
        """Perform health check on all endpoints."""
        serializer = AdminWebhookHealthCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_ids = serializer.validated_data.get('endpoint_ids')
        all_endpoints = serializer.validated_data.get('all_endpoints', False)
        force_check = serializer.validated_data.get('force_check', False)
        
        try:
            from ..services.analytics import HealthMonitorService
            health_service = HealthMonitorService()
            
            if all_endpoints:
                endpoints = WebhookEndpoint.objects.all()
            elif endpoint_ids:
                endpoints = WebhookEndpoint.objects.filter(id__in=endpoint_ids)
            else:
                endpoints = WebhookEndpoint.objects.filter(status='active')
            
            results = []
            for endpoint in endpoints:
                try:
                    health_result = health_service.check_endpoint_health(endpoint)
                    
                    result_data = {
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'is_healthy': health_result['is_healthy'],
                        'status_code': health_result.get('status_code'),
                        'response_time_ms': health_result.get('response_time_ms'),
                        'error': health_result.get('error'),
                        'checked_at': timezone.now().isoformat()
                    }
                    results.append(result_data)
                except Exception as e:
                    results.append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'is_healthy': False,
                        'error': str(e),
                        'checked_at': timezone.now().isoformat()
                    })
            
            return Response({
                'success': True,
                'results': results,
                'total_endpoints': len(results)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Health check failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cleanup_data(self, request):
        """Clean up old webhook data."""
        serializer = AdminWebhookCleanupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        operation = serializer.validated_data['operation']
        days = serializer.validated_data['days']
        
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            if operation == 'exhausted_logs':
                # Clean up exhausted logs
                from ..models import WebhookDeliveryLog
                deleted_count = WebhookDeliveryLog.objects.filter(
                    status='exhausted',
                    created_at__lt=cutoff_date
                ).delete()[0]
                message = f'Cleaned up {deleted_count} exhausted logs'
            elif operation == 'failed_logs':
                # Clean up failed logs
                from ..models import WebhookDeliveryLog
                deleted_count = WebhookDeliveryLog.objects.filter(
                    status='failed',
                    created_at__lt=cutoff_date
                ).delete()[0]
                message = f'Cleaned up {deleted_count} failed logs'
            elif operation == 'old_logs':
                # Clean up all old logs
                from ..models import WebhookDeliveryLog
                deleted_count = WebhookDeliveryLog.objects.filter(
                    created_at__lt=cutoff_date
                ).delete()[0]
                message = f'Cleaned up {deleted_count} old logs'
            elif operation == 'health_logs':
                # Clean up health logs
                from ..models import WebhookHealthLog
                deleted_count = WebhookHealthLog.objects.filter(
                    checked_at__lt=cutoff_date
                ).delete()[0]
                message = f'Cleaned up {deleted_count} health logs'
            elif operation == 'analytics':
                # Clean up analytics
                from ..models import WebhookAnalytics
                deleted_count = WebhookAnalytics.objects.filter(
                    date__lt=cutoff_date.date()
                ).delete()[0]
                message = f'Cleaned up {deleted_count} analytics records'
            elif operation == 'all_data':
                # Clean up all data
                from ..models import WebhookDeliveryLog, WebhookHealthLog, WebhookAnalytics
                
                delivery_deleted = WebhookDeliveryLog.objects.filter(
                    created_at__lt=cutoff_date
                ).delete()[0]
                
                health_deleted = WebhookHealthLog.objects.filter(
                    checked_at__lt=cutoff_date
                ).delete()[0]
                
                analytics_cutoff = timezone.now() - timedelta(days=365)
                analytics_deleted = WebhookAnalytics.objects.filter(
                    date__lt=analytics_cutoff.date()
                ).delete()[0]
                
                message = f'Cleaned up {delivery_deleted} delivery logs, {health_deleted} health logs, {analytics_deleted} analytics records'
            else:
                return Response({
                    'error': f'Unknown operation: {operation}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': message,
                'cutoff_date': cutoff_date.isoformat(),
                'days': days
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Data cleanup failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def export_data(self, request):
        """Export webhook data."""
        serializer = AdminWebhookExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        export_type = serializer.validated_data['export_type']
        export_format = serializer.validated_data['format']
        date_from = serializer.validated_data.get('date_from')
        date_to = serializer.validated_data.get('date_to')
        
        try:
            import csv
            import os
            from datetime import datetime
            
            # Create export directory
            export_dir = 'exports'
            os.makedirs(export_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'webhook_{export_type}_{timestamp}.{export_format}'
            filepath = os.path.join(export_dir, filename)
            
            # Export data based on type
            if export_type == 'endpoints':
                from ..models import WebhookEndpoint
                queryset = WebhookEndpoint.objects.all()
                
                if date_from:
                    queryset = queryset.filter(created_at__gte=date_from)
                if date_to:
                    queryset = queryset.filter(created_at__lte=date_to)
                
                # Write CSV
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'ID', 'Label', 'URL', 'Status', 'HTTP Method',
                        'Timeout', 'Max Retries', 'Verify SSL',
                        'Rate Limit', 'Owner', 'Created At'
                    ])
                    
                    # Write data
                    for endpoint in queryset:
                        writer.writerow([
                            str(endpoint.id),
                            endpoint.label or '',
                            endpoint.url,
                            endpoint.status,
                            endpoint.http_method,
                            endpoint.timeout_seconds,
                            endpoint.max_retries,
                            endpoint.verify_ssl,
                            endpoint.rate_limit_per_min,
                            endpoint.owner.username if endpoint.owner else '',
                            endpoint.created_at.isoformat()
                        ])
            
            elif export_type == 'subscriptions':
                from ..models import WebhookSubscription
                queryset = WebhookSubscription.objects.all()
                
                if date_from:
                    queryset = queryset.filter(created_at__gte=date_from)
                if date_to:
                    queryset = queryset.filter(created_at__lte=date_to)
                
                # Write CSV
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'ID', 'Endpoint', 'Event Type', 'Is Active',
                        'Filter Config', 'Created At'
                    ])
                    
                    # Write data
                    for subscription in queryset:
                        writer.writerow([
                            str(subscription.id),
                            str(subscription.endpoint.id),
                            subscription.event_type,
                            subscription.is_active,
                            str(subscription.filter_config) if subscription.filter_config else '',
                            subscription.created_at.isoformat()
                        ])
            
            elif export_type == 'delivery_logs':
                from ..models import WebhookDeliveryLog
                queryset = WebhookDeliveryLog.objects.all()
                
                if date_from:
                    queryset = queryset.filter(created_at__gte=date_from)
                if date_to:
                    queryset = queryset.filter(created_at__lte=date_to)
                
                # Write CSV
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'ID', 'Endpoint', 'Event Type', 'Status',
                        'HTTP Status Code', 'Duration (ms)', 'Error Message',
                        'Attempt Number', 'Created At'
                    ])
                    
                    # Write data
                    for log in queryset:
                        writer.writerow([
                            str(log.id),
                            str(log.endpoint.id),
                            log.event_type,
                            log.status,
                            log.http_status_code,
                            log.duration_ms,
                            log.error_message or '',
                            log.attempt_number,
                            log.created_at.isoformat()
                        ])
            
            else:
                return Response({
                    'error': f'Unknown export type: {export_type}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': f'Data exported to {filepath}',
                'filename': filename,
                'export_type': export_type,
                'format': export_format
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Data export failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def import_data(self, request):
        """Import webhook data."""
        serializer = AdminWebhookImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        import_type = serializer.validated_data['import_type']
        file = serializer.validated_data['file']
        overwrite = serializer.validated_data['overwrite']
        
        try:
            import csv
            import json
            
            # Read file content
            content = file.read().decode('utf-8')
            
            if import_type == 'endpoints':
                # Import endpoints
                reader = csv.DictReader(content.splitlines())
                imported_count = 0
                errors = []
                
                for row in reader:
                    try:
                        endpoint_data = {
                            'label': row.get('Label', ''),
                            'url': row['URL'],
                            'status': row.get('Status', 'active'),
                            'http_method': row.get('HTTP Method', 'POST'),
                            'timeout_seconds': int(row.get('Timeout', 30)),
                            'max_retries': int(row.get('Max Retries', 3)),
                            'verify_ssl': row.get('Verify SSL', 'True').lower() == 'true',
                            'rate_limit_per_min': int(row.get('Rate Limit', 60)),
                            'owner': request.user
                        }
                        
                        if overwrite:
                            endpoint, created = WebhookEndpoint.objects.update_or_create(
                                url=endpoint_data['url'],
                                defaults=endpoint_data
                            )
                        else:
                            endpoint = WebhookEndpoint.objects.create(**endpoint_data)
                        
                        imported_count += 1
                        
                    except Exception as e:
                        errors.append(f"Row {reader.line_num}: {str(e)}")
                        continue
                
                return Response({
                    'success': True,
                    'message': f'Imported {imported_count} endpoints',
                    'imported_count': imported_count,
                    'errors': errors
                })
            
            elif import_type == 'subscriptions':
                # Import subscriptions
                reader = csv.DictReader(content.splitlines())
                imported_count = 0
                errors = []
                
                for row in reader:
                    try:
                        subscription_data = {
                            'endpoint': WebhookEndpoint.objects.get(id=row['Endpoint']),
                            'event_type': row['Event Type'],
                            'is_active': row.get('Is Active', 'True').lower() == 'true',
                            'filter_config': json.loads(row.get('Filter Config', '{}'))
                        }
                        
                        if overwrite:
                            subscription, created = WebhookSubscription.objects.update_or_create(
                                endpoint=subscription_data['endpoint'],
                                event_type=subscription_data['event_type'],
                                defaults=subscription_data
                            )
                        else:
                            subscription = WebhookSubscription.objects.create(**subscription_data)
                        
                        imported_count += 1
                        
                    except Exception as e:
                        errors.append(f"Row {reader.line_num}: {str(e)}")
                        continue
                
                return Response({
                    'success': True,
                    'message': f'Imported {imported_count} subscriptions',
                    'imported_count': imported_count,
                    'errors': errors
                })
            
            else:
                return Response({
                    'error': f'Unknown import type: {import_type}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Data import failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def test_endpoint(self, request):
        """Test an endpoint."""
        serializer = AdminWebhookTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_id = serializer.validated_data['endpoint_id']
        test_payload = serializer.validated_data.get('test_payload')
        custom_headers = serializer.validated_data.get('custom_headers')
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
            
            # Prepare test payload
            if not test_payload:
                test_payload = {
                    'admin_test': True,
                    'timestamp': timezone.now().isoformat(),
                    'message': 'Admin test webhook'
                }
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'X-Admin-Test': 'True'
            }
            if custom_headers:
                headers.update(custom_headers)
            
            # Send test webhook
            from ..services.core import DispatchService
            dispatch_service = DispatchService()
            
            start_time = timezone.now()
            result = dispatch_service.emit(
                endpoint=endpoint,
                event_type='webhook.admin.test',
                payload=test_payload,
                headers=headers
            )
            end_time = timezone.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Get delivery log
            from ..models import WebhookDeliveryLog
            delivery_log = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                event_type='webhook.admin.test',
                created_at__gte=start_time
            ).first()
            
            result_data = {
                'success': result,
                'endpoint_id': str(endpoint_id),
                'endpoint_label': endpoint.label,
                'endpoint_url': endpoint.url,
                'processing_time': processing_time,
                'test_payload': test_payload,
                'tested_at': end_time.isoformat()
            }
            
            if result and delivery_log:
                result_data['status_code'] = delivery_log.http_status_code
                result_data['response_time_ms'] = delivery_log.duration_ms
                result_data['response_body'] = delivery_log.response_body
            elif not result:
                result_data['error'] = 'Test webhook failed'
            
            return Response(result_data)
            
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Test webhook failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """Get system health overview."""
        try:
            # Check database connectivity
            from django.db import connection
            connection.ensure_connection()
            
            # Check Redis connectivity (if available)
            redis_status = 'unknown'
            try:
                from django.core.cache import cache
                cache.set('health_check', 'ok', 10)
                redis_status = 'ok' if cache.get('health_check') == 'ok' else 'error'
            except:
                redis_status = 'unavailable'
            
            # Check Celery connectivity (if available)
            celery_status = 'unknown'
            try:
                from celery import current_app
                celery_status = 'ok' if current_app else 'error'
            except:
                celery_status = 'unavailable'
            
            # Get system statistics
            from ..models import WebhookEndpoint, WebhookDeliveryLog
            
            total_endpoints = WebhookEndpoint.objects.count()
            total_deliveries = WebhookDeliveryLog.objects.count()
            
            # Get recent activity
            from datetime import timedelta
            recent_deliveries = WebhookDeliveryLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            return Response({
                'database_status': 'ok',
                'redis_status': redis_status,
                'celery_status': celery_status,
                'total_endpoints': total_endpoints,
                'total_deliveries': total_deliveries,
                'recent_deliveries_1h': recent_deliveries,
                'system_time': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'database_status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
