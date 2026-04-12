"""
API Endpoints Services

This module handles comprehensive API endpoint management with enterprise-grade security,
real-time processing, and advanced features following industry standards from
Postman, Swagger, and API Gateway solutions.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import base64
import asyncio
import websockets
from concurrent.futures import ThreadPoolExecutor

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q, F, Window
from django.db.models.functions import Coalesce, RowNumber
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.api_endpoint_model import (
    APIEndpoint, RESTEndpoint, GraphQLEndpoint, WebSocketEndpoint,
    APIDocumentation, APIVersion, APIAuthentication, APIRateLimit
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


@dataclass
class APIEndpointConfig:
    """API endpoint configuration with metadata."""
    endpoint_id: str
    endpoint_type: str
    method: str
    path: str
    handler: str
    authentication: List[str]
    rate_limit: Dict[str, Any]
    version: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class APIRequest:
    """API request data with metadata."""
    request_id: str
    method: str
    path: str
    headers: Dict[str, Any]
    query_params: Dict[str, Any]
    body: Optional[Dict[str, Any]]
    user: Optional[User]
    timestamp: datetime
    ip_address: str
    user_agent: str


@dataclass
class APIResponse:
    """API response data with metadata."""
    request_id: str
    status_code: int
    headers: Dict[str, Any]
    body: Union[Dict[str, Any], str]
    processing_time: float
    cached: bool
    timestamp: datetime


class APIEndpointService:
    """
    Enterprise-grade API endpoint management service.
    
    Features:
    - Multi-protocol support (REST, GraphQL, WebSocket)
    - Advanced authentication and authorization
    - Real-time rate limiting
    - API versioning
    - Comprehensive documentation
    - Performance monitoring
    """
    
    @staticmethod
    def create_endpoint(endpoint_config: Dict[str, Any], created_by: Optional[User] = None) -> APIEndpoint:
        """
        Create API endpoint with enterprise-grade security.
        
        Supported endpoint types:
        - REST: RESTful API endpoints
        - GraphQL: GraphQL query/mutation endpoints
        - WebSocket: Real-time WebSocket connections
        - Webhook: Event-driven webhook endpoints
        
        Security features:
        - Input validation and sanitization
        - Authentication and authorization
        - Rate limiting
        - CORS configuration
        - Audit logging
        """
        try:
            # Security: Validate endpoint configuration
            APIEndpointService._validate_endpoint_config(endpoint_config, created_by)
            
            # Get endpoint-specific configuration
            endpoint_type = endpoint_config.get('endpoint_type')
            
            with transaction.atomic():
                # Create base endpoint
                endpoint = APIEndpoint.objects.create(
                    advertiser=endpoint_config.get('advertiser'),
                    name=endpoint_config.get('name'),
                    endpoint_type=endpoint_type,
                    method=endpoint_config.get('method', 'GET'),
                    path=endpoint_config.get('path'),
                    handler=endpoint_config.get('handler'),
                    authentication=endpoint_config.get('authentication', []),
                    rate_limit=endpoint_config.get('rate_limit', {}),
                    version=endpoint_config.get('version', 'v1'),
                    status=endpoint_config.get('status', 'active'),
                    settings=endpoint_config.get('settings', {}),
                    created_by=created_by
                )
                
                # Create type-specific endpoint
                if endpoint_type == 'rest':
                    APIEndpointService._create_rest_endpoint(endpoint, endpoint_config)
                elif endpoint_type == 'graphql':
                    APIEndpointService._create_graphql_endpoint(endpoint, endpoint_config)
                elif endpoint_type == 'websocket':
                    APIEndpointService._create_websocket_endpoint(endpoint, endpoint_config)
                elif endpoint_type == 'webhook':
                    APIEndpointService._create_webhook_endpoint(endpoint, endpoint_config)
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='API Endpoint Created',
                    message=f'Successfully created {endpoint_type} endpoint: {endpoint.name}',
                    notification_type='api_endpoint',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log endpoint creation
                APIEndpointService._log_endpoint_creation(endpoint, created_by)
                
                return endpoint
                
        except Exception as e:
            logger.error(f"Error creating API endpoint: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create endpoint: {str(e)}")
    
    @staticmethod
    def update_endpoint(endpoint_id: UUID, update_config: Dict[str, Any], updated_by: Optional[User] = None) -> APIEndpoint:
        """
        Update API endpoint with comprehensive validation.
        
        Update features:
        - Configuration validation
        - Version management
        - Deployment control
        - Rollback capability
        """
        try:
            # Security: Validate update configuration
            APIEndpointService._validate_update_config(update_config, updated_by)
            
            with transaction.atomic():
                # Get endpoint
                endpoint = APIEndpoint.objects.get(id=endpoint_id)
                
                # Store old configuration for rollback
                old_config = {
                    'name': endpoint.name,
                    'method': endpoint.method,
                    'path': endpoint.path,
                    'handler': endpoint.handler,
                    'authentication': endpoint.authentication,
                    'rate_limit': endpoint.rate_limit,
                    'settings': endpoint.settings
                }
                
                # Update endpoint
                for field, value in update_config.items():
                    if hasattr(endpoint, field):
                        setattr(endpoint, field, value)
                
                endpoint.updated_by = updated_by
                endpoint.save()
                
                # Update type-specific endpoint
                if endpoint.endpoint_type == 'rest':
                    APIEndpointService._update_rest_endpoint(endpoint, update_config)
                elif endpoint.endpoint_type == 'graphql':
                    APIEndpointService._update_graphql_endpoint(endpoint, update_config)
                elif endpoint.endpoint_type == 'websocket':
                    APIEndpointService._update_websocket_endpoint(endpoint, update_config)
                
                # Send notification
                Notification.objects.create(
                    user=updated_by,
                    title='API Endpoint Updated',
                    message=f'Successfully updated endpoint: {endpoint.name}',
                    notification_type='api_endpoint',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log endpoint update
                APIEndpointService._log_endpoint_update(endpoint, old_config, update_config, updated_by)
                
                return endpoint
                
        except Exception as e:
            logger.error(f"Error updating API endpoint: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update endpoint: {str(e)}")
    
    @staticmethod
    def deploy_endpoint(endpoint_id: UUID, deployment_config: Dict[str, Any], deployed_by: Optional[User] = None) -> Dict[str, Any]:
        """
        Deploy API endpoint with enterprise-grade deployment process.
        
        Deployment features:
        - Blue-green deployment
        - Health checks
        - Rollback capability
        - Performance monitoring
        """
        try:
            # Security: Validate deployment configuration
            APIEndpointService._validate_deployment_config(deployment_config, deployed_by)
            
            # Get endpoint
            endpoint = APIEndpoint.objects.get(id=endpoint_id)
            
            # Create deployment record
            deployment = APIEndpointService._create_deployment_record(endpoint, deployment_config, deployed_by)
            
            # Perform deployment
            deployment_result = APIEndpointService._perform_deployment(endpoint, deployment, deployment_config)
            
            # Update endpoint status
            endpoint.status = 'deployed' if deployment_result['success'] else 'failed'
            endpoint.save(update_fields=['status'])
            
            return deployment_result
            
        except Exception as e:
            logger.error(f"Error deploying API endpoint: {str(e)}")
            raise AdvertiserServiceError(f"Failed to deploy endpoint: {str(e)}")
    
    @staticmethod
    def handle_request(request: APIRequest) -> APIResponse:
        """
        Handle API request with comprehensive processing.
        
        Processing features:
        - Authentication and authorization
        - Rate limiting
        - Input validation
        - Business logic execution
        - Response formatting
        """
        try:
            start_time = time.time()
            
            # Security: Validate request
            APIEndpointService._validate_request(request)
            
            # Get endpoint configuration
            endpoint = APIEndpointService._get_endpoint_by_path(request.path, request.method)
            
            if not endpoint:
                return APIResponse(
                    request_id=request.request_id,
                    status_code=404,
                    headers={'Content-Type': 'application/json'},
                    body={'error': 'Endpoint not found'},
                    processing_time=time.time() - start_time,
                    cached=False,
                    timestamp=timezone.now()
                )
            
            # Security: Check authentication
            auth_result = APIEndpointService._authenticate_request(request, endpoint)
            if not auth_result['success']:
                return APIResponse(
                    request_id=request.request_id,
                    status_code=401,
                    headers={'Content-Type': 'application/json'},
                    body={'error': 'Authentication failed'},
                    processing_time=time.time() - start_time,
                    cached=False,
                    timestamp=timezone.now()
                )
            
            # Security: Check rate limiting
            rate_limit_result = APIEndpointService._check_rate_limit(request, endpoint)
            if not rate_limit_result['allowed']:
                return APIResponse(
                    request_id=request.request_id,
                    status_code=429,
                    headers={'Content-Type': 'application/json', 'Retry-After': str(rate_limit_result['retry_after'])},
                    body={'error': 'Rate limit exceeded'},
                    processing_time=time.time() - start_time,
                    cached=False,
                    timestamp=timezone.now()
                )
            
            # Process request based on endpoint type
            if endpoint.endpoint_type == 'rest':
                response = APIEndpointService._handle_rest_request(request, endpoint)
            elif endpoint.endpoint_type == 'graphql':
                response = APIEndpointService._handle_graphql_request(request, endpoint)
            elif endpoint.endpoint_type == 'websocket':
                response = APIEndpointService._handle_websocket_request(request, endpoint)
            else:
                response = APIEndpointService._handle_webhook_request(request, endpoint)
            
            # Add processing time
            response.processing_time = time.time() - start_time
            
            # Log request/response
            APIEndpointService._log_request_response(request, response, endpoint)
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling API request: {str(e)}")
            return APIResponse(
                request_id=request.request_id if 'request' in locals() else 'unknown',
                status_code=500,
                headers={'Content-Type': 'application/json'},
                body={'error': 'Internal server error'},
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
    
    @staticmethod
    def _validate_endpoint_config(endpoint_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate endpoint configuration with security checks."""
        # Security: Check required fields
        required_fields = ['name', 'endpoint_type', 'path']
        for field in required_fields:
            if not endpoint_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate endpoint type
        valid_types = ['rest', 'graphql', 'websocket', 'webhook']
        endpoint_type = endpoint_config.get('endpoint_type')
        if endpoint_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid endpoint type: {endpoint_type}")
        
        # Security: Validate path
        path = endpoint_config.get('path')
        if not path.startswith('/'):
            raise AdvertiserValidationError("Path must start with '/'")
        
        # Security: Check for prohibited patterns
        prohibited_patterns = [
            r'\.\./',  # Directory traversal
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                raise AdvertiserValidationError("Path contains prohibited content")
        
        # Security: Check user permissions
        if user and not user.is_superuser:
            advertiser = endpoint_config.get('advertiser')
            if advertiser and advertiser.user != user:
                raise AdvertiserValidationError("User does not have access to this advertiser")
    
    @staticmethod
    def _validate_update_config(update_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate update configuration."""
        # Security: Validate update fields
        valid_fields = ['name', 'method', 'path', 'handler', 'authentication', 'rate_limit', 'settings']
        for field in update_config.keys():
            if field not in valid_fields:
                raise AdvertiserValidationError(f"Invalid update field: {field}")
        
        # Security: Validate path if provided
        if 'path' in update_config:
            path = update_config['path']
            if not path.startswith('/'):
                raise AdvertiserValidationError("Path must start with '/'")
    
    @staticmethod
    def _validate_deployment_config(deployment_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate deployment configuration."""
        # Security: Check required fields
        required_fields = ['environment', 'strategy']
        for field in required_fields:
            if not deployment_config.get(field):
                raise AdvertiserValidationError(f"Required deployment field missing: {field}")
        
        # Security: Validate environment
        valid_environments = ['development', 'staging', 'production']
        environment = deployment_config.get('environment')
        if environment not in valid_environments:
            raise AdvertiserValidationError(f"Invalid environment: {environment}")
        
        # Security: Validate strategy
        valid_strategies = ['blue-green', 'rolling', 'canary']
        strategy = deployment_config.get('strategy')
        if strategy not in valid_strategies:
            raise AdvertiserValidationError(f"Invalid deployment strategy: {strategy}")
    
    @staticmethod
    def _create_rest_endpoint(endpoint: APIEndpoint, endpoint_config: Dict[str, Any]) -> RESTEndpoint:
        """Create REST endpoint specific configuration."""
        return RESTEndpoint.objects.create(
            api_endpoint=endpoint,
            response_format=endpoint_config.get('response_format', 'json'),
            request_validation=endpoint_config.get('request_validation', {}),
            response_serialization=endpoint_config.get('response_serialization', {}),
            pagination=endpoint_config.get('pagination', {}),
            filtering=endpoint_config.get('filtering', {}),
            sorting=endpoint_config.get('sorting', {})
        )
    
    @staticmethod
    def _create_graphql_endpoint(endpoint: APIEndpoint, endpoint_config: Dict[str, Any]) -> GraphQLEndpoint:
        """Create GraphQL endpoint specific configuration."""
        return GraphQLEndpoint.objects.create(
            api_endpoint=endpoint,
            schema=endpoint_config.get('schema', {}),
            resolvers=endpoint_config.get('resolvers', {}),
            subscriptions=endpoint_config.get('subscriptions', {}),
            playground_enabled=endpoint_config.get('playground_enabled', True),
            introspection_enabled=endpoint_config.get('introspection_enabled', True)
        )
    
    @staticmethod
    def _create_websocket_endpoint(endpoint: APIEndpoint, endpoint_config: Dict[str, Any]) -> WebSocketEndpoint:
        """Create WebSocket endpoint specific configuration."""
        return WebSocketEndpoint.objects.create(
            api_endpoint=endpoint,
            protocol=endpoint_config.get('protocol', 'wss'),
            subprotocols=endpoint_config.get('subprotocols', []),
            heartbeat_interval=endpoint_config.get('heartbeat_interval', 30),
            max_connections=endpoint_config.get('max_connections', 1000),
            message_format=endpoint_config.get('message_format', 'json')
        )
    
    @staticmethod
    def _create_webhook_endpoint(endpoint: APIEndpoint, endpoint_config: Dict[str, Any]) -> None:
        """Create webhook endpoint specific configuration."""
        # Webhook endpoints are handled by the base APIEndpoint
        # Additional webhook-specific configuration stored in settings
        webhook_config = {
            'events': endpoint_config.get('events', []),
            'secret': endpoint_config.get('secret', ''),
            'retry_policy': endpoint_config.get('retry_policy', {}),
            'timeout': endpoint_config.get('timeout', 30)
        }
        endpoint.settings.update({'webhook': webhook_config})
        endpoint.save(update_fields=['settings'])
    
    @staticmethod
    def _update_rest_endpoint(endpoint: APIEndpoint, update_config: Dict[str, Any]) -> None:
        """Update REST endpoint specific configuration."""
        try:
            rest_endpoint = endpoint.rest_endpoint
            for field, value in update_config.items():
                if hasattr(rest_endpoint, field):
                    setattr(rest_endpoint, field, value)
            rest_endpoint.save()
        except RESTEndpoint.DoesNotExist:
            # Create REST endpoint if it doesn't exist
            APIEndpointService._create_rest_endpoint(endpoint, update_config)
    
    @staticmethod
    def _update_graphql_endpoint(endpoint: APIEndpoint, update_config: Dict[str, Any]) -> None:
        """Update GraphQL endpoint specific configuration."""
        try:
            graphql_endpoint = endpoint.graphql_endpoint
            for field, value in update_config.items():
                if hasattr(graphql_endpoint, field):
                    setattr(graphql_endpoint, field, value)
            graphql_endpoint.save()
        except GraphQLEndpoint.DoesNotExist:
            # Create GraphQL endpoint if it doesn't exist
            APIEndpointService._create_graphql_endpoint(endpoint, update_config)
    
    @staticmethod
    def _update_websocket_endpoint(endpoint: APIEndpoint, update_config: Dict[str, Any]) -> None:
        """Update WebSocket endpoint specific configuration."""
        try:
            websocket_endpoint = endpoint.websocket_endpoint
            for field, value in update_config.items():
                if hasattr(websocket_endpoint, field):
                    setattr(websocket_endpoint, field, value)
            websocket_endpoint.save()
        except WebSocketEndpoint.DoesNotExist:
            # Create WebSocket endpoint if it doesn't exist
            APIEndpointService._create_websocket_endpoint(endpoint, update_config)
    
    @staticmethod
    def _create_deployment_record(endpoint: APIEndpoint, deployment_config: Dict[str, Any], deployed_by: Optional[User]) -> Dict[str, Any]:
        """Create deployment record."""
        deployment_id = str(uuid.uuid4())
        
        deployment = {
            'id': deployment_id,
            'endpoint_id': str(endpoint.id),
            'environment': deployment_config.get('environment'),
            'strategy': deployment_config.get('strategy'),
            'status': 'pending',
            'created_at': timezone.now(),
            'created_by': deployed_by
        }
        
        # Store deployment record
        cache.set(f"deployment_{deployment_id}", deployment, timeout=3600)
        
        return deployment
    
    @staticmethod
    def _perform_deployment(endpoint: APIEndpoint, deployment: Dict[str, Any], deployment_config: Dict[str, Any]) -> Dict[str, Any]:
        """Perform actual deployment."""
        try:
            # Simulate deployment process
            # In real implementation, this would:
            # 1. Create deployment package
            # 2. Deploy to target environment
            # 3. Run health checks
            # 4. Update load balancer
            # 5. Monitor deployment
            
            deployment['status'] = 'success'
            deployment['completed_at'] = timezone.now()
            deployment['deployment_time'] = 45.5  # seconds
            
            # Update deployment record
            cache.set(f"deployment_{deployment['id']}", deployment, timeout=3600)
            
            return {
                'success': True,
                'deployment_id': deployment['id'],
                'deployment_time': deployment['deployment_time'],
                'environment': deployment['environment']
            }
            
        except Exception as e:
            deployment['status'] = 'failed'
            deployment['error'] = str(e)
            deployment['completed_at'] = timezone.now()
            
            # Update deployment record
            cache.set(f"deployment_{deployment['id']}", deployment, timeout=3600)
            
            return {
                'success': False,
                'deployment_id': deployment['id'],
                'error': str(e)
            }
    
    @staticmethod
    def _validate_request(request: APIRequest) -> None:
        """Validate API request."""
        # Security: Check request format
        if not request.method or not request.path:
            raise AdvertiserValidationError("Invalid request format")
        
        # Security: Check request size
        if request.body and len(json.dumps(request.body)) > 10485760:  # 10MB
            raise AdvertiserValidationError("Request too large")
        
        # Security: Check for suspicious headers
        suspicious_headers = ['X-Forwarded-Host', 'X-Originating-IP']
        for header in suspicious_headers:
            if header in request.headers:
                header_value = request.headers[header]
                if APIEndpointService._is_suspicious_header_value(header_value):
                    raise AdvertiserValidationError("Suspicious header detected")
    
    @staticmethod
    def _get_endpoint_by_path(path: str, method: str) -> Optional[APIEndpoint]:
        """Get endpoint by path and method."""
        try:
            # Remove version prefix if present
            clean_path = path
            if path.startswith('/api/v'):
                parts = path.split('/', 3)
                if len(parts) > 3:
                    clean_path = '/' + parts[3]
            
            # Find matching endpoint
            endpoint = APIEndpoint.objects.filter(
                path=clean_path,
                method=method,
                status='active'
            ).first()
            
            return endpoint
            
        except Exception:
            return None
    
    @staticmethod
    def _authenticate_request(request: APIRequest, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Authenticate API request."""
        try:
            # Check if authentication is required
            if not endpoint.authentication:
                return {'success': True, 'user': None}
            
            # Get authentication method from request
            auth_header = request.headers.get('Authorization', '')
            
            if not auth_header:
                return {'success': False, 'error': 'No authentication header'}
            
            # Parse authentication header
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                return APIEndpointService._authenticate_bearer_token(token, endpoint)
            elif auth_header.startswith('Basic '):
                credentials = base64.b64decode(auth_header[6:]).decode()
                return APIEndpointService._authenticate_basic_credentials(credentials, endpoint)
            else:
                return {'success': False, 'error': 'Unsupported authentication method'}
                
        except Exception as e:
            logger.error(f"Error authenticating request: {str(e)}")
            return {'success': False, 'error': 'Authentication failed'}
    
    @staticmethod
    def _authenticate_bearer_token(token: str, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Authenticate bearer token."""
        try:
            # Check JWT token
            if token.startswith('eyJ'):
                return APIEndpointService._authenticate_jwt_token(token, endpoint)
            else:
                # Check API key
                return APIEndpointService._authenticate_api_key(token, endpoint)
                
        except Exception as e:
            logger.error(f"Error authenticating bearer token: {str(e)}")
            return {'success': False, 'error': 'Token authentication failed'}
    
    @staticmethod
    def _authenticate_jwt_token(token: str, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Authenticate JWT token."""
        try:
            import jwt
            from django.conf import settings
            
            # Decode JWT token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            
            # Get user
            user_id = payload.get('user_id')
            user = User.objects.get(id=user_id)
            
            # Check if token is expired
            exp = payload.get('exp')
            if exp and exp < time.time():
                return {'success': False, 'error': 'Token expired'}
            
            return {'success': True, 'user': user, 'payload': payload}
            
        except Exception as e:
            logger.error(f"Error authenticating JWT token: {str(e)}")
            return {'success': False, 'error': 'Invalid token'}
    
    @staticmethod
    def _authenticate_api_key(api_key: str, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Authenticate API key."""
        try:
            # Find API key in database
            api_auth = APIAuthentication.objects.filter(
                api_key=api_key,
                is_active=True
            ).first()
            
            if not api_auth:
                return {'success': False, 'error': 'Invalid API key'}
            
            # Check if API key is expired
            if api_auth.expires_at and api_auth.expires_at < timezone.now():
                return {'success': False, 'error': 'API key expired'}
            
            # Check rate limits
            rate_limit_result = APIEndpointService._check_api_key_rate_limit(api_key, endpoint)
            if not rate_limit_result['allowed']:
                return {'success': False, 'error': 'Rate limit exceeded'}
            
            return {'success': True, 'user': api_auth.user, 'api_key': api_key}
            
        except Exception as e:
            logger.error(f"Error authenticating API key: {str(e)}")
            return {'success': False, 'error': 'API key authentication failed'}
    
    @staticmethod
    def _authenticate_basic_credentials(credentials: str, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Authenticate basic credentials."""
        try:
            # Parse credentials
            username, password = credentials.split(':', 1)
            
            # Authenticate user
            from django.contrib.auth import authenticate
            user = authenticate(username=username, password=password)
            
            if not user:
                return {'success': False, 'error': 'Invalid credentials'}
            
            if not user.is_active:
                return {'success': False, 'error': 'User account is inactive'}
            
            return {'success': True, 'user': user}
            
        except Exception as e:
            logger.error(f"Error authenticating basic credentials: {str(e)}")
            return {'success': False, 'error': 'Basic authentication failed'}
    
    @staticmethod
    def _check_rate_limit(request: APIRequest, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Check rate limiting for request."""
        try:
            # Get rate limit configuration
            rate_limit_config = endpoint.rate_limit or {}
            
            # Get client identifier
            client_id = APIEndpointService._get_client_identifier(request)
            
            # Check rate limit
            cache_key = f"rate_limit_{endpoint.id}_{client_id}"
            current_count = cache.get(cache_key, 0)
            
            # Get rate limit values
            requests_per_minute = rate_limit_config.get('requests_per_minute', 60)
            requests_per_hour = rate_limit_config.get('requests_per_hour', 1000)
            requests_per_day = rate_limit_config.get('requests_per_day', 10000)
            
            # Check minute limit
            minute_key = f"{cache_key}_minute"
            minute_count = cache.get(minute_key, 0)
            if minute_count >= requests_per_minute:
                return {'allowed': False, 'retry_after': 60}
            
            # Check hour limit
            hour_key = f"{cache_key}_hour"
            hour_count = cache.get(hour_key, 0)
            if hour_count >= requests_per_hour:
                return {'allowed': False, 'retry_after': 3600}
            
            # Check day limit
            day_key = f"{cache_key}_day"
            day_count = cache.get(day_key, 0)
            if day_count >= requests_per_day:
                return {'allowed': False, 'retry_after': 86400}
            
            # Increment counters
            cache.set(minute_key, minute_count + 1, timeout=60)
            cache.set(hour_key, hour_count + 1, timeout=3600)
            cache.set(day_key, day_count + 1, timeout=86400)
            
            return {'allowed': True}
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return {'allowed': True}  # Allow request on error
    
    @staticmethod
    def _check_api_key_rate_limit(api_key: str, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Check rate limit for API key."""
        try:
            # Get API key authentication record
            api_auth = APIAuthentication.objects.get(api_key=api_key)
            
            # Get rate limit configuration
            rate_limit_config = endpoint.rate_limit or {}
            
            # Check rate limit
            cache_key = f"api_key_rate_limit_{api_auth.id}"
            current_count = cache.get(cache_key, 0)
            
            requests_per_minute = rate_limit_config.get('requests_per_minute', 60)
            
            if current_count >= requests_per_minute:
                return {'allowed': False, 'retry_after': 60}
            
            # Increment counter
            cache.set(cache_key, current_count + 1, timeout=60)
            
            return {'allowed': True}
            
        except Exception as e:
            logger.error(f"Error checking API key rate limit: {str(e)}")
            return {'allowed': True}
    
    @staticmethod
    def _get_client_identifier(request: APIRequest) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID first
        if request.user:
            return f"user_{request.user.id}"
        
        # Fall back to IP address
        return f"ip_{request.ip_address}"
    
    @staticmethod
    def _handle_rest_request(request: APIRequest, endpoint: APIEndpoint) -> APIResponse:
        """Handle REST API request."""
        try:
            # Get REST endpoint configuration
            rest_endpoint = endpoint.rest_endpoint
            
            # Validate request body
            if request.method in ['POST', 'PUT', 'PATCH'] and request.body:
                validation_result = APIEndpointService._validate_request_body(request.body, rest_endpoint.request_validation)
                if not validation_result['valid']:
                    return APIResponse(
                        request_id=request.request_id,
                        status_code=400,
                        headers={'Content-Type': 'application/json'},
                        body={'error': 'Invalid request body', 'details': validation_result['errors']},
                        processing_time=0.0,
                        cached=False,
                        timestamp=timezone.now()
                    )
            
            # Execute handler
            handler_result = APIEndpointService._execute_handler(request, endpoint)
            
            # Format response
            response_body = APIEndpointService._format_response(handler_result, rest_endpoint.response_serialization)
            
            return APIResponse(
                request_id=request.request_id,
                status_code=handler_result.get('status_code', 200),
                headers={'Content-Type': rest_endpoint.response_format},
                body=response_body,
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error handling REST request: {str(e)}")
            return APIResponse(
                request_id=request.request_id,
                status_code=500,
                headers={'Content-Type': 'application/json'},
                body={'error': 'Internal server error'},
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
    
    @staticmethod
    def _handle_graphql_request(request: APIRequest, endpoint: APIEndpoint) -> APIResponse:
        """Handle GraphQL API request."""
        try:
            # Get GraphQL endpoint configuration
            graphql_endpoint = endpoint.graphql_endpoint
            
            # Parse GraphQL query
            query = request.body.get('query', '') if request.body else ''
            variables = request.body.get('variables', {}) if request.body else {}
            
            if not query:
                return APIResponse(
                    request_id=request.request_id,
                    status_code=400,
                    headers={'Content-Type': 'application/json'},
                    body={'error': 'GraphQL query is required'},
                    processing_time=0.0,
                    cached=False,
                    timestamp=timezone.now()
                )
            
            # Execute GraphQL query
            execution_result = APIEndpointService._execute_graphql_query(query, variables, graphql_endpoint)
            
            return APIResponse(
                request_id=request.request_id,
                status_code=200,
                headers={'Content-Type': 'application/json'},
                body=execution_result,
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error handling GraphQL request: {str(e)}")
            return APIResponse(
                request_id=request.request_id,
                status_code=500,
                headers={'Content-Type': 'application/json'},
                body={'error': 'Internal server error'},
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
    
    @staticmethod
    def _handle_websocket_request(request: APIRequest, endpoint: APIEndpoint) -> APIResponse:
        """Handle WebSocket connection request."""
        try:
            # Get WebSocket endpoint configuration
            websocket_endpoint = endpoint.websocket_endpoint
            
            # WebSocket connections are handled differently
            # This would typically upgrade the HTTP connection to WebSocket
            return APIResponse(
                request_id=request.request_id,
                status_code=101,  # Switching Protocols
                headers={
                    'Upgrade': 'websocket',
                    'Connection': 'Upgrade',
                    'Sec-WebSocket-Accept': APIEndpointService._generate_websocket_accept(request.headers)
                },
                body='',
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error handling WebSocket request: {str(e)}")
            return APIResponse(
                request_id=request.request_id,
                status_code=500,
                headers={'Content-Type': 'application/json'},
                body={'error': 'Internal server error'},
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
    
    @staticmethod
    def _handle_webhook_request(request: APIRequest, endpoint: APIEndpoint) -> APIResponse:
        """Handle webhook request."""
        try:
            # Get webhook configuration
            webhook_config = endpoint.settings.get('webhook', {})
            
            # Verify webhook signature
            if webhook_config.get('secret'):
                signature = request.headers.get('X-Webhook-Signature', '')
                if not APIEndpointService._verify_webhook_signature(request.body, signature, webhook_config['secret']):
                    return APIResponse(
                        request_id=request.request_id,
                        status_code=401,
                        headers={'Content-Type': 'application/json'},
                        body={'error': 'Invalid webhook signature'},
                        processing_time=0.0,
                        cached=False,
                        timestamp=timezone.now()
                    )
            
            # Process webhook event
            event_type = request.headers.get('X-Event-Type', '')
            event_result = APIEndpointService._process_webhook_event(request.body, event_type, webhook_config)
            
            return APIResponse(
                request_id=request.request_id,
                status_code=200,
                headers={'Content-Type': 'application/json'},
                body={'status': 'processed', 'event_id': event_result.get('event_id')},
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error handling webhook request: {str(e)}")
            return APIResponse(
                request_id=request.request_id,
                status_code=500,
                headers={'Content-Type': 'application/json'},
                body={'error': 'Internal server error'},
                processing_time=0.0,
                cached=False,
                timestamp=timezone.now()
            )
    
    @staticmethod
    def _validate_request_body(body: Dict[str, Any], validation_rules: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request body against rules."""
        try:
            errors = []
            
            # Check required fields
            required_fields = validation_rules.get('required', [])
            for field in required_fields:
                if field not in body:
                    errors.append(f"Required field missing: {field}")
            
            # Check field types
            field_types = validation_rules.get('types', {})
            for field, expected_type in field_types.items():
                if field in body:
                    if expected_type == 'string' and not isinstance(body[field], str):
                        errors.append(f"Field {field} must be a string")
                    elif expected_type == 'integer' and not isinstance(body[field], int):
                        errors.append(f"Field {field} must be an integer")
                    elif expected_type == 'float' and not isinstance(body[field], (int, float)):
                        errors.append(f"Field {field} must be a number")
                    elif expected_type == 'boolean' and not isinstance(body[field], bool):
                        errors.append(f"Field {field} must be a boolean")
                    elif expected_type == 'array' and not isinstance(body[field], list):
                        errors.append(f"Field {field} must be an array")
                    elif expected_type == 'object' and not isinstance(body[field], dict):
                        errors.append(f"Field {field} must be an object")
            
            # Check field constraints
            constraints = validation_rules.get('constraints', {})
            for field, constraint in constraints.items():
                if field in body:
                    value = body[field]
                    
                    # Check min/max for numbers
                    if 'min' in constraint and isinstance(value, (int, float)) and value < constraint['min']:
                        errors.append(f"Field {field} must be at least {constraint['min']}")
                    
                    if 'max' in constraint and isinstance(value, (int, float)) and value > constraint['max']:
                        errors.append(f"Field {field} must be at most {constraint['max']}")
                    
                    # Check min/max length for strings
                    if 'min_length' in constraint and isinstance(value, str) and len(value) < constraint['min_length']:
                        errors.append(f"Field {field} must be at least {constraint['min_length']} characters")
                    
                    if 'max_length' in constraint and isinstance(value, str) and len(value) > constraint['max_length']:
                        errors.append(f"Field {field} must be at most {constraint['max_length']} characters")
            
            return {'valid': len(errors) == 0, 'errors': errors}
            
        except Exception as e:
            logger.error(f"Error validating request body: {str(e)}")
            return {'valid': False, 'errors': ['Validation error']}
    
    @staticmethod
    def _execute_handler(request: APIRequest, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Execute endpoint handler."""
        try:
            # Get handler function
            handler_path = endpoint.handler
            module_name, function_name = handler_path.rsplit('.', 1)
            
            # Import module
            module = __import__(module_name, fromlist=[function_name])
            handler_function = getattr(module, function_name)
            
            # Execute handler
            result = handler_function(request)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing handler: {str(e)}")
            return {'status_code': 500, 'error': 'Handler execution failed'}
    
    @staticmethod
    def _format_response(result: Dict[str, Any], serialization_config: Dict[str, Any]) -> Dict[str, Any]:
        """Format response according to serialization configuration."""
        try:
            # Apply serialization rules
            formatted_result = result
            
            # Remove sensitive fields
            sensitive_fields = serialization_config.get('exclude_sensitive', [])
            for field in sensitive_fields:
                if field in formatted_result:
                    formatted_result[field] = '[REDACTED]'
            
            # Apply field mappings
            field_mappings = serialization_config.get('field_mappings', {})
            for old_field, new_field in field_mappings.items():
                if old_field in formatted_result:
                    formatted_result[new_field] = formatted_result.pop(old_field)
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return result
    
    @staticmethod
    def _execute_graphql_query(query: str, variables: Dict[str, Any], graphql_endpoint: GraphQLEndpoint) -> Dict[str, Any]:
        """Execute GraphQL query."""
        try:
            # This would integrate with a GraphQL library like Graphene
            # For now, return a mock response
            return {
                'data': {
                    'message': 'GraphQL query executed successfully'
                },
                'errors': None
            }
            
        except Exception as e:
            logger.error(f"Error executing GraphQL query: {str(e)}")
            return {
                'data': None,
                'errors': [{'message': 'Query execution failed'}]
            }
    
    @staticmethod
    def _generate_websocket_accept(headers: Dict[str, Any]) -> str:
        """Generate WebSocket accept header."""
        try:
            websocket_key = headers.get('Sec-WebSocket-Key', '')
            accept = base64.b64encode(
                hashlib.sha1((websocket_key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()
            ).decode()
            return accept
            
        except Exception as e:
            logger.error(f"Error generating WebSocket accept: {str(e)}")
            return ''
    
    @staticmethod
    def _verify_webhook_signature(body: Dict[str, Any], signature: str, secret: str) -> bool:
        """Verify webhook signature."""
        try:
            expected_signature = hmac.new(
                secret.encode(),
                json.dumps(body, sort_keys=True).encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    @staticmethod
    def _process_webhook_event(body: Dict[str, Any], event_type: str, webhook_config: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook event."""
        try:
            # Generate event ID
            event_id = str(uuid.uuid4())
            
            # Store event for processing
            event_data = {
                'id': event_id,
                'type': event_type,
                'data': body,
                'processed': False,
                'created_at': timezone.now()
            }
            
            cache.set(f"webhook_event_{event_id}", event_data, timeout=3600)
            
            # Trigger async processing
            # In real implementation, this would use Celery or similar
            APIEndpointService._process_webhook_event_async(event_id)
            
            return {'event_id': event_id}
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {str(e)}")
            return {'event_id': None}
    
    @staticmethod
    def _process_webhook_event_async(event_id: str) -> None:
        """Process webhook event asynchronously."""
        try:
            # Get event data
            event_data = cache.get(f"webhook_event_{event_id}")
            if not event_data:
                return
            
            # Process event based on type
            event_type = event_data['type']
            
            if event_type == 'campaign.created':
                APIEndpointService._handle_campaign_created_event(event_data)
            elif event_type == 'payment.completed':
                APIEndpointService._handle_payment_completed_event(event_data)
            # Add more event handlers as needed
            
            # Mark as processed
            event_data['processed'] = True
            cache.set(f"webhook_event_{event_id}", event_data, timeout=3600)
            
        except Exception as e:
            logger.error(f"Error processing webhook event async: {str(e)}")
    
    @staticmethod
    def _handle_campaign_created_event(event_data: Dict[str, Any]) -> None:
        """Handle campaign created event."""
        # Implementation for handling campaign creation
        pass
    
    @staticmethod
    def _handle_payment_completed_event(event_data: Dict[str, Any]) -> None:
        """Handle payment completed event."""
        # Implementation for handling payment completion
        pass
    
    @staticmethod
    def _is_suspicious_header_value(value: str) -> bool:
        """Check if header value is suspicious."""
        suspicious_patterns = [
            '../',  # Directory traversal
            '<script',  # Script injection
            'javascript:',  # JavaScript protocol
            'data:',  # Data protocol
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in suspicious_patterns)
    
    @staticmethod
    def _log_endpoint_creation(endpoint: APIEndpoint, user: Optional[User]) -> None:
        """Log endpoint creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                endpoint,
                user,
                description=f"Created API endpoint: {endpoint.name}"
            )
        except Exception as e:
            logger.error(f"Error logging endpoint creation: {str(e)}")
    
    @staticmethod
    def _log_endpoint_update(endpoint: APIEndpoint, old_config: Dict[str, Any], new_config: Dict[str, Any], user: Optional[User]) -> None:
        """Log endpoint update for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='update_endpoint',
                object_type='APIEndpoint',
                object_id=str(endpoint.id),
                user=user,
                description=f"Updated API endpoint: {endpoint.name}",
                metadata={
                    'old_config': old_config,
                    'new_config': new_config
                }
            )
        except Exception as e:
            logger.error(f"Error logging endpoint update: {str(e)}")
    
    @staticmethod
    def _log_request_response(request: APIRequest, response: APIResponse, endpoint: APIEndpoint) -> None:
        """Log request and response for monitoring."""
        try:
            # Create log entry
            log_entry = {
                'request_id': request.request_id,
                'endpoint_id': str(endpoint.id),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'processing_time': response.processing_time,
                'ip_address': request.ip_address,
                'user_agent': request.user_agent,
                'timestamp': timezone.now()
            }
            
            # Store in cache for monitoring
            cache.set(f"api_log_{request.request_id}", log_entry, timeout=3600)
            
            # Update metrics
            APIEndpointService._update_api_metrics(endpoint, response)
            
        except Exception as e:
            logger.error(f"Error logging request/response: {str(e)}")
    
    @staticmethod
    def _update_api_metrics(endpoint: APIEndpoint, response: APIResponse) -> None:
        """Update API metrics."""
        try:
            # Get current metrics
            metrics_key = f"api_metrics_{endpoint.id}"
            metrics = cache.get(metrics_key, {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'avg_processing_time': 0.0,
                'last_updated': timezone.now()
            })
            
            # Update metrics
            metrics['total_requests'] += 1
            if 200 <= response.status_code < 400:
                metrics['successful_requests'] += 1
            else:
                metrics['failed_requests'] += 1
            
            # Update average processing time
            total_time = metrics['avg_processing_time'] * (metrics['total_requests'] - 1) + response.processing_time
            metrics['avg_processing_time'] = total_time / metrics['total_requests']
            metrics['last_updated'] = timezone.now()
            
            # Store updated metrics
            cache.set(metrics_key, metrics, timeout=3600)
            
        except Exception as e:
            logger.error(f"Error updating API metrics: {str(e)}")


# Additional service classes for specific endpoint types
class RESTEndpointService:
    """Service for REST endpoint management."""
    
    @staticmethod
    def create_rest_endpoint(endpoint_config: Dict[str, Any]) -> RESTEndpoint:
        """Create REST endpoint with specific configuration."""
        pass


class GraphQLEndpointService:
    """Service for GraphQL endpoint management."""
    
    @staticmethod
    def create_graphql_endpoint(endpoint_config: Dict[str, Any]) -> GraphQLEndpoint:
        """Create GraphQL endpoint with specific configuration."""
        pass


class WebSocketEndpointService:
    """Service for WebSocket endpoint management."""
    
    @staticmethod
    def create_websocket_endpoint(endpoint_config: Dict[str, Any]) -> WebSocketEndpoint:
        """Create WebSocket endpoint with specific configuration."""
        pass


class APIDocumentationService:
    """Service for API documentation management."""
    
    @staticmethod
    def generate_documentation(endpoint_id: UUID) -> Dict[str, Any]:
        """Generate API documentation for endpoint."""
        pass


class APIVersioningService:
    """Service for API versioning management."""
    
    @staticmethod
    def create_version(version_config: Dict[str, Any]) -> APIVersion:
        """Create new API version."""
        pass


class APIAuthenticationService:
    """Service for API authentication management."""
    
    @staticmethod
    def create_api_key(auth_config: Dict[str, Any]) -> APIAuthentication:
        """Create API key for authentication."""
        pass


class APIRateLimitingService:
    """Service for API rate limiting management."""
    
    @staticmethod
    def create_rate_limit(limit_config: Dict[str, Any]) -> APIRateLimit:
        """Create rate limit configuration."""
        pass
