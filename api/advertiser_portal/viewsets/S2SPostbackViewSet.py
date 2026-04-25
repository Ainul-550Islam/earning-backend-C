"""
S2S Postback ViewSet

ViewSet for server-to-server postback management,
including configuration, testing, and validation.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from ..models.tracking import S2SPostback
try:
    from ..services import S2SPostbackService
except ImportError:
    S2SPostbackService = None
from ..serializers import S2SPostbackSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class S2SPostbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for server-to-server postback management.
    
    Handles postback configuration, testing, sending,
    and validation.
    """
    
    queryset = S2SPostback.objects.all()
    serializer_class = S2SPostbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all postbacks
            return S2SPostback.objects.all()
        else:
            # Advertisers can only see their own postbacks
            return S2SPostback.objects.filter(advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create postback with associated advertiser."""
        user = self.request.user
        
        # Get advertiser for user
        from ..models.advertiser import Advertiser
        advertiser = get_object_or_404(Advertiser, user=user)
        
        postback_service = S2SPostbackService()
        postback = postback_service.create_s2s_postback(advertiser, serializer.validated_data)
        serializer.instance = postback
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test S2S postback.
        
        Validates postback configuration and connectivity.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        test_data = request.data.get('test_data', {})
        
        try:
            postback_service = S2SPostbackService()
            test_result = postback_service.test_postback(postback, test_data)
            
            return Response(test_result)
            
        except Exception as e:
            logger.error(f"Error testing postback: {e}")
            return Response(
                {'detail': 'Failed to test postback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def send_test(self, request, pk=None):
        """
        Send test postback.
        
        Sends actual test postback to configured URL.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        test_data = request.data.get('test_data', {})
        
        try:
            postback_service = S2SPostbackService()
            send_result = postback_service.send_test_postback(postback, test_data)
            
            return Response(send_result)
            
        except Exception as e:
            logger.error(f"Error sending test postback: {e}")
            return Response(
                {'detail': 'Failed to send test postback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate postback configuration.
        
        Checks URL, parameters, and security settings.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            postback_service = S2SPostbackService()
            validation_result = postback_service.validate_postback(postback)
            
            return Response(validation_result)
            
        except Exception as e:
            logger.error(f"Error validating postback: {e}")
            return Response(
                {'detail': 'Failed to validate postback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_url(self, request, pk=None):
        """
        Update postback URL.
        
        Updates the postback endpoint URL.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        postback_url = request.data.get('postback_url')
        
        if not postback_url:
            return Response(
                {'detail': 'Postback URL is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            postback_service = S2SPostbackService()
            updated_postback = postback_service.update_postback_url(postback, postback_url)
            
            serializer = self.get_serializer(updated_postback)
            return Response({
                'detail': 'Postback URL updated successfully',
                'postback': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating postback URL: {e}")
            return Response(
                {'detail': 'Failed to update postback URL'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_parameters(self, request, pk=None):
        """
        Update postback parameters.
        
        Updates the parameter configuration.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        parameters = request.data.get('parameters', {})
        
        try:
            postback_service = S2SPostbackService()
            updated_postback = postback_service.update_postback_parameters(postback, parameters)
            
            serializer = self.get_serializer(updated_postback)
            return Response({
                'detail': 'Postback parameters updated successfully',
                'postback': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating postback parameters: {e}")
            return Response(
                {'detail': 'Failed to update postback parameters'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_security(self, request, pk=None):
        """
        Update security settings.
        
        Updates HMAC and other security configurations.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        security_config = request.data.get('security', {})
        
        try:
            postback_service = S2SPostbackService()
            updated_postback = postback_service.update_security_settings(postback, security_config)
            
            serializer = self.get_serializer(updated_postback)
            return Response({
                'detail': 'Security settings updated successfully',
                'postback': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating security settings: {e}")
            return Response(
                {'detail': 'Failed to update security settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def regenerate_secret(self, request, pk=None):
        """
        Regenerate postback secret.
        
        Creates new HMAC secret key.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            postback_service = S2SPostbackService()
            updated_postback = postback_service.regenerate_postback_secret(postback)
            
            return Response({
                'detail': 'Postback secret regenerated successfully',
                'secret': updated_postback.secret,
                'updated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error regenerating postback secret: {e}")
            return Response(
                {'detail': 'Failed to regenerate postback secret'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """
        Enable S2S postback.
        
        Makes postback active for sending.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            postback.is_active = True
            postback.save()
            
            return Response({
                'detail': 'Postback enabled successfully',
                'is_active': True
            })
            
        except Exception as e:
            logger.error(f"Error enabling postback: {e}")
            return Response(
                {'detail': 'Failed to enable postback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """
        Disable S2S postback.
        
        Makes postback inactive.
        """
        postback = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or postback.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            postback.is_active = False
            postback.save()
            
            return Response({
                'detail': 'Postback disabled successfully',
                'is_active': False
            })
            
        except Exception as e:
            logger.error(f"Error disabling postback: {e}")
            return Response(
                {'detail': 'Failed to disable postback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """
        Get postback analytics.
        
        Returns sending statistics and performance metrics.
        """
        postback = self.get_object()
        
        try:
            postback_service = S2SPostbackService()
            analytics = postback_service.get_postback_analytics(postback)
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting postback analytics: {e}")
            return Response(
                {'detail': 'Failed to get analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def sending_history(self, request, pk=None):
        """
        Get postback sending history.
        
        Returns recent sending events and statistics.
        """
        postback = self.get_object()
        
        days = request.query_params.get('days', 7)
        
        try:
            # This would implement actual sending history tracking
            # For now, return placeholder data
            history = {
                'postback_id': postback.id,
                'postback_name': postback.name,
                'postback_url': postback.postback_url,
                'period_days': int(days),
                'total_sends': 0,
                'successful_sends': 0,
                'failed_sends': 0,
                'success_rate': 0.0,
                'average_response_time': 0.0,
                'daily_breakdown': {},
                'recent_sends': [],
                'error_breakdown': {},
            }
            
            return Response(history)
            
        except Exception as e:
            logger.error(f"Error getting sending history: {e}")
            return Response(
                {'detail': 'Failed to get sending history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get postback preview.
        
        Returns postback configuration preview and sample requests.
        """
        postback = self.get_object()
        
        try:
            postback_service = S2SPostbackService()
            
            # Generate sample postback URL with parameters
            sample_url = postback_service.generate_sample_postback_url(postback)
            
            # Generate sample payload
            sample_payload = postback_service.generate_sample_payload(postback)
            
            preview_data = {
                'postback_id': postback.id,
                'postback_name': postback.name,
                'postback_url': postback.postback_url,
                'method': postback.method,
                'is_active': postback.is_active,
                'timeout_ms': postback.timeout_ms,
                'retry_attempts': postback.retry_attempts,
                'retry_delay_ms': postback.retry_delay_ms,
                'sample_url': sample_url,
                'sample_payload': sample_payload,
                'parameters': postback.parameters,
                'security': {
                    'use_hmac': postback.use_hmac,
                    'hmac_algorithm': postback.hmac_algorithm,
                    'hmac_header': postback.hmac_header,
                },
                'headers': postback.headers,
                'created_at': postback.created_at.isoformat(),
            }
            
            return Response(preview_data)
            
        except Exception as e:
            logger.error(f"Error getting postback preview: {e}")
            return Response(
                {'detail': 'Failed to get preview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def postback_methods(self, request):
        """
        Get available postback methods.
        
        Returns list of supported HTTP methods.
        """
        try:
            methods = {
                'GET': {
                    'name': 'GET',
                    'description': 'Send postback via GET request',
                    'suitable_for': 'Simple postbacks with small data',
                },
                'POST': {
                    'name': 'POST',
                    'description': 'Send postback via POST request',
                    'suitable_for': 'Complex postbacks with large data',
                },
                'PUT': {
                    'name': 'PUT',
                    'description': 'Send postback via PUT request',
                    'suitable_for': 'Update operations',
                },
                'PATCH': {
                    'name': 'PATCH',
                    'description': 'Send postback via PATCH request',
                    'suitable_for': 'Partial updates',
                },
            }
            
            return Response(methods)
            
        except Exception as e:
            logger.error(f"Error getting postback methods: {e}")
            return Response(
                {'detail': 'Failed to get postback methods'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def security_options(self, request):
        """
        Get available security options.
        
        Returns list of supported security configurations.
        """
        try:
            security_options = {
                'hmac_algorithms': {
                    'SHA256': {
                        'name': 'SHA-256',
                        'description': 'HMAC using SHA-256 algorithm',
                        'security_level': 'high',
                    },
                    'SHA1': {
                        'name': 'SHA-1',
                        'description': 'HMAC using SHA-1 algorithm',
                        'security_level': 'medium',
                    },
                    'MD5': {
                        'name': 'MD5',
                        'description': 'HMAC using MD5 algorithm',
                        'security_level': 'low',
                    },
                },
                'common_headers': {
                    'X-Signature': 'Standard signature header',
                    'X-HMAC': 'HMAC signature header',
                    'X-Auth-Signature': 'Authentication signature header',
                    'Authorization': 'Authorization header with signature',
                },
                'best_practices': {
                    'use_https': 'Always use HTTPS URLs for postbacks',
                    'rotate_secrets': 'Regularly rotate HMAC secrets',
                    'validate_ip': 'Validate source IP addresses',
                    'rate_limit': 'Implement rate limiting',
                }
            }
            
            return Response(security_options)
            
        except Exception as e:
            logger.error(f"Error getting security options: {e}")
            return Response(
                {'detail': 'Failed to get security options'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_postback_config(self, request):
        """
        Validate postback configuration.
        
        Checks for logical errors and best practices.
        """
        config = request.data.get('config', {})
        
        if not config:
            return Response(
                {'detail': 'No configuration provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': [],
            }
            
            # Check required fields
            required_fields = ['name', 'postback_url']
            for field in required_fields:
                if field not in config:
                    validation_results['errors'].append(f'Missing required field: {field}')
                    validation_results['is_valid'] = False
            
            # Check URL format
            postback_url = config.get('postback_url')
            if postback_url:
                if not postback_url.startswith(('http://', 'https://')):
                    validation_results['errors'].append('Postback URL must start with http:// or https://')
                    validation_results['is_valid'] = False
                elif not postback_url.startswith('https://'):
                    validation_results['warnings'].append('Consider using HTTPS for better security')
            
            # Check method
            method = config.get('method', 'GET')
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH']
            if method not in valid_methods:
                validation_results['errors'].append(f'Invalid method: {method}')
                validation_results['is_valid'] = False
            
            # Check timeout
            timeout_ms = config.get('timeout_ms')
            if timeout_ms is not None and timeout_ms <= 0:
                validation_results['errors'].append('Timeout must be positive')
                validation_results['is_valid'] = False
            elif timeout_ms is not None and timeout_ms > 30000:
                validation_results['warnings'].append('Very long timeout may affect performance')
            
            # Check retry settings
            retry_attempts = config.get('retry_attempts')
            if retry_attempts is not None:
                if retry_attempts < 0:
                    validation_results['errors'].append('Retry attempts cannot be negative')
                    validation_results['is_valid'] = False
                elif retry_attempts > 10:
                    validation_results['warnings'].append('High number of retry attempts may be excessive')
            
            retry_delay_ms = config.get('retry_delay_ms')
            if retry_delay_ms is not None and retry_delay_ms < 0:
                validation_results['errors'].append('Retry delay cannot be negative')
                validation_results['is_valid'] = False
            
            # Check security settings
            use_hmac = config.get('use_hmac', False)
            if use_hmac:
                hmac_algorithm = config.get('hmac_algorithm')
                if not hmac_algorithm:
                    validation_results['errors'].append('HMAC algorithm is required when HMAC is enabled')
                    validation_results['is_valid'] = False
                else:
                    valid_algorithms = ['SHA256', 'SHA1', 'MD5']
                    if hmac_algorithm not in valid_algorithms:
                        validation_results['errors'].append(f'Invalid HMAC algorithm: {hmac_algorithm}')
                        validation_results['is_valid'] = False
            
            # Generate recommendations
            if validation_results['is_valid']:
                if not config.get('use_hmac', False):
                    validation_results['recommendations'].append('Consider enabling HMAC for better security')
                
                if not config.get('retry_attempts'):
                    validation_results['recommendations'].append('Set retry attempts for better reliability')
                
                if not config.get('timeout_ms'):
                    validation_results['recommendations'].append('Set a timeout to prevent hanging requests')
            
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Error validating postback config: {e}")
            return Response(
                {'detail': 'Failed to validate configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_test(self, request):
        """
        Bulk test multiple postbacks.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        postback_ids = request.data.get('postback_ids', [])
        
        if not postback_ids:
            return Response(
                {'detail': 'No postback IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            postback_service = S2SPostbackService()
            
            results = {
                'tested': 0,
                'failed': 0,
                'errors': []
            }
            
            for postback_id in postback_ids:
                try:
                    postback = S2SPostback.objects.get(id=postback_id)
                    test_result = postback_service.test_postback(postback, {})
                    
                    if test_result.get('overall_status') == 'passed':
                        results['tested'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'postback_id': postback_id,
                            'error': 'Test failed',
                            'issues': test_result.get('issues', [])
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'postback_id': postback_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk test: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        method = request.query_params.get('method')
        is_active = request.query_params.get('is_active')
        use_hmac = request.query_params.get('use_hmac')
        search = request.query_params.get('search')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if method:
            queryset = queryset.filter(method=method)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if use_hmac is not None:
            queryset = queryset.filter(use_hmac=use_hmac.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(postback_url__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
