"""
Utility Viewsets for Offer Routing System

This module contains utility viewsets for validation,
testing, and helper operations.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from ..services.utils import utils_service, validation_service
from ..services.evaluator import route_evaluator
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError

User = get_user_model()


class ValidationViewSet(viewsets.ViewSet):
    """
    ViewSet for validation operations.
    
    Provides endpoints for validating offer data,
    route configurations, and other routing components.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    @action(detail=False, methods=['post'])
    def validate_offer_data(self, request):
        """Validate offer data structure."""
        try:
            offer_data = request.data.get('offer_data', {})
            
            if not offer_data:
                return Response({
                    'success': False,
                    'error': 'offer_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validation_result = validation_service.validate_offer_data(offer_data)
            
            return Response({
                'success': True,
                'validation_result': validation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_route_data(self, request):
        """Validate route data structure."""
        try:
            route_data = request.data.get('route_data', {})
            
            if not route_data:
                return Response({
                    'success': False,
                    'error': 'route_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validation_result = validation_service.validate_route_data(route_data)
            
            return Response({
                'success': True,
                'validation_result': validation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_routing_data(self, request):
        """Validate routing request data."""
        try:
            validation_result = utils_service.validate_routing_data(request.data)
            
            return Response({
                'success': True,
                'validation_result': validation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def extract_user_agent(self, request):
        """Extract user agent information."""
        try:
            user_agent = request.data.get('user_agent')
            
            if not user_agent:
                return Response({
                    'success': False,
                    'error': 'user_agent is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_agent_info = utils_service.extract_user_agent_info(user_agent)
            
            return Response({
                'success': True,
                'user_agent': user_agent,
                'user_agent_info': user_agent_info
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def parse_ip_address(self, request):
        """Parse and validate IP address."""
        try:
            ip_address = request.data.get('ip_address')
            
            if not ip_address:
                return Response({
                    'success': False,
                    'error': 'ip_address is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            ip_info = utils_service.parse_ip_address(ip_address)
            
            return Response({
                'success': True,
                'ip_address': ip_address,
                'ip_info': ip_info
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def calculate_percentile(self, request):
        """Calculate percentile rank of a value."""
        try:
            values = request.data.get('values', [])
            target_value = request.data.get('target_value')
            
            if not values or target_value is None:
                return Response({
                    'success': False,
                    'error': 'values and target_value are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            percentile = utils_service.calculate_percentile(values, target_value)
            
            return Response({
                'success': True,
                'target_value': target_value,
                'percentile': percentile,
                'total_values': len(values)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def normalize_score(self, request):
        """Normalize score to specified range."""
        try:
            score = request.data.get('score')
            min_val = request.data.get('min_val', 0)
            max_val = request.data.get('max_val', 100)
            
            if score is None:
                return Response({
                    'success': False,
                    'error': 'score is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            normalized_score = utils_service.normalize_score(score, min_val, max_val)
            
            return Response({
                'success': True,
                'original_score': score,
                'normalized_score': normalized_score,
                'min_val': min_val,
                'max_val': max_val
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestingViewSet(viewsets.ViewSet):
    """
    ViewSet for testing operations.
    
    Provides endpoints for testing routes, configurations,
    and other routing components.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    @action(detail=False, methods=['post'])
    def test_route_with_user(self, request):
        """Test route with a specific user."""
        try:
            route_id = request.data.get('route_id')
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            
            if not route_id or not user_id:
                return Response({
                    'success': False,
                    'error': 'route_id and user_id are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify route belongs to tenant
            from ..models import OfferRoute
            try:
                route = OfferRoute.objects.get(id=route_id)
                if route.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'Route not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except OfferRoute.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Route not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test route
            test_result = route_evaluator.test_route_with_user(route, user, context)
            
            return Response({
                'success': True,
                'test_result': test_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_all_routes(self, request):
        """Validate all routes for the tenant."""
        try:
            validation_results = route_evaluator.validate_all_routes(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'validation_results': validation_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def test_routing_engine(self, request):
        """Test routing engine with sample data."""
        try:
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            limit = request.data.get('limit', 10)
            
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test routing engine
            from ..services.core import routing_engine
            
            routing_result = routing_engine.route_offers(
                user_id=user_id,
                context=context,
                limit=limit,
                cache_enabled=False  # Don't use cache for testing
            )
            
            return Response({
                'success': True,
                'routing_result': routing_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def simulate_load_test(self, request):
        """Simulate load test on routing engine."""
        try:
            user_ids = request.data.get('user_ids', [])
            context = request.data.get('context', {})
            requests_per_user = request.data.get('requests_per_user', 10)
            
            if not user_ids:
                return Response({
                    'success': False,
                    'error': 'user_ids is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify users belong to tenant
            valid_users = []
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id)
                    if user.tenant == request.user:
                        valid_users.append(user_id)
                except User.DoesNotExist:
                    continue
            
            if not valid_users:
                return Response({
                    'success': False,
                    'error': 'No valid users found in your tenant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Simulate load test
            from ..services.core import routing_engine
            import time
            
            results = []
            start_time = time.time()
            
            for user_id in valid_users:
                for i in range(requests_per_user):
                    try:
                        routing_result = routing_engine.route_offers(
                            user_id=user_id,
                            context=context,
                            limit=5,
                            cache_enabled=True
                        )
                        results.append({
                            'user_id': user_id,
                            'request': i + 1,
                            'success': routing_result['success'],
                            'offer_count': len(routing_result.get('offers', [])),
                            'response_time_ms': routing_result.get('metadata', {}).get('response_time_ms', 0)
                        })
                    except Exception as e:
                        results.append({
                            'user_id': user_id,
                            'request': i + 1,
                            'success': False,
                            'error': str(e),
                            'response_time_ms': 0
                        })
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Calculate statistics
            total_requests = len(results)
            successful_requests = len([r for r in results if r['success']])
            failed_requests = total_requests - successful_requests
            success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
            avg_response_time = sum(r['response_time_ms'] for r in results) / total_requests if total_requests > 0 else 0
            
            return Response({
                'success': True,
                'load_test_results': {
                    'total_users': len(valid_users),
                    'requests_per_user': requests_per_user,
                    'total_requests': total_requests,
                    'successful_requests': successful_requests,
                    'failed_requests': failed_requests,
                    'success_rate': success_rate,
                    'avg_response_time_ms': avg_response_time,
                    'total_time_seconds': total_time,
                    'requests_per_second': total_requests / total_time if total_time > 0 else 0
                },
                'detailed_results': results[:100]  # Return first 100 results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def benchmark_performance(self, request):
        """Benchmark routing performance."""
        try:
            iterations = int(request.data.get('iterations', 100))
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Benchmark routing engine
            from ..services.core import routing_engine
            import time
            
            response_times = []
            
            for i in range(iterations):
                start_time = time.time()
                
                routing_result = routing_engine.route_offers(
                    user_id=user_id,
                    context=context,
                    limit=10,
                    cache_enabled=True
                )
                
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                response_times.append(response_time)
            
            # Calculate statistics
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            median_response_time = sorted(response_times)[len(response_times) // 2]
            
            # Calculate percentiles
            p95 = sorted(response_times)[int(len(response_times) * 0.95)]
            p99 = sorted(response_times)[int(len(response_times) * 0.99)]
            
            return Response({
                'success': True,
                'benchmark_results': {
                    'iterations': iterations,
                    'avg_response_time_ms': avg_response_time,
                    'min_response_time_ms': min_response_time,
                    'max_response_time_ms': max_response_time,
                    'median_response_time_ms': median_response_time,
                    'p95_response_time_ms': p95,
                    'p99_response_time_ms': p99
                }
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HelperViewSet(viewsets.ViewSet):
    """
    ViewSet for helper operations.
    
    Provides endpoints for common helper functions
    and utility operations.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    @action(detail=False, methods=['get'])
    def generate_user_hash(self, request):
        """Generate consistent hash for user."""
        try:
            user_id = request.query_params.get('user_id')
            additional_data = request.query_params.get('additional_data', '{}')
            
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse additional data
            try:
                import json
                additional_data_dict = json.loads(additional_data) if isinstance(additional_data, str) else additional_data
            except:
                additional_data_dict = {}
            
            user_hash = utils_service.generate_user_hash(int(user_id), additional_data_dict)
            
            return Response({
                'success': True,
                'user_id': user_id,
                'additional_data': additional_data_dict,
                'user_hash': user_hash
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def generate_context_hash(self, request):
        """Generate hash for context data."""
        try:
            context = request.query_params.dict()
            
            if not context:
                return Response({
                    'success': False,
                    'error': 'No context parameters provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            context_hash = utils_service.generate_context_hash(context)
            
            return Response({
                'success': True,
                'context': context,
                'context_hash': context_hash
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def format_routing_response(self, request):
        """Format routing response data."""
        try:
            success = request.data.get('success', True)
            offers = request.data.get('offers', [])
            metadata = request.data.get('metadata', {})
            
            formatted_response = utils_service.format_routing_response(
                success=success,
                offers=offers,
                metadata=metadata
            )
            
            return Response({
                'success': True,
                'formatted_response': formatted_response
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def calculate_routing_quality_score(self, request):
        """Calculate routing quality score."""
        try:
            response_time_ms = float(request.query_params.get('response_time_ms', 0))
            cache_hit_rate = float(request.query_params.get('cache_hit_rate', 0))
            error_rate = float(request.query_params.get('error_rate', 0))
            
            quality_score = utils_service.calculate_routing_quality_score(
                response_time_ms=response_time_ms,
                cache_hit_rate=cache_hit_rate,
                error_rate=error_rate
            )
            
            return Response({
                'success': True,
                'response_time_ms': response_time_ms,
                'cache_hit_rate': cache_hit_rate,
                'error_rate': error_rate,
                'quality_score': quality_score
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cleanup_old_data(self, request):
        """Clean up old routing data."""
        try:
            days = int(request.data.get('days', 90))
            
            deleted_count = utils_service.cleanup_old_data(days)
            
            return Response({
                'success': True,
                'deleted_count': deleted_count,
                'retention_days': days
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def export_routing_data(self, request):
        """Export routing data for analysis."""
        try:
            days = int(request.data.get('days', 30))
            
            export_data = utils_service.export_routing_data(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'export_data': export_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def import_routing_data(self, request):
        """Import routing data from export."""
        try:
            import_data = request.data.get('import_data', {})
            
            if not import_data:
                return Response({
                    'success': False,
                    'error': 'import_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success = utils_service.import_routing_data(
                tenant_id=request.user.id,
                import_data=import_data
            )
            
            return Response({
                'success': success,
                'imported_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
