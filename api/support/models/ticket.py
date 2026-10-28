# api/support/models/ticket.py  — WORLD #1
"""Ticket thread, attachment, tag, assignment, SLA, rating, merge models."""
from django.db import models
from django.conf import settings
import uuid


class TicketMessage(models.Model):
    """Full conversation thread message for a ticket."""
    ticket      = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='messages')
    sender      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content     = models.TextField()
    is_agent    = models.BooleanField(default=False, db_index=True)
    is_internal = models.BooleanField(default=False, help_text='Only visible to agents')
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    is_edited   = models.BooleanField(default=False)
    edited_at   = models.DateTimeField(null=True, blank=True)
    attachment  = models.FileField(upload_to='ticket_msg_attachments/', null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'support'
        ordering  = ['created_at']
        db_table  = 'support_ticket_message'
        indexes   = [models.Index(fields=['ticket','is_internal','created_at'])]

    def __str__(self):
        return f'[{"Agent" if self.is_agent else "User"}] {self.ticket.ticket_id}'


class TicketAttachment(models.Model):
    """File attachment on a ticket or message."""
    ticket       = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='attachments')
    message      = models.ForeignKey(TicketMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='attachments')
    file         = models.FileField(upload_to='ticket_attachments/')
    filename     = models.CharField(max_length=255)
    mime_type    = models.CharField(max_length=100, blank=True, default='')
    size_bytes   = models.IntegerField(default=0)
    uploaded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_ticket_attachment'

    @property
    def size_mb(self):
        return round(self.size_bytes / 1024 / 1024, 2)

    def __str__(self):
        return f'{self.filename} ({self.size_mb}MB)'


class TicketTag(models.Model):
    """Tag for categorizing tickets."""
    name        = models.CharField(max_length=50, unique=True)
    color       = models.CharField(max_length=10, default='#6366f1')
    description = models.CharField(max_length=200, blank=True, default='')
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_ticket_tag'

    def __str__(self):
        return self.name


class TicketTagging(models.Model):
    """M2M through table: Ticket ↔ Tag."""
    ticket     = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='ticket_tags')
    tag        = models.ForeignKey(TicketTag, on_delete=models.CASCADE)
    tagged_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tagged_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['ticket', 'tag']]
        db_table        = 'support_ticket_tagging'


class TicketAssignment(models.Model):
    """Assignment history for a ticket."""
    ticket        = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='assignments')
    agent         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ticket_assignments')
    assigned_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='assignments_made')
    assigned_at   = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)
    reason        = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        app_label = 'support'
        ordering  = ['-assigned_at']
        db_table  = 'support_ticket_assignment'

    def __str__(self):
        return f'{self.ticket.ticket_id} → {self.agent.username}'


class TicketSLA(models.Model):
    """SLA tracking per ticket."""
    ticket                  = models.OneToOneField('SupportTicket', on_delete=models.CASCADE, related_name='sla')
    policy                  = models.ForeignKey('SLAPolicy', on_delete=models.SET_NULL, null=True, blank=True)
    first_response_due      = models.DateTimeField(null=True, blank=True)
    resolution_due          = models.DateTimeField(null=True, blank=True)
    first_response_at       = models.DateTimeField(null=True, blank=True)
    resolution_at           = models.DateTimeField(null=True, blank=True)
    first_response_breached = models.BooleanField(default=False, db_index=True)
    resolution_breached     = models.BooleanField(default=False, db_index=True)
    warning_sent            = models.BooleanField(default=False)
    paused_at               = models.DateTimeField(null=True, blank=True)
    pause_reason            = models.CharField(max_length=100, blank=True, default='')
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_ticket_sla'

    @property
    def is_breached(self):
        return self.first_response_breached or self.resolution_breached

    def __str__(self):
        return f'SLA — {self.ticket.ticket_id}'


class TicketRating(models.Model):
    """CSAT rating submitted by user after ticket resolution."""
    ticket          = models.OneToOneField('SupportTicket', on_delete=models.CASCADE, related_name='ticket_rating')
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score           = models.IntegerField(help_text='1-5 star rating')
    review_text     = models.TextField(blank=True, default='')
    agent_rating    = models.IntegerField(null=True, blank=True)
    speed_rating    = models.IntegerField(null=True, blank=True)
    solution_rating = models.IntegerField(null=True, blank=True)
    rated_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        ordering  = ['-rated_at']
        db_table  = 'support_ticket_rating'

    def __str__(self):
        return f'{self.ticket.ticket_id} — {self.score}★'


class TicketMerge(models.Model):
    """Record of ticket merges."""
    primary_ticket  = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='merges_as_primary')
    merged_ticket   = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='merges_as_secondary')
    merged_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    merged_at       = models.DateTimeField(auto_now_add=True)
    reason          = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        app_label = 'support'
        db_table  = 'support_ticket_merge'

    def __str__(self):
        return f'{self.merged_ticket.ticket_id} → {self.primary_ticket.ticket_id}'