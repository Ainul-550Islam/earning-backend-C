"""
Analytics Management Serializers

This module contains Django REST Framework serializers for analytics
management data validation and serialization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from rest_framework import serializers
from django.core.exceptions import ValidationError

from ..database_models.analytics_model import AnalyticsReport, AnalyticsDashboard, AnalyticsAlert, AnalyticsMetric, AnalyticsDataPoint, AnalyticsWidget, AnalyticsEvent
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..enums import *
from ..validators import *


class AnalyticsMetricSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsMetric model."""
    
    class Meta:
        model = AnalyticsMetric
        fields = [
            'id', 'name', 'description', 'metric_type', 'unit',
            'formula', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AnalyticsAlertSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsAlert model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AnalyticsAlert
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'alert_type', 'metric', 'threshold_value', 'threshold_operator',
            'threshold_type', 'notification_channels', 'is_active',
            'last_triggered', 'trigger_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'last_triggered',
            'trigger_count', 'created_at', 'updated_at'
        ]


class AnalyticsReportSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsReport model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    class Meta:
        model = AnalyticsReport
        fields = [
            'id', 'advertiser', 'advertiser_name', 'campaign', 'campaign_name',
            'report_name', 'report_type', 'start_date', 'end_date',
            'metrics', 'dimensions', 'filters', 'schedule_frequency',
            'schedule_time', 'recipients', 'delivery_method',
            'output_format', 'template_id', 'is_scheduled', 'status',
            'last_run', 'last_file', 'run_count', 'success_count',
            'failure_count', 'average_run_time', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'campaign', 'campaign_name',
            'last_run', 'last_file', 'run_count', 'success_count',
            'failure_count', 'average_run_time', 'created_at', 'updated_at'
        ]


class AnalyticsReportDetailSerializer(AnalyticsReportSerializer):
    """Detailed serializer for AnalyticsReport model with additional fields."""
    
    report_data = serializers.SerializerMethodField()
    generation_history = serializers.SerializerMethodField()
    next_run = serializers.SerializerMethodField()
    
    class Meta(AnalyticsReportSerializer.Meta):
        fields = AnalyticsReportSerializer.Meta.fields + [
            'report_data', 'generation_history', 'next_run'
        ]
    
    def get_report_data(self, obj):
        """Get report data."""
        try:
            if obj.last_file:
                # This would read actual report data
                return {'status': 'available', 'file_path': obj.last_file}
            return {'status': 'not_generated'}
        except Exception:
            return {'status': 'error'}
    
    def get_generation_history(self, obj):
        """Get generation history."""
        try:
            # This would query actual generation history
            return []
        except Exception:
            return []
    
    def get_next_run(self, obj):
        """Get next scheduled run time."""
        return obj.next_run.isoformat() if obj.next_run else None


class AnalyticsDashboardSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsDashboard model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AnalyticsDashboard
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'layout_type', 'theme', 'refresh_interval', 'widgets',
            'layout_config', 'default_filters', 'available_filters',
            'is_public', 'shared_users', 'sharing_token', 'is_active',
            'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'advertiser', 'advertiser_name', 'sharing_token',
            'created_at', 'updated_at'
        ]


class AnalyticsDashboardDetailSerializer(AnalyticsDashboardSerializer):
    """Detailed serializer for AnalyticsDashboard model with additional fields."""
    
    dashboard_data = serializers.SerializerMethodField()
    widget_count = serializers.SerializerMethodField()
    last_refreshed = serializers.SerializerMethodField()
    
    class Meta(AnalyticsDashboardSerializer.Meta):
        fields = AnalyticsDashboardSerializer.Meta.fields + [
            'dashboard_data', 'widget_count', 'last_refreshed'
        ]
    
    def get_dashboard_data(self, obj):
        """Get dashboard data."""
        try:
            # This would get actual dashboard data
            return {'status': 'ready'}
        except Exception:
            return {'status': 'error'}
    
    def get_widget_count(self, obj):
        """Get number of widgets."""
        return len(obj.widgets) if obj.widgets else 0
    
    def get_last_refreshed(self, obj):
        """Get last refresh time."""
        # This would get actual last refresh time
        return timezone.now().isoformat()


class AnalyticsReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating AnalyticsReport."""
    
    class Meta:
        model = AnalyticsReport
        fields = [
            'advertiser', 'campaign', 'report_name', 'report_type',
            'start_date', 'end_date', 'metrics', 'dimensions',
            'filters', 'schedule_frequency', 'schedule_time',
            'recipients', 'delivery_method', 'output_format',
            'template_id', 'is_scheduled'
        ]
    
    def validate(self, attrs):
        """Validate report data."""
        # Validate date range
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date")
        
        # Validate schedule configuration
        is_scheduled = attrs.get('is_scheduled', False)
        schedule_frequency = attrs.get('schedule_frequency')
        
        if is_scheduled and not schedule_frequency:
            raise serializers.ValidationError("Schedule frequency is required for scheduled reports")
        
        # Validate recipients for email delivery
        delivery_method = attrs.get('delivery_method', 'email')
        recipients = attrs.get('recipients', [])
        
        if delivery_method == 'email' and not recipients:
            raise serializers.ValidationError("Recipients are required for email delivery")
        
        return attrs
    
    def validate_start_date(self, value):
        """Validate start date."""
        if value and value < date.today():
            raise serializers.ValidationError("Start date cannot be in the past")
        return value
    
    def validate_end_date(self, value):
        """Validate end date."""
        if value and value < date.today():
            raise serializers.ValidationError("End date cannot be in the past")
        return value
    
    def validate_schedule_time(self, value):
        """Validate schedule time."""
        if value:
            if not isinstance(value, str):
                raise serializers.ValidationError("Schedule time must be a string")
            # Add more validation for time format if needed
        return value


class AnalyticsDashboardCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating AnalyticsDashboard."""
    
    class Meta:
        model = AnalyticsDashboard
        fields = [
            'advertiser', 'name', 'description', 'layout_type',
            'theme', 'refresh_interval', 'widgets', 'layout_config',
            'default_filters', 'available_filters', 'is_public',
            'shared_users', 'is_active', 'is_default'
        ]
    
    def validate_widgets(self, value):
        """Validate widgets configuration."""
        if not value:
            raise serializers.ValidationError("At least one widget is required")
        
        # Validate each widget
        for widget in value:
            if not isinstance(widget, dict):
                raise serializers.ValidationError("Each widget must be a dictionary")
            
            if 'id' not in widget:
                raise serializers.ValidationError("Each widget must have an id")
            
            if 'type' not in widget:
                raise serializers.ValidationError("Each widget must have a type")
        
        return value
    
    def validate_refresh_interval(self, value):
        """Validate refresh interval."""
        if value and value < 30:
            raise serializers.ValidationError("Refresh interval must be at least 30 seconds")
        return value
    
    def validate_layout_config(self, value):
        """Validate layout configuration."""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Layout config must be a dictionary")
        return value


class AnalyticsDataPointSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsDataPoint model."""
    
    class Meta:
        model = AnalyticsDataPoint
        fields = [
            'id', 'report', 'metric', 'dimension', 'value',
            'date', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CampaignAnalyticsRequestSerializer(serializers.Serializer):
    """Serializer for campaign analytics requests."""
    
    campaign_id = serializers.UUIDField()
    date_range = serializers.DictField(
        child=serializers.CharField(),
        required=False
    )
    metrics = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    dimensions = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_campaign_id(self, value):
        """Validate campaign exists."""
        try:
            Campaign.objects.get(id=value, is_deleted=False)
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Campaign not found")
        return value
    
    def validate_date_range(self, value):
        """Validate date range format."""
        if 'start_date' in value:
            try:
                date.fromisoformat(value['start_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid start_date format")
        
        if 'end_date' in value:
            try:
                date.fromisoformat(value['end_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid end_date format")
        
        return value


class CreativeAnalyticsRequestSerializer(serializers.Serializer):
    """Serializer for creative analytics requests."""
    
    creative_id = serializers.UUIDField()
    date_range = serializers.DictField(
        child=serializers.CharField(),
        required=False
    )
    metrics = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    dimensions = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_creative_id(self, value):
        """Validate creative exists."""
        try:
            Creative.objects.get(id=value, is_deleted=False)
        except Creative.DoesNotExist:
            raise serializers.ValidationError("Creative not found")
        return value
    
    def validate_date_range(self, value):
        """Validate date range format."""
        if 'start_date' in value:
            try:
                date.fromisoformat(value['start_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid start_date format")
        
        if 'end_date' in value:
            try:
                date.fromisoformat(value['end_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid end_date format")
        
        return value


class AdvertiserAnalyticsRequestSerializer(serializers.Serializer):
    """Serializer for advertiser analytics requests."""
    
    advertiser_id = serializers.UUIDField()
    date_range = serializers.DictField(
        child=serializers.CharField(),
        required=False
    )
    metrics = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    dimensions = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_advertiser_id(self, value):
        """Validate advertiser exists."""
        from ..database_models.advertiser_model import Advertiser
        try:
            Advertiser.objects.get(id=value, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise serializers.ValidationError("Advertiser not found")
        return value
    
    def validate_date_range(self, value):
        """Validate date range format."""
        if 'start_date' in value:
            try:
                date.fromisoformat(value['start_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid start_date format")
        
        if 'end_date' in value:
            try:
                date.fromisoformat(value['end_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid end_date format")
        
        return value


class RealTimeMetricsRequestSerializer(serializers.Serializer):
    """Serializer for real-time metrics requests."""
    
    entity_type = serializers.ChoiceField(
        choices=['campaign', 'creative']
    )
    entity_id = serializers.UUIDField()
    
    def validate_entity_id(self, value):
        """Validate entity exists."""
        # This would validate based on entity_type
        return value


class AttributionRequestSerializer(serializers.Serializer):
    """Serializer for attribution calculation requests."""
    
    conversion_id = serializers.UUIDField()
    attribution_model = serializers.ChoiceField(
        choices=['last_click', 'first_click', 'linear', 'time_decay'],
        default='last_click'
    )
    
    def validate_conversion_id(self, value):
        """Validate conversion exists."""
        from ..database_models.conversion_model import Conversion
        try:
            Conversion.objects.get(id=value)
        except Conversion.DoesNotExist:
            raise serializers.ValidationError("Conversion not found")
        return value


class MetricCalculationRequestSerializer(serializers.Serializer):
    """Serializer for metric calculation requests."""
    
    entity_type = serializers.ChoiceField(
        choices=['campaign', 'creative']
    )
    entity_id = serializers.UUIDField()
    metric_name = serializers.ChoiceField(
        choices=['ctr', 'cpc', 'cpa', 'conversion_rate', 'roas']
    )
    date_range = serializers.DictField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_entity_id(self, value):
        """Validate entity exists."""
        # This would validate based on entity_type
        return value
    
    def validate_date_range(self, value):
        """Validate date range format."""
        if 'start_date' in value:
            try:
                date.fromisoformat(value['start_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid start_date format")
        
        if 'end_date' in value:
            try:
                date.fromisoformat(value['end_date'])
            except ValueError:
                raise serializers.ValidationError("Invalid end_date format")
        
        return value


class ReportGenerationRequestSerializer(serializers.Serializer):
    """Serializer for report generation requests."""
    
    report_id = serializers.UUIDField()
    
    def validate_report_id(self, value):
        """Validate report exists."""
        try:
            AnalyticsReport.objects.get(id=value)
        except AnalyticsReport.DoesNotExist:
            raise serializers.ValidationError("Report not found")
        return value


class ReportScheduleRequestSerializer(serializers.Serializer):
    """Serializer for report scheduling requests."""
    
    report_id = serializers.UUIDField()
    frequency = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly']
    )
    time = serializers.TimeField(required=False)
    recipients = serializers.ListField(child=serializers.CharField(), required=False)
    
    def validate_report_id(self, value):
        """Validate report exists."""
        try:
            AnalyticsReport.objects.get(id=value)
        except AnalyticsReport.DoesNotExist:
            raise serializers.ValidationError("Report not found")
        return value


class DashboardShareRequestSerializer(serializers.Serializer):
    """Serializer for dashboard sharing requests."""
    
    dashboard_id = serializers.UUIDField()
    is_public = serializers.BooleanField(default=False)
    shared_users = serializers.ListField(child=serializers.CharField(), required=False)
    
    def validate_dashboard_id(self, value):
        """Validate dashboard exists."""
        try:
            AnalyticsDashboard.objects.get(id=value)
        except AnalyticsDashboard.DoesNotExist:
            raise serializers.ValidationError("Dashboard not found")
        return value


class VisualizationCreateRequestSerializer(serializers.Serializer):
    """Serializer for visualization creation requests."""
    
    name = serializers.CharField()
    type = serializers.ChoiceField(
        choices=['chart', 'graph', 'table', 'map', 'custom']
    )
    data_config = serializers.JSONField()
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_data_config(self, value):
        """Validate data configuration."""
        if not value:
            raise serializers.ValidationError("Data configuration is required")
        return value


class ChartDataRequestSerializer(serializers.Serializer):
    """Serializer for chart data requests."""
    
    data_config = serializers.JSONField()
    
    def validate_data_config(self, value):
        """Validate data configuration."""
        if not value:
            raise serializers.ValidationError("Data configuration is required")
        return value


# Response serializers for API responses

class AnalyticsDataSerializer(serializers.Serializer):
    """Serializer for analytics data response."""
    
    campaign = serializers.DictField(read_only=True)
    creative = serializers.DictField(read_only=True)
    advertiser = serializers.DictField(read_only=True)
    date_range = serializers.DictField(read_only=True)
    metrics = serializers.ListField(read_only=True)
    dimensions = serializers.ListField(read_only=True)
    data = serializers.DictField(read_only=True)


class RealTimeMetricsSerializer(serializers.Serializer):
    """Serializer for real-time metrics response."""
    
    current_impressions = serializers.IntegerField(read_only=True)
    current_clicks = serializers.IntegerField(read_only=True)
    current_conversions = serializers.IntegerField(read_only=True)
    current_cost = serializers.FloatField(read_only=True)
    current_ctr = serializers.FloatField(read_only=True)
    current_cpc = serializers.FloatField(read_only=True)
    current_cpa = serializers.FloatField(read_only=True)
    current_conversion_rate = serializers.FloatField(read_only=True)
    current_roas = serializers.FloatField(read_only=True)
    timestamp = serializers.CharField(read_only=True)


class AttributionDataSerializer(serializers.Serializer):
    """Serializer for attribution data response."""
    
    conversion_id = serializers.CharField(read_only=True)
    conversion_value = serializers.FloatField(read_only=True)
    attribution_model = serializers.CharField(read_only=True)
    attribution_data = serializers.DictField(read_only=True)


class DashboardDataSerializer(serializers.Serializer):
    """Serializer for dashboard data response."""
    
    dashboard = serializers.DictField(read_only=True)
    widgets = serializers.ListField(read_only=True)
    filters = serializers.DictField(read_only=True)
    generated_at = serializers.CharField(read_only=True)


class MetricDefinitionsSerializer(serializers.Serializer):
    """Serializer for metric definitions response."""
    
    # This would contain all metric definitions
    pass


class ChartTypesSerializer(serializers.Serializer):
    """Serializer for chart types response."""
    
    chart_types = serializers.ListField(read_only=True)


class ReportHistorySerializer(serializers.Serializer):
    """Serializer for report history response."""
    
    history = serializers.ListField(read_only=True)


class ActionResponseSerializer(serializers.Serializer):
    """Serializer for action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)
