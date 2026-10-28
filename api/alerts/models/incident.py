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
    # Additional fields for test compatibility
    escalation_level = models.IntegerField(default=0)
    closure_note = models.TextField(blank=True, default='')
    is_false_positive = models.BooleanField(default=False)
    business_hours_duration_minutes = models.FloatField(null=True, blank=True)

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
    description = models.TextField(blank=True)
    
    # Incident classification
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, db_index=True)
    impact = models.CharField(max_length=20, choices=IMPACT_LEVELS)
    urgency = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    identified_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Acknowledgment details
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alerts_incident_acknowledged_by'
    )
    acknowledgment_note = models.TextField(blank=True)

    # Escalation details
    escalation_reason = models.TextField(blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    # Resolution details
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alerts_incident_resolved_by'
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alerts_incident_closed_by'
    )
    
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
        return f"Incident: {self.title} - {self.severity}"

    @property
    def is_resolved(self):
        """Whether this incident has reached a resolved/closed terminal state."""
        return self.status in ('resolved', 'closed')
    
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
    
    def acknowledge(self, user, notes=""):
        """Acknowledge the incident"""
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.acknowledgment_note = notes
        self.status = 'investigating'
        self.assigned_to = user
        self.save(update_fields=['acknowledged_at', 'acknowledged_by', 'acknowledgment_note', 'status', 'assigned_to'])
        from api.alerts.signals.incident import incident_acknowledged
        incident_acknowledged.send(sender=self.__class__, instance=self, user=user)
        return True

    def identify(self, root_cause="", contributing_factors="", user=None, notes=""):
        """Mark incident as identified"""
        self.status = 'identified'
        self.identified_at = timezone.now()
        self.root_cause = root_cause
        if isinstance(contributing_factors, str) and contributing_factors:
            self.contributing_factors = [contributing_factors]
        elif isinstance(contributing_factors, list):
            self.contributing_factors = contributing_factors
        if user:
            self.updated_by = user
        self.save(update_fields=['status', 'identified_at', 'root_cause', 'contributing_factors'])
        return True

    def resolve(self, user, resolution_summary="", resolution_actions=""):
        """Resolve the incident"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_summary = resolution_summary
        if isinstance(resolution_actions, str) and resolution_actions:
            self.resolution_actions = [resolution_actions]
        elif isinstance(resolution_actions, list):
            self.resolution_actions = resolution_actions
        self.updated_by = user
        if self.acknowledged_at:
            self.response_time_minutes = (self.acknowledged_at - self.detected_at).total_seconds() / 60
        if self.identified_at:
            self.resolution_time_minutes = (self.resolved_at - self.identified_at).total_seconds() / 60
        self.total_downtime_minutes = (self.resolved_at - self.detected_at).total_seconds() / 60
        self.save(update_fields=[
            'status', 'resolved_at', 'resolved_by', 'resolution_summary', 'resolution_actions',
            'updated_by', 'response_time_minutes', 'resolution_time_minutes', 'total_downtime_minutes'
        ])
        from api.alerts.signals.incident import incident_resolved
        incident_resolved.send(sender=self.__class__, instance=self, user=user)
        return True

    def should_escalate(self):
        """
        Whether this incident should be auto-escalated right now, based
        on how long it's been sitting since it was last escalated (or
        detected, if never escalated) relative to a severity-scaled
        time budget. Resolved/closed/false-positive incidents never
        escalate.
        """
        if self.status in ('resolved', 'closed', 'false_positive'):
            return False

        thresholds_minutes = {
            'critical': 15,
            'high': 30,
            'medium': 120,
            'low': 480,
        }
        threshold = thresholds_minutes.get(self.severity, 120)

        reference_time = self.escalated_at or self.acknowledged_at or self.detected_at
        if not reference_time:
            return False

        minutes_since = (timezone.now() - reference_time).total_seconds() / 60
        return minutes_since >= threshold

    def escalate(self, reason="", user=None):
        """Escalate the incident, optionally reassigning it to `user`."""
        self.escalation_level += 1
        self.escalation_reason = reason
        self.escalated_at = timezone.now()
        update_fields = ['escalation_level', 'escalation_reason', 'escalated_at']
        if user is not None:
            self.assigned_to = user
            update_fields.append('assigned_to')
        self.save(update_fields=update_fields)
        from api.alerts.signals.incident import incident_escalated
        incident_escalated.send(sender=self.__class__, instance=self, user=user, reason=reason)
        return True

    def close(self, user, notes=""):
        self.closed_by = user
        self.closure_note = notes
        self.status = 'closed'
        from django.utils import timezone
        self.closed_at = timezone.now()
        self.save()
        from api.alerts.signals.incident import incident_closed
        incident_closed.send(sender=self.__class__, instance=self, user=user)
        return True

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


    def is_overdue(self):
        """Check if incident is overdue based on SLA"""
        from django.utils import timezone
        from datetime import timedelta
        sla_map = {'critical': 60, 'high': 240, 'medium': 480, 'low': 1440}
        sla_minutes = sla_map.get(getattr(self, 'severity', 'medium'), 480)
        detected = getattr(self, 'detected_at', None)
        if not detected:
            return False
        age_minutes = (timezone.now() - detected).total_seconds() / 60
        return age_minutes > sla_minutes and getattr(self, 'status', 'open') not in ('resolved', 'closed')

    def add_timeline_entry(self, event_type, title, description="", user=None):
        """Add an entry to the incident timeline"""
        try:
            from api.alerts.models.incident import IncidentTimeline
            entry = IncidentTimeline.objects.create(
                incident=self,
                event_type=event_type,
                title=title,
                description=description,
                participants=[user.id] if user else []
            )
            return entry
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"add_timeline_entry error: {e}")
            return None

    def get_responders(self):
        """Return all responders for this incident"""
        try:
            from api.alerts.models.incident import IncidentResponder
            return IncidentResponder.objects.filter(incident=self)
        except Exception:
            return []


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
        ('auto_resolved', 'Incident Auto-Resolved'),
        ('closed', 'Incident Closed'),
        ('update', 'Status Update'),
        ('status_change', 'Status Changed'),
        ('escalation', 'Incident Escalated'),
        ('escalated', 'Incident Escalated'),
        ('de_escalation', 'Incident De-escalated'),
        ('responder_assigned', 'Responder Assigned'),
        ('responder_status_change', 'Responder Status Changed'),
        ('post_mortem_started', 'Post-Mortem Started'),
        ('post_mortem_status_change', 'Post-Mortem Status Changed'),
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
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
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
        return f"IncidentTimeline: {self.id} - {self.event_type}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if not self.title or not self.title.strip():
            errors['title'] = 'Timeline event must have a title.'
        if self.event_type == 'resolution' and not self.description:
            errors['description'] = 'Resolution events must include a description.'
        if errors:
            raise ValidationError(errors)


    @classmethod
    def add_event(cls, incident, event_type, title, description, user=None, **kwargs):
        """Add timeline event to incident"""
        event = cls.objects.create(
            incident=incident,
            event_type=event_type,
            title=title,
            description=description,
            created_by=user,
            **kwargs
        )
        from api.alerts.signals.incident import timeline_event_added
        timeline_event_added.send(sender=cls, instance=event, incident=incident, user=user)
        return event
    
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

    def add_participant(self, user_id):
        """Add a participant to this timeline event"""
        parts = list(self.participants or [])
        if user_id not in parts:
            parts.append(user_id)
        self.participants = parts

    def remove_participant(self, user_id):
        """Remove a participant from this timeline event"""
        parts = list(self.participants or [])
        if user_id in parts:
            parts.remove(user_id)
        self.participants = parts

    def has_participant(self, user_id):
        """Check if user_id is a participant"""
        return user_id in (self.participants or [])

    def get_duration(self):
        """Return elapsed time since timestamp as timedelta, or None"""
        if not self.timestamp:
            return None
        return timezone.now() - self.timestamp

    def get_formatted_timestamp(self):
        """Return human-readable formatted timestamp"""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else ''

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
        ('responder', 'Responder'),
        ('lead', 'Lead'),
        ('manager', 'Manager'),
        ('escalation', 'Escalation'),
    ]

    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('active', 'Active'),
        ('away', 'Away'),
        ('completed', 'Completed'),
        ('escalated', 'Escalated'),
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
    completion_note = models.TextField(blank=True)
    available_hours_start = models.TimeField(null=True, blank=True)
    available_hours_end = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"IncidentResponder: {self.user.username} - {self.role}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.active_at and self.completed_at:
            if self.completed_at < self.active_at:
                errors['completed_at'] = 'completed_at cannot be before active_at.'
        if self.status == 'completed' and not self.completed_at:
            errors['completed_at'] = 'Completed responders must have a completed_at timestamp.'
        if self.status == 'active' and not self.active_at:
            errors['active_at'] = 'Active responders must have an active_at timestamp.'
        if errors:
            raise ValidationError(errors)

    def activate(self):
        """Mark responder as active"""
        self.status = 'active'
        self.active_at = timezone.now()
        self.save(update_fields=['status', 'active_at'])
        return True


    def deactivate(self):
        """Mark responder as away"""
        self.status = 'away'
        self.save(update_fields=['status'])
        return True

    def complete(self, user=None, note=""):
        """Mark responder as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if note:
            self.completion_note = note
        self.save(update_fields=['status', 'completed_at', 'completion_note'])
        return True

    def is_available_now(self):
        """Check if responder is available now"""
        start = self.available_hours_start or self.available_from
        end = self.available_hours_end or self.available_to
        if not start or not end:
            return True
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(self.timezone)
        except Exception:
            import zoneinfo
            tz = zoneinfo.ZoneInfo('UTC')
        now = timezone.now().astimezone(tz)
        current_time = now.time()
        return start <= current_time <= end

    def has_responsibility(self, responsibility):
        """Check if this responder has the given responsibility"""
        return responsibility in (self.responsibilities or [])

    def add_responsibility(self, responsibility):
        """Add a responsibility"""
        parts = list(self.responsibilities or [])
        if responsibility not in parts:
            parts.append(responsibility)
        self.responsibilities = parts

    def remove_responsibility(self, responsibility):
        """Remove a responsibility"""
        parts = list(self.responsibilities or [])
        if responsibility in parts:
            parts.remove(responsibility)
        self.responsibilities = parts

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
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('submitted_for_review', 'Submitted For Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
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

    # Approval details
    approval_note = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Publication
    published_at = models.DateTimeField(null=True, blank=True)
    internal_only = models.BooleanField(default=True)
    external_summary = models.TextField(blank=True)

    # Post-mortem content fields (aliases for convenience)
    root_cause = models.TextField(blank=True)
    timeline = models.TextField(blank=True)
    description = models.TextField(blank=True)
    lessons_learned_text = models.TextField(blank=True)
    preventive_measures_text = models.TextField(blank=True)

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
        return f"IncidentPostMortem: {self.id} - {self.status}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        # Published post-mortems must have key fields filled in
        if self.status == 'published':
            if not self.root_cause:
                errors['root_cause'] = 'Published post-mortems must document a root cause.'
            if not self.action_items:
                errors['action_items'] = 'Published post-mortems must include action items.'
        # Timeline consistency
        if self.submitted_at and self.created_at:
            if self.submitted_at < self.created_at:
                errors['submitted_at'] = 'submitted_at cannot be before created_at.'
        if self.approved_at and self.submitted_at:
            if self.approved_at < self.submitted_at:
                errors['approved_at'] = 'approved_at cannot be before submitted_at.'
        if self.published_at and self.approved_at:
            if self.published_at < self.approved_at:
                errors['published_at'] = 'published_at cannot be before approved_at.'
        if errors:
            raise ValidationError(errors)


    def submit_for_review(self, user=None):
        """Submit post-mortem for review"""
        self.status = 'submitted_for_review'
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitted_at'])
        return True

    def approve(self, user, note=""):
        """Approve post-mortem"""
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        if note:
            self.approval_note = note
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_note'])
        return True

    def reject(self, user, note=""):
        """Reject post-mortem"""
        self.status = 'rejected'
        self.approved_by = user
        self.approved_at = timezone.now()
        if note:
            self.approval_note = note
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_note'])
        return True

    def publish(self, internal_only=True):
        """Publish post-mortem"""
        self.status = 'published'
        self.published_at = timezone.now()
        self.internal_only = internal_only
        self.save(update_fields=['status', 'published_at', 'internal_only'])
        return True

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
        default=list,  # Monday to Friday
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
        default=list,
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
        return f"OnCallSchedule: {self.name} - {self.schedule_type}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.rotation_period_days is not None and self.rotation_period_days < 1:
            errors['rotation_period_days'] = 'Rotation period must be at least 1 day.'
        if self.schedule_type == 'fixed':
            if not getattr(self, 'start_time', None) or not getattr(self, 'end_time', None):
                errors['start_time'] = 'Fixed schedules require both start_time and end_time.'
        if self.schedule_type == 'rotation' and not self.rotation_period_days:
            errors['rotation_period_days'] = 'Rotation schedules require a rotation_period_days.'
        if errors:
            raise ValidationError(errors)


    def get_current_on_call(self):
        """Get current on-call person"""
        if not self.is_active:
            return None
        try:
            import zoneinfo
            from datetime import time as dtime
            tz = zoneinfo.ZoneInfo(self.timezone or 'UTC')
            local_now = timezone.now().astimezone(tz)
            current_time = local_now.time()
            current_weekday = local_now.weekday()

            # Normalise start/end to time objects
            def _to_time(val):
                if isinstance(val, dtime):
                    return val
                if isinstance(val, str):
                    parts = val.split(':')
                    return dtime(int(parts[0]), int(parts[1]), int(parts[2].split('.')[0]) if len(parts) > 2 else 0)
                return dtime(9, 0)

            start = _to_time(self.start_time)
            end = _to_time(self.end_time)
            days = list(self.days_of_week or [])

            if days and current_weekday not in days:
                return None
            if not (start <= current_time <= end):
                return None

            if self.schedule_type == 'rotation':
                return self._get_rotation_on_call(timezone.now())
            elif self.schedule_type == 'fixed':
                return self._get_fixed_on_call()
        except Exception:
            pass
        return None

    @classmethod
    def get_current_on_call_all(cls):
        """
        Who's on call right now, across every active schedule.
        Returns a list of dicts: [{'user': <User>, 'schedule': <OnCallSchedule>,
        'schedule_name': str}, ...]. Schedules with nobody currently on
        call (outside configured hours/days, or no primary_users) are
        skipped. Used for auto-assigning new incidents and for the
        incident dashboard's "who's on call" panel.
        """
        results = []
        for schedule in cls.objects.filter(is_active=True):
            user = schedule.get_current_on_call()
            if user:
                results.append({
                    'user': user,
                    'schedule': schedule,
                    'schedule_name': schedule.name,
                })
        return results
    
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

    @property
    def users(self):
        """Alias for primary_users for convenience"""
        return self.primary_users

    @property
    def profile_type(self):
        """Return human-readable schedule type"""
        choices = {
            'rotation': 'Rotation', 'fixed': 'Fixed',
            'on_demand': 'On Demand', 'backup': 'Backup',
            'weekly': 'Weekly', 'custom': 'Custom',
        }
        return choices.get(self.schedule_type, self.schedule_type.title())

    def add_user(self, user):
        """Add user to primary_users"""
        self.primary_users.add(user)

    def remove_user(self, user):
        """Remove user from primary_users"""
        self.primary_users.remove(user)

    def is_user_on_call(self, user):
        """Check if user is currently on call (alias for is_on_call)"""
        return self.is_on_call(user)

    def get_users_count(self):
        """Return count of primary users"""
        return self.primary_users.count()

    def get_next_rotation(self):
        """Return next rotation datetime or None"""
        if not self.rotation_start_date or not self.rotation_period_days:
            return None
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        if not self.rotation_start_date:
            return None
        days_since = (today - self.rotation_start_date).days
        days_until = self.rotation_period_days - (days_since % self.rotation_period_days)
        return timezone.now() + timedelta(days=days_until)

    def rotate(self):
        """Advance the rotation start date by one period"""
        from datetime import timedelta
        if self.rotation_start_date and self.rotation_period_days:
            from django.utils.timezone import now
            self.rotation_start_date = self.rotation_start_date + timedelta(days=self.rotation_period_days)
            self.save(update_fields=['rotation_start_date'])
        return True

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['schedule_type', 'is_active']),
            models.Index(fields=['is_active']),
        ]
        db_table_comment = "On-call schedule management"
        verbose_name = "On-Call Schedule"
        verbose_name_plural = "On-Call Schedules"

# Alias for backward compatibility
IncidentPostmortem = IncidentPostMortem
