"""
Documentation Serializers

This module provides comprehensive serializers for documentation management with
enterprise-grade validation, security, and performance optimization following
industry standards from Swagger, OpenAPI, and Confluence.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import Coalesce

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


class DocumentationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Documentation model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    created_at_formatted = serializers.SerializerMethodField()
    updated_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Documentation
        fields = [
            'id', 'title', 'type', 'content', 'category', 'tags',
            'version', 'status', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted',
            'created_by', 'updated_by'
        ]
    
    def get_created_at_formatted(self, obj: Documentation) -> str:
        """Get formatted creation time."""
        try:
            if obj.created_at:
                return obj.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def get_updated_at_formatted(self, obj: Documentation) -> str:
        """Get formatted update time."""
        try:
            if obj.updated_at:
                return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def validate_title(self, value: str) -> str:
        """Validate documentation title with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Documentation title must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Documentation title contains prohibited characters")
        
        return value
    
    def validate_type(self, value: str) -> str:
        """Validate documentation type with security checks."""
        valid_types = ['api', 'user_guide', 'technical', 'policy']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid documentation type. Must be one of: {valid_types}")
        return value
    
    def validate_content(self, value: str) -> str:
        """Validate documentation content with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Documentation content is too short")
        
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
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Documentation content contains prohibited code")
        
        return value
    
    def validate_category(self, value: str) -> str:
        """Validate documentation category with security checks."""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Documentation category must be at least 2 characters long")
        
        # Security: Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Documentation category contains prohibited characters")
        
        return value.strip()
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate documentation tags with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        
        # Validate each tag
        validated_tags = []
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("All tags must be strings")
            
            tag = tag.strip()
            if not tag:
                continue
            
            # Security: Check for prohibited characters
            prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
            if any(char in tag for char in prohibited_chars):
                raise serializers.ValidationError(f"Tag contains prohibited characters: {tag}")
            
            validated_tags.append(tag.lower())
        
        # Remove duplicates
        return list(set(validated_tags))
    
    def validate_version(self, value: str) -> str:
        """Validate documentation version with security checks."""
        if not value:
            raise serializers.ValidationError("Documentation version is required")
        
        # Basic version validation (semantic versioning)
        import re
        version_pattern = r'^\d+\.\d+\.\d+$'
        if not re.match(version_pattern, value):
            raise serializers.ValidationError("Version must follow semantic versioning (e.g., 1.0.0)")
        
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate documentation status with security checks."""
        valid_statuses = ['draft', 'review', 'published', 'archived']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate documentation type vs content
        doc_type = attrs.get('type')
        content = attrs.get('content', '')
        
        if doc_type == 'api':
            DocumentationSerializer._validate_api_content(content)
        elif doc_type == 'user_guide':
            DocumentationSerializer._validate_user_guide_content(content)
        elif doc_type == 'technical':
            DocumentationSerializer._validate_technical_content(content)
        elif doc_type == 'policy':
            DocumentationSerializer._validate_policy_content(content)
        
        return attrs
    
    @staticmethod
    def _validate_api_content(content: str) -> None:
        """Validate API documentation content."""
        # API documentation should contain API-related content
        api_patterns = [
            r'openapi\s*:',
            r'swagger\s*:',
            r'\/api\/',
            r'get\s*\|',
            r'post\s*\|',
            r'put\s*\|',
            r'delete\s*\|',
        ]
        
        import re
        api_found = any(re.search(pattern, content, re.IGNORECASE) for pattern in api_patterns)
        
        if not api_found:
            raise serializers.ValidationError("API documentation should contain API-related content")
    
    @staticmethod
    def _validate_user_guide_content(content: str) -> None:
        """Validate user guide content."""
        # User guides should have structured content
        guide_patterns = [
            r'##\s*Step',
            r'###\s*Example',
            r'1\.',
            r'\*\s+',
            r'!\[.*\]\(.*\)',
        ]
        
        # Not strictly required, but good to have
        pass
    
    @staticmethod
    def _validate_technical_content(content: str) -> None:
        """Validate technical documentation content."""
        # Technical docs should have code examples
        tech_patterns = [
            r'```',
            r'`[^`]+`',
            r'\[.*\]\(.*\)',
            r'table\s*\|',
        ]
        
        # Not strictly required, but good to have
        pass
    
    @staticmethod
    def _validate_policy_content(content: str) -> None:
        """Validate policy documentation content."""
        # Policy documents should have clear structure
        policy_patterns = [
            r'##\s*Policy',
            r'##\s*Guidelines',
            r'##\s*Rules',
            r'##\s*Compliance',
        ]
        
        # Not strictly required, but good to have
        pass


class DocumentationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating documentation.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    title = serializers.CharField(max_length=255, required=True)
    type = serializers.ChoiceField(
        choices=['api', 'user_guide', 'technical', 'policy'],
        required=True
    )
    content = serializers.CharField(required=True)
    category = serializers.CharField(max_length=100, required=True)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    version = serializers.CharField(max_length=20, required=False, default='1.0.0')
    status = serializers.ChoiceField(
        choices=['draft', 'review', 'published', 'archived'],
        required=False,
        default='draft'
    )
    
    def validate_title(self, value: str) -> str:
        """Validate documentation title with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Documentation title must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Documentation title contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Documentation title contains prohibited characters")
        
        # Validate title length
        if len(value) > 255:
            raise serializers.ValidationError("Documentation title is too long")
        
        return value
    
    def validate_type(self, value: str) -> str:
        """Validate documentation type with comprehensive security checks."""
        valid_types = ['api', 'user_guide', 'technical', 'policy']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid documentation type. Must be one of: {valid_types}")
        return value
    
    def validate_content(self, value: str) -> str:
        """Validate documentation content with comprehensive security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Documentation content is too short")
        
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
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Documentation content contains prohibited code")
        
        # Validate content length
        if len(value) > 1048576:  # 1MB limit
            raise serializers.ValidationError("Documentation content is too large")
        
        return value
    
    def validate_category(self, value: str) -> str:
        """Validate documentation category with comprehensive security checks."""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Documentation category must be at least 2 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Documentation category contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Documentation category contains prohibited characters")
        
        # Validate category length
        if len(value.strip()) > 100:
            raise serializers.ValidationError("Documentation category is too long")
        
        return value.strip()
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate documentation tags with comprehensive security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        
        # Validate each tag
        validated_tags = []
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("All tags must be strings")
            
            tag = tag.strip()
            if not tag:
                continue
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, tag, re.IGNORECASE):
                    raise serializers.ValidationError(f"Tag contains prohibited content: {tag}")
            
            # Check for prohibited characters
            prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
            if any(char in tag for char in prohibited_chars):
                raise serializers.ValidationError(f"Tag contains prohibited characters: {tag}")
            
            # Validate tag length
            if len(tag) > 50:
                raise serializers.ValidationError(f"Tag is too long: {tag}")
            
            validated_tags.append(tag.lower())
        
        # Remove duplicates and limit count
        unique_tags = list(set(validated_tags))
        if len(unique_tags) > 20:
            raise serializers.ValidationError("Too many tags (maximum 20)")
        
        return unique_tags
    
    def validate_version(self, value: str) -> str:
        """Validate documentation version with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Documentation version is required")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script', r'javascript:', r'on\w+\s*='
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Version contains prohibited content")
        
        # Basic version validation (semantic versioning)
        version_pattern = r'^\d+\.\d+\.\d+$'
        if not re.match(version_pattern, value):
            raise serializers.ValidationError("Version must follow semantic versioning (e.g., 1.0.0)")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate documentation type vs content
        doc_type = attrs.get('type')
        content = attrs.get('content', '')
        
        if doc_type == 'api':
            DocumentationCreateSerializer._validate_api_content(content)
        elif doc_type == 'user_guide':
            DocumentationCreateSerializer._validate_user_guide_content(content)
        elif doc_type == 'technical':
            DocumentationCreateSerializer._validate_technical_content(content)
        elif doc_type == 'policy':
            DocumentationCreateSerializer._validate_policy_content(content)
        
        # Business logic: Set default version if not provided
        if 'version' not in attrs:
            attrs['version'] = '1.0.0'
        
        # Business logic: Set default status if not provided
        if 'status' not in attrs:
            attrs['status'] = 'draft'
        
        return attrs
    
    @staticmethod
    def _validate_api_content(content: str) -> None:
        """Validate API documentation content."""
        # API documentation should contain API-related content
        api_patterns = [
            r'openapi\s*:',
            r'swagger\s*:',
            r'\/api\/',
            r'get\s*\|',
            r'post\s*\|',
            r'put\s*\|',
            r'delete\s*\|',
        ]
        
        import re
        api_found = any(re.search(pattern, content, re.IGNORECASE) for pattern in api_patterns)
        
        if not api_found:
            raise serializers.ValidationError("API documentation should contain API-related content")
    
    @staticmethod
    def _validate_user_guide_content(content: str) -> None:
        """Validate user guide content."""
        # User guides should have structured content
        # Not strictly required, but good to have
        pass
    
    @staticmethod
    def _validate_technical_content(content: str) -> None:
        """Validate technical documentation content."""
        # Technical docs should have code examples
        # Not strictly required, but good to have
        pass
    
    @staticmethod
    def _validate_policy_content(content: str) -> None:
        """Validate policy documentation content."""
        # Policy documents should have clear structure
        # Not strictly required, but good to have
        pass


class APIDocumentationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIDocumentation model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = APIDocumentation
        fields = [
            'id', 'documentation', 'api_version', 'base_url',
            'endpoints', 'schemas', 'authentication'
        ]
        read_only_fields = ['id', 'documentation']
    
    def validate_api_version(self, value: str) -> str:
        """Validate API version with security checks."""
        if not value:
            raise serializers.ValidationError("API version is required")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("API version contains prohibited content")
        
        return value
    
    def validate_base_url(self, value: str) -> str:
        """Validate base URL with security checks."""
        if not value:
            raise serializers.ValidationError("Base URL is required")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Base URL contains prohibited content")
        
        # Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Base URL must start with http:// or https://")
        
        return value
    
    def validate_endpoints(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate endpoints with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Endpoints must be a list")
        
        # Validate each endpoint
        for endpoint in value:
            if not isinstance(endpoint, dict):
                raise serializers.ValidationError("Each endpoint must be a dictionary")
            
            # Validate required fields
            if 'path' not in endpoint:
                raise serializers.ValidationError("Endpoint path is required")
            
            if 'method' not in endpoint:
                raise serializers.ValidationError("Endpoint method is required")
            
            # Validate method
            valid_methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
            if endpoint['method'].lower() not in valid_methods:
                raise serializers.ValidationError(f"Invalid method: {endpoint['method']}")
        
        return value
    
    def validate_schemas(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate schemas with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schemas must be a dictionary")
        
        # Security: Check for prohibited content
        schemas_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, schemas_str, re.IGNORECASE):
                raise serializers.ValidationError("Schemas contain prohibited content")
        
        return value
    
    def validate_authentication(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate authentication with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Authentication must be a dictionary")
        
        # Security: Check for prohibited content
        auth_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, auth_str, re.IGNORECASE):
                raise serializers.ValidationError("Authentication contains prohibited content")
        
        return value


class UserGuideSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for UserGuide model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = UserGuide
        fields = [
            'id', 'documentation', 'target_audience', 'difficulty_level',
            'estimated_time', 'prerequisites', 'steps'
        ]
        read_only_fields = ['id', 'documentation']
    
    def validate_target_audience(self, value: str) -> str:
        """Validate target audience with security checks."""
        if not value:
            raise serializers.ValidationError("Target audience is required")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Target audience contains prohibited content")
        
        return value
    
    def validate_difficulty_level(self, value: str) -> str:
        """Validate difficulty level with security checks."""
        valid_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        if value not in valid_levels:
            raise serializers.ValidationError(f"Invalid difficulty level. Must be one of: {valid_levels}")
        return value
    
    def validate_estimated_time(self, value: int) -> int:
        """Validate estimated time with security checks."""
        if not isinstance(value, int) or value < 0 or value > 1000:
            raise serializers.ValidationError("Estimated time must be between 0 and 1000 minutes")
        return value
    
    def validate_prerequisites(self, value: List[str]) -> List[str]:
        """Validate prerequisites with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Prerequisites must be a list")
        
        # Validate each prerequisite
        for prereq in value:
            if not isinstance(prereq, str):
                raise serializers.ValidationError("All prerequisites must be strings")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, prereq, re.IGNORECASE):
                    raise serializers.ValidationError(f"Prerequisite contains prohibited content: {prereq}")
        
        return value
    
    def validate_steps(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate steps with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Steps must be a list")
        
        # Validate each step
        for step in value:
            if not isinstance(step, dict):
                raise serializers.ValidationError("Each step must be a dictionary")
            
            # Validate required fields
            if 'title' not in step:
                raise serializers.ValidationError("Step title is required")
            
            if 'description' not in step:
                raise serializers.ValidationError("Step description is required")
            
            # Security: Check for prohibited content
            step_str = json.dumps(step)
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, step_str, re.IGNORECASE):
                    raise serializers.ValidationError("Step contains prohibited content")
        
        return value


class TechnicalDocumentationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for TechnicalDocumentation model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = TechnicalDocumentation
        fields = [
            'id', 'documentation', 'technical_level', 'components',
            'dependencies', 'configuration', 'troubleshooting'
        ]
        read_only_fields = ['id', 'documentation']
    
    def validate_technical_level(self, value: str) -> str:
        """Validate technical level with security checks."""
        valid_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        if value not in valid_levels:
            raise serializers.ValidationError(f"Invalid technical level. Must be one of: {valid_levels}")
        return value
    
    def validate_components(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate components with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Components must be a list")
        
        # Validate each component
        for component in value:
            if not isinstance(component, dict):
                raise serializers.ValidationError("Each component must be a dictionary")
            
            # Validate required fields
            if 'name' not in component:
                raise serializers.ValidationError("Component name is required")
            
            # Security: Check for prohibited content
            component_str = json.dumps(component)
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, component_str, re.IGNORECASE):
                    raise serializers.ValidationError("Component contains prohibited content")
        
        return value
    
    def validate_dependencies(self, value: List[str]) -> List[str]:
        """Validate dependencies with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Dependencies must be a list")
        
        # Validate each dependency
        for dep in value:
            if not isinstance(dep, str):
                raise serializers.ValidationError("All dependencies must be strings")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, dep, re.IGNORECASE):
                    raise serializers.ValidationError(f"Dependency contains prohibited content: {dep}")
        
        return value
    
    def validate_configuration(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a dictionary")
        
        # Security: Check for prohibited content
        config_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, config_str, re.IGNORECASE):
                raise serializers.ValidationError("Configuration contains prohibited content")
        
        return value
    
    def validate_troubleshooting(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate troubleshooting with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Troubleshooting must be a list")
        
        # Validate each troubleshooting item
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each troubleshooting item must be a dictionary")
            
            # Validate required fields
            if 'problem' not in item:
                raise serializers.ValidationError("Troubleshooting problem is required")
            
            if 'solution' not in item:
                raise serializers.ValidationError("Troubleshooting solution is required")
            
            # Security: Check for prohibited content
            item_str = json.dumps(item)
            prohibited_patterns = [
                r'<script.*?>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, item_str, re.IGNORECASE):
                    raise serializers.ValidationError("Troubleshooting item contains prohibited content")
        
        return value


class DocumentationSearchSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for documentation search.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    query = serializers.CharField(max_length=500, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    type = serializers.ChoiceField(
        choices=['api', 'user_guide', 'technical', 'policy'],
        required=False,
        allow_null=True
    )
    limit = serializers.IntegerField(required=False, default=50, min_value=1, max_value=100)
    sort_by = serializers.ChoiceField(
        choices=['relevance', 'updated_at', 'title', 'created_at'],
        required=False,
        default='relevance'
    )
    
    def validate_query(self, value: str) -> str:
        """Validate search query with security checks."""
        if value:
            # Security: Check for injection attempts
            prohibited_patterns = [
                r'<script',
                r'javascript:',
                r'on\w+\s*=',
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Search query contains prohibited content")
            
            # Validate query length
            if len(value) > 500:
                raise serializers.ValidationError("Search query is too long")
        
        return value
    
    def validate_category(self, value: str) -> str:
        """Validate category with security checks."""
        if value:
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    raise serializers.ValidationError("Category contains prohibited content")
        
        return value
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate tags with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        
        # Validate each tag
        validated_tags = []
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("All tags must be strings")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, tag, re.IGNORECASE):
                    raise serializers.ValidationError(f"Tag contains prohibited content: {tag}")
            
            validated_tags.append(tag.lower())
        
        # Remove duplicates
        return list(set(validated_tags))
    
    def validate_limit(self, value: int) -> int:
        """Validate limit with security checks."""
        if not isinstance(value, int) or value < 1 or value > 100:
            raise serializers.ValidationError("Limit must be between 1 and 100")
        return value


class DocumentationVersioningSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for DocumentationVersioning model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = DocumentationVersioning
        fields = [
            'id', 'documentation', 'version', 'title', 'content',
            'category', 'tags', 'status', 'created_at',
            'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'id', 'documentation', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def validate_version(self, value: str) -> str:
        """Validate version with security checks."""
        if not value:
            raise serializers.ValidationError("Version is required")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Version contains prohibited content")
        
        # Basic version validation
        version_pattern = r'^\d+\.\d+\.\d+$'
        if not re.match(version_pattern, value):
            raise serializers.ValidationError("Version must follow semantic versioning (e.g., 1.0.0)")
        
        return value
    
    def validate_title(self, value: str) -> str:
        """Validate title with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Title contains prohibited content")
        
        return value.strip()
    
    def validate_content(self, value: str) -> str:
        """Validate content with security checks."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Content is too short")
        
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
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Content contains prohibited code")
        
        return value
    
    def validate_category(self, value: str) -> str:
        """Validate category with security checks."""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Category must be at least 2 characters long")
        
        # Security: Check for prohibited content
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Category contains prohibited content")
        
        return value.strip()
    
    def validate_tags(self, value: List[str]) -> List[str]:
        """Validate tags with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        
        # Validate each tag
        validated_tags = []
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("All tags must be strings")
            
            # Security: Check for prohibited content
            prohibited_patterns = [
                r'<script', r'javascript:', r'on\w+\s*='
            ]
            
            import re
            for pattern in prohibited_patterns:
                if re.search(pattern, tag, re.IGNORECASE):
                    raise serializers.ValidationError(f"Tag contains prohibited content: {tag}")
            
            validated_tags.append(tag.lower())
        
        # Remove duplicates
        return list(set(validated_tags))
    
    def validate_status(self, value: str) -> str:
        """Validate status with security checks."""
        valid_statuses = ['draft', 'review', 'published', 'archived']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value


class DocumentationAnalyticsSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for DocumentationAnalytics model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    class Meta:
        model = DocumentationAnalytics
        fields = [
            'id', 'documentation', 'user', 'view_count', 'search_count',
            'rating', 'date', 'viewed_at'
        ]
        read_only_fields = [
            'id', 'documentation', 'viewed_at'
        ]
    
    def validate_view_count(self, value: int) -> int:
        """Validate view count with security checks."""
        if not isinstance(value, int) or value < 0:
            raise serializers.ValidationError("View count must be a non-negative integer")
        return value
    
    def validate_search_count(self, value: int) -> int:
        """Validate search count with security checks."""
        if not isinstance(value, int) or value < 0:
            raise serializers.ValidationError("Search count must be a non-negative integer")
        return value
    
    def validate_rating(self, value: float) -> float:
        """Validate rating with security checks."""
        if not isinstance(value, (int, float)) or value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5")
        return float(value)
    
    def validate_date(self, value: date) -> date:
        """Validate date with security checks."""
        if not isinstance(value, date):
            raise serializers.ValidationError("Date must be a valid date")
        
        # Check if date is not too far in the future
        if value > timezone.now().date() + timedelta(days=1):
            raise serializers.ValidationError("Date cannot be more than 1 day in the future")
        
        return value


# Request/Response Serializers for Documentation Endpoints

class DocumentationCreateRequestSerializer(serializers.Serializer):
    """Serializer for documentation creation requests."""
    
    title = serializers.CharField(max_length=255, required=True)
    type = serializers.ChoiceField(
        choices=['api', 'user_guide', 'technical', 'policy'],
        required=True
    )
    content = serializers.CharField(required=True)
    category = serializers.CharField(max_length=100, required=True)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    version = serializers.CharField(max_length=20, required=False, default='1.0.0')
    status = serializers.ChoiceField(
        choices=['draft', 'review', 'published', 'archived'],
        required=False,
        default='draft'
    )


class DocumentationUpdateRequestSerializer(serializers.Serializer):
    """Serializer for documentation update requests."""
    
    title = serializers.CharField(max_length=255, required=False)
    content = serializers.CharField(required=False)
    category = serializers.CharField(max_length=100, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    version = serializers.CharField(max_length=20, required=False)
    status = serializers.ChoiceField(
        choices=['draft', 'review', 'published', 'archived'],
        required=False
    )


class DocumentationSearchRequestSerializer(serializers.Serializer):
    """Serializer for documentation search requests."""
    
    query = serializers.CharField(max_length=500, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    type = serializers.ChoiceField(
        choices=['api', 'user_guide', 'technical', 'policy'],
        required=False,
        allow_null=True
    )
    limit = serializers.IntegerField(required=False, default=50, min_value=1, max_value=100)
    sort_by = serializers.ChoiceField(
        choices=['relevance', 'updated_at', 'title', 'created_at'],
        required=False,
        default='relevance'
    )


class DocumentationSearchResponseSerializer(serializers.Serializer):
    """Serializer for documentation search responses."""
    
    documentation_id = serializers.UUIDField()
    title = serializers.CharField()
    content_snippet = serializers.CharField()
    relevance_score = serializers.FloatField()
    doc_type = serializers.CharField()
    category = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    updated_at = serializers.DateTimeField()


class DocumentationStatsResponseSerializer(serializers.Serializer):
    """Serializer for documentation stats responses."""
    
    documentation_id = serializers.UUIDField()
    title = serializers.CharField()
    type = serializers.CharField()
    total_views = serializers.IntegerField()
    total_searches = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    avg_rating = serializers.FloatField()
    recent_views_7d = serializers.IntegerField()
    last_updated = serializers.DateTimeField()


class DocumentationAnalyticsResponseSerializer(serializers.Serializer):
    """Serializer for documentation analytics responses."""
    
    date_range = serializers.DictField()
    popular_documentation = serializers.ListField()
    search_trends = serializers.ListField()
    user_engagement = serializers.DictField()
    type_distribution = serializers.ListField()


class APIOpenAPISpecResponseSerializer(serializers.Serializer):
    """Serializer for OpenAPI specification responses."""
    
    openapi = serializers.CharField()
    info = serializers.DictField()
    servers = serializers.ListField()
    paths = serializers.DictField()
    components = serializers.DictField()


class UserGuideTOCResponseSerializer(serializers.Serializer):
    """Serializer for table of contents responses."""
    
    table_of_contents = serializers.ListField(
        child=serializers.DictField()
    )


class UserGuideReadingTimeResponseSerializer(serializers.Serializer):
    """Serializer for reading time responses."""
    
    reading_time_minutes = serializers.IntegerField()


class TechnicalCodeBlocksResponseSerializer(serializers.Serializer):
    """Serializer for code blocks responses."""
    
    code_blocks = serializers.ListField(
        child=serializers.DictField()
    )


class DocumentationVersionCreateRequestSerializer(serializers.Serializer):
    """Serializer for version creation requests."""
    
    version = serializers.CharField(max_length=20, required=True)
    changelog = serializers.CharField(required=False, allow_blank=True)


class DocumentationVersionRestoreRequestSerializer(serializers.Serializer):
    """Serializer for version restore requests."""
    
    version = serializers.CharField(max_length=20, required=True)


class DocumentationVersionHistoryResponseSerializer(serializers.Serializer):
    """Serializer for version history responses."""
    
    history = serializers.ListField(
        child=serializers.DictField()
    )


class DocumentationEngagementReportResponseSerializer(serializers.Serializer):
    """Serializer for engagement report responses."""
    
    period = serializers.DictField()
    summary = serializers.DictField()
    daily_engagement = serializers.ListField()
    top_documentation = serializers.ListField()
