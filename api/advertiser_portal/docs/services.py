"""
Documentation Services

This module handles comprehensive documentation management with enterprise-grade
security, real-time processing, and advanced features following industry
standards from Swagger, OpenAPI, and Confluence.
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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
import os
import sys
import hashlib
import shutil
import markdown
import re
from bs4 import BeautifulSoup

from django.db import transaction, connection
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
from django.core.management import call_command
from django.apps import apps

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

User = get_user_model()


@dataclass
class DocumentationConfig:
    """Documentation configuration with metadata."""
    doc_id: str
    title: str
    type: str
    content: str
    category: str
    tags: List[str]
    version: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class DocumentationSearchResult:
    """Documentation search result with metadata."""
    doc_id: str
    title: str
    content_snippet: str
    relevance_score: float
    doc_type: str
    category: str
    tags: List[str]
    updated_at: datetime


class DocumentationService:
    """
    Enterprise-grade documentation management service.
    
    Features:
    - Multi-type documentation support
    - Advanced search capabilities
    - Version control
    - Analytics and metrics
    - Performance optimization
    """
    
    @staticmethod
    def create_documentation(doc_config: Dict[str, Any], created_by: Optional[User] = None) -> Documentation:
        """
        Create documentation with enterprise-grade security.
        
        Supported documentation types:
        - API: API documentation with OpenAPI/Swagger
        - User Guide: User guides and tutorials
        - Technical: Technical documentation and specs
        - Policy: Policy and compliance documents
        
        Security features:
        - Content validation and sanitization
        - Permission validation
        - Version control
        - Audit logging
        """
        try:
            # Security: Validate documentation configuration
            DocumentationService._validate_documentation_config(doc_config, created_by)
            
            # Get documentation-specific configuration
            doc_type = doc_config.get('type')
            
            with transaction.atomic():
                # Create base documentation
                documentation = Documentation.objects.create(
                    title=doc_config.get('title'),
                    type=doc_type,
                    content=doc_config.get('content'),
                    category=doc_config.get('category'),
                    tags=doc_config.get('tags', []),
                    version=doc_config.get('version', '1.0.0'),
                    status=doc_config.get('status', 'draft'),
                    created_by=created_by
                )
                
                # Create type-specific documentation
                if doc_type == 'api':
                    DocumentationService._create_api_documentation(documentation, doc_config)
                elif doc_type == 'user_guide':
                    DocumentationService._create_user_guide(documentation, doc_config)
                elif doc_type == 'technical':
                    DocumentationService._create_technical_documentation(documentation, doc_config)
                elif doc_type == 'policy':
                    DocumentationService._create_policy_documentation(documentation, doc_config)
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='Documentation Created',
                    message=f'Successfully created {doc_type} documentation: {documentation.title}',
                    notification_type='documentation',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                # Log documentation creation
                DocumentationService._log_documentation_creation(documentation, created_by)
                
                return documentation
                
        except Exception as e:
            logger.error(f"Error creating documentation: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create documentation: {str(e)}")
    
    @staticmethod
    def update_documentation(doc_id: UUID, doc_config: Dict[str, Any], updated_by: Optional[User] = None) -> Documentation:
        """
        Update documentation with enterprise-grade processing.
        
        Update features:
        - Content validation and sanitization
        - Version control
        - Change tracking
        - Audit logging
        """
        try:
            # Security: Validate update configuration
            DocumentationService._validate_update_config(doc_config, updated_by)
            
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            with transaction.atomic():
                # Create version backup
                DocumentationService._create_version_backup(documentation, updated_by)
                
                # Update documentation
                documentation.title = doc_config.get('title', documentation.title)
                documentation.content = doc_config.get('content', documentation.content)
                documentation.category = doc_config.get('category', documentation.category)
                documentation.tags = doc_config.get('tags', documentation.tags)
                documentation.version = doc_config.get('version', documentation.version)
                documentation.status = doc_config.get('status', documentation.status)
                documentation.updated_by = updated_by
                documentation.save()
                
                # Update type-specific documentation
                if documentation.type == 'api':
                    DocumentationService._update_api_documentation(documentation, doc_config)
                elif documentation.type == 'user_guide':
                    DocumentationService._update_user_guide(documentation, doc_config)
                elif documentation.type == 'technical':
                    DocumentationService._update_technical_documentation(documentation, doc_config)
                
                # Send notification
                Notification.objects.create(
                    user=updated_by,
                    title='Documentation Updated',
                    message=f'Successfully updated documentation: {documentation.title}',
                    notification_type='documentation',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                return documentation
                
        except Exception as e:
            logger.error(f"Error updating documentation: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update documentation: {str(e)}")
    
    @staticmethod
    def search_documentation(search_config: Dict[str, Any], searched_by: Optional[User] = None) -> List[DocumentationSearchResult]:
        """
        Search documentation with advanced capabilities.
        
        Search features:
        - Full-text search
        - Category filtering
        - Tag filtering
        - Relevance scoring
        - Performance optimization
        """
        try:
            # Security: Validate search configuration
            DocumentationService._validate_search_config(search_config, searched_by)
            
            # Get search parameters
            query = search_config.get('query', '')
            category = search_config.get('category')
            tags = search_config.get('tags', [])
            doc_type = search_config.get('type')
            limit = search_config.get('limit', 50)
            
            # Perform search
            search_results = DocumentationService._perform_search(query, category, tags, doc_type, limit)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching documentation: {str(e)}")
            raise AdvertiserServiceError(f"Failed to search documentation: {str(e)}")
    
    @staticmethod
    def get_documentation_stats(doc_id: UUID) -> Dict[str, Any]:
        """
        Get documentation statistics with comprehensive metrics.
        
        Statistics include:
        - View counts
        - Search appearances
        - User engagement
        - Performance metrics
        """
        try:
            # Get documentation
            documentation = Documentation.objects.get(id=doc_id)
            
            # Calculate statistics
            stats = DocumentationService._calculate_documentation_stats(documentation)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting documentation stats: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get documentation stats: {str(e)}")
    
    @staticmethod
    def get_documentation_analytics(date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get documentation analytics with comprehensive metrics.
        
        Analytics include:
        - Popular documentation
        - Search trends
        - User engagement
        - Performance metrics
        """
        try:
            # Get date range
            if not date_from:
                date_from = timezone.now() - timedelta(days=30)
            if not date_to:
                date_to = timezone.now()
            
            # Calculate analytics
            analytics = DocumentationService._calculate_analytics(date_from, date_to)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting documentation analytics: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get documentation analytics: {str(e)}")
    
    @staticmethod
    def _validate_documentation_config(doc_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate documentation configuration with security checks."""
        # Security: Check required fields
        required_fields = ['title', 'type', 'content']
        for field in required_fields:
            if not doc_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate documentation type
        valid_types = ['api', 'user_guide', 'technical', 'policy']
        doc_type = doc_config.get('type')
        if doc_type not in valid_types:
            raise AdvertiserValidationError(f"Invalid documentation type: {doc_type}")
        
        # Security: Validate content
        content = doc_config.get('content', '')
        if content:
            DocumentationService._validate_content(content, doc_type)
        
        # Security: Check user permissions
        if user and not DocumentationService._has_documentation_permission(user, 'create'):
            raise AdvertiserValidationError("User does not have documentation creation permissions")
    
    @staticmethod
    def _validate_content(content: str, doc_type: str) -> None:
        """Validate documentation content with security checks."""
        if not content or len(content.strip()) < 10:
            raise AdvertiserValidationError("Documentation content is too short")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'eval\s*\(',             # Code execution
            r'exec\s*\(',             # Code execution
            r'system\s*\(',           # System calls
            r'os\.system',            # System calls
            r'subprocess\.call',       # Subprocess calls
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise AdvertiserValidationError("Documentation content contains prohibited code")
        
        # Type-specific validation
        if doc_type == 'api':
            DocumentationService._validate_api_content(content)
        elif doc_type == 'user_guide':
            DocumentationService._validate_user_guide_content(content)
        elif doc_type == 'technical':
            DocumentationService._validate_technical_content(content)
    
    @staticmethod
    def _validate_api_content(content: str) -> None:
        """Validate API documentation content."""
        # Check for API-specific patterns
        api_patterns = [
            r'openapi\s*:',           # OpenAPI specification
            r'swagger\s*:',           # Swagger specification
            r'\/api\/',               # API endpoints
            r'get\s*\|',              # HTTP methods
            r'post\s*\|',
            r'put\s*\|',
            r'delete\s*\|',
        ]
        
        import re
        api_found = any(re.search(pattern, content, re.IGNORECASE) for pattern in api_patterns)
        
        if not api_found:
            # API documentation should contain API-related content
            pass  # Not strictly required, but good to have
    
    @staticmethod
    def _validate_user_guide_content(content: str) -> None:
        """Validate user guide content."""
        # Check for user guide patterns
        guide_patterns = [
            r'##\s*Step',              # Steps
            r'###\s*Example',          # Examples
            r'1\.',                    # Numbered lists
            r'\*\s+',                  # Bullet points
            r'!\[.*\]\(.*\)',          # Images
        ]
        
        # User guides should have structured content
        pass  # Not strictly required
    
    @staticmethod
    def _validate_technical_content(content: str) -> None:
        """Validate technical documentation content."""
        # Check for technical patterns
        tech_patterns = [
            r'```',                    # Code blocks
            r'`[^`]+`',               # Inline code
            r'\[.*\]\(.*\)',          # Links
            r'table\s*\|',            # Tables
        ]
        
        # Technical docs should have code examples
        pass  # Not strictly required
    
    @staticmethod
    def _validate_update_config(doc_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate update configuration with security checks."""
        # Security: Check user permissions
        if user and not DocumentationService._has_documentation_permission(user, 'update'):
            raise AdvertiserValidationError("User does not have documentation update permissions")
        
        # Security: Validate content if provided
        content = doc_config.get('content')
        if content:
            DocumentationService._validate_content(content, doc_config.get('type'))
    
    @staticmethod
    def _validate_search_config(search_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate search configuration with security checks."""
        # Security: Check user permissions
        if user and not DocumentationService._has_documentation_permission(user, 'search'):
            raise AdvertiserValidationError("User does not have documentation search permissions")
        
        # Security: Validate search query
        query = search_config.get('query', '')
        if query:
            # Check for injection attempts
            prohibited_patterns = [
                r'<script',  # Script injection
                r'javascript:',  # JavaScript protocol
                r'on\w+\s*=',  # Event handlers
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    raise AdvertiserValidationError("Search query contains prohibited content")
    
    @staticmethod
    def _has_documentation_permission(user: User, action: str) -> bool:
        """Check if user has documentation permissions."""
        if user.is_superuser:
            return True
        
        if user.is_staff:
            return True
        
        # Check user role permissions
        if hasattr(user, 'role'):
            role_permissions = {
                'admin': ['create', 'update', 'delete', 'search', 'view'],
                'developer': ['create', 'update', 'search', 'view'],
                'user': ['search', 'view'],
                'guest': ['search', 'view']
            }
            
            return action in role_permissions.get(user.role, [])
        
        # Default permissions
        return action in ['search', 'view']
    
    @staticmethod
    def _create_api_documentation(documentation: Documentation, doc_config: Dict[str, Any]) -> APIDocumentation:
        """Create API documentation specific configuration."""
        return APIDocumentation.objects.create(
            documentation=documentation,
            api_version=doc_config.get('api_version', 'v1'),
            base_url=doc_config.get('base_url', ''),
            endpoints=doc_config.get('endpoints', []),
            schemas=doc_config.get('schemas', {}),
            authentication=doc_config.get('authentication', {})
        )
    
    @staticmethod
    def _create_user_guide(documentation: Documentation, doc_config: Dict[str, Any]) -> UserGuide:
        """Create user guide specific configuration."""
        return UserGuide.objects.create(
            documentation=documentation,
            target_audience=doc_config.get('target_audience', 'general'),
            difficulty_level=doc_config.get('difficulty_level', 'beginner'),
            estimated_time=doc_config.get('estimated_time', 0),
            prerequisites=doc_config.get('prerequisites', []),
            steps=doc_config.get('steps', [])
        )
    
    @staticmethod
    def _create_technical_documentation(documentation: Documentation, doc_config: Dict[str, Any]) -> TechnicalDocumentation:
        """Create technical documentation specific configuration."""
        return TechnicalDocumentation.objects.create(
            documentation=documentation,
            technical_level=doc_config.get('technical_level', 'intermediate'),
            components=doc_config.get('components', []),
            dependencies=doc_config.get('dependencies', []),
            configuration=doc_config.get('configuration', {}),
            troubleshooting=doc_config.get('troubleshooting', [])
        )
    
    @staticmethod
    def _create_policy_documentation(documentation: Documentation, doc_config: Dict[str, Any]) -> None:
        """Create policy documentation specific configuration."""
        # Policy documentation uses base fields only
        pass
    
    @staticmethod
    def _create_version_backup(documentation: Documentation, user: Optional[User]) -> DocumentationVersioning:
        """Create version backup for documentation."""
        try:
            return DocumentationVersioning.objects.create(
                documentation=documentation,
                version=documentation.version,
                title=documentation.title,
                content=documentation.content,
                category=documentation.category,
                tags=documentation.tags,
                status=documentation.status,
                created_by=documentation.created_by,
                updated_by=user,
                created_at=documentation.created_at,
                updated_at=documentation.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error creating version backup: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create version backup: {str(e)}")
    
    @staticmethod
    def _update_api_documentation(documentation: Documentation, doc_config: Dict[str, Any]) -> None:
        """Update API documentation specific configuration."""
        try:
            api_doc = documentation.api_documentation
            
            if doc_config.get('api_version'):
                api_doc.api_version = doc_config['api_version']
            
            if doc_config.get('base_url'):
                api_doc.base_url = doc_config['base_url']
            
            if doc_config.get('endpoints'):
                api_doc.endpoints = doc_config['endpoints']
            
            if doc_config.get('schemas'):
                api_doc.schemas = doc_config['schemas']
            
            if doc_config.get('authentication'):
                api_doc.authentication = doc_config['authentication']
            
            api_doc.save()
            
        except APIDocumentation.DoesNotExist:
            DocumentationService._create_api_documentation(documentation, doc_config)
    
    @staticmethod
    def _update_user_guide(documentation: Documentation, doc_config: Dict[str, Any]) -> None:
        """Update user guide specific configuration."""
        try:
            user_guide = documentation.user_guide
            
            if doc_config.get('target_audience'):
                user_guide.target_audience = doc_config['target_audience']
            
            if doc_config.get('difficulty_level'):
                user_guide.difficulty_level = doc_config['difficulty_level']
            
            if doc_config.get('estimated_time'):
                user_guide.estimated_time = doc_config['estimated_time']
            
            if doc_config.get('prerequisites'):
                user_guide.prerequisites = doc_config['prerequisites']
            
            if doc_config.get('steps'):
                user_guide.steps = doc_config['steps']
            
            user_guide.save()
            
        except UserGuide.DoesNotExist:
            DocumentationService._create_user_guide(documentation, doc_config)
    
    @staticmethod
    def _update_technical_documentation(documentation: Documentation, doc_config: Dict[str, Any]) -> None:
        """Update technical documentation specific configuration."""
        try:
            tech_doc = documentation.technical_documentation
            
            if doc_config.get('technical_level'):
                tech_doc.technical_level = doc_config['technical_level']
            
            if doc_config.get('components'):
                tech_doc.components = doc_config['components']
            
            if doc_config.get('dependencies'):
                tech_doc.dependencies = doc_config['dependencies']
            
            if doc_config.get('configuration'):
                tech_doc.configuration = doc_config['configuration']
            
            if doc_config.get('troubleshooting'):
                tech_doc.troubleshooting = doc_config['troubleshooting']
            
            tech_doc.save()
            
        except TechnicalDocumentation.DoesNotExist:
            DocumentationService._create_technical_documentation(documentation, doc_config)
    
    @staticmethod
    def _perform_search(query: str, category: Optional[str], tags: List[str], doc_type: Optional[str], limit: int) -> List[DocumentationSearchResult]:
        """Perform advanced search with relevance scoring."""
        try:
            # Build search query
            queryset = Documentation.objects.filter(status='published')
            
            # Apply filters
            if category:
                queryset = queryset.filter(category=category)
            
            if tags:
                queryset = queryset.filter(tags__overlap=tags)
            
            if doc_type:
                queryset = queryset.filter(type=doc_type)
            
            # Full-text search
            if query:
                # Search in title and content
                queryset = queryset.filter(
                    Q(title__icontains=query) | Q(content__icontains=query)
                )
            
            # Get results
            results = queryset[:limit * 2]  # Get more for ranking
            
            # Calculate relevance scores
            search_results = []
            for doc in results:
                score = DocumentationService._calculate_relevance_score(doc, query, category, tags, doc_type)
                
                # Create content snippet
                content_snippet = DocumentationService._create_content_snippet(doc.content, query)
                
                search_results.append(DocumentationSearchResult(
                    doc_id=str(doc.id),
                    title=doc.title,
                    content_snippet=content_snippet,
                    relevance_score=score,
                    doc_type=doc.type,
                    category=doc.category,
                    tags=doc.tags,
                    updated_at=doc.updated_at
                ))
            
            # Sort by relevance score
            search_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return search_results[:limit]
            
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_relevance_score(documentation: Documentation, query: str, category: Optional[str], tags: List[str], doc_type: Optional[str]) -> float:
        """Calculate relevance score for search result."""
        score = 0.0
        
        # Title match (highest weight)
        if query and query.lower() in documentation.title.lower():
            score += 10.0
        
        # Content match
        if query:
            content_matches = documentation.content.lower().count(query.lower())
            score += min(content_matches * 0.5, 5.0)
        
        # Category match
        if category and documentation.category == category:
            score += 3.0
        
        # Tag matches
        if tags:
            matching_tags = set(documentation.tags) & set(tags)
            score += len(matching_tags) * 2.0
        
        # Type match
        if doc_type and documentation.type == doc_type:
            score += 2.0
        
        # Recency boost
        days_old = (timezone.now() - documentation.updated_at).days
        recency_boost = max(0, 1.0 - (days_old / 365.0))
        score += recency_boost
        
        return score
    
    @staticmethod
    def _create_content_snippet(content: str, query: str, max_length: int = 200) -> str:
        """Create content snippet with highlighted query."""
        if not query:
            return content[:max_length] + '...' if len(content) > max_length else content
        
        # Find first occurrence of query
        query_lower = query.lower()
        content_lower = content.lower()
        
        index = content_lower.find(query_lower)
        if index == -1:
            return content[:max_length] + '...' if len(content) > max_length else content
        
        # Create snippet around query
        start = max(0, index - 50)
        end = min(len(content), index + len(query) + 50)
        
        snippet = content[start:end]
        
        # Add ellipsis if needed
        if start > 0:
            snippet = '...' + snippet
        if end < len(content):
            snippet = snippet + '...'
        
        return snippet
    
    @staticmethod
    def _calculate_documentation_stats(documentation: Documentation) -> Dict[str, Any]:
        """Calculate documentation statistics."""
        try:
            # Get analytics data
            analytics = DocumentationAnalytics.objects.filter(documentation=documentation)
            
            # Calculate metrics
            total_views = analytics.aggregate(
                total_views=Sum('view_count')
            )['total_views'] or 0
            
            total_searches = analytics.aggregate(
                total_searches=Sum('search_count')
            )['total_searches'] or 0
            
            unique_users = analytics.aggregate(
                unique_users=Count('user_id', distinct=True)
            )['unique_users'] or 0
            
            avg_rating = analytics.aggregate(
                avg_rating=Avg('rating')
            )['avg_rating'] or 0
            
            # Get recent activity
            recent_views = analytics.filter(
                viewed_at__gte=timezone.now() - timedelta(days=7)
            ).aggregate(
                recent_views=Sum('view_count')
            )['recent_views'] or 0
            
            return {
                'documentation_id': str(documentation.id),
                'title': documentation.title,
                'type': documentation.type,
                'total_views': total_views,
                'total_searches': total_searches,
                'unique_users': unique_users,
                'avg_rating': round(avg_rating, 2),
                'recent_views_7d': recent_views,
                'last_updated': documentation.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating documentation stats: {str(e)}")
            return {
                'documentation_id': str(documentation.id),
                'error': 'Failed to calculate statistics'
            }
    
    @staticmethod
    def _calculate_analytics(date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Calculate comprehensive analytics."""
        try:
            # Get analytics data for date range
            analytics = DocumentationAnalytics.objects.filter(
                viewed_at__gte=date_from,
                viewed_at__lte=date_to
            )
            
            # Popular documentation
            popular_docs = analytics.values('documentation__title', 'documentation__type').annotate(
                total_views=Sum('view_count')
            ).order_by('-total_views')[:10]
            
            # Search trends
            search_trends = DocumentationSearch.objects.filter(
                searched_at__gte=date_from,
                searched_at__lte=date_to
            ).values('query').annotate(
                search_count=Count('id')
            ).order_by('-search_count')[:10]
            
            # User engagement
            user_engagement = analytics.aggregate(
                total_views=Sum('view_count'),
                unique_users=Count('user_id', distinct=True),
                avg_rating=Avg('rating')
            )
            
            # Type distribution
            type_distribution = analytics.values('documentation__type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {
                'date_range': {
                    'from': date_from.isoformat(),
                    'to': date_to.isoformat()
                },
                'popular_documentation': list(popular_docs),
                'search_trends': list(search_trends),
                'user_engagement': {
                    'total_views': user_engagement['total_views'] or 0,
                    'unique_users': user_engagement['unique_users'] or 0,
                    'avg_rating': round(user_engagement['avg_rating'] or 0, 2)
                },
                'type_distribution': list(type_distribution)
            }
            
        except Exception as e:
            logger.error(f"Error calculating analytics: {str(e)}")
            return {
                'error': 'Failed to calculate analytics'
            }
    
    @staticmethod
    def _log_documentation_creation(documentation: Documentation, user: Optional[User]) -> None:
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


class APIDocumentationService:
    """Service for API documentation management."""
    
    @staticmethod
    def generate_openapi_spec(documentation: Documentation) -> Dict[str, Any]:
        """Generate OpenAPI specification from documentation."""
        try:
            api_doc = documentation.api_documentation
            
            # Build OpenAPI spec
            openapi_spec = {
                'openapi': '3.0.0',
                'info': {
                    'title': documentation.title,
                    'description': documentation.content,
                    'version': api_doc.api_version
                },
                'servers': [
                    {'url': api_doc.base_url}
                ],
                'paths': {},
                'components': {
                    'schemas': api_doc.schemas,
                    'securitySchemes': api_doc.authentication
                }
            }
            
            # Add endpoints
            for endpoint in api_doc.endpoints:
                path = endpoint.get('path', '/')
                method = endpoint.get('method', 'get').lower()
                
                if path not in openapi_spec['paths']:
                    openapi_spec['paths'][path] = {}
                
                openapi_spec['paths'][path][method] = {
                    'summary': endpoint.get('summary', ''),
                    'description': endpoint.get('description', ''),
                    'parameters': endpoint.get('parameters', []),
                    'responses': endpoint.get('responses', {}),
                    'tags': endpoint.get('tags', [])
                }
            
            return openapi_spec
            
        except Exception as e:
            logger.error(f"Error generating OpenAPI spec: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate OpenAPI spec: {str(e)}")
    
    @staticmethod
    def validate_api_documentation(api_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API documentation configuration."""
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            # Validate base URL
            base_url = api_config.get('base_url', '')
            if not base_url:
                validation_result['errors'].append('Base URL is required')
                validation_result['valid'] = False
            elif not base_url.startswith(('http://', 'https://')):
                validation_result['errors'].append('Base URL must start with http:// or https://')
                validation_result['valid'] = False
            
            # Validate endpoints
            endpoints = api_config.get('endpoints', [])
            for endpoint in endpoints:
                if not endpoint.get('path'):
                    validation_result['errors'].append('Endpoint path is required')
                    validation_result['valid'] = False
                
                if not endpoint.get('method'):
                    validation_result['errors'].append('Endpoint method is required')
                    validation_result['valid'] = False
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating API documentation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)]
            }


class UserGuideService:
    """Service for user guide management."""
    
    @staticmethod
    def generate_table_of_contents(documentation: Documentation) -> List[Dict[str, Any]]:
        """Generate table of contents from user guide."""
        try:
            user_guide = documentation.user_guide
            
            # Parse content for headings
            content = documentation.content
            
            # Use regex to find markdown headings
            heading_pattern = r'^(#{1,6})\s+(.+)$'
            headings = re.findall(heading_pattern, content, re.MULTILINE)
            
            # Build TOC
            toc = []
            for level, title in headings:
                toc.append({
                    'level': len(level),
                    'title': title.strip(),
                    'anchor': title.strip().lower().replace(' ', '-').replace('?', '').replace('!', '')
                })
            
            return toc
            
        except Exception as e:
            logger.error(f"Error generating table of contents: {str(e)}")
            return []
    
    @staticmethod
    def estimate_reading_time(content: str) -> int:
        """Estimate reading time in minutes."""
        try:
            # Average reading speed: 200 words per minute
            words = len(content.split())
            reading_time = max(1, words // 200)
            
            return reading_time
            
        except Exception as e:
            logger.error(f"Error estimating reading time: {str(e)}")
            return 5  # Default estimate


class TechnicalDocumentationService:
    """Service for technical documentation management."""
    
    @staticmethod
    def extract_code_blocks(content: str) -> List[Dict[str, Any]]:
        """Extract code blocks from technical documentation."""
        try:
            # Use regex to find code blocks
            code_block_pattern = r'```(\w+)?\n(.*?)\n```'
            code_blocks = re.findall(code_block_pattern, content, re.DOTALL)
            
            extracted_blocks = []
            for language, code in code_blocks:
                extracted_blocks.append({
                    'language': language or 'text',
                    'code': code.strip(),
                    'line_count': len(code.split('\n'))
                })
            
            return extracted_blocks
            
        except Exception as e:
            logger.error(f"Error extracting code blocks: {str(e)}")
            return []
    
    @staticmethod
    def validate_technical_documentation(tech_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate technical documentation configuration."""
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            # Validate technical level
            tech_level = tech_config.get('technical_level', '')
            valid_levels = ['beginner', 'intermediate', 'advanced', 'expert']
            
            if tech_level and tech_level not in valid_levels:
                validation_result['errors'].append(f'Invalid technical level: {tech_level}')
                validation_result['valid'] = False
            
            # Validate components
            components = tech_config.get('components', [])
            for component in components:
                if not component.get('name'):
                    validation_result['errors'].append('Component name is required')
                    validation_result['valid'] = False
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating technical documentation: {str(e)}")
            return {
                'valid': False,
                'errors': [str(e)]
            }


class DocumentationSearchService:
    """Service for documentation search functionality."""
    
    @staticmethod
    def index_documentation(documentation: Documentation) -> None:
        """Index documentation for search."""
        try:
            # Create search index entry
            DocumentationSearch.objects.update_or_create(
                documentation=documentation,
                defaults={
                    'title': documentation.title,
                    'content': documentation.content,
                    'category': documentation.category,
                    'tags': documentation.tags,
                    'type': documentation.type,
                    'indexed_at': timezone.now()
                }
            )
            
        except Exception as e:
            logger.error(f"Error indexing documentation: {str(e)}")
    
    @staticmethod
    def perform_advanced_search(search_config: Dict[str, Any]) -> List[DocumentationSearchResult]:
        """Perform advanced search with filters."""
        try:
            # Get search parameters
            query = search_config.get('query', '')
            filters = search_config.get('filters', {})
            sort_by = search_config.get('sort_by', 'relevance')
            
            # Build search query
            queryset = DocumentationSearch.objects.all()
            
            # Apply filters
            if filters.get('category'):
                queryset = queryset.filter(category=filters['category'])
            
            if filters.get('type'):
                queryset = queryset.filter(type=filters['type'])
            
            if filters.get('tags'):
                queryset = queryset.filter(tags__overlap=filters['tags'])
            
            # Apply text search
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | Q(content__icontains=query)
                )
            
            # Sort results
            if sort_by == 'relevance':
                # Custom relevance scoring
                results = queryset.all()
                scored_results = []
                
                for result in results:
                    score = DocumentationSearchService._calculate_search_score(result, query)
                    scored_results.append((result, score))
                
                scored_results.sort(key=lambda x: x[1], reverse=True)
                results = [item[0] for item in scored_results]
            
            elif sort_by == 'updated_at':
                results = queryset.order_by('-documentation__updated_at')
            
            elif sort_by == 'title':
                results = queryset.order_by('title')
            
            else:
                results = queryset.order_by('-indexed_at')
            
            # Convert to search results
            search_results = []
            for result in results[:search_config.get('limit', 50)]:
                search_results.append(DocumentationSearchResult(
                    doc_id=str(result.documentation.id),
                    title=result.title,
                    content_snippet=DocumentationService._create_content_snippet(result.content, query),
                    relevance_score=DocumentationSearchService._calculate_search_score(result, query),
                    doc_type=result.type,
                    category=result.category,
                    tags=result.tags,
                    updated_at=result.documentation.updated_at
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error performing advanced search: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_search_score(search_result: DocumentationSearch, query: str) -> float:
        """Calculate search relevance score."""
        score = 0.0
        
        if not query:
            return score
        
        query_lower = query.lower()
        
        # Title match (highest weight)
        if query_lower in search_result.title.lower():
            score += 10.0
        
        # Content match
        content_matches = search_result.content.lower().count(query_lower)
        score += min(content_matches * 0.5, 5.0)
        
        return score


class DocumentationVersioningService:
    """Service for documentation versioning."""
    
    @staticmethod
    def create_version(documentation: Documentation, version: str, created_by: Optional[User] = None) -> DocumentationVersioning:
        """Create new version of documentation."""
        try:
            return DocumentationVersioning.objects.create(
                documentation=documentation,
                version=version,
                title=documentation.title,
                content=documentation.content,
                category=documentation.category,
                tags=documentation.tags,
                status=documentation.status,
                created_by=documentation.created_by,
                updated_by=created_by,
                created_at=documentation.created_at,
                updated_at=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error creating version: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create version: {str(e)}")
    
    @staticmethod
    def restore_version(documentation: Documentation, version: str, restored_by: Optional[User] = None) -> Documentation:
        """Restore documentation to specific version."""
        try:
            # Get version to restore
            version_doc = DocumentationVersioning.objects.get(
                documentation=documentation,
                version=version
            )
            
            # Create backup of current version
            DocumentationService._create_version_backup(documentation, restored_by)
            
            # Restore content
            documentation.title = version_doc.title
            documentation.content = version_doc.content
            documentation.category = version_doc.category
            documentation.tags = version_doc.tags
            documentation.status = version_doc.status
            documentation.updated_by = restored_by
            documentation.save()
            
            return documentation
            
        except Exception as e:
            logger.error(f"Error restoring version: {str(e)}")
            raise AdvertiserServiceError(f"Failed to restore version: {str(e)}")
    
    @staticmethod
    def get_version_history(documentation: Documentation) -> List[Dict[str, Any]]:
        """Get version history for documentation."""
        try:
            versions = DocumentationVersioning.objects.filter(
                documentation=documentation
            ).order_by('-updated_at')
            
            history = []
            for version in versions:
                history.append({
                    'version': version.version,
                    'title': version.title,
                    'updated_at': version.updated_at.isoformat(),
                    'updated_by': version.updated_by.username if version.updated_by else None,
                    'changes': DocumentationVersioningService._calculate_changes(version)
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_changes(version: DocumentationVersioning) -> Dict[str, Any]:
        """Calculate changes between versions."""
        try:
            # Get previous version
            previous_version = DocumentationVersioning.objects.filter(
                documentation=version.documentation,
                updated_at__lt=version.updated_at
            ).order_by('-updated_at').first()
            
            if not previous_version:
                return {
                    'type': 'initial',
                    'changes': ['Initial version']
                }
            
            changes = []
            
            # Compare title
            if version.title != previous_version.title:
                changes.append(f"Title changed from '{previous_version.title}' to '{version.title}'")
            
            # Compare content (simplified)
            if version.content != previous_version.content:
                changes.append('Content updated')
            
            # Compare category
            if version.category != previous_version.category:
                changes.append(f"Category changed from '{previous_version.category}' to '{version.category}'")
            
            # Compare tags
            if version.tags != previous_version.tags:
                changes.append('Tags updated')
            
            return {
                'type': 'update',
                'changes': changes
            }
            
        except Exception as e:
            logger.error(f"Error calculating changes: {str(e)}")
            return {
                'type': 'error',
                'changes': ['Failed to calculate changes']
            }


class DocumentationAnalyticsService:
    """Service for documentation analytics."""
    
    @staticmethod
    def track_view(documentation: Documentation, user: Optional[User] = None) -> None:
        """Track documentation view."""
        try:
            # Get or create analytics record
            analytics, created = DocumentationAnalytics.objects.get_or_create(
                documentation=documentation,
                user=user,
                date=timezone.now().date(),
                defaults={
                    'view_count': 1,
                    'viewed_at': timezone.now()
                }
            )
            
            if not created:
                analytics.view_count += 1
                analytics.viewed_at = timezone.now()
                analytics.save(update_fields=['view_count', 'viewed_at'])
            
        except Exception as e:
            logger.error(f"Error tracking view: {str(e)}")
    
    @staticmethod
    def track_search(query: str, user: Optional[User] = None) -> None:
        """Track documentation search."""
        try:
            DocumentationSearch.objects.create(
                query=query,
                user=user,
                searched_at=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error tracking search: {str(e)}")
    
    @staticmethod
    def generate_engagement_report(date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Generate engagement report."""
        try:
            # Get analytics data
            analytics = DocumentationAnalytics.objects.filter(
                viewed_at__gte=date_from,
                viewed_at__lte=date_to
            )
            
            # Calculate metrics
            total_views = analytics.aggregate(
                total_views=Sum('view_count')
            )['total_views'] or 0
            
            unique_users = analytics.aggregate(
                unique_users=Count('user_id', distinct=True)
            )['unique_users'] or 0
            
            # Daily engagement
            daily_engagement = analytics.values('date').annotate(
                daily_views=Sum('view_count'),
                daily_users=Count('user_id', distinct=True)
            ).order_by('date')
            
            # Top documentation
            top_docs = analytics.values('documentation__title').annotate(
                doc_views=Sum('view_count')
            ).order_by('-doc_views')[:10]
            
            return {
                'period': {
                    'from': date_from.isoformat(),
                    'to': date_to.isoformat()
                },
                'summary': {
                    'total_views': total_views,
                    'unique_users': unique_users,
                    'avg_views_per_user': round(total_views / max(unique_users, 1), 2)
                },
                'daily_engagement': list(daily_engagement),
                'top_documentation': list(top_docs)
            }
            
        except Exception as e:
            logger.error(f"Error generating engagement report: {str(e)}")
            return {
                'error': 'Failed to generate engagement report'
            }
