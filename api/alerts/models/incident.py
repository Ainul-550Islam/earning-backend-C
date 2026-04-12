"""
Alert Incident Models
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from datetime import timedelta
import json

from decimal import Decimal
import uuid

from .core import AlertRule, AlertLog


class Incident(models.Model):
    """Incident management for major alert events"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('identified', 'Identified'),
        ('monitoring', 'Monitoring'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('false_positive', 'False Positive'),
    ]
    
    IMPACT_LEVELS = [
        ('none', 'No Impact'),
        ('minimal', 'Minimal'),
        ('minor', 'Minor'),
        ('major', 'Major'),
        ('severe', 'Severe'),
        ('critical', 'Critical'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Incident classification
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, db_index=True)
    impact = models.CharField(max_length=20, choices=IMPACT_LEVELS)
    urgency = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    identified_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Duration tracking
    response_time_minutes = models.FloatField(null=True, blank=True)
    resolution_time_minutes = models.FloatField(null=True, blank=True)
    total_downtime_minutes = models.FloatField(null=True, blank=True)
    
    # Root cause analysis
    root_cause = models.TextField(blank=True)
    contributing_factors = models.JSONField(default=list)
    
    # Affected systems
    affected_services = models.JSONField(default=list)
    affected_users_count = models.IntegerField(default=0)
    affected_regions = models.JSONField(default=list)
    
    # Business impact
    business_impact = models.TextField(blank=True)
    financial_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    customer_impact = models.TextField(blank=True)
    
    # Communication
    communication_plan = models.TextField(blank=True)
    stakeholder_notifications = models.JSONField(default=list)
    
    # Resolution details
    resolution_summary = models.TextField(blank=True)
    resolution_actions = models.JSONField(default=list)
    preventive_measures = models.JSONField(default=list)
    
    # Related alerts
    related_alerts = models.ManyToManyField(
        AlertLog,
        related_name='%(app_label)s_%(class)s_tenant',
        blank=True
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_incident_assigned_to'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_incident_created_by'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_incident_updated_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Incident: {self.title} ({self.get_severity_display()})"
    
    def clean(self):
        """Validate incident data"""
        super().clean()
        
        # Validate timeline consistency
        if self.identified_at and self.detected_at and self.identified_at < self.detected_at:
            raise ValidationError("Identified time cannot be before detected time")
        
        if self.resolved_at and self.identified_at and self.resolved_at < self.identified_at:
            raise ValidationError("Resolved time cannot be before identified time")
        
        if self.closed_at and self.resolved_at and self.closed_at < self.resolved_at:
            raise ValidationError("Closed time cannot be before resolved time")
    
    def acknowledge(self, user):
        """Acknowledge the incident"""
        if not self.acknowledged_at:
            self.acknowledged_at = timezone.now()
            self.assigned_to = user
            self.save(update_fields=['acknowledged_at', 'assigned_to'])
            return True
        return False
    
    def identify(self, user, root_cause=""):
        """Mark incident as identified"""
        if self.status == 'investigating':
            self.status = 'identified'
            self.identified_at = timezone.now()
            self.root_cause = root_cause
            self.updated_by = user
            self.save(update_fields=['status', 'identified_at', 'root_cause', 'updated_by'])
            return True
        return False
    
    def resolve(self, user, resolution_summary=""):
        """Resolve the incident"""
        if self.status in ['open', 'investigating', 'identified', 'monitoring']:
            self.status = 'resolved'
            self.resolved_at = timezone.now()
            self.resolution_summary = resolution_summary
            self.updated_by = user
            
            # Calculate response and resolution times
            if self.acknowledged_at:
                self.response_time_minutes = (self.acknowledged_at - self.detected_at).total_seconds() / 60
            
            if self.identified_at:
                self.resolution_time_minutes = (self.resolved_at - self.identified_at).total_seconds() / 60
            
            self.total_downtime_minutes = (self.resolved_at - self.detected_at).total_seconds() / 60
            
            self.save(update_fields=[
                'status', 'resolved_at', 'resolution_summary', 'updated_by',
                'response_time_minutes', 'resolution_time_minutes', 'total_downtime_minutes'
            ])
            return True
        return False
    
    def close(self, user):
        """Close the incident"""
        if self.status == 'resolved':
            self.status = 'closed'
            self.closed_at = timezone.now()
            self.updated_by = user
            self.save(update_fields=['status', 'closed_at', 'updated_by'])
            return True
        return False
    
    def mark_false_positive(self, user):
        """Mark incident as false positive"""
        self.status = 'false_positive'
        self.closed_at = timezone.now()
        self.updated_by = user
        self.save(update_fields=['status', 'closed_at', 'updated_by'])
    
    def add_related_alert(self, alert_log):
        """Add related alert to incident"""
        self.related_alerts.add(alert_log)
    
    def get_duration_minutes(self):
        """Get total duration in minutes"""
        end_time = self.resolved_at or self.closed_at or timezone.now()
        return (end_time - self.detected_at).total_seconds() / 60
    
    def get_business_hours_duration(self):
        """Calculate duration during business hours only"""
        # Simplified business hours calculation (9 AM - 5 PM, Mon-Fri)
        start = self.acknowledged_at or self.detected_at
        end = self.resolved_at or self.closed_at or timezone.now()
        
        business_minutes = 0
        current = start
        
        while current < end:
            # Check if current time is during business hours
            if current.weekday() < 5 and 9 <= current.hour < 17:
                business_minutes += 1
            
            current += timedelta(minutes=1)
        
        return business_minutes
    
    def get_severity_score(self):
        """Calculate severity score for prioritization"""
        severity_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        impact_scores = {'none': 0, 'minimal': 1, 'minor': 2, 'major': 3, 'severe': 4, 'critical': 5}
        urgency_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        
        return (
            severity_scores.get(self.severity, 2) * 3 +
            impact_scores.get(self.impact, 1) * 2 +
            urgency_scores.get(self.urgency, 2) * 1
        )
    
    @classmethod
    def create_from_alert(cls, alert_log, title=None, severity=None):
        """Create incident from alert log"""
        if not title:
            title = f"Incident: {alert_log.rule.name}"
        
        if not severity:
            severity = alert_log.rule.severity
        
        incident = cls.objects.create(
            title=title,
            description=alert_log.message,
            severity=severity,
            impact='minor',  # Default impact
            urgency=severity,
            created_by=None  # Would be current user in views
        )
        
        incident.add_related_alert(alert_log)
        return incident
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['status', 'detected_at']),
            models.Index(fields=['severity', 'detected_at']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['detected_at']),
        ]
        db_table_comment = "Incident management for major alert events"
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"


class IncidentTimeline(models.Model):
    """Timeline events for incidents"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    EVENT_TYPES = [
        ('detected', 'Incident Detected'),
        ('acknowledged', 'Incident Acknowledged'),
        ('investigation_started', 'Investigation Started'),
        ('identified', 'Root Cause Identified'),
        ('communication_sent', 'Communication Sent'),
        ('mitigation_applied', 'Mitigation Applied'),
        ('monitoring', 'Monitoring Progress'),
        ('resolved', 'Incident Resolved'),
        ('closed', 'Incident Closed'),
        ('update', 'Status Update'),
        ('escalation', 'Incident Escalated'),
        ('de_escalation', 'Incident De-escalated'),
    ]
    
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Event details
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    duration_minutes = models.FloatField(null=True, blank=True)
    
    # Participants
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_incidenttimeline_created_by'
    )
    participants = models.JSONField(default=list)
    
    # Event data
    event_data = models.JSONField(default=dict)
    attachments = models.JSONField(default=list)
    
    # Impact metrics
    users_affected = models.IntegerField(default=0)
    services_affected = models.JSONField(default=list)
    metrics_affected = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.incident.title} - {self.get_event_type_display()}"
    
    @classmethod
    def add_event(cls, incident, event_type, title, description, user=None, **kwargs):
        """Add timeline event to incident"""
        return cls.objects.create(
            incident=incident,
            event_type=event_type,
            title=title,
            description=description,
            created_by=user,
            **kwargs
        )
    
    @classmethod
    def auto_detect_event(cls, incident):
        """Add automatic detection event"""
        return cls.add_event(
            incident,
            'detected',
            'Incident Detected',
            f'Incident automatically detected from alert: {incident.title}',
            event_data={'auto_detected': True}
        )
    
    @classmethod
    def auto_acknowledge_event(cls, incident, user):
        """Add automatic acknowledgment event"""
        return cls.add_event(
            incident,
            'acknowledged',
            'Incident Acknowledged',
            f'Incident acknowledged by {user.get_full_name() or user.username}',
            user=user,
            participants=[user.id]
        )
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['incident', 'timestamp']),
            models.Index(fields=['event_type', 'timestamp']),
        ]
        db_table_comment = "Timeline events for incidents"
        verbose_name = "Incident Timeline"
        verbose_name_plural = "Incident Timelines"


class IncidentResponder(models.Model):
    """People responding to incidents"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ROLE_TYPES = [
        ('incident_commander', 'Incident Commander'),
        ('technical_lead', 'Technical Lead'),
        ('communications_lead', 'Communications Lead'),
        ('subject_matter_expert', 'Subject Matter Expert'),
        ('stakeholder', 'Stakeholder'),
        ('observer', 'Observer'),
    ]
    
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('active', 'Active'),
        ('away', 'Away'),
        ('completed', 'Completed'),
    ]
    
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alerts_incidentresponder_user'
    )
    
    # Role and status
    role = models.CharField(max_length=30, choices=ROLE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    # Timing
    assigned_at = models.DateTimeField(auto_now_add=True)
    active_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Contact information
    contact_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('slack', 'Slack'),
            ('teams', 'Teams'),
        ],
        default='email'
    )
    contact_details = models.JSONField(default=dict)
    
    # Availability
    available_from = models.TimeField(null=True, blank=True)
    available_to = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Responsibilities
    responsibilities = models.JSONField(default=list)
    skills = models.JSONField(default=list)
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"
    
    def activate(self):
        """Mark responder as active"""
        if self.status == 'assigned':
            self.status = 'active'
            self.active_at = timezone.now()
            self.save(update_fields=['status', 'active_at'])
            return True
        return False
    
    def complete(self):
        """Mark responder as completed"""
        if self.status == 'active':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
            return True
        return False
    
    def is_available_now(self):
        """Check if responder is available now"""
        if self.status != 'active':
            return False
        
        if not self.available_from or not self.available_to:
            return True
        
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(self.timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo('UTC')
        
        now = timezone.now().astimezone(tz)
        current_time = now.time()
        
        return self.available_from <= current_time <= self.available_to
    
    class Meta:
        ordering = ['role', 'assigned_at']
        unique_together = ['incident', 'user']
        indexes = [
            models.Index(fields=['incident', 'role']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'assigned_at']),
        ]
        db_table_comment = "People responding to incidents"
        verbose_name = "Incident Responder"
        verbose_name_plural = "Incident Responders"


class IncidentPostMortem(models.Model):
    """Post-mortem analysis for incidents"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    incident = models.OneToOneField(
        Incident,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Post-mortem details
    title = models.CharField(max_length=200)
    summary = models.TextField()
    
    # Timeline summary
    timeline_summary = models.TextField()
    key_events = models.JSONField(default=list)
    
    # Analysis
    root_cause_analysis = models.TextField()
    contributing_factors = models.JSONField(default=list)
    what_went_well = models.JSONField(default=list)
    what_could_be_improved = models.JSONField(default=list)
    
    # Impact assessment
    business_impact = models.TextField()
    technical_impact = models.TextField()
    customer_impact = models.TextField()
    financial_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Lessons learned
    lessons_learned = models.JSONField(default=list)
    action_items = models.JSONField(default=list)
    preventive_measures = models.JSONField(default=list)
    
    # Process improvements
    process_changes = models.JSONField(default=list)
    tool_improvements = models.JSONField(default=list)
    training_needs = models.JSONField(default=list)
    
    # Review and approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_incidentpostmortem_reviewed_by'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_incidentpostmortem_approved_by'
    )
    
    # Publication
    published_at = models.DateTimeField(null=True, blank=True)
    internal_only = models.BooleanField(default=True)
    external_summary = models.TextField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_incidentpostmortem_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Post-mortem: {self.incident.title}"
    
    def submit_for_review(self, user):
        """Submit post-mortem for review"""
        if self.status == 'draft':
            self.status = 'review'
            self.save(update_fields=['status'])
            return True
        return False
    
    def approve(self, user):
        """Approve post-mortem"""
        if self.status == 'review':
            self.status = 'approved'
            self.approved_by = user
            self.save(update_fields=['status', 'approved_by'])
            return True
        return False
    
    def publish(self, internal_only=True):
        """Publish post-mortem"""
        if self.status == 'approved':
            self.status = 'published'
            self.published_at = timezone.now()
            self.internal_only = internal_only
            self.save(update_fields=['status', 'published_at', 'internal_only'])
            return True
        return False
    
    def get_completion_score(self):
        """Calculate completion score for post-mortem"""
        required_sections = [
            'summary', 'timeline_summary', 'root_cause_analysis',
            'business_impact', 'lessons_learned', 'action_items'
        ]
        
        completed_sections = 0
        for section in required_sections:
            if getattr(self, section, None):
                completed_sections += 1
        
        return (completed_sections / len(required_sections)) * 100
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['incident']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['published_at']),
        ]
        db_table_comment = "Post-mortem analysis for incidents"
        verbose_name = "Incident Post-Mortem"
        verbose_name_plural = "Incident Post-Mortems"


class OnCallSchedule(models.Model):
    """On-call schedule management"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    SCHEDULE_TYPES = [
        ('rotation', 'Rotation'),
        ('fixed', 'Fixed Schedule'),
        ('on_demand', 'On Demand'),
        ('backup', 'Backup'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Schedule configuration
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Rotation settings
    rotation_period_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    rotation_start_date = models.DateField(null=True, blank=True)
    
    # Time settings
    timezone = models.CharField(max_length=50, default='UTC')
    start_time = models.TimeField(default='09:00:00')
    end_time = models.TimeField(default='17:00:00')
    days_of_week = models.JSONField(
        default=lambda: [0, 1, 2, 3, 4],  # Monday to Friday
        help_text="Days of week (0=Monday)"
    )
    
    # Coverage
    primary_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='%(app_label)s_%(class)s_primary',
        blank=True
    )
    backup_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='%(app_label)s_%(class)s_backup',
        blank=True
    )
    
    # Escalation
    escalation_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    escalation_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='%(app_label)s_%(class)s_escalation',
        blank=True
    )
    
    # Notification preferences
    notification_channels = models.JSONField(
        default=lambda: ['email', 'sms'],
        help_text="Preferred notification channels"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_oncallschedule_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"On-call: {self.name}"
    
    def get_current_on_call(self):
        """Get current on-call person"""
        if not self.is_active:
            return None
        
        now = timezone.now()
        
        # Check if within business hours
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(self.timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo('UTC')
        
        local_now = now.astimezone(tz)
        current_time = local_now.time()
        current_weekday = local_now.weekday()
        
        # Check if current time is within schedule
        if not (self.start_time <= current_time <= self.end_time):
            return None
        
        if current_weekday not in self.days_of_week:
            return None
        
        # Get rotation-based assignment
        if self.schedule_type == 'rotation':
            return self._get_rotation_on_call(now)
        elif self.schedule_type == 'fixed':
            return self._get_fixed_on_call()
        
        return None
    
    def _get_rotation_on_call(self, now):
        """Get on-call person based on rotation"""
        if not self.rotation_start_date or not self.rotation_period_days:
            return None
        
        primary_users = list(self.primary_users.all())
        if not primary_users:
            return None
        
        # Calculate current rotation position
        days_since_start = (now.date() - self.rotation_start_date).days
        rotation_cycles = days_since_start // self.rotation_period_days
        current_position = rotation_cycles % len(primary_users)
        
        return primary_users[current_position]
    
    def _get_fixed_on_call(self):
        """Get on-call person for fixed schedule"""
        primary_users = list(self.primary_users.all())
        return primary_users[0] if primary_users else None
    
    def get_escalation_chain(self):
        """Get escalation chain for current time"""
        chain = []
        
        # Add primary on-call
        primary = self.get_current_on_call()
        if primary:
            chain.append({
                'user': primary,
                'level': 1,
                'delay_minutes': 0
            })
        
        # Add backup users
        for i, backup in enumerate(self.backup_users.all(), 2):
            chain.append({
                'user': backup,
                'level': i,
                'delay_minutes': self.escalation_minutes * (i - 1)
            })
        
        # Add escalation users
        escalation_count = len(chain)
        for i, escalation in enumerate(self.escalation_users.all(), escalation_count + 1):
            chain.append({
                'user': escalation,
                'level': i,
                'delay_minutes': self.escalation_minutes * (i - 1)
            })
        
        return chain
    
    def is_on_call(self, user):
        """Check if user is currently on call"""
        current = self.get_current_on_call()
        return current == user
    
    def get_upcoming_schedule(self, days=30):
        """Get upcoming on-call schedule"""
        schedule = []
        now = timezone.now()
        
        if self.schedule_type == 'rotation' and self.rotation_start_date:
            primary_users = list(self.primary_users.all())
            if primary_users:
                for day_offset in range(days):
                    check_date = now.date() + timedelta(days=day_offset)
                    days_since_start = (check_date - self.rotation_start_date).days
                    rotation_cycles = days_since_start // self.rotation_period_days
                    position = rotation_cycles % len(primary_users)
                    
                    schedule.append({
                        'date': check_date,
                        'user': primary_users[position],
                        'type': 'primary'
                    })
        
        return schedule
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['schedule_type', 'is_active']),
            models.Index(fields=['is_active']),
        ]
        db_table_comment = "On-call schedule management"
        verbose_name = "On-Call Schedule"
        verbose_name_plural = "On-Call Schedules"
