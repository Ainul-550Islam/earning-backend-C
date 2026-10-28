# api/support/admin.py  — WORLD #1 FINAL
# Original forms, filters, display methods EXACTLY preserved
# New models added underneath
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from django import forms
from django.contrib.auth import get_user_model
import csv
from datetime import timedelta

from .models import (
    SupportSettings, SupportTicket, FAQ,
    TicketMessage, TicketAttachment, TicketTag, TicketRating, TicketSLA,
    TicketMerge, TicketAuditLog, Department, SupportAgent, AgentStatus,
    CannedResponse, ChatSession, ChatMessage, ChatTranscript,
    KBCategory, KBArticle, SLAPolicy, SLABreach,
    AutomationRule, AutomationCondition, AutomationAction,
    OfferDispute, WithdrawalDispute, NetworkAnnouncement,
    SupportNotificationLog,
)

User = get_user_model()


# ══════════════════════════════════════════════════════════════════
# ORIGINAL FORMS (EXACTLY from your uploaded admin.py)
# ══════════════════════════════════════════════════════════════════

class SupportSettingsForm(forms.ModelForm):
    class Meta:
        model  = SupportSettings
        fields = '__all__'
        widgets = {
            'maintenance_message': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Enter maintenance message to display to users...',
                'class': 'unfold-textarea'
            }),
            'update_message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Important update message for users...',
                'class': 'unfold-textarea'
            }),
            'support_hours_start': forms.TimeInput(attrs={'type': 'time', 'class': 'unfold-input'}),
            'support_hours_end':   forms.TimeInput(attrs={'type': 'time', 'class': 'unfold-input'}),
            'telegram_group': forms.URLInput(attrs={
                'placeholder': 'https://t.me/your_group', 'class': 'unfold-input'
            }),
            'telegram_admin': forms.URLInput(attrs={
                'placeholder': 'https://t.me/admin_username', 'class': 'unfold-input'
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'placeholder': '+8801XXXXXXXXX', 'class': 'unfold-input'
            }),
            'whatsapp_group': forms.URLInput(attrs={
                'placeholder': 'https://chat.whatsapp.com/group_code', 'class': 'unfold-input'
            }),
            'facebook_page': forms.URLInput(attrs={
                'placeholder': 'https://facebook.com/your_page', 'class': 'unfold-input'
            }),
            'email_support': forms.EmailInput(attrs={
                'placeholder': 'support@yourdomain.com', 'class': 'unfold-input'
            }),
            'play_store_url': forms.URLInput(attrs={
                'placeholder': 'https://play.google.com/store/apps/details?id=com.yourapp',
                'class': 'unfold-input'
            }),
        }

    def clean(self):
        cleaned_data        = super().clean()
        hours_start         = cleaned_data.get('support_hours_start')
        hours_end           = cleaned_data.get('support_hours_end')
        if hours_start and hours_end and hours_end <= hours_start:
            raise ValidationError({'support_hours_end': 'End time must be after start time.'})
        version_code = cleaned_data.get('latest_version_code')
        if version_code and version_code < 1:
            raise ValidationError({'latest_version_code': 'Version code must be at least 1.'})
        return cleaned_data


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model  = SupportTicket
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Please describe your issue in detail...',
                'class': 'unfold-textarea'
            }),
            'admin_response': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Enter your response to the user here...',
                'class': 'unfold-textarea'
            }),
            'subject': forms.TextInput(attrs={
                'placeholder': 'Brief subject of your issue', 'class': 'unfold-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'user' in self.fields:
            self.fields['user'].queryset = get_user_model().objects.all()

    def clean(self):
        cleaned_data   = super().clean()
        status         = cleaned_data.get('status')
        admin_response = cleaned_data.get('admin_response')
        if status in ('resolved', 'closed') and not (admin_response and admin_response.strip()):
            raise ValidationError({
                'admin_response': 'Please provide a response before resolving or closing the ticket.'
            })
        return cleaned_data


class FAQForm(forms.ModelForm):
    class Meta:
        model  = FAQ
        fields = '__all__'
        widgets = {
            'question': forms.TextInput(attrs={
                'placeholder': 'Enter frequently asked question...', 'class': 'unfold-input'
            }),
            'answer': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': 'Provide detailed answer...',
                'class': 'unfold-textarea'
            }),
            'category': forms.TextInput(attrs={
                'placeholder': 'general, payment, account, withdrawal, technical',
                'class': 'unfold-input'
            }),
        }


# ══════════════════════════════════════════════════════════════════
# ORIGINAL FILTERS (EXACTLY from your uploaded admin.py)
# ══════════════════════════════════════════════════════════════════

class TicketStatusFilter(admin.SimpleListFilter):
    title          = 'Ticket Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('open',         '📥 Open'),
            ('in_progress',  '⏳ In Progress'),
            ('waiting_user', '🟠 Waiting User'),
            ('resolved',     '✅ Resolved'),
            ('closed',       '🔒 Closed'),
            ('spam',         '🚫 Spam'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class TicketPriorityFilter(admin.SimpleListFilter):
    title          = 'Priority Level'
    parameter_name = 'priority'

    def lookups(self, request, model_admin):
        return [
            ('urgent', '🚨 Urgent'),
            ('high',   '🔴 High'),
            ('medium', '🟡 Medium'),
            ('low',    '🟢 Low'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(priority=self.value())
        return queryset


class TicketCategoryFilter(admin.SimpleListFilter):
    title          = 'Category'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        return [
            ('payment',    '💰 Payment Issue'),
            ('coins',      '🪙 Coins Not Added'),
            ('account',    '👤 Account Problem'),
            ('technical',  '🔧 Technical Issue'),
            ('withdrawal', '💸 Withdrawal Issue'),
            ('fraud',      '🚨 Fraud/Security'),
            ('kyc',        '🪪 KYC Verification'),
            ('referral',   '👥 Referral Issue'),
            ('offer',      '🎯 Offer Issue'),
            ('other',      '❓ Other'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category=self.value())
        return queryset


class ResponseStatusFilter(admin.SimpleListFilter):
    title          = 'Response Status'
    parameter_name = 'has_response'

    def lookups(self, request, model_admin):
        return [
            ('responded',   '💬 Responded'),
            ('unresponded', '⏳ Awaiting Response'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'responded':
            return queryset.exclude(admin_response='').filter(admin_response__isnull=False)
        if self.value() == 'unresponded':
            return queryset.filter(Q(admin_response='') | Q(admin_response__isnull=True))
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    title          = 'Date Range'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return [
            ('today',      '📅 Today'),
            ('yesterday',  '📅 Yesterday'),
            ('week',       '📅 This Week'),
            ('month',      '📅 This Month'),
        ]

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        if self.value() == 'yesterday':
            return queryset.filter(created_at__date=today - timedelta(days=1))
        if self.value() == 'week':
            return queryset.filter(created_at__date__gte=today - timedelta(days=7))
        if self.value() == 'month':
            return queryset.filter(created_at__date__gte=today - timedelta(days=30))
        return queryset


class FAQCategoryFilter(admin.SimpleListFilter):
    title          = 'Category'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        cats = FAQ.objects.values_list('category', flat=True).distinct()
        return [(c, c.title()) for c in sorted(cats) if c]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category=self.value())
        return queryset


class FAQStatusFilter(admin.SimpleListFilter):
    title          = 'Status'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return [('active', '✅ Active'), ('inactive', '❌ Inactive')]

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset


# ══════════════════════════════════════════════════════════════════
# INLINES
# ══════════════════════════════════════════════════════════════════

class TicketMessageInline(TabularInline):
    model          = TicketMessage
    extra          = 0
    fields         = ['sender', 'content', 'is_agent', 'is_internal', 'created_at']
    readonly_fields= ['created_at']
    ordering       = ['created_at']
    show_change_link = True


class TicketAttachmentInline(TabularInline):
    model          = TicketAttachment
    extra          = 0
    fields         = ['filename', 'mime_type', 'size_bytes', 'created_at']
    readonly_fields= ['created_at']


class AutomationConditionInline(TabularInline):
    model = AutomationCondition
    extra = 1


class AutomationActionInline(TabularInline):
    model   = AutomationAction
    extra   = 1
    ordering = ['order']


# ══════════════════════════════════════════════════════════════════
# MODEL ADMINS — ORIGINAL ONES (preserved exactly)
# ══════════════════════════════════════════════════════════════════

@admin.register(SupportSettings)
class SupportSettingsAdmin(ModelAdmin):
    form         = SupportSettingsForm
    list_display = [
        'id', 'support_status_display', 'maintenance_status_display',
        'update_status_display', 'support_hours_display',
    ]

    def has_add_permission(self, request):
        return not SupportSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def support_status_display(self, obj):
        color  = 'emerald' if obj.is_support_online else 'rose'
        status = 'Online'  if obj.is_support_online else 'Offline'
        icon   = '✅' if obj.is_support_online else '❌'
        return format_html(
            '<span style="color:{}">{} Support {}</span>',
            'green' if obj.is_support_online else 'red', icon, status
        )
    support_status_display.short_description = 'Support Status'

    def maintenance_status_display(self, obj):
        if obj.maintenance_mode:
            return format_html('<span style="color:orange;font-weight:bold">⚠ Maintenance Active</span>')
        return format_html('<span style="color:green">✅ Normal Operation</span>')
    maintenance_status_display.short_description = 'Maintenance'

    def update_status_display(self, obj):
        return format_html('📱 v{}', obj.latest_version_name)
    update_status_display.short_description = 'App Version'

    def support_hours_display(self, obj):
        return format_html(
            '{} → {}',
            obj.support_hours_start.strftime('%I:%M %p'),
            obj.support_hours_end.strftime('%I:%M %p'),
        )
    support_hours_display.short_description = 'Support Hours'


@admin.register(SupportTicket)
class SupportTicketAdmin(ModelAdmin):
    form           = SupportTicketForm
    list_display   = [
        'ticket_id', 'user_display', 'category_display', 'subject_preview',
        'priority_display', 'status_display', 'has_response_display',
        'escalated', 'created_at_display',
    ]
    list_filter    = [
        TicketStatusFilter, TicketPriorityFilter, TicketCategoryFilter,
        ResponseStatusFilter, DateRangeFilter, 'escalated',
    ]
    search_fields  = ['ticket_id', 'user__username', 'user__email', 'subject']
    readonly_fields = [
        'ticket_id', 'created_at', 'updated_at', 'resolved_at',
        'admin_responded_at', 'first_response_at', 'screenshot_preview',
    ]
    inlines        = [TicketMessageInline, TicketAttachmentInline]
    date_hierarchy = 'created_at'
    ordering       = ['-created_at']
    list_select_related = ['user', 'assigned_to']

    def user_display(self, obj):
        if obj.user:
            return format_html('<b>{}</b><br><small>{}</small>', obj.user.username, obj.user.email)
        return '-'
    user_display.short_description = 'User'

    def category_display(self, obj):
        return obj.get_category_display()
    category_display.short_description = 'Category'

    def subject_preview(self, obj):
        s = obj.subject or ''
        return s[:30] + '...' if len(s) > 30 else s
    subject_preview.short_description = 'Subject'

    def priority_display(self, obj):
        colors = {'urgent': '#dc2626', 'high': '#ea580c', 'medium': '#ca8a04', 'low': '#16a34a'}
        color  = colors.get(obj.priority or '', '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, (obj.priority or '').upper()
        )
    priority_display.short_description = 'Priority'

    def status_display(self, obj):
        emojis = {
            'open': '🟡', 'in_progress': '🔵', 'waiting_user': '🟠',
            'resolved': '✅', 'closed': '⛔', 'spam': '🚫',
        }
        return format_html('{} {}', emojis.get(obj.status, ''), obj.get_status_display())
    status_display.short_description = 'Status'

    def has_response_display(self, obj):
        return bool(obj.admin_response)
    has_response_display.boolean = True
    has_response_display.short_description = 'Replied'

    def created_at_display(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_display.short_description = 'Created'

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" width="150"/></a>',
                obj.screenshot.url, obj.screenshot.url
            )
        return 'No screenshot'
    screenshot_preview.short_description = 'Screenshot'

    def save_model(self, request, obj, form, change):
        if obj.admin_response and not obj.admin_responded_at:
            obj.admin_responded_at = timezone.now()
        if obj.status in ('resolved', 'closed') and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(FAQ)
class FAQAdmin(ModelAdmin):
    form           = FAQForm
    list_display   = ['question_preview', 'category', 'is_active', 'order', 'view_count', 'helpful_display']
    list_filter    = [FAQCategoryFilter, FAQStatusFilter]
    search_fields  = ['question', 'answer']
    readonly_fields = ['helpful_yes', 'helpful_no', 'view_count', 'created_at']
    ordering       = ['order', '-created_at']

    def question_preview(self, obj):
        q = obj.question or ''
        return q[:60] + '…' if len(q) > 60 else q
    question_preview.short_description = 'Question'

    def helpful_display(self, obj):
        total = (obj.helpful_yes or 0) + (obj.helpful_no or 0)
        if not total:
            return '—'
        return f'{round((obj.helpful_yes or 0)/total*100)}% ({obj.helpful_yes}/{total})'
    helpful_display.short_description = 'Helpful'


# ══════════════════════════════════════════════════════════════════
# NEW MODEL ADMINS (World #1 additions)
# ══════════════════════════════════════════════════════════════════

@admin.register(SupportAgent)
class SupportAgentAdmin(ModelAdmin):
    list_display  = ['user', 'role', 'department', 'is_active', 'is_available', 'max_concurrent_tickets', 'created_at']
    list_filter   = ['role', 'is_active', 'is_available', 'department']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']


@admin.register(AgentStatus)
class AgentStatusAdmin(ModelAdmin):
    list_display  = ['agent', 'status', 'last_seen', 'status_message']
    list_filter   = ['status']
    readonly_fields = ['last_seen']


@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'routing_rule', 'auto_assign', 'is_active', 'email_address']
    list_filter  = ['routing_rule', 'is_active', 'auto_assign']
    search_fields = ['name', 'email_address']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CannedResponse)
class CannedResponseAdmin(ModelAdmin):
    list_display  = ['shortcut', 'title', 'category', 'usage_count', 'is_active', 'created_at']
    list_filter   = ['category', 'is_active']
    search_fields = ['shortcut', 'title', 'content']
    readonly_fields = ['usage_count', 'created_at']


@admin.register(ChatSession)
class ChatSessionAdmin(ModelAdmin):
    list_display  = ['session_id_short', 'user', 'agent', 'status', 'rating', 'started_at', 'ended_at']
    list_filter   = ['status']
    search_fields = ['user__username', 'agent__username']
    readonly_fields = ['session_id', 'started_at']

    def session_id_short(self, obj):
        return str(obj.session_id)[:8] + '...'
    session_id_short.short_description = 'Session ID'


@admin.register(KBCategory)
class KBCategoryAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'parent', 'sort_order', 'is_active', 'article_count']
    list_filter  = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def article_count(self, obj):
        return obj.articles.filter(status='published').count()
    article_count.short_description = 'Articles'


@admin.register(KBArticle)
class KBArticleAdmin(ModelAdmin):
    list_display  = ['title', 'category', 'author', 'status', 'is_public', 'views_count', 'helpful_ratio', 'created_at']
    list_filter   = ['status', 'is_public', 'category']
    search_fields = ['title', 'body', 'summary']
    readonly_fields = ['views_count', 'helpful_yes', 'helpful_no', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('title',)}

    def helpful_ratio(self, obj):
        total = (obj.helpful_yes or 0) + (obj.helpful_no or 0)
        if not total:
            return '—'
        return f'{round((obj.helpful_yes or 0)/total*100)}%'
    helpful_ratio.short_description = 'Helpful'


@admin.register(SLAPolicy)
class SLAPolicyAdmin(ModelAdmin):
    list_display = ['name', 'priority_level', 'first_response_hours', 'resolution_hours', 'business_hours_only', 'is_active']
    list_filter  = ['priority_level', 'is_active', 'business_hours_only']


@admin.register(SLABreach)
class SLABreachAdmin(ModelAdmin):
    list_display  = ['ticket', 'breach_type', 'overdue_hours', 'resolved', 'notified', 'breached_at']
    list_filter   = ['breach_type', 'resolved', 'notified']
    search_fields = ['ticket__ticket_id']
    readonly_fields = ['breached_at']


@admin.register(AutomationRule)
class AutomationRuleAdmin(ModelAdmin):
    list_display  = ['name', 'trigger', 'conditions_logic', 'is_active', 'priority', 'run_count', 'created_at']
    list_filter   = ['trigger', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['run_count', 'created_at']
    inlines       = [AutomationConditionInline, AutomationActionInline]


@admin.register(OfferDispute)
class OfferDisputeAdmin(ModelAdmin):
    list_display  = ['id', 'user', 'offer_id', 'expected_amount', 'status', 'confidence_score', 'verification_status', 'created_at']
    list_filter   = ['status', 'verification_status']
    search_fields = ['offer_id', 'click_id', 'user__username']
    readonly_fields = ['created_at', 'confidence_score', 'verification_status']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'ticket')


@admin.register(WithdrawalDispute)
class WithdrawalDisputeAdmin(ModelAdmin):
    list_display  = ['id', 'user', 'transaction_id', 'amount', 'payment_method', 'status', 'created_at']
    list_filter   = ['status', 'payment_method']
    search_fields = ['transaction_id', 'user__username', 'account_number']
    readonly_fields = ['created_at']


@admin.register(NetworkAnnouncement)
class NetworkAnnouncementAdmin(ModelAdmin):
    list_display  = ['title', 'type', 'is_active', 'show_in_app', 'show_in_portal', 'starts_at', 'ends_at']
    list_filter   = ['type', 'is_active', 'show_in_app']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at']


@admin.register(SupportNotificationLog)
class SupportNotificationLogAdmin(ModelAdmin):
    list_display  = ['event', 'channel', 'status', 'user', 'recipient', 'created_at']
    list_filter   = ['channel', 'status', 'event']
    search_fields = ['recipient', 'event', 'user__username']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        return False  # Logs are auto-created, not manually


@admin.register(TicketTag)
class TicketTagAdmin(ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']


# ══════════════════════════════════════════════════════════════════
# REGISTER ON CUSTOM ADMIN SITE IF AVAILABLE
# ══════════════════════════════════════════════════════════════════

def _force_register_support():
    """Register on custom admin_panel if available."""
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (SupportSettings, SupportSettingsAdmin),
            (SupportTicket,   SupportTicketAdmin),
            (FAQ,             FAQAdmin),
            (OfferDispute,    OfferDisputeAdmin),
            (SupportAgent,    SupportAgentAdmin),
        ]
        registered = 0
        for model, model_admin in pairs:
            try:
                if not modern_site.is_registered(model):
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception:
                pass
        if registered:
            import logging
            logging.getLogger(__name__).info(f'Support: {registered} models on custom admin')
    except Exception:
        pass