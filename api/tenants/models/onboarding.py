"""
Onboarding Models

This module contains tenant onboarding models for tracking
setup progress, trial extensions, and user guidance.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class TenantOnboarding(TimeStampedModel, SoftDeleteModel):
    """
    Tenant onboarding progress tracking.
    
    This model tracks the overall onboarding progress
    for tenants, including completion percentage and
    current step information.
    """
    
    STATUS_CHOICES = [
        ('not_started', _('Not Started')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('paused', _('Paused')),
        ('skipped', _('Skipped')),
    ]
    
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='onboarding',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this onboarding belongs to')
    )
    
    # Progress tracking
    completion_pct = models.IntegerField(
        default=0,
        verbose_name=_('Completion Percentage'),
        help_text=_('Percentage of onboarding completed')
    )
    current_step = models.CharField(
        max_length=100,
        default='welcome',
        verbose_name=_('Current Step'),
        help_text=_('Current onboarding step')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started',
        verbose_name=_('Status'),
        help_text=_('Current onboarding status')
    )
    
    # Timing
    started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Started At'),
        help_text=_('When onboarding was started')
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Completed At'),
        help_text=_('When onboarding was completed')
    )
    last_activity_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Activity At'),
        help_text=_('Last onboarding activity timestamp')
    )
    
    # User tracking
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_onboardings',
        verbose_name=_('Assigned To'),
        help_text=_('User assigned to help with onboarding')
    )
    
    # Preferences and settings
    skip_welcome = models.BooleanField(
        default=False,
        verbose_name=_('Skip Welcome'),
        help_text=_('Whether to skip welcome steps')
    )
    enable_tips = models.BooleanField(
        default=True,
        verbose_name=_('Enable Tips'),
        help_text=_('Whether to show contextual tips')
    )
    send_reminders = models.BooleanField(
        default=True,
        verbose_name=_('Send Reminders'),
        help_text=_('Whether to send onboarding reminders')
    )
    
    # Customization
    custom_flow = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Custom Flow'),
        help_text=_('Custom onboarding flow configuration')
    )
    skipped_steps = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Skipped Steps'),
        help_text=_('List of skipped onboarding steps')
    )
    
    # Notes and feedback
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Internal notes about onboarding progress')
    )
    feedback = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Feedback'),
        help_text=_('User feedback about onboarding experience')
    )
    
    class Meta:
        db_table = 'tenant_onboarding'
        verbose_name = _('Tenant Onboarding')
        verbose_name_plural = _('Tenant Onboarding')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant'], name='idx_tenant_1801'),
            models.Index(fields=['status'], name='idx_status_1802'),
            models.Index(fields=['completion_pct'], name='idx_completion_pct_1803'),
            models.Index(fields=['started_at'], name='idx_started_at_1804'),
            models.Index(fields=['completed_at'], name='idx_completed_at_1805'),
        ]
    
    def __str__(self):
        return f"Onboarding for {self.tenant.name} ({self.completion_pct}%)"
    
    def clean(self):
        super().clean()
        if self.completion_pct < 0 or self.completion_pct > 100:
            raise ValidationError(_('Completion percentage must be between 0 and 100.'))
    
    def start_onboarding(self):
        """Start the onboarding process."""
        from django.utils import timezone
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.last_activity_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'last_activity_at'])
    
    def complete_onboarding(self):
        """Complete the onboarding process."""
        from django.utils import timezone
        self.status = 'completed'
        self.completion_pct = 100
        self.completed_at = timezone.now()
        self.last_activity_at = timezone.now()
        self.save(update_fields=['status', 'completion_pct', 'completed_at', 'last_activity_at'])
    
    def pause_onboarding(self):
        """Pause the onboarding process."""
        self.status = 'paused'
        self.save(update_fields=['status'])
    
    def update_progress(self, step, increment=0):
        """Update onboarding progress."""
        self.current_step = step
        self.completion_pct = min(100, self.completion_pct + increment)
        self.last_activity_at = timezone.now()
        
        if self.completion_pct >= 100:
            self.complete_onboarding()
        else:
            self.save(update_fields=['current_step', 'completion_pct', 'last_activity_at'])
    
    def skip_step(self, step_key):
        """Skip an onboarding step."""
        if step_key not in self.skipped_steps:
            self.skipped_steps.append(step_key)
            self.save(update_fields=['skipped_steps'])
    
    def is_step_completed(self, step_key):
        """Check if a step is completed."""
        # This would check against the completed steps
        # For now, return False as placeholder
        return False
    
    @property
    def is_completed(self):
        """Check if onboarding is completed."""
        return self.status == 'completed'
    
    @property
    def days_since_start(self):
        """Days since onboarding started."""
        if not self.started_at:
            return 0
        delta = timezone.now() - self.started_at
        return delta.days
    
    @property
    def needs_attention(self):
        """Check if onboarding needs attention."""
        return (
            self.status == 'in_progress' and
            self.days_since_start > 7 and
            self.completion_pct < 50
        )


class TenantOnboardingStep(TimeStampedModel, SoftDeleteModel):
    """
    Individual onboarding steps for tenants.
    
    This model defines individual steps in the onboarding
    process and tracks their completion status.
    """
    
    STEP_TYPE_CHOICES = [
        ('welcome', _('Welcome')),
        ('profile_setup', _('Profile Setup')),
        ('team_invitation', _('Team Invitation')),
        ('integration_setup', _('Integration Setup')),
        ('first_campaign', _('First Campaign')),
        ('billing_setup', _('Billing Setup')),
        ('domain_setup', _('Domain Setup')),
        ('branding_setup', _('Branding Setup')),
        ('api_setup', _('API Setup')),
        ('final_review', _('Final Review')),
        ('custom', _('Custom')),
    ]
    
    STATUS_CHOICES = [
        ('not_started', _('Not Started')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('skipped', _('Skipped')),
        ('failed', _('Failed')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='onboarding_steps',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this step belongs to')
    )
    
    # Step information
    step_key = models.CharField(
        max_length=100,
        verbose_name=_('Step Key'),
        help_text=_('Unique identifier for the step')
    )
    step_type = models.CharField(
        max_length=50,
        choices=STEP_TYPE_CHOICES,
        verbose_name=_('Step Type'),
        help_text=_('Type of onboarding step')
    )
    label = models.CharField(
        max_length=255,
        verbose_name=_('Label'),
        help_text=_('Display label for the step')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Detailed description of the step')
    )
    
    # Status and progress
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started',
        verbose_name=_('Status'),
        help_text=_('Current status of the step')
    )
    is_done = models.BooleanField(
        default=False,
        verbose_name=_('Is Done'),
        help_text=_('Whether the step is completed')
    )
    done_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Done At'),
        help_text=_('When the step was completed')
    )
    
    # Step configuration
    is_required = models.BooleanField(
        default=True,
        verbose_name=_('Is Required'),
        help_text=_('Whether this step is required')
    )
    can_skip = models.BooleanField(
        default=False,
        verbose_name=_('Can Skip'),
        help_text=_('Whether this step can be skipped')
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order'),
        help_text=_('Order in which steps should be displayed')
    )
    
    # Resources and help
    help_text = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Help Text'),
        help_text=_('Additional help text for the step')
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Video URL'),
        help_text=_('URL to instructional video')
    )
    documentation_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Documentation URL'),
        help_text=_('URL to relevant documentation')
    )
    
    # Step data
    step_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Step Data'),
        help_text=_('Data collected during this step')
    )
    validation_rules = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Validation Rules'),
        help_text=_('Rules for validating step completion')
    )
    
    # Timing
    started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Started At'),
        help_text=_('When this step was started')
    )
    time_spent_seconds = models.IntegerField(
        default=0,
        verbose_name=_('Time Spent (seconds)'),
        help_text=_('Time spent on this step in seconds')
    )
    
    class Meta:
        db_table = 'tenant_onboarding_steps'
        verbose_name = _('Tenant Onboarding Step')
        verbose_name_plural = _('Tenant Onboarding Steps')
        ordering = ['sort_order', 'step_key']
        unique_together = ['tenant', 'step_key']
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_1806'),
            models.Index(fields=['step_type'], name='idx_step_type_1807'),
            models.Index(fields=['sort_order'], name='idx_sort_order_1808'),
            models.Index(fields=['is_done'], name='idx_is_done_1809'),
        ]
    
    def __str__(self):
        return f"{self.label} for {self.tenant.name}"
    
    def start_step(self):
        """Start the onboarding step."""
        from django.utils import timezone
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def complete_step(self, step_data=None):
        """Complete the onboarding step."""
        from django.utils import timezone
        self.status = 'completed'
        self.is_done = True
        self.done_at = timezone.now()
        
        if step_data:
            self.step_data.update(step_data)
        
        # Calculate time spent
        if self.started_at:
            time_delta = timezone.now() - self.started_at
            self.time_spent_seconds = int(time_delta.total_seconds())
        
        self.save(update_fields=['status', 'is_done', 'done_at', 'step_data', 'time_spent_seconds'])
    
    def skip_step(self, reason=None):
        """Skip the onboarding step."""
        from django.utils import timezone
        if not self.can_skip:
            raise ValidationError(_('This step cannot be skipped.'))
        
        self.status = 'skipped'
        self.done_at = timezone.now()
        if reason:
            self.step_data['skip_reason'] = reason
        self.save(update_fields=['status', 'done_at', 'step_data'])
    
    def fail_step(self, error_message=None):
        """Mark the step as failed."""
        self.status = 'failed'
        if error_message:
            self.step_data['error'] = error_message
        self.save(update_fields=['status', 'step_data'])
    
    def validate_completion(self):
        """Validate that the step can be completed."""
        if not self.validation_rules:
            return True
        
        # Implement validation logic based on rules
        # For now, return True as placeholder
        return True
    
    @property
    def is_active(self):
        """Check if this is the current active step."""
        onboarding = getattr(self.tenant, 'onboarding', None)
        if onboarding:
            return onboarding.current_step == self.step_key
        return False
    
    @property
    def time_spent_display(self):
        """Get human-readable time spent."""
        if self.time_spent_seconds < 60:
            return f"{self.time_spent_seconds}s"
        elif self.time_spent_seconds < 3600:
            minutes = self.time_spent_seconds // 60
            return f"{minutes}m"
        else:
            hours = self.time_spent_seconds // 3600
            minutes = (self.time_spent_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


class TenantTrialExtension(TimeStampedModel, SoftDeleteModel):
    """
    Trial extension requests and approvals for tenants.
    
    This model manages trial extension requests,
    approvals, and tracking for tenant trials.
    """
    
    STATUS_CHOICES = [
        ('requested', _('Requested')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('expired', _('Expired')),
        ('cancelled', _('Cancelled')),
    ]
    
    REASON_CHOICES = [
        ('setup_complexity', _('Setup Complexity')),
        ('team_training', _('Team Training')),
        ('integration_delay', _('Integration Delay')),
        ('business_review', _('Business Review')),
        ('custom_requirements', _('Custom Requirements')),
        ('other', _('Other')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='trial_extensions',
        verbose_name=_('Tenant'),
        help_text=_('The tenant requesting the extension')
    )
    
    # Extension details
    days_extended = models.IntegerField(
        verbose_name=_('Days Extended'),
        help_text=_('Number of additional days requested')
    )
    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        verbose_name=_('Reason'),
        help_text=_('Reason for extension request')
    )
    reason_details = models.TextField(
        verbose_name=_('Reason Details'),
        help_text=_('Detailed explanation for the extension request')
    )
    
    # Status and approval
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='requested',
        verbose_name=_('Status'),
        help_text=_('Current status of the extension request')
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='approved_trial_extensions',
        verbose_name=_('Approved By'),
        help_text=_('User who approved the extension')
    )
    approved_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Approved At'),
        help_text=_('When the extension was approved')
    )
    
    # Trial timing
    original_trial_end = models.DateTimeField(
        verbose_name=_('Original Trial End'),
        help_text=_('Original trial end date')
    )
    new_trial_end = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('New Trial End'),
        help_text=_('New trial end date after extension')
    )
    
    # Communication
    notification_sent = models.BooleanField(
        default=False,
        verbose_name=_('Notification Sent'),
        help_text=_('Whether notification was sent to tenant')
    )
    follow_up_required = models.BooleanField(
        default=False,
        verbose_name=_('Follow Up Required'),
        help_text=_('Whether follow-up is required')
    )
    follow_up_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Follow Up Date'),
        help_text=_('Date for follow-up contact')
    )
    
    # Internal notes
    internal_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Internal Notes'),
        help_text=_('Internal notes about the extension request')
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Rejection Reason'),
        help_text=_('Reason for rejecting the extension')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional metadata about the extension')
    )
    
    class Meta:
        db_table = 'tenant_trial_extensions'
        verbose_name = _('Tenant Trial Extension')
        verbose_name_plural = _('Tenant Trial Extensions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_1810'),
            models.Index(fields=['status'], name='idx_status_1811'),
            models.Index(fields=['approved_at'], name='idx_approved_at_1812'),
            models.Index(fields=['new_trial_end'], name='idx_new_trial_end_1813'),
        ]
    
    def __str__(self):
        return f"{self.days_extended} days extension for {self.tenant.name}"
    
    def clean(self):
        super().clean()
        if self.days_extended <= 0:
            raise ValidationError(_('Days extended must be greater than 0.'))
        
        if self.days_extended > 90:
            raise ValidationError(_('Cannot extend trial by more than 90 days.'))
    
    def approve(self, approved_by, notes=None):
        """Approve the trial extension."""
        from django.utils import timezone
        import datetime
        
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        
        # Calculate new trial end date
        if self.original_trial_end:
            self.new_trial_end = self.original_trial_end + datetime.timedelta(days=self.days_extended)
        
        if notes:
            self.internal_notes = notes
        
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'new_trial_end', 'internal_notes'])
        
        # Update tenant trial end date
        if self.new_trial_end:
            self.tenant.trial_ends_at = self.new_trial_end
            self.tenant.save(update_fields=['trial_ends_at'])
    
    def reject(self, approved_by, reason=None):
        """Reject the trial extension."""
        from django.utils import timezone
        
        self.status = 'rejected'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        
        if reason:
            self.rejection_reason = reason
        
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'rejection_reason'])
    
    def cancel(self):
        """Cancel the trial extension."""
        self.status = 'cancelled'
        self.save(update_fields=['status'])
    
    @property
    def is_approved(self):
        """Check if extension is approved."""
        return self.status == 'approved'
    
    @property
    def is_pending(self):
        """Check if extension is pending approval."""
        return self.status == 'requested'
    
    @property
    def days_until_new_trial_end(self):
        """Days until new trial end date."""
        if not self.new_trial_end:
            return None
        
        delta = self.new_trial_end - timezone.now()
        return max(0, delta.days)
    
    def send_notification(self):
        """Send notification to tenant about extension status."""
        # This would implement actual notification sending
        self.notification_sent = True
        self.save(update_fields=['notification_sent'])
    
    def schedule_follow_up(self, days_from_now=7):
        """Schedule follow-up contact."""
        from django.utils import timezone
        import datetime
        
        self.follow_up_required = True
        self.follow_up_date = timezone.now().date() + datetime.timedelta(days=days_from_now)
        self.save(update_fields=['follow_up_required', 'follow_up_date'])
