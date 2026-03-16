from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
import uuid
from .models import (
    AnalyticsEvent, UserAnalytics, RevenueAnalytics, 
    OfferPerformanceAnalytics, FunnelAnalytics, RetentionAnalytics,
    Dashboard, Report, RealTimeMetric, AlertRule, AlertHistory
)

class AnalyticsEventSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    formatted_time = serializers.DateTimeField(source='event_time', format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    class Meta:
        model = AnalyticsEvent
        fields = [
            'id', 'event_type', 'user', 'user_email', 'user_username',
            'session_id', 'ip_address', 'device_type', 'browser', 'os',
            'country', 'city', 'referrer', 'metadata', 'duration', 'value',
            'event_time', 'formatted_time', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_event_time(self, value):
        """Ensure event_time is not in the future"""
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("Event time cannot be in the future")
        return value

class UserAnalyticsSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    engagement_score = serializers.FloatField(read_only=True)
    lifetime_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    period_start_date = serializers.DateTimeField(source='period_start', format="%Y-%m-%d", read_only=True)
    period_end_date = serializers.DateTimeField(source='period_end', format="%Y-%m-%d", read_only=True)
    
    class Meta:
        model = UserAnalytics
        fields = [
            'id', 'user', 'user_email', 'user_username', 'period', 'period_display',
            'period_start', 'period_start_date', 'period_end', 'period_end_date',
            
            # Activity metrics
            'login_count', 'active_days', 'session_duration_avg', 'page_views',
            
            # Task metrics
            'tasks_completed', 'tasks_attempted', 'task_success_rate',
            
            # Offer metrics
            'offers_viewed', 'offers_completed', 'offer_conversion_rate',
            
            # Earning metrics
            'earnings_total', 'earnings_from_tasks', 'earnings_from_offers',
            'earnings_from_referrals',
            
            # Referral metrics
            'referrals_sent', 'referrals_joined', 'referrals_active',
            'referral_conversion_rate',
            
            # Withdrawal metrics
            'withdrawals_requested', 'withdrawals_completed', 'withdrawals_amount',
            
            # Device metrics
            'device_mobile_count', 'device_desktop_count', 'device_tablet_count',
            
            # Additional metrics
            'notifications_received', 'notifications_opened', 'support_tickets',
            'app_rating', 'is_retained', 'churn_risk_score',
            
            # Calculated fields
            'engagement_score', 'lifetime_value', 'calculated_at', 'metadata'
        ]
        read_only_fields = ['id', 'calculated_at']

class RevenueAnalyticsSerializer(serializers.ModelSerializer):
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    period_start_date = serializers.DateTimeField(source='period_start', format="%Y-%m-%d", read_only=True)
    period_end_date = serializers.DateTimeField(source='period_end', format="%Y-%m-%d", read_only=True)
    
    # Formatted monetary fields
    revenue_total_formatted = serializers.SerializerMethodField()
    gross_profit_formatted = serializers.SerializerMethodField()
    net_profit_formatted = serializers.SerializerMethodField()
    arpu_formatted = serializers.SerializerMethodField()
    arppu_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = RevenueAnalytics
        fields = [
            'id', 'period', 'period_display', 'period_start', 'period_start_date',
            'period_end', 'period_end_date',
            
            # Revenue metrics
            'revenue_total', 'revenue_total_formatted', 'revenue_by_source',
            
            # Cost metrics
            'cost_total', 'cost_breakdown',
            
            # Profit metrics
            'gross_profit', 'gross_profit_formatted', 'net_profit', 
            'net_profit_formatted', 'profit_margin',
            
            # User metrics
            'active_users', 'paying_users', 'conversion_rate',
            
            # ARPU/ARPPU
            'arpu', 'arpu_formatted', 'arppu', 'arppu_formatted',
            
            # Withdrawal metrics
            'total_withdrawals', 'withdrawal_requests',
            
            # Platform metrics
            'platform_fee_earned', 'tax_deducted',
            
            # Calculated fields
            'calculated_at', 'metadata'
        ]
        read_only_fields = ['id', 'calculated_at']
    
    def get_revenue_total_formatted(self, obj):
        return f"${obj.revenue_total:,.2f}"
    
    def get_gross_profit_formatted(self, obj):
        return f"${obj.gross_profit:,.2f}"
    
    def get_net_profit_formatted(self, obj):
        return f"${obj.net_profit:,.2f}"
    
    def get_arpu_formatted(self, obj):
        return f"${obj.arpu:,.2f}"
    
    def get_arppu_formatted(self, obj):
        return f"${obj.arppu:,.2f}"

class OfferPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    period_start_date = serializers.DateTimeField(source='period_start', format="%Y-%m-%d", read_only=True)
    period_end_date = serializers.DateTimeField(source='period_end', format="%Y-%m-%d", read_only=True)
    
    # Calculated rates
    click_through_rate = serializers.FloatField(read_only=True)
    engagement_rate = serializers.FloatField(read_only=True)
    
    # Formatted fields
    revenue_generated_formatted = serializers.SerializerMethodField()
    cost_per_completion_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferPerformanceAnalytics
        fields = [
            'id', 'offer', 'offer_name', 'period', 'period_display',
            'period_start', 'period_start_date', 'period_end', 'period_end_date',
            
            # View metrics
            'impressions', 'unique_views', 'clicks',
            
            # Completion metrics
            'completions', 'completion_rate',
            
            # Calculated rates
            'click_through_rate', 'engagement_rate',
            
            # Revenue metrics
            'revenue_generated', 'revenue_generated_formatted',
            'cost_per_completion', 'cost_per_completion_formatted', 'roi',
            
            # User metrics
            'unique_users_completed', 'avg_completion_time',
            
            # Breakdowns
            'device_breakdown', 'country_breakdown', 'peak_hours',
            
            # Calculated fields
            'calculated_at', 'metadata'
        ]
        read_only_fields = ['id', 'calculated_at']
    
    def get_revenue_generated_formatted(self, obj):
        return f"${obj.revenue_generated:,.2f}"
    
    def get_cost_per_completion_formatted(self, obj):
        return f"${obj.cost_per_completion:,.2f}"

class FunnelAnalyticsSerializer(serializers.ModelSerializer):
    funnel_type_display = serializers.CharField(source='get_funnel_type_display', read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    period_start_date = serializers.DateTimeField(source='period_start', format="%Y-%m-%d", read_only=True)
    period_end_date = serializers.DateTimeField(source='period_end', format="%Y-%m-%d", read_only=True)
    
    # Stage breakdown
    stages_list = serializers.SerializerMethodField()
    drop_off_analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = FunnelAnalytics
        fields = [
            'id', 'funnel_type', 'funnel_type_display', 'period', 'period_display',
            'period_start', 'period_start_date', 'period_end', 'period_end_date',
            
            # Funnel data
            'stages', 'stages_list', 'total_entered', 'total_converted',
            'conversion_rate', 'drop_off_points', 'drop_off_analysis',
            
            # Time metrics
            'avg_time_to_convert', 'median_time_to_convert',
            
            # Segment breakdown
            'segment_breakdown',
            
            # Calculated fields
            'calculated_at', 'metadata'
        ]
        read_only_fields = ['id', 'calculated_at']
    
    def get_stages_list(self, obj):
        """Convert stages dict to list for frontend"""
        return [{'name': k, 'count': v} for k, v in obj.stages.items()]
    
    def get_drop_off_analysis(self, obj):
        """Analyze drop-off points"""
        analysis = []
        stages = list(obj.stages.items())
        
        for i in range(len(stages) - 1):
            current_stage, current_count = stages[i]
            next_stage, next_count = stages[i + 1]
            
            if current_count > 0:
                drop_off = current_count - next_count
                drop_off_rate = (drop_off / current_count) * 100 if current_count > 0 else 0
                
                analysis.append({
                    'from': current_stage,
                    'to': next_stage,
                    'drop_off_count': drop_off,
                    'drop_off_rate': round(drop_off_rate, 2),
                    'retention_rate': round(100 - drop_off_rate, 2)
                })
        
        return analysis

class RetentionAnalyticsSerializer(serializers.ModelSerializer):
    cohort_type_display = serializers.CharField(source='get_cohort_type_display', read_only=True)
    cohort_date_formatted = serializers.DateTimeField(source='cohort_date', format="%Y-%m-%d", read_only=True)
    
    # Retention curve
    retention_curve = serializers.SerializerMethodField()
    
    # Formatted monetary fields
    revenue_by_user_formatted = serializers.SerializerMethodField()
    ltv_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = RetentionAnalytics
        fields = [
            'id', 'cohort_type', 'cohort_type_display', 'cohort_date',
            'cohort_date_formatted', 'total_users',
            
            # Retention rates
            'retention_day_1', 'retention_day_3', 'retention_day_7',
            'retention_day_14', 'retention_day_30', 'retention_day_60',
            'retention_day_90',
            
            # Activity metrics
            'active_users_by_period',
            
            # Revenue metrics
            'revenue_by_user', 'revenue_by_user_formatted', 'ltv', 'ltv_formatted',
            
            # Churn metrics
            'churned_users', 'churn_rate',
            
            # Calculated fields
            'retention_curve', 'calculated_at', 'metadata'
        ]
        read_only_fields = ['id', 'calculated_at']
    
    def get_retention_curve(self, obj):
        """Create retention curve data for charts"""
        return {
            'day_1': obj.retention_day_1,
            'day_3': obj.retention_day_3,
            'day_7': obj.retention_day_7,
            'day_14': obj.retention_day_14,
            'day_30': obj.retention_day_30,
            'day_60': obj.retention_day_60,
            'day_90': obj.retention_day_90,
        }
    
    def get_revenue_by_user_formatted(self, obj):
        return f"${obj.revenue_by_user:,.2f}"
    
    def get_ltv_formatted(self, obj):
        return f"${obj.ltv:,.2f}"

class DashboardSerializer(serializers.ModelSerializer):
    dashboard_type_display = serializers.CharField(source='get_dashboard_type_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    created_at_formatted = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M", read_only=True)
    updated_at_formatted = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M", read_only=True)
    
    # Widget preview
    widget_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'dashboard_type', 'dashboard_type_display',
            'description', 'layout_config', 'widget_configs', 'is_public',
            'allowed_users', 'allowed_roles', 'refresh_interval',
            'default_time_range', 'created_at', 'created_at_formatted',
            'updated_at', 'updated_at_formatted', 'created_by',
            'created_by_username', 'widget_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_widget_count(self, obj):
        return len(obj.widget_configs) if obj.widget_configs else 0
    
    def validate_widget_configs(self, value):
        """Validate widget configurations"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Widget configs must be a list")
        
        # Validate each widget config
        required_fields = ['type', 'title', 'data_source']
        for i, widget in enumerate(value):
            if not isinstance(widget, dict):
                raise serializers.ValidationError(f"Widget {i} must be a dictionary")
            
            for field in required_fields:
                if field not in widget:
                    raise serializers.ValidationError(f"Widget {i} missing required field: {field}")
        
        return value

class ReportSerializer(serializers.ModelSerializer):
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    generated_by_username = serializers.CharField(source='generated_by.username', read_only=True)
    generated_at_formatted = serializers.DateTimeField(source='generated_at', format="%Y-%m-%d %H:%M", read_only=True)
    
    # File info
    file_size_formatted = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    def get_download_url(self, obj):
        return obj.download_url
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'report_type', 'report_type_display', 'format',
            'format_display', 'parameters', 'data', 'file', 'file_size',
            'file_size_formatted', 'file_url', 'download_url', 'generated_at',
            'generated_at_formatted', 'generation_duration', 'generated_by',
            'generated_by_username', 'status', 'email_sent', 'email_recipients',
            'metadata'
        ]
        read_only_fields = [
            'id', 'generated_at', 'file_size', 'download_url'
        ]
    
    def get_file_size_formatted(self, obj):
        """Format file size for display"""
        if not obj.file_size:
            return "0 B"
        
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

class RealTimeMetricSerializer(serializers.ModelSerializer):
    metric_type_display = serializers.CharField(source='get_metric_type_display', read_only=True)
    metric_time_formatted = serializers.DateTimeField(source='metric_time', format="%Y-%m-%d %H:%M:%S", read_only=True)
    recorded_at_formatted = serializers.DateTimeField(source='recorded_at', format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    class Meta:
        model = RealTimeMetric
        fields = [
            'id', 'metric_type', 'metric_type_display', 'value', 'unit',
            'dimension', 'dimension_value', 'recorded_at', 'recorded_at_formatted',
            'metric_time', 'metric_time_formatted', 'metadata'
        ]
        read_only_fields = ['id', 'recorded_at']

class AlertRuleSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    metric_type_display = serializers.CharField(source='get_metric_type_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    created_at_formatted = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M", read_only=True)
    updated_at_formatted = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M", read_only=True)
    
    # Alert statistics
    alert_count = serializers.SerializerMethodField()
    last_alert_time = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'description', 'alert_type', 'alert_type_display',
            'metric_type', 'metric_type_display', 'condition', 'condition_display',
            'threshold_value', 'threshold_value_2', 'time_window',
            'evaluation_interval', 'severity', 'severity_display', 'is_active',
            'cooldown_period', 'notify_email', 'notify_slack', 'notify_webhook',
            'email_recipients', 'slack_webhook', 'webhook_url', 'created_at',
            'created_at_formatted', 'updated_at', 'updated_at_formatted',
            'created_by', 'created_by_username', 'alert_count', 'last_alert_time'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_alert_count(self, obj):
        return obj.alerts.count()
    
    def get_last_alert_time(self, obj):
        last_alert = obj.alerts.order_by('-triggered_at').first()
        if last_alert:
            return last_alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S") if last_alert else None

class AlertHistorySerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    triggered_at_formatted = serializers.DateTimeField(source='triggered_at', format="%Y-%m-%d %H:%M:%S", read_only=True)
    resolved_at_formatted = serializers.DateTimeField(source='resolved_at', format="%Y-%m-%d %H:%M:%S", read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)
    
    class Meta:
        model = AlertHistory
        fields = [
            'id', 'rule', 'rule_name', 'severity', 'severity_display',
            'metric_value', 'threshold_value', 'condition_met', 'is_resolved',
            'resolved_at', 'resolved_at_formatted', 'resolved_by',
            'resolved_by_username', 'resolution_notes', 'email_sent',
            'slack_sent', 'webhook_sent', 'triggered_at', 'triggered_at_formatted'
        ]
        read_only_fields = ['id', 'triggered_at']

# Summary Serializers
class AnalyticsSummarySerializer(serializers.Serializer):
    """Summary of analytics data"""
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    new_users_today = serializers.IntegerField()
    revenue_today = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    tasks_completed_today = serializers.IntegerField()
    offers_completed_today = serializers.IntegerField()
    withdrawals_processed_today = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    avg_engagement_score = serializers.FloatField()
    
    # Trends
    revenue_trend = serializers.FloatField(help_text="Percentage change from previous period")
    user_growth_trend = serializers.FloatField()
    task_completion_trend = serializers.FloatField()
    
    # Platform health
    system_uptime = serializers.FloatField(help_text="Percentage uptime")
    avg_response_time = serializers.FloatField(help_text="In milliseconds")
    error_rate = serializers.FloatField(help_text="Percentage of requests with errors")

class TimeSeriesDataSerializer(serializers.Serializer):
    """Time series data for charts"""
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )
    metadata = serializers.DictField(required=False)

class ExportAnalyticsSerializer(serializers.Serializer):
    """Serializer for exporting analytics data"""
    start_date = serializers.DateTimeField(required=True)
    end_date = serializers.DateTimeField(required=True)
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'user_activity', 'revenue', 'offer_performance', 
            'retention', 'funnel', 'all'
        ]),
        required=True
    )
    format = serializers.ChoiceField(
        choices=['csv', 'excel', 'json'],
        default='csv'
    )
    include_metadata = serializers.BooleanField(default=True)
    group_by = serializers.ChoiceField(
        choices=['day', 'week', 'month'],
        default='day',
        required=False
    )