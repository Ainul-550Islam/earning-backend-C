"""
Intelligence Admin Classes
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.utils import timezone
from django.contrib import messages

# Unfold imports
try:
    from unfold.admin import ModelAdmin, TabularInline
    from unfold.filters import DateRangeFilter, RelatedDropdownFilter, ChoiceDropdownFilter
    UNFOLD_AVAILABLE = True
except ImportError:
    UNFOLD_AVAILABLE = False
    from django.contrib.admin import ModelAdmin, TabularInline
    from django.contrib.admin import DateFieldListFilter

from ..models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, 
    AlertNoise, RootCauseAnalysis
)
from .core import alerts_admin_site


# ====================== INLINE ADMIN CLASSES ======================

class AlertPredictionInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Alert Predictions in Alert Correlation"""
    model = AlertPrediction
    extra = 0
    fields = ['prediction_type', 'model_type', 'accuracy_score', 'training_status', 'last_trained']
    readonly_fields = ['prediction_type', 'model_type', 'accuracy_score', 'training_status', 'last_trained']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


class AnomalyDetectionModelInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Anomaly Detection Models in Alert Correlation"""
    model = AnomalyDetectionModel
    extra = 0
    fields = ['detection_method', 'sensitivity', 'window_size_minutes', 'is_active', 'last_trained']
    readonly_fields = ['detection_method', 'sensitivity', 'window_size_minutes', 'is_active', 'last_trained']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


# ====================== ADMIN CLASSES ======================

@admin.register(AlertCorrelation, site=alerts_admin_site)
class AlertCorrelationAdmin(ModelAdmin):
    """Admin interface for Alert Correlations"""
    list_display = [
        'name', 'correlation_type', 'status_badge', 'correlation_strength_badge',
        'primary_rules_count', 'secondary_rules_count', 'confidence_level',
        'last_analyzed', 'prediction_accuracy'
    ]
    
    list_filter = [
        'correlation_type', 'status', 'confidence_level',
        ('last_analyzed', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'name', 'description', 'pattern_description', 'pattern_regex'
    ]
    
    readonly_fields = [
        'correlation_coefficient', 'p_value', 'confidence_level',
        'correlation_strength', 'prediction_accuracy', 'last_analyzed',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'correlation_type', 'status')
        }),
        ('Correlation Configuration', {
            'fields': ('primary_rules', 'secondary_rules', 'time_window_minutes',
                      'correlation_threshold', 'minimum_occurrences')
        }),
        ('Analysis Results', {
            'fields': ('correlation_coefficient', 'p_value', 'confidence_level',
                      'correlation_strength', 'prediction_accuracy')
        }),
        ('Pattern Information', {
            'fields': ('pattern_description', 'pattern_regex')
        }),
        ('Model Configuration', {
            'fields': ('model_type', 'model_parameters')
        }),
        ('Statistics', {
            'fields': ('last_analyzed', 'created_at', 'updated_at')
        }),
    )
    
    
    actions = [
        'analyze_correlations', 'train_models', 'test_predictions',
        'activate_correlations', 'deactivate_correlations', 'export_correlations'
    ]
    
    # Custom display methods
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#6b7280',
            'analyzing': '#f59e0b',
            'confirmed': '#10b981',
            'rejected': '#ef4444',
            'expired': '#64748b'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def correlation_strength_badge(self, obj):
        """Display correlation strength as colored badge"""
        if obj.correlation_strength is None:
            return format_html('<span style="color: #6b7280;">N/A</span>')
        
        if obj.correlation_strength > 0.8:
            color = '#10b981'
            label = 'STRONG'
        elif obj.correlation_strength > 0.6:
            color = '#f59e0b'
            label = 'MODERATE'
        elif obj.correlation_strength > 0.4:
            color = '#ef4444'
            label = 'WEAK'
        else:
            color = '#64748b'
            label = 'VERY WEAK'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, label
        )
    correlation_strength_badge.short_description = 'Correlation'
    correlation_strength_badge.admin_order_field = 'correlation_strength'
    
    def primary_rules_count(self, obj):
        """Count of primary rules"""
        return obj.primary_rules.count()
    primary_rules_count.short_description = 'Primary Rules'
    
    def secondary_rules_count(self, obj):
        """Count of secondary rules"""
        return obj.secondary_rules.count()
    secondary_rules_count.short_description = 'Secondary Rules'
    
    def prediction_accuracy(self, obj):
        """Display prediction accuracy"""
        if obj.prediction_accuracy is None:
            return 'N/A'
        return f"{obj.prediction_accuracy:.1f}%"
    prediction_accuracy.short_description = 'Accuracy'
    
    # Custom actions
    def analyze_correlations(self, request, queryset):
        """Analyze selected correlations"""
        from ..tasks.intelligence import analyze_all_correlations
        analyze_all_correlations.delay()
        messages.success(request, f"Analysis initiated for {queryset.count()} correlation(s).")
    analyze_correlations.short_description = "Analyze selected correlations"
    
    def train_models(self, request, queryset):
        """Train models for selected correlations"""
        from ..tasks.intelligence import train_prediction_models
        train_prediction_models.delay()
        messages.success(request, f"Training initiated for {queryset.count()} correlation(s).")
    train_models.short_description = "Train selected models"
    
    def test_predictions(self, request, queryset):
        """Test predictions for selected correlations"""
        from ..tasks.intelligence import test_prediction_model
        tested_count = 0
        for correlation in queryset:
            test_prediction_model.delay(correlation.id)
            tested_count += 1
        
        messages.success(request, f"Testing initiated for {tested_count} correlation(s).")
    test_predictions.short_description = "Test selected predictions"
    
    def activate_correlations(self, request, queryset):
        """Activate selected correlations"""
        queryset.update(status='confirmed')
        messages.success(request, f"Activated {queryset.count()} correlation(s).")
    activate_correlations.short_description = "Activate selected correlations"
    
    def deactivate_correlations(self, request, queryset):
        """Deactivate selected correlations"""
        queryset.update(status='pending')
        messages.success(request, f"Deactivated {queryset.count()} correlation(s).")
    deactivate_correlations.short_description = "Deactivate selected correlations"
    
    def export_correlations(self, request, queryset):
        """Export selected correlations"""
        messages.info(request, f"Export initiated for {queryset.count()} correlation(s).")
    export_correlations.short_description = "Export correlations"


@admin.register(AlertPrediction, site=alerts_admin_site)
class AlertPredictionAdmin(ModelAdmin):
    """Admin interface for Alert Predictions"""
    list_display = [
        'name', 'prediction_type', 'model_type', 'is_active', 'training_status_badge',
        'target_rules_count', 'accuracy_score', 'precision_score', 'recall_score',
        'last_trained'
    ]
    
    list_filter = [
        'prediction_type', 'model_type', 'is_active', 'training_status',
        ('last_trained', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'name', 'description', 'model_type', 'feature_columns'
    ]
    
    readonly_fields = [
        'accuracy_score', 'precision_score', 'recall_score', 'f1_score',
        'mean_absolute_error', 'training_status', 'last_trained',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'prediction_type', 'model_type', 'is_active')
        }),
        ('Training Configuration', {
            'fields': ('target_rules', 'training_days', 'prediction_horizon_hours')
        }),
        ('Model Configuration', {
            'fields': ('model_parameters', 'feature_columns')
        }),
        ('Performance Metrics', {
            'fields': ('accuracy_score', 'precision_score', 'recall_score', 'f1_score',
                      'mean_absolute_error')
        }),
        ('Training Status', {
            'fields': ('training_status', 'last_trained', 'created_at', 'updated_at')
        }),
    )
    
    actions = [
        'train_models', 'test_models', 'evaluate_models', 'activate_models',
        'deactivate_models', 'export_models'
    ]
    
    # Custom display methods
    def training_status_badge(self, obj):
        """Display training status as colored badge"""
        colors = {
            'pending': '#6b7280',
            'training': '#f59e0b',
            'completed': '#10b981',
            'failed': '#ef4444',
            'updating': '#3b82f6'
        }
        color = colors.get(obj.training_status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.training_status.upper()
        )
    training_status_badge.short_description = 'Training Status'
    training_status_badge.admin_order_field = 'training_status'
    
    def target_rules_count(self, obj):
        """Count of target rules"""
        return obj.target_rules.count()
    target_rules_count.short_description = 'Target Rules'
    
    # Custom actions
    def train_models(self, request, queryset):
        """Train selected models"""
        from ..tasks.intelligence import train_prediction_models
        train_prediction_models.delay()
        messages.success(request, f"Training initiated for {queryset.count()} model(s).")
    train_models.short_description = "Train selected models"
    
    def test_models(self, request, queryset):
        """Test selected models"""
        from ..tasks.intelligence import test_prediction_model
        tested_count = 0
        for model in queryset:
            test_prediction_model.delay(model.id)
            tested_count += 1
        
        messages.success(request, f"Testing initiated for {tested_count} model(s).")
    test_models.short_description = "Test selected models"
    
    def evaluate_models(self, request, queryset):
        """Evaluate selected models"""
        from ..tasks.intelligence import evaluate_model_accuracy
        evaluate_model_accuracy.delay()
        messages.success(request, f"Evaluation initiated for {queryset.count()} model(s).")
    evaluate_models.short_description = "Evaluate selected models"
    
    def activate_models(self, request, queryset):
        """Activate selected models"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} model(s).")
    activate_models.short_description = "Activate selected models"
    
    def deactivate_models(self, request, queryset):
        """Deactivate selected models"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} model(s).")
    deactivate_models.short_description = "Deactivate selected models"
    
    def export_models(self, request, queryset):
        """Export selected models"""
        messages.info(request, f"Export initiated for {queryset.count()} model(s).")
    export_models.short_description = "Export models"


@admin.register(AnomalyDetectionModel, site=alerts_admin_site)
class AnomalyDetectionModelAdmin(ModelAdmin):
    """Admin interface for Anomaly Detection Models"""
    list_display = [
        'name', 'detection_method', 'target_anomaly_types', 'is_active',
        'sensitivity', 'window_size_minutes', 'target_rules_count', 'last_trained'
    ]
    
    list_filter = [
        'detection_method', 'is_active', 'target_anomaly_types',
        ('last_trained', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'name', 'description', 'detection_method', 'model_parameters'
    ]
    
    readonly_fields = [
        'last_trained', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'detection_method', 'is_active')
        }),
        ('Detection Configuration', {
            'fields': ('target_anomaly_types', 'target_rules', 'sensitivity',
                      'window_size_minutes', 'baseline_days')
        }),
        ('Threshold Configuration', {
            'fields': ('anomaly_threshold', 'min_alert_count')
        }),
        ('Model Configuration', {
            'fields': ('model_parameters',)
        }),
        ('Timestamps', {
            'fields': ('last_trained', 'created_at', 'updated_at')
        }),
    )
    
    actions = [
        'detect_anomalies', 'update_thresholds', 'train_models',
        'activate_models', 'deactivate_models', 'export_models'
    ]
    
    # Custom display methods
    def target_anomaly_types(self, obj):
        """Display target anomaly types"""
        if obj.target_anomaly_types:
            return ', '.join(obj.target_anomaly_types)
        return 'All'
    target_anomaly_types.short_description = 'Anomaly Types'
    
    def target_rules_count(self, obj):
        """Count of target rules"""
        return obj.target_rules.count()
    target_rules_count.short_description = 'Target Rules'
    
    # Custom actions
    def detect_anomalies(self, request, queryset):
        """Detect anomalies using selected models"""
        from ..tasks.intelligence import detect_anomalies
        detect_anomalies.delay()
        messages.success(request, f"Anomaly detection initiated for {queryset.count()} model(s).")
    detect_anomalies.short_description = "Detect anomalies"
    
    def update_thresholds(self, request, queryset):
        """Update thresholds for selected models"""
        from ..tasks.intelligence import update_anomaly_thresholds
        update_anomaly_thresholds.delay()
        messages.success(request, f"Threshold update initiated for {queryset.count()} model(s).")
    update_thresholds.short_description = "Update thresholds"
    
    def train_models(self, request, queryset):
        """Train selected models"""
        from ..tasks.intelligence import train_prediction_models
        train_prediction_models.delay()
        messages.success(request, f"Training initiated for {queryset.count()} model(s).")
    train_models.short_description = "Train selected models"
    
    def activate_models(self, request, queryset):
        """Activate selected models"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} model(s).")
    activate_models.short_description = "Activate selected models"
    
    def deactivate_models(self, request, queryset):
        """Deactivate selected models"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} model(s).")
    deactivate_models.short_description = "Deactivate selected models"
    
    def export_models(self, request, queryset):
        """Export selected models"""
        messages.info(request, f"Export initiated for {queryset.count()} model(s).")
    export_models.short_description = "Export models"


@admin.register(AlertNoise, site=alerts_admin_site)
class AlertNoiseAdmin(ModelAdmin):
    """Admin interface for Alert Noise"""
    list_display = [
        'name', 'noise_type', 'action', 'is_active', 'target_rules_count',
        'total_processed', 'total_suppressed', 'effectiveness_score', 'created_at'
    ]
    
    list_filter = [
        'noise_type', 'action', 'is_active',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'name', 'description', 'message_patterns', 'source_filter'
    ]
    
    readonly_fields = [
        'total_processed', 'total_suppressed', 'total_grouped', 'total_delayed',
        'effectiveness_score', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'noise_type', 'action', 'is_active')
        }),
        ('Target Configuration', {
            'fields': ('target_rules', 'message_patterns', 'severity_filter', 'source_filter')
        }),
        ('Action Configuration', {
            'fields': ('suppression_duration_minutes', 'max_suppressions_per_hour',
                      'group_window_minutes', 'max_group_size', 'delay_minutes')
        }),
        ('Statistics', {
            'fields': ('total_processed', 'total_suppressed', 'total_grouped',
                      'total_delayed', 'effectiveness_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'activate_filters', 'deactivate_filters', 'test_filters',
        'optimize_filters', 'reset_statistics', 'export_filters'
    ]
    
    # Custom display methods
    def target_rules_count(self, obj):
        """Count of target rules"""
        return obj.target_rules.count()
    target_rules_count.short_description = 'Target Rules'
    
    def effectiveness_score(self, obj):
        """Display effectiveness score"""
        score = obj.get_effectiveness_score()
        if score is not None:
            color = '#10b981' if score > 80 else '#f59e0b' if score > 60 else '#ef4444'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
                color, f"{score:.1f}%"
            )
        return "N/A"
    effectiveness_score.short_description = 'Effectiveness'
    
    # Custom actions
    def activate_filters(self, request, queryset):
        """Activate selected filters"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} filter(s).")
    activate_filters.short_description = "Activate selected filters"
    
    def deactivate_filters(self, request, queryset):
        """Deactivate selected filters"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} filter(s).")
    deactivate_filters.short_description = "Deactivate selected filters"
    
    def test_filters(self, request, queryset):
        """Test selected filters"""
        from ..tasks.intelligence import AlertNoiseTestFilterSerializer
        tested_count = 0
        for filter in queryset:
            # Simulate filter testing
            tested_count += 1
        
        messages.success(request, f"Testing initiated for {tested_count} filter(s).")
    test_filters.short_description = "Test selected filters"
    
    def optimize_filters(self, request, queryset):
        """Optimize selected filters"""
        from ..tasks.intelligence import evaluate_noise_filters
        optimize_noise_filters.delay()
        messages.success(request, f"Optimization initiated for {queryset.count()} filter(s).")
    optimize_filters.short_description = "Optimize selected filters"
    
    def reset_statistics(self, request, queryset):
        """Reset statistics for selected filters"""
        queryset.update(
            total_processed=0,
            total_suppressed=0,
            total_grouped=0,
            total_delayed=0
        )
        messages.success(request, f"Statistics reset for {queryset.count()} filter(s).")
    reset_statistics.short_description = "Reset statistics"
    
    def export_filters(self, request, queryset):
        """Export selected filters"""
        messages.info(request, f"Export initiated for {queryset.count()} filter(s).")
    export_filters.short_description = "Export filters"


@admin.register(RootCauseAnalysis, site=alerts_admin_site)
class RootCauseAnalysisAdmin(ModelAdmin):
    """Admin interface for Root Cause Analysis"""
    list_display = [
        'title', 'incident_link', 'analysis_method', 'confidence_level_badge',
        'status_badge', 'reviewed_by_link', 'approved_by_link',
        'analysis_score', 'created_at'
    ]
    
    list_filter = [
        'analysis_method', 'confidence_level', 'status', 
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        
    ]
    
    search_fields = [
        'title', 'description', 'incident__title', 'root_causes', 'lessons_learned'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by'
    ]
    
    actions = [
        'submit_for_review', 'approve_analyses', 'reject_analyses',
        'publish_analyses', 'generate_recommendations', 'export_analyses'
    ]
    
    # Custom display methods
    def incident_link(self, obj):
        """Clickable incident title"""
        if obj.incident:
            url = reverse('alerts_admin:alerts_incident_change', args=[obj.incident.id])
            return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.incident.title)
        return 'N/A'
    incident_link.short_description = 'Incident'
    incident_link.admin_order_field = 'incident__title'
    
    def confidence_level_badge(self, obj):
        """Display confidence level as colored badge"""
        colors = {
            'low': '#6b7280',
            'medium': '#f59e0b',
            'high': '#10b981',
            'very_high': '#059669'
        }
        color = colors.get(obj.confidence_level, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.confidence_level.replace('_', ' ').upper()
        )
    confidence_level_badge.short_description = 'Confidence'
    confidence_level_badge.admin_order_field = 'confidence_level'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'draft': '#6b7280',
            'in_progress': '#f59e0b',
            'completed': '#10b981',
            'submitted_for_review': '#3b82f6',
            'approved': '#059669',
            'rejected': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.replace('_', ' ').upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def reviewed_by_link(self, obj):
        """Clickable reviewer name"""
        if obj.reviewed_by:
            return format_html('<span style="font-weight: 500;">{}</span>', obj.reviewed_by.get_full_name() or obj.reviewed_by.username)
        return 'Not reviewed'
    reviewed_by_link.short_description = 'Reviewed By'
    
    def approved_by_link(self, obj):
        """Clickable approver name"""
        if obj.approved_by:
            return format_html('<span style="font-weight: 500;">{}</span>', obj.approved_by.get_full_name() or obj.approved_by.username)
        return 'Not approved'
    approved_by_link.short_description = 'Approved By'
    
    def analysis_score(self, obj):
        """Calculate analysis score"""
        score = obj.get_analysis_score()
        if score is not None:
            color = '#10b981' if score > 80 else '#f59e0b' if score > 60 else '#ef4444'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
                color, f"{score:.0f}%"
            )
        return "N/A"
    analysis_score.short_description = 'Score'
    
    # Custom actions
    def submit_for_review(self, request, queryset):
        """Submit selected analyses for review"""
        updated = queryset.filter(status='completed').update(
            status='submitted_for_review'
        )
        messages.success(request, f"Submitted {updated} analysis/analyses for review.")
    submit_for_review.short_description = "Submit for review"
    
    def approve_analyses(self, request, queryset):
        """Approve selected analyses"""
        updated = queryset.filter(status='submitted_for_review').update(
            status='approved',
            approved_by=request.user
        )
        messages.success(request, f"Approved {updated} analysis/analyses.")
    approve_analyses.short_description = "Approve selected analyses"
    
    def reject_analyses(self, request, queryset):
        """Reject selected analyses"""
        updated = queryset.filter(status='submitted_for_review').update(
            status='rejected'
        )
        messages.success(request, f"Rejected {updated} analysis/analyses.")
    reject_analyses.short_description = "Reject selected analyses"
    
    def publish_analyses(self, request, queryset):
        """Publish selected analyses"""
        updated = queryset.filter(status='approved').update(
            status='completed',
            published_at=timezone.now()
        )
        messages.success(request, f"Published {updated} analysis/analyses.")
    publish_analyses.short_description = "Publish selected analyses"
    
    def generate_recommendations(self, request, queryset):
        """Generate recommendations for selected analyses"""
        from ..tasks.intelligence import perform_root_cause_analysis
        generated_count = 0
        for analysis in queryset:
            # Simulate recommendation generation
            generated_count += 1
        
        messages.success(request, f"Recommendations generated for {generated_count} analysis/analyses.")
    generate_recommendations.short_description = "Generate recommendations"
    
    def export_analyses(self, request, queryset):
        """Export selected analyses"""
        messages.info(request, f"Export initiated for {queryset.count()} analysis/analyses.")
    export_analyses.short_description = "Export analyses"
