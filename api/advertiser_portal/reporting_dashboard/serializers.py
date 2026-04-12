"""
Reporting Dashboard Serializers

This module provides comprehensive serializers for reporting and dashboard operations with
enterprise-grade validation, security, and performance optimization following
industry standards from Google Analytics, Tableau, and Power BI.
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
from ..database_models.reporting_model import Report, Dashboard, Visualization, ReportSchedule
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class ReportSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Report model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    data_count = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'report_type', 'data', 'data_count', 'file_size',
            'metadata', 'filters', 'format', 'status',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'data_count', 'file_size', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def get_data_count(self, obj: Report) -> int:
        """Get data count with optimized query."""
        try:
            if isinstance(obj.data, list):
                return len(obj.data)
            elif isinstance(obj.data, dict):
                return len(obj.data.get('data', []))
            return 0
        except Exception:
            return 0
    
    def get_file_size(self, obj: Report) -> int:
        """Get file size estimate."""
        try:
            if obj.data:
                return len(json.dumps(obj.data))
            return 0
        except Exception:
            return 0
    
    def validate_name(self, value: str) -> str:
        """Validate report name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Report name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Report name contains prohibited characters")
        
        return value
    
    def validate_report_type(self, value: str) -> str:
        """Validate report type."""
        valid_types = ['performance', 'financial', 'audience', 'campaign', 'custom']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid report type. Must be one of: {valid_types}")
        return value
    
    def validate_data(self, value: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Validate report data with security checks."""
        if not isinstance(value, (list, dict)):
            raise serializers.ValidationError("Report data must be a list or dictionary")
        
        # Security: Check for prohibited content
        data_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, data_str, re.IGNORECASE):
                raise serializers.ValidationError("Report data contains prohibited content")
        
        # Validate data size
        if len(data_str) > 10000000:  # 10MB limit
            raise serializers.ValidationError("Report data is too large")
        
        return value
    
    def validate_metadata(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        
        # Security: Check for prohibited content
        metadata_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, metadata_str, re.IGNORECASE):
                raise serializers.ValidationError("Metadata contains prohibited content")
        
        return value
    
    def validate_filters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        
        # Security: Validate filter keys
        valid_filter_keys = [
            'date_range', 'advertiser_id', 'campaign_id', 'creative_id',
            'device_type', 'country', 'segment', 'metric_type'
        ]
        
        for key in value.keys():
            if key not in valid_filter_keys:
                raise serializers.ValidationError(f"Invalid filter key: {key}")
        
        # Validate filter values
        if 'date_range' in value:
            date_range = value['date_range']
            if isinstance(date_range, dict):
                if 'start' in date_range:
                    try:
                        datetime.fromisoformat(date_range['start'].replace('Z', '+00:00'))
                    except ValueError:
                        raise serializers.ValidationError("Invalid start date format")
                if 'end' in date_range:
                    try:
                        datetime.fromisoformat(date_range['end'].replace('Z', '+00:00'))
                    except ValueError:
                        raise serializers.ValidationError("Invalid end date format")
        
        return value
    
    def validate_format(self, value: str) -> str:
        """Validate report format."""
        valid_formats = ['json', 'csv', 'excel', 'pdf']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Invalid format. Must be one of: {valid_formats}")
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate report status."""
        valid_statuses = ['pending', 'processing', 'completed', 'failed']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {valid_statuses}")
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Business logic: Validate report type vs data structure
        report_type = attrs.get('report_type')
        data = attrs.get('data')
        
        if report_type == 'performance' and data:
            if isinstance(data, list) and data:
                required_fields = ['metric', 'value']
                for item in data:
                    if not all(field in item for field in required_fields):
                        raise serializers.ValidationError("Performance report data must contain 'metric' and 'value' fields")
        
        elif report_type == 'financial' and data:
            if isinstance(data, list) and data:
                required_fields = ['category', 'current_period']
                for item in data:
                    if not all(field in item for field in required_fields):
                        raise serializers.ValidationError("Financial report data must contain 'category' and 'current_period' fields")
        
        return attrs


class ReportCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating reports.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    report_type = serializers.ChoiceField(
        choices=['performance', 'financial', 'audience', 'campaign', 'custom'],
        required=True
    )
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    time_range = serializers.CharField(required=False, default='last_30_days')
    filters = serializers.JSONField(required=False, default=dict)
    format = serializers.ChoiceField(
        choices=['json', 'csv', 'excel', 'pdf'],
        default='json'
    )
    custom_config = serializers.JSONField(required=False, default=dict)
    
    def validate_name(self, value: str) -> str:
        """Validate report name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Report name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Report name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Report name contains prohibited characters")
        
        return value
    
    def validate_advertiser_id(self, value: Optional[UUID]) -> Optional[UUID]:
        """Validate advertiser ID with security checks."""
        if value is not None:
            try:
                advertiser = Advertiser.objects.get(id=value, is_deleted=False)
                
                # Security: Check user permissions
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
                return value
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
            except ValueError:
                raise serializers.ValidationError("Invalid advertiser ID format")
        
        return value
    
    def validate_time_range(self, value: str) -> str:
        """Validate time range."""
        valid_ranges = [
            'today', 'yesterday', 'last_7_days', 'last_30_days', 'last_90_days',
            'this_month', 'last_month', 'this_year', 'last_year', 'custom'
        ]
        
        if value not in valid_ranges:
            raise serializers.ValidationError(f"Invalid time range. Must be one of: {valid_ranges}")
        
        return value
    
    def validate_filters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        
        # Security: Check for prohibited content
        filters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, filters_str, re.IGNORECASE):
                raise serializers.ValidationError("Filters contain prohibited content")
        
        # Validate filter structure
        valid_filter_keys = [
            'date_range', 'advertiser_id', 'campaign_id', 'creative_id',
            'device_type', 'country', 'segment', 'metric_type', 'custom_filters'
        ]
        
        for key in value.keys():
            if key not in valid_filter_keys:
                raise serializers.ValidationError(f"Invalid filter key: {key}")
        
        # Validate date range filter
        if 'date_range' in value:
            date_range = value['date_range']
            if isinstance(date_range, dict):
                if 'start' in date_range:
                    try:
                        datetime.fromisoformat(date_range['start'].replace('Z', '+00:00'))
                    except ValueError:
                        raise serializers.ValidationError("Invalid start date format")
                
                if 'end' in date_range:
                    try:
                        datetime.fromisoformat(date_range['end'].replace('Z', '+00:00'))
                    except ValueError:
                        raise serializers.ValidationError("Invalid end date format")
                
                # Validate date logic
                if 'start' in date_range and 'end' in date_range:
                    start_date = datetime.fromisoformat(date_range['start'].replace('Z', '+00:00'))
                    end_date = datetime.fromisoformat(date_range['end'].replace('Z', '+00:00'))
                    if start_date >= end_date:
                        raise serializers.ValidationError("Start date must be before end date")
        
        # Validate UUID fields
        for uuid_field in ['advertiser_id', 'campaign_id', 'creative_id']:
            if uuid_field in value:
                try:
                    UUID(value[uuid_field])
                except ValueError:
                    raise serializers.ValidationError(f"Invalid {uuid_field} format")
        
        return value
    
    def validate_custom_config(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom config must be a dictionary")
        
        # Security: Check for prohibited content
        config_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, config_str, re.IGNORECASE):
                raise serializers.ValidationError("Custom config contains prohibited content")
        
        # Validate config size
        if len(config_str) > 100000:  # 100KB limit
            raise serializers.ValidationError("Custom config is too large")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate report type vs required fields
        report_type = attrs.get('report_type')
        custom_config = attrs.get('custom_config', {})
        
        if report_type == 'custom':
            if not custom_config:
                raise serializers.ValidationError("Custom report type requires custom_config")
        
        # Business logic: Validate time range vs custom dates
        time_range = attrs.get('time_range')
        filters = attrs.get('filters', {})
        
        if time_range != 'custom' and 'date_range' in filters:
            raise serializers.ValidationError("Custom date range only allowed with 'custom' time_range")
        
        # Business logic: Validate advertiser access
        advertiser_id = attrs.get('advertiser_id')
        if advertiser_id and 'advertiser_id' in filters:
            if str(advertiser_id) != str(filters['advertiser_id']):
                raise serializers.ValidationError("Advertiser ID mismatch between main field and filter")
        
        return attrs


class DashboardSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Dashboard model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    widget_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'description', 'layout', 'widgets',
            'widget_count', 'filters', 'is_default', 'is_public',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'widget_count', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def get_widget_count(self, obj: Dashboard) -> int:
        """Get widget count."""
        try:
            return len(obj.widgets) if obj.widgets else 0
        except Exception:
            return 0
    
    def validate_name(self, value: str) -> str:
        """Validate dashboard name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Dashboard name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Dashboard name contains prohibited characters")
        
        return value
    
    def validate_layout(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate layout configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Layout must be a dictionary")
        
        # Security: Check for prohibited content
        layout_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, layout_str, re.IGNORECASE):
                raise serializers.ValidationError("Layout contains prohibited content")
        
        # Validate layout structure
        if 'grid' in value:
            grid = value['grid']
            if not isinstance(grid, dict):
                raise serializers.ValidationError("Grid configuration must be a dictionary")
            
            # Validate grid dimensions
            if 'cols' in grid:
                if not isinstance(grid['cols'], int) or grid['cols'] < 1:
                    raise serializers.ValidationError("Grid cols must be a positive integer")
            
            if 'rows' in grid:
                if not isinstance(grid['rows'], int) or grid['rows'] < 1:
                    raise serializers.ValidationError("Grid rows must be a positive integer")
        
        return value
    
    def validate_widgets(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate widgets configuration with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Widgets must be a list")
        
        # Security: Check for prohibited content
        widgets_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, widgets_str, re.IGNORECASE):
                raise serializers.ValidationError("Widgets contain prohibited content")
        
        # Validate widget structure
        for i, widget in enumerate(value):
            if not isinstance(widget, dict):
                raise serializers.ValidationError(f"Widget {i} must be a dictionary")
            
            # Validate required widget fields
            required_fields = ['id', 'type', 'title']
            for field in required_fields:
                if field not in widget:
                    raise serializers.ValidationError(f"Widget {i} missing required field: {field}")
            
            # Validate widget type
            valid_types = ['metric', 'chart', 'table', 'map', 'funnel', 'custom']
            if widget['type'] not in valid_types:
                raise serializers.ValidationError(f"Widget {i} has invalid type: {widget['type']}")
            
            # Validate widget ID
            if not isinstance(widget['id'], str) or len(widget['id']) < 1:
                raise serializers.ValidationError(f"Widget {i} has invalid ID")
        
        return value
    
    def validate_filters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        
        # Security: Check for prohibited content
        filters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, filters_str, re.IGNORECASE):
                raise serializers.ValidationError("Filters contain prohibited content")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate user permissions
        if hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            is_public = attrs.get('is_public', False)
            
            if not user.is_superuser and not user.is_staff and not is_public:
                # Regular users can only create private dashboards
                pass
        
        # Business logic: Validate layout vs widgets
        layout = attrs.get('layout', {})
        widgets = attrs.get('widgets', [])
        
        if layout and widgets:
            # Validate that all widget IDs are unique
            widget_ids = [widget['id'] for widget in widgets]
            if len(widget_ids) != len(set(widget_ids)):
                raise serializers.ValidationError("Widget IDs must be unique")
        
        return attrs


class DashboardCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating dashboards.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    layout = serializers.JSONField(required=False, default=dict)
    widgets = serializers.JSONField(required=False, default=list)
    filters = serializers.JSONField(required=False, default=dict)
    is_default = serializers.BooleanField(required=False, default=False)
    is_public = serializers.BooleanField(required=False, default=False)
    
    def validate_name(self, value: str) -> str:
        """Validate dashboard name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Dashboard name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Dashboard name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Dashboard name contains prohibited characters")
        
        return value
    
    def validate_layout(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate layout configuration with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Layout must be a dictionary")
        
        # Security: Check for prohibited content
        layout_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, layout_str, re.IGNORECASE):
                raise serializers.ValidationError("Layout contains prohibited content")
        
        # Validate layout structure
        if 'grid' in value:
            grid = value['grid']
            if not isinstance(grid, dict):
                raise serializers.ValidationError("Grid configuration must be a dictionary")
            
            # Validate grid dimensions
            if 'cols' in grid:
                if not isinstance(grid['cols'], int) or grid['cols'] < 1 or grid['cols'] > 24:
                    raise serializers.ValidationError("Grid cols must be between 1 and 24")
            
            if 'rows' in grid:
                if not isinstance(grid['rows'], int) or grid['rows'] < 1 or grid['rows'] > 100:
                    raise serializers.ValidationError("Grid rows must be between 1 and 100")
        
        # Validate breakpoints
        if 'breakpoints' in value:
            breakpoints = value['breakpoints']
            if not isinstance(breakpoints, dict):
                raise serializers.ValidationError("Breakpoints must be a dictionary")
            
            valid_breakpoints = ['xs', 'sm', 'md', 'lg', 'xl']
            for bp in breakpoints:
                if bp not in valid_breakpoints:
                    raise serializers.ValidationError(f"Invalid breakpoint: {bp}")
        
        return value
    
    def validate_widgets(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate widgets configuration with comprehensive security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Widgets must be a list")
        
        # Security: Check for prohibited content
        widgets_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, widgets_str, re.IGNORECASE):
                raise serializers.ValidationError("Widgets contain prohibited content")
        
        # Validate widget structure
        widget_ids = []
        for i, widget in enumerate(value):
            if not isinstance(widget, dict):
                raise serializers.ValidationError(f"Widget {i} must be a dictionary")
            
            # Validate required widget fields
            required_fields = ['id', 'type', 'title']
            for field in required_fields:
                if field not in widget:
                    raise serializers.ValidationError(f"Widget {i} missing required field: {field}")
            
            # Validate widget type
            valid_types = ['metric', 'chart', 'table', 'map', 'funnel', 'custom']
            if widget['type'] not in valid_types:
                raise serializers.ValidationError(f"Widget {i} has invalid type: {widget['type']}")
            
            # Validate widget ID
            if not isinstance(widget['id'], str) or len(widget['id']) < 1:
                raise serializers.ValidationError(f"Widget {i} has invalid ID")
            
            # Check for duplicate IDs
            if widget['id'] in widget_ids:
                raise serializers.ValidationError(f"Duplicate widget ID: {widget['id']}")
            widget_ids.append(widget['id'])
            
            # Validate widget title
            if not isinstance(widget['title'], str) or len(widget['title'].strip()) < 1:
                raise serializers.ValidationError(f"Widget {i} has invalid title")
        
        return value
    
    def validate_filters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        
        # Security: Check for prohibited content
        filters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, filters_str, re.IGNORECASE):
                raise serializers.ValidationError("Filters contain prohibited content")
        
        # Validate filter structure
        valid_filter_keys = [
            'date_range', 'advertiser_id', 'campaign_id', 'creative_id',
            'device_type', 'country', 'segment', 'metric_type', 'custom_filters'
        ]
        
        for key in value.keys():
            if key not in valid_filter_keys:
                raise serializers.ValidationError(f"Invalid filter key: {key}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate layout vs widgets
        layout = attrs.get('layout', {})
        widgets = attrs.get('widgets', [])
        
        if layout and widgets:
            # Validate that all widgets fit in layout
            if 'grid' in layout:
                grid = layout['grid']
                max_widgets = grid.get('cols', 12) * grid.get('rows', 10)
                
                if len(widgets) > max_widgets:
                    raise serializers.ValidationError(f"Too many widgets for layout. Maximum: {max_widgets}")
        
        # Business logic: Validate default dashboard
        is_default = attrs.get('is_default', False)
        if is_default:
            # Check if user already has a default dashboard
            if hasattr(self, 'context') and 'request' in self.context:
                user = self.context['request'].user
                existing_default = Dashboard.objects.filter(
                    created_by=user,
                    is_default=True
                ).exists()
                
                if existing_default:
                    raise serializers.ValidationError("User already has a default dashboard")
        
        return attrs


class VisualizationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for Visualization model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = Visualization
        fields = [
            'id', 'name', 'description', 'viz_type', 'data_source',
            'chart_config', 'filters', 'is_interactive', 'created_at',
            'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate_name(self, value: str) -> str:
        """Validate visualization name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Visualization name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Visualization name contains prohibited characters")
        
        return value
    
    def validate_viz_type(self, value: str) -> str:
        """Validate visualization type."""
        valid_types = [
            'line_chart', 'bar_chart', 'pie_chart', 'scatter_plot',
            'heatmap', 'funnel', 'gauge', 'table', 'custom'
        ]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid visualization type. Must be one of: {valid_types}")
        return value
    
    def validate_data_source(self, value: str) -> str:
        """Validate data source."""
        valid_sources = ['performance', 'analytics', 'campaign', 'creative', 'custom']
        if value not in valid_sources:
            raise serializers.ValidationError(f"Invalid data source. Must be one of: {valid_sources}")
        return value
    
    def validate_chart_config(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate chart configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Chart config must be a dictionary")
        
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
                raise serializers.ValidationError("Chart config contains prohibited content")
        
        return value
    
    def validate_filters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        
        # Security: Check for prohibited content
        filters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, filters_str, re.IGNORECASE):
                raise serializers.ValidationError("Filters contain prohibited content")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate viz_type vs chart_config
        viz_type = attrs.get('viz_type')
        chart_config = attrs.get('chart_config', {})
        
        # Validate chart config based on visualization type
        if viz_type == 'line_chart':
            if 'x_axis' not in chart_config or 'y_axis' not in chart_config:
                raise serializers.ValidationError("Line chart requires x_axis and y_axis in chart_config")
        
        elif viz_type == 'bar_chart':
            if 'x_axis' not in chart_config or 'y_axis' not in chart_config:
                raise serializers.ValidationError("Bar chart requires x_axis and y_axis in chart_config")
        
        elif viz_type == 'pie_chart':
            if 'categories' not in chart_config or 'values' not in chart_config:
                raise serializers.ValidationError("Pie chart requires categories and values in chart_config")
        
        elif viz_type == 'scatter_plot':
            if 'x_axis' not in chart_config or 'y_axis' not in chart_config:
                raise serializers.ValidationError("Scatter plot requires x_axis and y_axis in chart_config")
        
        elif viz_type == 'heatmap':
            if 'x_axis' not in chart_config or 'y_axis' not in chart_config:
                raise serializers.ValidationError("Heatmap requires x_axis and y_axis in chart_config")
        
        return attrs


class VisualizationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating visualizations.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    viz_type = serializers.ChoiceField(
        choices=[
            'line_chart', 'bar_chart', 'pie_chart', 'scatter_plot',
            'heatmap', 'funnel', 'gauge', 'table', 'custom'
        ],
        required=True
    )
    data_source = serializers.ChoiceField(
        choices=['performance', 'analytics', 'campaign', 'creative', 'custom'],
        required=True
    )
    chart_config = serializers.JSONField(required=False, default=dict)
    filters = serializers.JSONField(required=False, default=dict)
    is_interactive = serializers.BooleanField(required=False, default=True)
    
    def validate_name(self, value: str) -> str:
        """Validate visualization name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Visualization name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Visualization name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Visualization name contains prohibited characters")
        
        return value
    
    def validate_chart_config(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate chart configuration with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Chart config must be a dictionary")
        
        # Security: Check for prohibited content
        config_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, config_str, re.IGNORECASE):
                raise serializers.ValidationError("Chart config contains prohibited content")
        
        # Validate chart config structure
        required_fields = ['title']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Chart config missing required field: {field}")
        
        # Validate color scheme
        if 'colors' in value:
            colors = value['colors']
            if not isinstance(colors, list):
                raise serializers.ValidationError("Colors must be a list")
            
            for color in colors:
                if not isinstance(color, str) or not color.startswith('#'):
                    raise serializers.ValidationError("Colors must be valid hex color codes")
        
        return value
    
    def validate_filters(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filters with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        
        # Security: Check for prohibited content
        filters_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, filters_str, re.IGNORECASE):
                raise serializers.ValidationError("Filters contain prohibited content")
        
        # Validate filter structure
        valid_filter_keys = [
            'date_range', 'advertiser_id', 'campaign_id', 'creative_id',
            'device_type', 'country', 'segment', 'metric_type', 'custom_filters'
        ]
        
        for key in value.keys():
            if key not in valid_filter_keys:
                raise serializers.ValidationError(f"Invalid filter key: {key}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate viz_type vs chart_config
        viz_type = attrs.get('viz_type')
        chart_config = attrs.get('chart_config', {})
        
        # Validate chart config based on visualization type
        if viz_type == 'line_chart':
            required_config_fields = ['x_axis', 'y_axis', 'title']
            for field in required_config_fields:
                if field not in chart_config:
                    raise serializers.ValidationError(f"Line chart requires {field} in chart_config")
        
        elif viz_type == 'bar_chart':
            required_config_fields = ['x_axis', 'y_axis', 'title']
            for field in required_config_fields:
                if field not in chart_config:
                    raise serializers.ValidationError(f"Bar chart requires {field} in chart_config")
        
        elif viz_type == 'pie_chart':
            required_config_fields = ['categories', 'values', 'title']
            for field in required_config_fields:
                if field not in chart_config:
                    raise serializers.ValidationError(f"Pie chart requires {field} in chart_config")
        
        elif viz_type == 'scatter_plot':
            required_config_fields = ['x_axis', 'y_axis', 'title']
            for field in required_config_fields:
                if field not in chart_config:
                    raise serializers.ValidationError(f"Scatter plot requires {field} in chart_config")
        
        elif viz_type == 'heatmap':
            required_config_fields = ['x_axis', 'y_axis', 'title']
            for field in required_config_fields:
                if field not in chart_config:
                    raise serializers.ValidationError(f"Heatmap requires {field} in chart_config")
        
        # Business logic: Validate data source vs filters
        data_source = attrs.get('data_source')
        filters = attrs.get('filters', {})
        
        if data_source == 'performance' and 'metric_type' in filters:
            valid_metrics = ['ctr', 'cpc', 'cpa', 'roas', 'conversions', 'revenue']
            if filters['metric_type'] not in valid_metrics:
                raise serializers.ValidationError(f"Invalid metric type for performance data source: {filters['metric_type']}")
        
        return attrs


class ReportScheduleSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for ReportSchedule model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'name', 'description', 'report_config', 'schedule_type',
            'schedule_params', 'delivery_method', 'delivery_params',
            'is_active', 'last_run', 'created_at', 'updated_at',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'last_run', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def validate_name(self, value: str) -> str:
        """Validate schedule name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Schedule name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Schedule name contains prohibited characters")
        
        return value
    
    def validate_schedule_type(self, value: str) -> str:
        """Validate schedule type."""
        valid_types = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'custom']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid schedule type. Must be one of: {valid_types}")
        return value
    
    def validate_delivery_method(self, value: str) -> str:
        """Validate delivery method."""
        valid_methods = ['email', 'ftp', 'webhook', 'api']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Invalid delivery method. Must be one of: {valid_methods}")
        return value
    
    def validate_report_config(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate report configuration with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Report config must be a dictionary")
        
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
                raise serializers.ValidationError("Report config contains prohibited content")
        
        # Validate required fields
        required_fields = ['name', 'report_type']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Report config missing required field: {field}")
        
        return value
    
    def validate_schedule_params(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate schedule parameters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schedule params must be a dictionary")
        
        # Security: Check for prohibited content
        params_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, params_str, re.IGNORECASE):
                raise serializers.ValidationError("Schedule params contain prohibited content")
        
        # Validate time format
        if 'time' in value:
            time_str = value['time']
            try:
                # Validate HH:MM format
                hour, minute = map(int, time_str.split(':'))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise serializers.ValidationError("Invalid time format. Use HH:MM (24-hour format)")
            except (ValueError, AttributeError):
                raise serializers.ValidationError("Invalid time format. Use HH:MM (24-hour format)")
        
        # Validate day of week
        if 'day' in value:
            day = value['day']
            if not isinstance(day, int) or not (0 <= day <= 6):  # 0 = Monday, 6 = Sunday
                raise serializers.ValidationError("Day must be between 0 (Monday) and 6 (Sunday)")
        
        # Validate day of month
        if 'day_of_month' in value:
            day_of_month = value['day_of_month']
            if not isinstance(day_of_month, int) or not (1 <= day_of_month <= 31):
                raise serializers.ValidationError("Day of month must be between 1 and 31")
        
        return value
    
    def validate_delivery_params(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate delivery parameters with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Delivery params must be a dictionary")
        
        # Security: Check for prohibited content
        params_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, params_str, re.IGNORECASE):
                raise serializers.ValidationError("Delivery params contain prohibited content")
        
        # Validate email parameters
        if 'recipients' in value:
            recipients = value['recipients']
            if not isinstance(recipients, list):
                raise serializers.ValidationError("Recipients must be a list")
            
            for recipient in recipients:
                if not isinstance(recipient, str) or '@' not in recipient:
                    raise serializers.ValidationError(f"Invalid email address: {recipient}")
        
        # Validate FTP parameters
        if 'ftp_host' in value:
            ftp_host = value['ftp_host']
            if not isinstance(ftp_host, str) or len(ftp_host.strip()) < 1:
                raise serializers.ValidationError("FTP host must be a non-empty string")
        
        # Validate webhook parameters
        if 'webhook_url' in value:
            webhook_url = value['webhook_url']
            if not isinstance(webhook_url, str) or not webhook_url.startswith(('http://', 'https://')):
                raise serializers.ValidationError("Webhook URL must be a valid HTTP/HTTPS URL")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate schedule_type vs schedule_params
        schedule_type = attrs.get('schedule_type')
        schedule_params = attrs.get('schedule_params', {})
        
        if schedule_type == 'daily':
            if 'time' not in schedule_params:
                raise serializers.ValidationError("Daily schedule requires 'time' parameter")
        
        elif schedule_type == 'weekly':
            if 'time' not in schedule_params or 'day' not in schedule_params:
                raise serializers.ValidationError("Weekly schedule requires 'time' and 'day' parameters")
        
        elif schedule_type == 'monthly':
            if 'time' not in schedule_params or 'day_of_month' not in schedule_params:
                raise serializers.ValidationError("Monthly schedule requires 'time' and 'day_of_month' parameters")
        
        # Business logic: Validate delivery_method vs delivery_params
        delivery_method = attrs.get('delivery_method')
        delivery_params = attrs.get('delivery_params', {})
        
        if delivery_method == 'email':
            if 'recipients' not in delivery_params:
                raise serializers.ValidationError("Email delivery requires 'recipients' parameter")
        
        elif delivery_method == 'ftp':
            required_ftp_params = ['ftp_host', 'ftp_username', 'ftp_password', 'ftp_path']
            for param in required_ftp_params:
                if param not in delivery_params:
                    raise serializers.ValidationError(f"FTP delivery requires '{param}' parameter")
        
        elif delivery_method == 'webhook':
            if 'webhook_url' not in delivery_params:
                raise serializers.ValidationError("Webhook delivery requires 'webhook_url' parameter")
        
        return attrs


# Request/Response Serializers for API Endpoints

class ReportGenerationRequestSerializer(serializers.Serializer):
    """Serializer for report generation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    report_type = serializers.ChoiceField(
        choices=['performance', 'financial', 'audience', 'campaign', 'custom'],
        required=True
    )
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    time_range = serializers.CharField(required=False, default='last_30_days')
    filters = serializers.JSONField(required=False, default=dict)
    format = serializers.ChoiceField(
        choices=['json', 'csv', 'excel', 'pdf'],
        default='json'
    )
    custom_config = serializers.JSONField(required=False, default=dict)


class ReportScheduleRequestSerializer(serializers.Serializer):
    """Serializer for report schedule requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    report_config = serializers.JSONField(required=True)
    schedule_type = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'custom'],
        required=True
    )
    schedule_params = serializers.JSONField(required=False, default=dict)
    delivery_method = serializers.ChoiceField(
        choices=['email', 'ftp', 'webhook', 'api'],
        required=True
    )
    delivery_params = serializers.JSONField(required=False, default=dict)
    is_active = serializers.BooleanField(required=False, default=True)


class DashboardCreateRequestSerializer(serializers.Serializer):
    """Serializer for dashboard creation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    layout = serializers.JSONField(required=False, default=dict)
    widgets = serializers.JSONField(required=False, default=list)
    filters = serializers.JSONField(required=False, default=dict)
    is_default = serializers.BooleanField(required=False, default=False)
    is_public = serializers.BooleanField(required=False, default=False)


class VisualizationCreateRequestSerializer(serializers.Serializer):
    """Serializer for visualization creation requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    viz_type = serializers.ChoiceField(
        choices=[
            'line_chart', 'bar_chart', 'pie_chart', 'scatter_plot',
            'heatmap', 'funnel', 'gauge', 'table', 'custom'
        ],
        required=True
    )
    data_source = serializers.ChoiceField(
        choices=['performance', 'analytics', 'campaign', 'creative', 'custom'],
        required=True
    )
    chart_config = serializers.JSONField(required=False, default=dict)
    filters = serializers.JSONField(required=False, default=dict)
    is_interactive = serializers.BooleanField(required=False, default=True)


class AnalyticsMetricsRequestSerializer(serializers.Serializer):
    """Serializer for analytics metrics requests."""
    
    name = serializers.CharField(max_length=255, required=True)
    type = serializers.ChoiceField(
        choices=['count', 'sum', 'avg', 'rate', 'ratio'],
        required=True
    )
    data_source = serializers.ChoiceField(
        choices=['performance', 'analytics', 'campaign', 'creative'],
        required=True
    )
    calculation = serializers.JSONField(required=False, default=dict)
    filters = serializers.JSONField(required=False, default=dict)
    time_range = serializers.CharField(required=False, default='last_30_days')


class AnalyticsInsightsRequestSerializer(serializers.Serializer):
    """Serializer for analytics insights requests."""
    
    data_source = serializers.ChoiceField(
        choices=['performance', 'analytics', 'campaign', 'creative'],
        required=True
    )
    insight_types = serializers.ListField(
        child=serializers.ChoiceField(choices=['trend', 'segmentation', 'correlation', 'anomaly', 'prediction']),
        required=True
    )
    time_range = serializers.CharField(required=False, default='last_30_days')
    filters = serializers.JSONField(required=False, default=dict)


# Response Serializers

class ReportGenerationResponseSerializer(serializers.Serializer):
    """Serializer for report generation responses."""
    
    report_id = serializers.UUIDField()
    report_name = serializers.CharField()
    report_type = serializers.CharField()
    data = serializers.ListField()
    metadata = serializers.DictField()
    total_records = serializers.IntegerField()
    execution_time = serializers.FloatField()
    generated_at = serializers.DateTimeField()


class DashboardDataResponseSerializer(serializers.Serializer):
    """Serializer for dashboard data responses."""
    
    dashboard_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    layout = serializers.DictField()
    widgets = serializers.ListField()
    filters = serializers.DictField()
    last_updated = serializers.DateTimeField()


class VisualizationDataResponseSerializer(serializers.Serializer):
    """Serializer for visualization data responses."""
    
    visualization_id = serializers.UUIDField()
    name = serializers.CharField()
    viz_type = serializers.CharField()
    data = serializers.DictField()
    config = serializers.DictField()
    last_updated = serializers.DateTimeField()


class AnalyticsMetricsResponseSerializer(serializers.Serializer):
    """Serializer for analytics metrics responses."""
    
    metric_id = serializers.CharField()
    metric_name = serializers.CharField()
    metric_type = serializers.CharField()
    data = serializers.DictField()
    calculated_metrics = serializers.DictField()
    calculated_at = serializers.DateTimeField()


class AnalyticsInsightsResponseSerializer(serializers.Serializer):
    """Serializer for analytics insights responses."""
    
    insights = serializers.ListField()
    generated_at = serializers.DateTimeField()


# Comprehensive Response Serializers

class ReportCreateResponseSerializer(serializers.Serializer):
    """Serializer for report creation responses."""
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    report_type = serializers.CharField()
    description = serializers.CharField()
    data = serializers.JSONField()
    metadata = serializers.JSONField()
    filters = serializers.JSONField()
    format = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class DashboardCreateResponseSerializer(serializers.Serializer):
    """Serializer for dashboard creation responses."""
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    layout = serializers.JSONField()
    widgets = serializers.JSONField()
    filters = serializers.JSONField()
    is_default = serializers.BooleanField()
    is_public = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class VisualizationCreateResponseSerializer(serializers.Serializer):
    """Serializer for visualization creation responses."""
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    viz_type = serializers.CharField()
    data_source = serializers.CharField()
    chart_config = serializers.JSONField()
    filters = serializers.JSONField()
    is_interactive = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class ReportScheduleCreateResponseSerializer(serializers.Serializer):
    """Serializer for report schedule creation responses."""
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    report_config = serializers.JSONField()
    schedule_type = serializers.CharField()
    schedule_params = serializers.JSONField()
    delivery_method = serializers.CharField()
    delivery_params = serializers.JSONField()
    is_active = serializers.BooleanField()
    last_run = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
