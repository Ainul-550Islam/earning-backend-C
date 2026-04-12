"""
Incident Admin Classes
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

from ..models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)
from .core import alerts_admin_site


# ====================== INLINE ADMIN CLASSES ======================

class IncidentTimelineInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Incident Timeline in Incident"""
    model = IncidentTimeline
    extra = 0
    fields = ['event_type', 'title', 'description', 'timestamp', 'participants']
    readonly_fields = ['event_type', 'title', 'description', 'timestamp', 'participants']
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj):
        return False


class IncidentResponderInline(TabularInline if UNFOLD_AVAILABLE else admin.TabularInline):
    """Inline for Incident Responders in Incident"""
    model = IncidentResponder
    extra = 0
    fields = ['user', 'role', 'status', 'assigned_at', 'active_at']
    readonly_fields = ['assigned_at', 'active_at']
    can_delete = False
    show_change_link = True


# ====================== ADMIN CLASSES ======================

@admin.register(Incident, site=alerts_admin_site)
class IncidentAdmin(ModelAdmin):
    """Admin interface for Incidents"""
    list_display = [
        'title', 'severity_badge', 'impact_badge', 'urgency_badge',
        'status_badge', 'assigned_to_link', 'detected_at', 'duration_minutes',
            ]
    
    list_filter = [
        'severity', 'impact', 'urgency', 'status',
        ('detected_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('resolved_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'title', 'description', 'root_cause', 'assigned_to__username', 'assigned_to__email'
    ]
    
    readonly_fields = [
        'detected_at', 'acknowledged_at', 'identified_at', 'resolved_at', 'closed_at',
        'response_time_minutes', 'resolution_time_minutes', 'total_downtime_minutes',
        'duration_minutes'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'severity', 'impact', 'urgency', 'status')
        }),
        ('Assignment', {
            'fields': ('assigned_to',)
        }),
        ('Timeline', {
            'fields': ('detected_at', 'acknowledged_at', 'identified_at', 'resolved_at', 'closed_at')
        }),
        ('Metrics', {
            'fields': ('response_time_minutes', 'resolution_time_minutes', 'total_downtime_minutes',
                      'duration_minutes', 'severity_score')
        }),
        ('Impact Assessment', {
            'fields': ('affected_services', 'affected_users_count', 'affected_regions',
                      'business_impact', 'financial_impact', 'customer_impact')
        }),
        ('Resolution', {
            'fields': ('root_cause', 'contributing_factors', 'resolution_summary',
                      'resolution_actions', 'preventive_measures')
        }),
        ('Communication', {
            'fields': ('communication_plan', 'stakeholder_notifications')
        }),
        ('Related Items', {
            'fields': ('related_alerts',)
        }),
    )
    
    inlines = [IncidentTimelineInline, IncidentResponderInline]
    
    actions = [
        'acknowledge_incidents', 'identify_incidents', 'resolve_incidents',
        'close_incidents', 'escalate_incidents', 'assign_to_me',
        'create_post_mortems', 'export_incidents'
    ]
    
    # Custom display methods
    def severity_badge(self, obj):
        """Display severity as colored badge"""
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'critical': '#dc2626'
        }
        color = colors.get(obj.severity, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'
    severity_badge.admin_order_field = 'severity'
    
    def impact_badge(self, obj):
        """Display impact as colored badge"""
        colors = {
            'none': '#10b981',
            'minimal': '#22c55e',
            'minor': '#f59e0b',
            'major': '#ef4444',
            'severe': '#dc2626',
            'critical': '#991b1b'
        }
        color = colors.get(obj.impact, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.impact.upper()
        )
    impact_badge.short_description = 'Impact'
    impact_badge.admin_order_field = 'impact'
    
    def urgency_badge(self, obj):
        """Display urgency as colored badge"""
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'critical': '#dc2626'
        }
        color = colors.get(obj.urgency, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.urgency.upper()
        )
    urgency_badge.short_description = 'Urgency'
    urgency_badge.admin_order_field = 'urgency'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'open': '#ef4444',
            'investigating': '#f59e0b',
            'identified': '#3b82f6',
            'monitoring': '#8b5cf6',
            'resolved': '#10b981',
            'closed': '#6b7280',
            'false_positive': '#64748b'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.replace('_', ' ').upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def assigned_to_link(self, obj):
        """Clickable assigned to user"""
        if obj.assigned_to:
            return format_html('<span style="font-weight: 500;">{}</span>', obj.assigned_to.get_full_name() or obj.assigned_to.username)
        return 'Unassigned'
    assigned_to_link.short_description = 'Assigned To'
    assigned_to_link.admin_order_field = 'assigned_to__username'
    
    def duration_minutes(self, obj):
        """Calculate duration in minutes"""
        duration = obj.get_duration_minutes()
        if duration:
            if duration > 1440:  # More than 1 day
                return f"{duration / 1440:.1f} days"
            elif duration > 60:  # More than 1 hour
                return f"{duration / 60:.1f} hours"
            else:
                return f"{duration:.0f} min"
        return "N/A"
    duration_minutes.short_description = 'Duration'
    
    # Custom actions
    def acknowledge_incidents(self, request, queryset):
        """Acknowledge selected incidents"""
        updated = queryset.filter(status='open').update(
            status='investigating',
            acknowledged_at=timezone.now()
        )
        messages.success(request, f"Acknowledged {updated} incident(s).")
    acknowledge_incidents.short_description = "Acknowledge selected incidents"
    
    def identify_incidents(self, request, queryset):
        """Identify selected incidents"""
        updated = queryset.filter(status='investigating').update(
            status='identified',
            identified_at=timezone.now()
        )
        messages.success(request, f"Identified {updated} incident(s).")
    identify_incidents.short_description = "Identify selected incidents"
    
    def resolve_incidents(self, request, queryset):
        """Resolve selected incidents"""
        updated = queryset.filter(status__in=['identified', 'monitoring']).update(
            status='resolved',
            resolved_at=timezone.now()
        )
        messages.success(request, f"Resolved {updated} incident(s).")
    resolve_incidents.short_description = "Resolve selected incidents"
    
    def close_incidents(self, request, queryset):
        """Close selected incidents"""
        updated = queryset.filter(status='resolved').update(
            status='closed',
            closed_at=timezone.now()
        )
        messages.success(request, f"Closed {updated} incident(s).")
    close_incidents.short_description = "Close selected incidents"
    
    def escalate_incidents(self, request, queryset):
        """Escalate selected incidents"""
        escalated_count = 0
        for incident in queryset:
            incident.escalation_level += 1
            incident.save(update_fields=['escalation_level'])
            escalated_count += 1
        
        messages.success(request, f"Escalated {escalated_count} incident(s).")
    escalate_incidents.short_description = "Escalate selected incidents"
    
    def assign_to_me(self, request, queryset):
        """Assign selected incidents to current user"""
        updated = queryset.update(assigned_to=request.user)
        messages.success(request, f"Assigned {updated} incident(s) to you.")
    assign_to_me.short_description = "Assign to me"
    
    def create_post_mortems(self, request, queryset):
        """Create post-mortems for selected incidents"""
        from ..models.incident import IncidentPostMortem
        created_count = 0
        for incident in queryset:
            if not incident.postmortem_set.exists():
                IncidentPostMortem.objects.create(
                    incident=incident,
                    title=f"Post-Mortem: {incident.title}",
                    description=f"Post-mortem analysis for incident: {incident.title}",
                    created_by=request.user
                )
                created_count += 1
        
        messages.success(request, f"Created post-mortems for {created_count} incident(s).")
    create_post_mortems.short_description = "Create post-mortems"
    
    def export_incidents(self, request, queryset):
        """Export selected incidents"""
        messages.info(request, f"Export initiated for {queryset.count()} incident(s).")
    export_incidents.short_description = "Export incidents"


@admin.register(IncidentTimeline, site=alerts_admin_site)
class IncidentTimelineAdmin(ModelAdmin):
    """Admin interface for Incident Timeline"""
    list_display = [
        'incident_link', 'event_type', 'title', 'timestamp', 'duration_minutes',
        'participants_count'
    ]
    
    list_filter = [
        'event_type',
        ('timestamp', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'incident__title', 'title', 'description', 'event_data'
    ]
    
    readonly_fields = [
        'incident', 'event_type', 'title', 'description', 'timestamp',
        'duration_minutes', 'participants', 'event_data', 'attachments'
    ]
    
    actions = ['export_timeline', 'cleanup_old_events']
    
    # Custom display methods
    def incident_link(self, obj):
        """Clickable incident title"""
        url = reverse('alerts_admin:alerts_incident_change', args=[obj.incident.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.incident.title)
    incident_link.short_description = 'Incident'
    incident_link.admin_order_field = 'incident__title'
    
    def participants_count(self, obj):
        """Count of participants"""
        return len(obj.participants) if obj.participants else 0
    participants_count.short_description = 'Participants'
    
    # Custom actions
    def export_timeline(self, request, queryset):
        """Export selected timeline events"""
        messages.info(request, f"Export initiated for {queryset.count()} timeline event(s).")
    export_timeline.short_description = "Export timeline"
    
    def cleanup_old_events(self, request, queryset):
        """Clean up old timeline events"""
        messages.info(request, f"Cleanup initiated for old timeline events.")
    cleanup_old_events.short_description = "Cleanup old events"


@admin.register(IncidentResponder, site=alerts_admin_site)
class IncidentResponderAdmin(ModelAdmin):
    """Admin interface for Incident Responders"""
    list_display = [
        'incident_link', 'user_link', 'role_badge', 'status_badge',
        'assigned_at', 'is_available_now', 'contact_method'
    ]
    
    list_filter = [
        'role', 'status', 'contact_method',
        ('assigned_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'incident__title', 'user__username', 'user__email', 'responsibilities'
    ]
    
    readonly_fields = ['assigned_at', 'active_at']
    
    actions = [
        'activate_responders', 'deactivate_responders', 'complete_responders',
        'update_availability', 'export_responders'
    ]
    
    # Custom display methods
    def incident_link(self, obj):
        """Clickable incident title"""
        url = reverse('alerts_admin:alerts_incident_change', args=[obj.incident.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.incident.title)
    incident_link.short_description = 'Incident'
    incident_link.admin_order_field = 'incident__title'
    
    def user_link(self, obj):
        """Clickable user name"""
        if obj.user:
            return format_html('<span style="font-weight: 500;">{}</span>', obj.user.get_full_name() or obj.user.username)
        return 'N/A'
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def role_badge(self, obj):
        """Display role as colored badge"""
        colors = {
            'lead': '#dc2626',
            'responder': '#3b82f6',
            'observer': '#6b7280',
            'escalation': '#f59e0b',
            'manager': '#8b5cf6'
        }
        color = colors.get(obj.role, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.role.upper()
        )
    role_badge.short_description = 'Role'
    role_badge.admin_order_field = 'role'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'assigned': '#6b7280',
            'active': '#10b981',
            'away': '#f59e0b',
            'completed': '#3b82f6',
            'escalated': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def is_available_now(self, obj):
        """Check if responder is available now"""
        is_available = obj.is_available_now()
        color = '#10b981' if is_available else '#ef4444'
        status = 'YES' if is_available else 'NO'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color, status
        )
    is_available_now.short_description = 'Available Now'
    
    # Custom actions
    def activate_responders(self, request, queryset):
        """Activate selected responders"""
        updated = queryset.filter(status='assigned').update(
            status='active',
            active_at=timezone.now()
        )
        messages.success(request, f"Activated {updated} responder(s).")
    activate_responders.short_description = "Activate selected responders"
    
    def deactivate_responders(self, request, queryset):
        """Deactivate selected responders"""
        updated = queryset.filter(status='active').update(
            status='away'
        )
        messages.success(request, f"Deactivated {updated} responder(s).")
    deactivate_responders.short_description = "Deactivate selected responders"
    
    def complete_responders(self, request, queryset):
        """Complete selected responders"""
        updated = queryset.filter(status__in=['active', 'away']).update(
            status='completed',
            completed_at=timezone.now()
        )
        messages.success(request, f"Completed {updated} responder(s).")
    complete_responders.short_description = "Complete selected responders"
    
    def update_availability(self, request, queryset):
        """Update availability for selected responders"""
        from ..tasks.incident import check_responder_availability
        check_responder_availability.delay()
        messages.success(request, f"Availability update initiated for {queryset.count()} responder(s).")
    update_availability.short_description = "Update availability"
    
    def export_responders(self, request, queryset):
        """Export selected responders"""
        messages.info(request, f"Export initiated for {queryset.count()} responder(s).")
    export_responders.short_description = "Export responders"


@admin.register(IncidentPostMortem, site=alerts_admin_site)
class IncidentPostMortemAdmin(ModelAdmin):
    """Admin interface for Incident Post-Mortems"""
    list_display = [
        'incident_link', 'title', 'status_badge', 'reviewed_by_link',
        'approved_by_link', 'completion_score', 'created_at'
    ]
    
    list_filter = [
        'status',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'incident__title', 'title', 'summary', 'lessons_learned'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by'
    ]
    
    actions = [
        'submit_for_review', 'approve_post_mortems', 'reject_post_mortems',
        'publish_post_mortems', 'export_post_mortems'
    ]
    
    # Custom display methods
    def incident_link(self, obj):
        """Clickable incident title"""
        url = reverse('alerts_admin:alerts_incident_change', args=[obj.incident.id])
        return format_html('<a href="{}" style="font-weight: 500;">{}</a>', url, obj.incident.title)
    incident_link.short_description = 'Incident'
    incident_link.admin_order_field = 'incident__title'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'draft': '#6b7280',
            'in_progress': '#f59e0b',
            'submitted_for_review': '#3b82f6',
            'approved': '#10b981',
            'rejected': '#ef4444',
            'published': '#8b5cf6'
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
    
    def completion_score(self, obj):
        """Calculate completion score"""
        score = obj.get_completion_score()
        if score:
            color = '#10b981' if score > 80 else '#f59e0b' if score > 60 else '#ef4444'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
                color, f"{score:.0f}%"
            )
        return "N/A"
    completion_score.short_description = 'Completion'
    
    # Custom actions
    def submit_for_review(self, request, queryset):
        """Submit selected post-mortems for review"""
        updated = queryset.filter(status='draft').update(
            status='submitted_for_review'
        )
        messages.success(request, f"Submitted {updated} post-mortem(s) for review.")
    submit_for_review.short_description = "Submit for review"
    
    def approve_post_mortems(self, request, queryset):
        """Approve selected post-mortems"""
        updated = queryset.filter(status='submitted_for_review').update(
            status='approved',
            approved_by=request.user
        )
        messages.success(request, f"Approved {updated} post-mortem(s).")
    approve_post_mortems.short_description = "Approve selected post-mortems"
    
    def reject_post_mortems(self, request, queryset):
        """Reject selected post-mortems"""
        updated = queryset.filter(status='submitted_for_review').update(
            status='rejected'
        )
        messages.success(request, f"Rejected {updated} post-mortem(s).")
    reject_post_mortems.short_description = "Reject selected post-mortems"
    
    def publish_post_mortems(self, request, queryset):
        """Publish selected post-mortems"""
        updated = queryset.filter(status='approved').update(
            status='published',
            published_at=timezone.now()
        )
        messages.success(request, f"Published {updated} post-mortem(s).")
    publish_post_mortems.short_description = "Publish selected post-mortems"
    
    def export_post_mortems(self, request, queryset):
        """Export selected post-mortems"""
        messages.info(request, f"Export initiated for {queryset.count()} post-mortem(s).")
    export_post_mortems.short_description = "Export post-mortems"


@admin.register(OnCallSchedule, site=alerts_admin_site)
class OnCallScheduleAdmin(ModelAdmin):
    """Admin interface for On-Call Schedules"""
    list_display = [
        'name', 'schedule_type', 'is_active', 'timezone', 'rotation_period_days',
        'current_on_call_display', 'next_rotation', 'created_at'
    ]
    
    list_filter = [
        'schedule_type', 'is_active', 'timezone',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = ['name', 'description', 'timezone']
    
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'current_on_call_display'
    ]
    
    actions = [
        'activate_schedules', 'deactivate_schedules', 'rotate_schedules',
        'update_rotation', 'export_schedules'
    ]
    
    # Custom display methods
    def current_on_call_display(self, obj):
        """Display current on-call person"""
        current_on_call = obj.get_current_on_call()
        if current_on_call:
            return format_html(
                '<span style="font-weight: 500;">{}</span>',
                current_on_call.get_full_name() or current_on_call.username
            )
        return 'None'
    current_on_call_display.short_description = 'Current On-Call'
    
    def next_rotation(self, obj):
        """Display next rotation time"""
        if obj.schedule_type == 'rotation' and obj.rotation_start_date:
            # Calculate next rotation
            next_rotation = obj.rotation_start_date + timezone.timedelta(days=obj.rotation_period_days)
            return next_rotation.strftime('%Y-%m-%d %H:%M')
        return 'N/A'
    next_rotation.short_description = 'Next Rotation'
    
    # Custom actions
    def activate_schedules(self, request, queryset):
        """Activate selected schedules"""
        queryset.update(is_active=True)
        messages.success(request, f"Activated {queryset.count()} schedule(s).")
    activate_schedules.short_description = "Activate selected schedules"
    
    def deactivate_schedules(self, request, queryset):
        """Deactivate selected schedules"""
        queryset.update(is_active=False)
        messages.success(request, f"Deactivated {queryset.count()} schedule(s).")
    deactivate_schedules.short_description = "Deactivate selected schedules"
    
    def rotate_schedules(self, request, queryset):
        """Rotate selected schedules"""
        from ..tasks.incident import update_on_call_schedules
        update_on_call_schedules.delay()
        messages.success(request, f"Rotation initiated for {queryset.count()} schedule(s).")
    rotate_schedules.short_description = "Rotate selected schedules"
    
    def update_rotation(self, request, queryset):
        """Update rotation for selected schedules"""
        from ..tasks.incident import notify_on_call_changes
        notify_on_call_changes.delay()
        messages.success(request, f"Rotation update initiated for {queryset.count()} schedule(s).")
    update_rotation.short_description = "Update rotation"
    
    def export_schedules(self, request, queryset):
        """Export selected schedules"""
        messages.info(request, f"Export initiated for {queryset.count()} schedule(s).")
    export_schedules.short_description = "Export schedules"
