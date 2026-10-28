# api/support/models.py  — WORLD #1 FINAL
# Original 3 models সম্পূর্ণ রাখা হয়েছে + নতুন যোগ হয়েছে
# Migration: 0001→0002→0003 (original) → 0004 (world1 new models)

import datetime
import random
import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


# ════════════════════════════════════════════════════════════════
# MODEL 1: SupportSettings  ← ORIGINAL (exact fields kept)
# ════════════════════════════════════════════════════════════════
class SupportSettings(models.Model):
    """Admin can update support links without app update"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # ── Original fields (UNCHANGED) ────────────────────────────
    telegram_group  = models.URLField(blank=True, null=True, help_text="Telegram group/channel link")
    telegram_admin  = models.URLField(blank=True, null=True, help_text="Direct admin chat link")
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True, help_text="With country code")
    whatsapp_group  = models.URLField(blank=True, null=True)
    facebook_page   = models.URLField(blank=True, null=True)
    email_support   = models.EmailField(blank=True)
    support_hours_start = models.TimeField(default=datetime.time(9, 0))
    support_hours_end   = models.TimeField(default=datetime.time(18, 0))
    is_support_online   = models.BooleanField(default=True)
    maintenance_mode    = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    force_update        = models.BooleanField(default=False)
    latest_version_code = models.IntegerField(default=1)
    latest_version_name = models.CharField(max_length=20, default="1.0.0", null=True, blank=True)
    update_message      = models.TextField(blank=True)
    play_store_url      = models.URLField(blank=True, null=True)

    # ── New fields (added in 0004) ─────────────────────────────
    support_timezone         = models.CharField(max_length=50, default='Asia/Dhaka')
    ai_auto_response_enabled = models.BooleanField(default=False)
    sla_business_hours_only  = models.BooleanField(default=True)
    chat_widget_enabled      = models.BooleanField(default=True)
    chat_widget_color        = models.CharField(max_length=10, default='#6366f1')
    chat_bot_enabled         = models.BooleanField(default=True)
    support_admin_email      = models.EmailField(blank=True)
    slack_webhook_url        = models.URLField(blank=True, null=True)
    updated_at               = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Support Settings"

    def __str__(self):
        return "Support Settings"


# ════════════════════════════════════════════════════════════════
# MODEL 2: SupportTicket  ← ORIGINAL (exact fields kept)
# ════════════════════════════════════════════════════════════════
class SupportTicket(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # ── Original choices (extended with new options) ────────────
    STATUS_CHOICES = [
        ('open',         'Open'),
        ('in_progress',  'In Progress'),
        ('resolved',     'Resolved'),
        ('closed',       'Closed'),
        # New statuses added in 0004
        ('waiting_user', 'Waiting for User'),
        ('spam',         'Spam'),
    ]
    PRIORITY_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
        ('urgent', 'Urgent'),
    ]
    CATEGORY_CHOICES = [
        # Original 5 categories (UNCHANGED)
        ('payment',   'Payment Issue'),
        ('coins',     'Coins Not Added'),
        ('account',   'Account Problem'),
        ('technical', 'Technical Issue'),
        ('other',     'Other'),
        # New categories added in 0004
        ('withdrawal', 'Withdrawal Issue'),
        ('fraud',      'Fraud/Security'),
        ('kyc',        'KYC Verification'),
        ('referral',   'Referral Issue'),
        ('offer',      'Offer Issue'),
    ]
    CHANNEL_CHOICES = [
        ('web',      'Web Portal'),
        ('email',    'Email'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('facebook', 'Facebook'),
        ('chat',     'Live Chat'),
        ('api',      'API'),
    ]

    # ── Original user FK (related_name='support_supportticket_user' from 0002) ─
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_supportticket_user',  # ← matches 0003 AlterField
    )

    # ── Original fields (UNCHANGED) ────────────────────────────
    ticket_id        = models.CharField(max_length=20, unique=True, blank=True)
    category         = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    subject          = models.CharField(max_length=200)
    description      = models.TextField()
    screenshot       = models.ImageField(upload_to='support_tickets/', null=True, blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority         = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    resolved_at      = models.DateTimeField(null=True, blank=True)
    admin_response   = models.TextField(blank=True)
    admin_responded_at = models.DateTimeField(null=True, blank=True)

    # ── New fields (added in 0004) ─────────────────────────────
    channel         = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='web')
    assigned_to     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_support_tickets',
    )
    escalated        = models.BooleanField(default=False, db_index=True)
    escalated_at     = models.DateTimeField(null=True, blank=True)
    satisfaction_rating = models.IntegerField(null=True, blank=True)
    rating_comment   = models.TextField(blank=True, default='')
    rated_at         = models.DateTimeField(null=True, blank=True)
    ai_category      = models.CharField(max_length=50, blank=True, default='')
    ai_sentiment     = models.CharField(max_length=30, blank=True, default='')
    message_count    = models.IntegerField(default=0)
    first_response_at = models.DateTimeField(null=True, blank=True)
    source_email     = models.EmailField(blank=True, default='')

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f"TKT{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.ticket_id} - {self.user.username}"


# ════════════════════════════════════════════════════════════════
# MODEL 3: FAQ  ← ORIGINAL (exact fields kept)
# ════════════════════════════════════════════════════════════════
class FAQ(models.Model):
    """Frequently Asked Questions"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    # ── Original fields (UNCHANGED) ────────────────────────────
    question  = models.CharField(max_length=300)
    answer    = models.TextField()
    category  = models.CharField(max_length=50, default='general')
    is_active = models.BooleanField(default=True)
    order     = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── New fields (added in 0004) ─────────────────────────────
    helpful_yes = models.IntegerField(default=0)
    helpful_no  = models.IntegerField(default=0)
    view_count  = models.IntegerField(default=0)
    tags        = models.JSONField(default=list, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    @property
    def helpful_ratio(self):
        t = self.helpful_yes + self.helpful_no
        return round(self.helpful_yes / t * 100, 1) if t else 0

    def __str__(self):
        return self.question


# ════════════════════════════════════════════════════════════════
# MODEL 4-11: TICKET THREAD & ATTACHMENTS (New in 0004)
# ════════════════════════════════════════════════════════════════
class TicketMessage(models.Model):
    """Multi-message thread for each ticket — replaces single admin_response"""
    ticket      = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content     = models.TextField()
    is_agent    = models.BooleanField(default=False, db_index=True)
    is_internal = models.BooleanField(default=False)
    is_read     = models.BooleanField(default=False)
    attachment  = models.FileField(upload_to='ticket_attachments/', null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    is_edited   = models.BooleanField(default=False)
    edited_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        db_table = 'support_ticket_message'

    def __str__(self):
        return f'{"[Agent]" if self.is_agent else "[User]"} {self.ticket.ticket_id}'


class TicketAttachment(models.Model):
    ticket      = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='attachments')
    message     = models.ForeignKey(TicketMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='attachments')
    file        = models.FileField(upload_to='ticket_attachments/')
    filename    = models.CharField(max_length=255)
    mime_type   = models.CharField(max_length=100, blank=True, default='')
    size_bytes  = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_ticket_attachment'

    @property
    def size_mb(self):
        return round(self.size_bytes / 1024 / 1024, 2)


class TicketTag(models.Model):
    name  = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=10, default='#6366f1')

    class Meta:
        db_table = 'support_ticket_tag'

    def __str__(self):
        return self.name


class TicketTagging(models.Model):
    ticket    = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='ticket_tags')
    tag       = models.ForeignKey(TicketTag, on_delete=models.CASCADE)
    tagged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tagged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['ticket', 'tag']]
        db_table = 'support_ticket_tagging'


class TicketRating(models.Model):
    ticket      = models.OneToOneField(SupportTicket, on_delete=models.CASCADE, related_name='ticket_rating')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score       = models.IntegerField()
    review_text = models.TextField(blank=True, default='')
    agent_rating = models.IntegerField(null=True, blank=True)
    speed_rating = models.IntegerField(null=True, blank=True)
    rated_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-rated_at']
        db_table = 'support_ticket_rating'


class TicketSLA(models.Model):
    ticket                  = models.OneToOneField(SupportTicket, on_delete=models.CASCADE, related_name='sla')
    first_response_due      = models.DateTimeField(null=True, blank=True)
    resolution_due          = models.DateTimeField(null=True, blank=True)
    first_response_at       = models.DateTimeField(null=True, blank=True)
    resolution_at           = models.DateTimeField(null=True, blank=True)
    first_response_breached = models.BooleanField(default=False, db_index=True)
    resolution_breached     = models.BooleanField(default=False, db_index=True)
    warning_sent            = models.BooleanField(default=False)
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_ticket_sla'

    @property
    def is_breached(self):
        return self.first_response_breached or self.resolution_breached


class TicketMerge(models.Model):
    primary_ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='merges_as_primary')
    merged_ticket  = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='merges_as_secondary')
    merged_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    merged_at      = models.DateTimeField(auto_now_add=True)
    reason         = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        db_table = 'support_ticket_merge'


class TicketAuditLog(models.Model):
    ticket     = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='audit_logs')
    actor      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action     = models.CharField(max_length=100)
    field      = models.CharField(max_length=100, blank=True, default='')
    old_value  = models.TextField(blank=True, default='')
    new_value  = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_ticket_audit_log'


# ════════════════════════════════════════════════════════════════
# AGENT MANAGEMENT (New in 0004)
# ════════════════════════════════════════════════════════════════
class Department(models.Model):
    ROUTING_CHOICES = [
        ('round_robin', 'Round Robin'),
        ('least_busy',  'Least Busy'),
        ('skill_match', 'Skill Match'),
    ]
    tenant       = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name         = models.CharField(max_length=100)
    slug         = models.SlugField(unique=True)
    routing_rule = models.CharField(max_length=20, choices=ROUTING_CHOICES, default='least_busy')
    auto_assign  = models.BooleanField(default=True)
    email_address = models.EmailField(blank=True, default='')
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_department'

    def __str__(self):
        return self.name


class SupportAgent(models.Model):
    ROLE_CHOICES = [
        ('agent',          'Agent'),
        ('senior_agent',   'Senior Agent'),
        ('supervisor',     'Supervisor'),
        ('manager',        'Manager'),
        ('account_manager','Account Manager'),
    ]
    user                   = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_agent')
    tenant                 = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    department             = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    role                   = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    is_active              = models.BooleanField(default=True, db_index=True)
    is_available           = models.BooleanField(default=True, db_index=True)
    max_concurrent_chats   = models.IntegerField(default=3)
    max_concurrent_tickets = models.IntegerField(default=10)
    skills                 = models.JSONField(default=list, blank=True)
    telegram_chat_id       = models.CharField(max_length=50, blank=True, default='')
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_agent'

    def __str__(self):
        return f'{self.user.username} [{self.role}]'


class AgentStatus(models.Model):
    STATUS_CHOICES = [
        ('online',  'Online'),
        ('busy',    'Busy'),
        ('away',    'Away'),
        ('offline', 'Offline'),
    ]
    agent          = models.OneToOneField(SupportAgent, on_delete=models.CASCADE, related_name='status_record')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline', db_index=True)
    last_seen      = models.DateTimeField(auto_now=True)
    status_message = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'support_agent_status'


class CannedResponse(models.Model):
    """Pre-written agent replies"""
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    shortcut    = models.CharField(max_length=50, unique=True)
    title       = models.CharField(max_length=200)
    content     = models.TextField()
    category    = models.CharField(max_length=50, blank=True, default='general')
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    usage_count = models.IntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['shortcut']
        db_table = 'support_canned_response'

    def __str__(self):
        return f'{self.shortcut} — {self.title}'


# ════════════════════════════════════════════════════════════════
# LIVE CHAT (New in 0004)
# ════════════════════════════════════════════════════════════════
class ChatSession(models.Model):
    STATUS_CHOICES = [('waiting', 'Waiting'), ('active', 'Active'), ('ended', 'Ended')]
    session_id     = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    tenant         = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    agent          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_chat_sessions')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting', db_index=True)
    queue_position = models.IntegerField(default=0)
    rating         = models.IntegerField(null=True, blank=True)
    rating_comment = models.TextField(blank=True, default='')
    started_at     = models.DateTimeField(auto_now_add=True)
    ended_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        db_table = 'support_chat_session'

    def __str__(self):
        return f'Chat {str(self.session_id)[:8]} — {self.user.username}'


class ChatMessage(models.Model):
    MSG_TYPES = [('text', 'Text'), ('image', 'Image'), ('file', 'File'), ('system', 'System')]
    session   = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content   = models.TextField()
    msg_type  = models.CharField(max_length=20, choices=MSG_TYPES, default='text')
    is_agent  = models.BooleanField(default=False)
    is_bot    = models.BooleanField(default=False)
    is_read   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        db_table = 'support_chat_message'


class ChatTranscript(models.Model):
    session      = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='transcript')
    content_text = models.TextField(blank=True, default='')
    content_html = models.TextField(blank=True, default='')
    generated_at = models.DateTimeField(auto_now_add=True)
    emailed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'support_chat_transcript'


# ════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE (New in 0004)
# ════════════════════════════════════════════════════════════════
class KBCategory(models.Model):
    tenant     = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name       = models.CharField(max_length=100)
    slug       = models.SlugField(unique=True)
    icon       = models.CharField(max_length=10, default='📄')
    description = models.TextField(blank=True, default='')
    parent     = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    sort_order = models.IntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']
        db_table = 'support_kb_category'

    def __str__(self):
        return self.name


class KBArticle(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')]
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    category    = models.ForeignKey(KBCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    author      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='kb_articles')
    title       = models.CharField(max_length=300)
    slug        = models.SlugField(unique=True)
    body        = models.TextField()
    summary     = models.TextField(blank=True, default='')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    is_public   = models.BooleanField(default=True)
    tags        = models.JSONField(default=list, blank=True)
    views_count = models.IntegerField(default=0)
    helpful_yes = models.IntegerField(default=0)
    helpful_no  = models.IntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_kb_article'

    def __str__(self):
        return self.title


# ════════════════════════════════════════════════════════════════
# SLA (New in 0004)
# ════════════════════════════════════════════════════════════════
class SLAPolicy(models.Model):
    tenant               = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name                 = models.CharField(max_length=100)
    priority_level       = models.CharField(max_length=20, default='medium')
    first_response_hours = models.IntegerField(default=8)
    resolution_hours     = models.IntegerField(default=48)
    business_hours_only  = models.BooleanField(default=True)
    is_active            = models.BooleanField(default=True, db_index=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_sla_policy'

    def __str__(self):
        return f'{self.name} [{self.priority_level}]'


class SLABreach(models.Model):
    BREACH_TYPES = [('first_response', 'First Response'), ('resolution', 'Resolution')]
    ticket       = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='sla_breaches')
    breach_type  = models.CharField(max_length=20, choices=BREACH_TYPES, db_index=True)
    due_at       = models.DateTimeField()
    breached_at  = models.DateTimeField(auto_now_add=True)
    overdue_hours = models.FloatField(default=0.0)
    notified     = models.BooleanField(default=False)
    resolved     = models.BooleanField(default=False)

    class Meta:
        ordering = ['-breached_at']
        db_table = 'support_sla_breach'


# ════════════════════════════════════════════════════════════════
# AUTOMATION (New in 0004)
# ════════════════════════════════════════════════════════════════
class AutomationRule(models.Model):
    tenant           = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name             = models.CharField(max_length=200)
    description      = models.TextField(blank=True, default='')
    trigger          = models.CharField(max_length=100, db_index=True)
    conditions_logic = models.CharField(max_length=10, default='AND')
    is_active        = models.BooleanField(default=True, db_index=True)
    priority         = models.IntegerField(default=0)
    run_count        = models.IntegerField(default=0)
    created_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority', 'name']
        db_table = 'support_automation_rule'


class AutomationCondition(models.Model):
    rule     = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='conditions')
    field    = models.CharField(max_length=100)
    operator = models.CharField(max_length=30)
    value    = models.TextField()

    class Meta:
        db_table = 'support_automation_condition'


class AutomationAction(models.Model):
    rule        = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=100)
    value       = models.TextField(blank=True, default='')
    order       = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        db_table = 'support_automation_action'


# ════════════════════════════════════════════════════════════════
# CPA SPECIFIC (New in 0004)
# ════════════════════════════════════════════════════════════════
class OfferDispute(models.Model):
    STATUS_CHOICES = [
        ('pending',       'Pending'),
        ('investigating', 'Investigating'),
        ('approved',      'Approved'),
        ('rejected',      'Rejected'),
        ('needs_proof',   'Needs Proof'),
    ]
    tenant              = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    user                = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_disputes')
    ticket              = models.ForeignKey(SupportTicket, on_delete=models.SET_NULL, null=True, blank=True)
    offer_id            = models.CharField(max_length=200, blank=True, default='', db_index=True)
    offer_name          = models.CharField(max_length=500, blank=True, default='')
    expected_amount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    click_id            = models.CharField(max_length=200, blank=True, default='')
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    verification_status = models.CharField(max_length=30, blank=True, default='unknown')
    confidence_score    = models.FloatField(default=0.0)
    agent_notes         = models.TextField(blank=True, default='')
    created_at          = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_offer_dispute'

    def __str__(self):
        return f'Dispute: {self.offer_id} [{self.status}]'


class WithdrawalDispute(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('reviewing', 'Reviewing'),
        ('resolved',  'Resolved'),
        ('rejected',  'Rejected'),
    ]
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawal_disputes')
    ticket           = models.ForeignKey(SupportTicket, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_id   = models.CharField(max_length=200, blank=True, default='')
    amount           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method   = models.CharField(max_length=50, blank=True, default='')
    account_number   = models.CharField(max_length=100, blank=True, default='')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    resolution_notes = models.TextField(blank=True, default='')
    created_at       = models.DateTimeField(auto_now_add=True)
    resolved_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_withdrawal_dispute'


class NetworkAnnouncement(models.Model):
    TYPE_CHOICES = [
        ('info', 'Info'), ('warning', 'Warning'),
        ('maintenance', 'Maintenance'), ('update', 'Update'),
    ]
    tenant         = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    title          = models.CharField(max_length=300)
    content        = models.TextField()
    ann_type       = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    is_active      = models.BooleanField(default=True, db_index=True)
    show_in_app    = models.BooleanField(default=True)
    show_in_portal = models.BooleanField(default=True)
    starts_at      = models.DateTimeField(null=True, blank=True)
    ends_at        = models.DateTimeField(null=True, blank=True)
    created_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_network_announcement'

    def __str__(self):
        return f'[{self.ann_type.upper()}] {self.title}'


class SupportNotificationLog(models.Model):
    CHANNEL_CHOICES = [
        ('email', 'Email'), ('sms', 'SMS'), ('push', 'Push'),
        ('telegram', 'Telegram'), ('whatsapp', 'WhatsApp'), ('slack', 'Slack'),
    ]
    STATUS_CHOICES = [('sent', 'Sent'), ('failed', 'Failed'), ('pending', 'Pending')]
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='support_notification_logs')
    ticket    = models.ForeignKey(SupportTicket, null=True, blank=True, on_delete=models.SET_NULL, related_name='notification_logs')
    channel   = models.CharField(max_length=20, choices=CHANNEL_CHOICES, db_index=True)
    event     = models.CharField(max_length=100, db_index=True)
    recipient = models.CharField(max_length=255, blank=True, default='')
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_msg = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_notification_log'