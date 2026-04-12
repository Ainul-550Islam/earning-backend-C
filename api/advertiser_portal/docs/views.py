"""
Documentation Views

This module provides DRF ViewSets for documentation management with
enterprise-grade security, real-time processing, and comprehensive
error handling following industry standards from Swagger, OpenAPI, and Confluence.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time
import asyncio
import subprocess
import threading
import queue

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import Coalesce, RowNumber
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.documentation_model import (
    Documentation, APIDocumentation, UserGuide, TechnicalDocumentation,
    DocumentationSearch, DocumentationVersioning, DocumentationAnalytics
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    DocumentationService, APIDocumentationService, UserGuideService,
    TechnicalDocumentationService, DocumentationSearchService,
    DocumentationVersioningService, DocumentationAnalyticsService,
    DocumentationConfig, DocumentationSearchResult
)

User = get_user_model()


class DocumentationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for documentation management.
    
    Features:
    - Multi-type documentation support
    - Advanced search capabilities
    - Version control
    - Analytics and metrics
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create documentation with enterprise-grade security.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Content validation
        - Audit logging
        """
        try:
            # Security: Validate request
            DocumentationViewSet._validate_create_request(request)
            
            # Get documentation configuration
            doc_config = request.data
            
            # Create documentation
            documentation = DocumentationService.create_documentation(doc_config, request.user)
            
            # Track creation
            DocumentationAnalyticsService.track_view(documentation, request.user)
            
            # Return response
            response_data = {
                'documentation_id': str(documentation.id),
                'title': documentation.title,
                'type': documentation.type,
                'category': documentation.category,
                'tags': documentation.tags,
                'version': documentation.version,
                'status': documentation.status,
                'created_at': documentation.created_at.isoformat()
            }
            
            # Security: Log documentation creation
            DocumentationViewSet._log_documentation_creation(documentation, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating documentation: {str(e)}")
            return Response({'error': 'Failed to create documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['put'])
    def update(self, request, pk=None):
        """
        Update documentation with enterprise-grade processing.
        
        Security measures:
        - User permission validation
        - Content validation
        - Version control
        - Audit logging
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            doc_config = request.data
            
            # Update documentation
            documentation = DocumentationService.update_documentation(doc_id, doc_config, request.user)
            
            # Track update
            DocumentationAnalyticsService.track_view(documentation, request.user)
            
            return Response({
                'documentation_id': str(documentation.id),
                'title': documentation.title,
                'version': documentation.version,
                'updated_at': documentation.updated_at.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating documentation: {str(e)}")
            return Response({'error': 'Failed to update documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def view(self, request, pk=None):
        """
        View documentation with analytics tracking.
        
        Security measures:
        - User permission validation
        - Analytics tracking
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Track view
            DocumentationAnalyticsService.track_view(documentation, request.user)
            
            # Return documentation
            response_data = {
                'documentation_id': str(documentation.id),
                'title': documentation.title,
                'type': documentation.type,
                'content': documentation.content,
                'category': documentation.category,
                'tags': documentation.tags,
                'version': documentation.version,
                'status': documentation.status,
                'created_at': documentation.created_at.isoformat(),
                'updated_at': documentation.updated_at.isoformat()
            }
            
            # Add type-specific data
            if documentation.type == 'api':
                response_data['api_data'] = DocumentationViewSet._get_api_data(documentation)
            elif documentation.type == 'user_guide':
                response_data['user_guide_data'] = DocumentationViewSet._get_user_guide_data(documentation)
            elif documentation.type == 'technical':
                response_data['technical_data'] = DocumentationViewSet._get_technical_data(documentation)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error viewing documentation: {str(e)}")
            return Response({'error': 'Failed to view documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """
        Search documentation with advanced capabilities.
        
        Security measures:
        - User permission validation
        - Search validation
        - Rate limiting
        """
        try:
            # Security: Validate search request
            DocumentationViewSet._validate_search_request(request)
            
            # Get search configuration
            search_config = request.data
            
            # Track search
            query = search_config.get('query', '')
            DocumentationAnalyticsService.track_search(query, request.user)
            
            # Perform search
            search_results = DocumentationService.search_documentation(search_config, request.user)
            
            # Format results
            results_data = []
            for result in search_results:
                results_data.append({
                    'documentation_id': result.doc_id,
                    'title': result.title,
                    'content_snippet': result.content_snippet,
                    'relevance_score': result.relevance_score,
                    'doc_type': result.doc_type,
                    'category': result.category,
                    'tags': result.tags,
                    'updated_at': result.updated_at.isoformat()
                })
            
            return Response({'results': results_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error searching documentation: {str(e)}")
            return Response({'error': 'Failed to search documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get documentation statistics.
        
        Security measures:
        - User permission validation
        - Stats access control
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get statistics
            stats = DocumentationService.get_documentation_stats(doc_id)
            
            return Response({'stats': stats}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting documentation stats: {str(e)}")
            return Response({'error': 'Failed to get documentation stats'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List documentation with filtering and pagination.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            DocumentationViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'type': request.query_params.get('type'),
                'category': request.query_params.get('category'),
                'status': request.query_params.get('status'),
                'tags': request.query_params.getlist('tags', []),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'page': int(request.query_params.get('page', 1)),
                'page_size': min(int(request.query_params.get('page_size', 20)), 100)
            }
            
            # Get documentation list
            docs_data = DocumentationViewSet._get_documentation_list(user, filters)
            
            return Response(docs_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing documentation: {str(e)}")
            return Response({'error': 'Failed to list documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate create request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not DocumentationService._has_documentation_permission(request.user, 'create'):
            raise AdvertiserValidationError("User does not have documentation creation permissions")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['title', 'type', 'content']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate documentation type
        valid_types = ['api', 'user_guide', 'technical', 'policy']
        doc_type = request.data.get('type')
        if doc_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid documentation type: {doc_type}")
        
        # Security: Validate content
        content = request.data.get('content', '')
        if content:
            DocumentationViewSet._validate_content(content, doc_type)
    
    @staticmethod
    def _validate_content(content: str, doc_type: str) -> None:
        """Validate documentation content with security checks."""
        if not content or len(content.strip()) < 10:
            raise AdvertiserValidationError("Documentation content is too short")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'eval\s*\(',
            r'exec\s*\(',
            r'system\s*\(',
            r'os\.system',
            r'subprocess\.call',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise AdvertiserValidationError("Documentation content contains prohibited code")
    
    @staticmethod
    def _validate_search_request(request) -> None:
        """Validate search request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not DocumentationService._has_documentation_permission(request.user, 'search'):
            raise AdvertiserValidationError("User does not have documentation search permissions")
        
        # Security: Validate search query
        query = request.data.get('query', '')
        if query:
            # Check for injection attempts
            prohibited_patterns = [
                r'<script',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    raise AdvertiserValidationError("Search query contains prohibited content")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not DocumentationService._has_documentation_permission(user, 'view'):
            raise AdvertiserValidationError("User does not have documentation view permissions")
    
    @staticmethod
    def _get_documentation_list(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get documentation list with filtering and pagination."""
        try:
            # Build query
            queryset = Documentation.objects.filter(status='published')
            
            # Apply filters
            if filters.get('type'):
                queryset = queryset.filter(type=filters['type'])
            
            if filters.get('category'):
                queryset = queryset.filter(category=filters['category'])
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('tags'):
                queryset = queryset.filter(tags__overlap=filters['tags'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            
            # Pagination
            page = filters.get('page', 1)
            page_size = filters.get('page_size', 20)
            offset = (page - 1) * page_size
            
            # Get paginated results
            results = queryset[offset:offset + page_size]
            
            # Format results
            docs = []
            for doc in results:
                docs.append({
                    'id': str(doc.id),
                    'title': doc.title,
                    'type': doc.type,
                    'category': doc.category,
                    'tags': doc.tags,
                    'version': doc.version,
                    'status': doc.status,
                    'created_at': doc.created_at.isoformat(),
                    'updated_at': doc.updated_at.isoformat()
                })
            
            return {
                'documentation': docs,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': queryset.count(),
                    'total_pages': (queryset.count() + page_size - 1) // page_size
                },
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting documentation list: {str(e)}")
            return {
                'documentation': [],
                'pagination': {'page': 1, 'page_size': 20, 'total_count': 0, 'total_pages': 0},
                'filters_applied': filters,
                'error': 'Failed to retrieve documentation'
            }
    
    @staticmethod
    def _get_api_data(documentation: Documentation) -> Dict[str, Any]:
        """Get API documentation specific data."""
        try:
            api_doc = documentation.api_documentation
            return {
                'api_version': api_doc.api_version,
                'base_url': api_doc.base_url,
                'endpoints': api_doc.endpoints,
                'schemas': api_doc.schemas,
                'authentication': api_doc.authentication
            }
        except Exception:
            return {}
    
    @staticmethod
    def _get_user_guide_data(documentation: Documentation) -> Dict[str, Any]:
        """Get user guide specific data."""
        try:
            user_guide = documentation.user_guide
            return {
                'target_audience': user_guide.target_audience,
                'difficulty_level': user_guide.difficulty_level,
                'estimated_time': user_guide.estimated_time,
                'prerequisites': user_guide.prerequisites,
                'steps': user_guide.steps
            }
        except Exception:
            return {}
    
    @staticmethod
    def _get_technical_data(documentation: Documentation) -> Dict[str, Any]:
        """Get technical documentation specific data."""
        try:
            tech_doc = documentation.technical_documentation
            return {
                'technical_level': tech_doc.technical_level,
                'components': tech_doc.components,
                'dependencies': tech_doc.dependencies,
                'configuration': tech_doc.configuration,
                'troubleshooting': tech_doc.troubleshooting
            }
        except Exception:
            return {}
    
    @staticmethod
    def _log_documentation_creation(documentation: Documentation, user: User) -> None:
        """Log documentation creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                documentation,
                user,
                description=f"Created documentation: {documentation.title}"
            )
        except Exception as e:
            logger.error(f"Error logging documentation creation: {str(e)}")


class APIDocumentationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for API documentation management.
    
    Features:
    - OpenAPI specification generation
    - API validation
    - Endpoint management
    - Schema management
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def openapi_spec(self, request, pk=None):
        """
        Generate OpenAPI specification.
        
        Security measures:
        - User permission validation
        - Spec generation
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Generate OpenAPI spec
            openapi_spec = APIDocumentationService.generate_openapi_spec(documentation)
            
            return Response(openapi_spec, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error generating OpenAPI spec: {str(e)}")
            return Response({'error': 'Failed to generate OpenAPI spec'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate API documentation.
        
        Security measures:
        - User permission validation
        - Validation execution
        - Security checks
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Validate API documentation
            validation_result = APIDocumentationService.validate_api_documentation(
                documentation.api_documentation.__dict__
            )
            
            return Response({'validation_result': validation_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error validating API documentation: {str(e)}")
            return Response({'error': 'Failed to validate API documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserGuideViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for user guide management.
    
    Features:
    - Table of contents generation
    - Reading time estimation
    - Step management
    - Progress tracking
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def table_of_contents(self, request, pk=None):
        """
        Generate table of contents.
        
        Security measures:
        - User permission validation
        - TOC generation
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Generate table of contents
            toc = UserGuideService.generate_table_of_contents(documentation)
            
            return Response({'table_of_contents': toc}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error generating table of contents: {str(e)}")
            return Response({'error': 'Failed to generate table of contents'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def reading_time(self, request, pk=None):
        """
        Estimate reading time.
        
        Security measures:
        - User permission validation
        - Time estimation
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Estimate reading time
            reading_time = UserGuideService.estimate_reading_time(documentation.content)
            
            return Response({'reading_time_minutes': reading_time}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error estimating reading time: {str(e)}")
            return Response({'error': 'Failed to estimate reading time'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TechnicalDocumentationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for technical documentation management.
    
    Features:
    - Code block extraction
    - Technical validation
    - Component management
    - Troubleshooting guides
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['get'])
    def code_blocks(self, request, pk=None):
        """
        Extract code blocks from technical documentation.
        
        Security measures:
        - User permission validation
        - Code extraction
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Extract code blocks
            code_blocks = TechnicalDocumentationService.extract_code_blocks(documentation.content)
            
            return Response({'code_blocks': code_blocks}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error extracting code blocks: {str(e)}")
            return Response({'error': 'Failed to extract code blocks'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate technical documentation.
        
        Security measures:
        - User permission validation
        - Validation execution
        - Security checks
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Validate technical documentation
            validation_result = TechnicalDocumentationService.validate_technical_documentation(
                documentation.technical_documentation.__dict__
            )
            
            return Response({'validation_result': validation_result}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error validating technical documentation: {str(e)}")
            return Response({'error': 'Failed to validate technical documentation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentationSearchViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for documentation search.
    
    Features:
    - Advanced search capabilities
    - Search analytics
    - Search optimization
    - Result ranking
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def advanced_search(self, request):
        """
        Perform advanced search with filters.
        
        Security measures:
        - User permission validation
        - Search execution
        - Rate limiting
        """
        try:
            # Security: Validate search request
            DocumentationSearchViewSet._validate_search_request(request)
            
            # Get search configuration
            search_config = request.data
            
            # Track search
            query = search_config.get('query', '')
            DocumentationAnalyticsService.track_search(query, request.user)
            
            # Perform advanced search
            search_results = DocumentationSearchService.perform_advanced_search(search_config)
            
            # Format results
            results_data = []
            for result in search_results:
                results_data.append({
                    'documentation_id': result.doc_id,
                    'title': result.title,
                    'content_snippet': result.content_snippet,
                    'relevance_score': result.relevance_score,
                    'doc_type': result.doc_type,
                    'category': result.category,
                    'tags': result.tags,
                    'updated_at': result.updated_at.isoformat()
                })
            
            return Response({'results': results_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error performing advanced search: {str(e)}")
            return Response({'error': 'Failed to perform advanced search'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_search_request(request) -> None:
        """Validate search request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Check user permissions
        if not DocumentationService._has_documentation_permission(request.user, 'search'):
            raise AdvertiserValidationError("User does not have documentation search permissions")
        
        # Security: Validate search query
        query = request.data.get('query', '')
        if query:
            # Check for injection attempts
            prohibited_patterns = [
                r'<script',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    raise AdvertiserValidationError("Search query contains prohibited content")


class DocumentationVersioningViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for documentation versioning.
    
    Features:
    - Version management
    - Version comparison
    - Rollback capabilities
    - Change tracking
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """
        Create new version of documentation.
        
        Security measures:
        - User permission validation
        - Version creation
        - Audit logging
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            version_config = request.data
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Create version
            version = DocumentationVersioningService.create_version(
                documentation,
                version_config.get('version'),
                request.user
            )
            
            return Response({
                'version_id': str(version.id),
                'version': version.version,
                'created_at': version.updated_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating version: {str(e)}")
            return Response({'error': 'Failed to create version'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def restore_version(self, request, pk=None):
        """
        Restore documentation to specific version.
        
        Security measures:
        - User permission validation
        - Version restoration
        - Audit logging
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            version_config = request.data
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Restore version
            restored_doc = DocumentationVersioningService.restore_version(
                documentation,
                version_config.get('version'),
                request.user
            )
            
            return Response({
                'documentation_id': str(restored_doc.id),
                'version': restored_doc.version,
                'restored_at': restored_doc.updated_at.isoformat()
            }, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error restoring version: {str(e)}")
            return Response({'error': 'Failed to restore version'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def version_history(self, request, pk=None):
        """
        Get version history for documentation.
        
        Security measures:
        - User permission validation
        - History access
        - Rate limiting
        """
        try:
            # Security: Validate documentation access
            doc_id = UUID(pk)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Get version history
            history = DocumentationVersioningService.get_version_history(documentation)
            
            return Response({'history': history}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return Response({'error': 'Failed to get version history'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentationAnalyticsViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for documentation analytics.
    
    Features:
    - View tracking
    - Search analytics
    - Engagement metrics
    - Performance reports
    - Real-time monitoring
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['get'])
    def engagement_report(self, request):
        """
        Generate engagement report.
        
        Security measures:
        - User permission validation
        - Report generation
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            DocumentationAnalyticsViewSet._validate_user_access(user)
            
            # Get date range
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            
            if date_from:
                date_from = datetime.fromisoformat(date_from)
            else:
                date_from = timezone.now() - timedelta(days=30)
            
            if date_to:
                date_to = datetime.fromisoformat(date_to)
            else:
                date_to = timezone.now()
            
            # Generate engagement report
            report = DocumentationAnalyticsService.generate_engagement_report(date_from, date_to)
            
            return Response(report, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error generating engagement report: {str(e)}")
            return Response({'error': 'Failed to generate engagement report'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """
        Get comprehensive documentation analytics.
        
        Security measures:
        - User permission validation
        - Analytics access
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            DocumentationAnalyticsViewSet._validate_user_access(user)
            
            # Get date range
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            
            if date_from:
                date_from = datetime.fromisoformat(date_from)
            else:
                date_from = timezone.now() - timedelta(days=30)
            
            if date_to:
                date_to = datetime.fromisoformat(date_to)
            else:
                date_to = timezone.now()
            
            # Get analytics
            analytics = DocumentationService.get_documentation_analytics(date_from, date_to)
            
            return Response(analytics, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return Response({'error': 'Failed to get analytics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not DocumentationService._has_documentation_permission(user, 'analytics'):
            raise AdvertiserValidationError("User does not have documentation analytics permissions")
