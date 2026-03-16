# api/support/admin.py
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html, mark_safe
from django.utils import timezone
from django.db.models import Count, Q, F, Avg, Min, Max
from django.core.exceptions import ValidationError
from django import forms
import json
from django.contrib.auth import get_user_model # Corrected import
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from datetime import timedelta, datetime
import csv
import io

from .models import SupportSettings, SupportTicket, FAQ

# Get the User model dynamically to avoid loading issues
User = get_user_model()

# ==================== Custom Forms ====================

class SupportSettingsForm(forms.ModelForm):
    class Meta:
        model = SupportSettings
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
            'support_hours_end': forms.TimeInput(attrs={'type': 'time', 'class': 'unfold-input'}),
            'telegram_group': forms.URLInput(attrs={
                'placeholder': 'https://t.me/your_group',
                'class': 'unfold-input'
            }),
            'telegram_admin': forms.URLInput(attrs={
                'placeholder': 'https://t.me/admin_username',
                'class': 'unfold-input'
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'placeholder': '+8801XXXXXXXXX',
                'class': 'unfold-input'
            }),
            'whatsapp_group': forms.URLInput(attrs={
                'placeholder': 'https://chat.whatsapp.com/group_code',
                'class': 'unfold-input'
            }),
            'facebook_page': forms.URLInput(attrs={
                'placeholder': 'https://facebook.com/your_page',
                'class': 'unfold-input'
            }),
            'email_support': forms.EmailInput(attrs={
                'placeholder': 'support@yourdomain.com',
                'class': 'unfold-input'
            }),
            'play_store_url': forms.URLInput(attrs={
                'placeholder': 'https://play.google.com/store/apps/details?id=com.yourapp',
                'class': 'unfold-input'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        support_hours_start = cleaned_data.get('support_hours_start')
        support_hours_end = cleaned_data.get('support_hours_end')
        
        if support_hours_start and support_hours_end:
            if support_hours_end <= support_hours_start:
                raise ValidationError({
                    'support_hours_end': 'Support end time must be after start time.'
                })
        
        latest_version_code = cleaned_data.get('latest_version_code')
        if latest_version_code and latest_version_code < 1:
            raise ValidationError({
                'latest_version_code': 'Version code must be at least 1.'
            })
        
        return cleaned_data


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
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
                'placeholder': 'Brief subject of your issue',
                'class': 'unfold-input'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'user' in self.fields:
            self.fields['user'].queryset = get_user_model().objects.all()
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        admin_response = cleaned_data.get('admin_response')
        
        if status in ['resolved', 'closed'] and (not admin_response or not admin_response.strip()):
            raise ValidationError({
                'admin_response': 'Please provide a response before resolving or closing the ticket.'
            })
        
        return cleaned_data


class FAQForm(forms.ModelForm):
    class Meta:
        model = FAQ
        fields = '__all__'
        widgets = {
            'question': forms.TextInput(attrs={
                'placeholder': 'Enter frequently asked question...',
                'class': 'unfold-input'
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

# ==================== Custom Filters ====================
# [Keeping your filter classes as they are...]

class TicketStatusFilter(admin.SimpleListFilter):
    title = 'Ticket Status'
    parameter_name = 'status'
    def lookups(self, request, model_admin):
        return [('open', '📥 Open'), ('in_progress', '⏳ In Progress'), ('resolved', '[OK] Resolved'), ('closed', '🔒 Closed')]
    def queryset(self, request, queryset):
        if self.value(): return queryset.filter(status=self.value())
        return queryset

class TicketPriorityFilter(admin.SimpleListFilter):
    title = 'Priority Level'
    parameter_name = 'priority'
    def lookups(self, request, model_admin):
        return [('urgent', '🚨 Urgent'), ('high', '🔴 High'), ('medium', '🟡 Medium'), ('low', '🟢 Low')]
    def queryset(self, request, queryset):
        if self.value(): return queryset.filter(priority=self.value())
        return queryset

class TicketCategoryFilter(admin.SimpleListFilter):
    title = 'Category'
    parameter_name = 'category'
    def lookups(self, request, model_admin):
        return [('payment', '[MONEY] Payment Issue'), ('coins', '🪙 Coins Not Added'), ('account', '👤 Account Problem'), ('technical', '[FIX] Technical Issue'), ('other', '❓ Other')]
    def queryset(self, request, queryset):
        if self.value(): return queryset.filter(category=self.value())
        return queryset

class ResponseStatusFilter(admin.SimpleListFilter):
    title = 'Response Status'
    parameter_name = 'has_response'
    def lookups(self, request, model_admin):
        return [('responded', '💬 Responded'), ('unresponded', '⏳ Awaiting Response')]
    def queryset(self, request, queryset):
        if self.value() == 'responded': return queryset.exclude(admin_response='').filter(admin_response__isnull=False)
        elif self.value() == 'unresponded': return queryset.filter(Q(admin_response='') | Q(admin_response__isnull=True))
        return queryset

class DateRangeFilter(admin.SimpleListFilter):
    title = 'Date Range'
    parameter_name = 'date_range'
    def lookups(self, request, model_admin):
        return [('today', '📅 Today'), ('yesterday', '📅 Yesterday'), ('week', '📅 This Week'), ('month', '📅 This Month'), ('last_month', '📅 Last Month')]
    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'today': return queryset.filter(created_at__date=today)
        elif self.value() == 'yesterday': return queryset.filter(created_at__date=today - timedelta(days=1))
        elif self.value() == 'week': return queryset.filter(created_at__date__gte=today - timedelta(days=7))
        elif self.value() == 'month': return queryset.filter(created_at__date__gte=today - timedelta(days=30))
        return queryset

class FAQCategoryFilter(admin.SimpleListFilter):
    title = 'Category'
    parameter_name = 'category'
    def lookups(self, request, model_admin):
        categories = FAQ.objects.values_list('category', flat=True).distinct()
        return [(cat, cat.title()) for cat in sorted(categories)]
    def queryset(self, request, queryset):
        if self.value(): return queryset.filter(category=self.value())
        return queryset

class FAQStatusFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'is_active'
    def lookups(self, request, model_admin):
        return [('active', '[OK] Active'), ('inactive', '[ERROR] Inactive')]
    def queryset(self, request, queryset):
        if self.value() == 'active': return queryset.filter(is_active=True)
        elif self.value() == 'inactive': return queryset.filter(is_active=False)
        return queryset

# ==================== Model Admins ====================

@admin.register(SupportSettings)
class SupportSettingsAdmin(ModelAdmin):
    form = SupportSettingsForm
    list_display = ['id', 'support_status_display', 'maintenance_status_display', 'update_status_display', 'support_hours_display', 'last_updated']
    
    def has_add_permission(self, request):
        return not SupportSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False

    # Display methods (Keeping your UI logic)
    def support_status_display(self, obj):
        color = "emerald" if obj.is_support_online else "rose"
        status = "Online" if obj.is_support_online else "Offline"
        icon = "[OK]" if obj.is_support_online else "[ERROR]"
        return format_html(f'<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-{color}-100 text-{color}-800 dark:bg-{color}-900 dark:text-{color}-200"><span class="mr-1">{icon}</span> Support {status}</span>')
    
    def maintenance_status_display(self, obj):
        if obj.maintenance_mode:
            return format_html('<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"><span class="mr-1">[WARN]</span> Maintenance Active</span>')
        return format_html('<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"><span class="mr-1">[OK]</span> Normal Operation</span>')

    def update_status_display(self, obj):
        return format_html(f'📱 v{obj.latest_version_name}')
    
    def support_hours_display(self, obj):
        return format_html(f'{obj.support_hours_start.strftime("%I:%M %p")} → {obj.support_hours_end.strftime("%I:%M %p")}')

    def last_updated(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M')

@admin.register(SupportTicket)
class SupportTicketAdmin(ModelAdmin):
    form = SupportTicketForm
    list_display = ['ticket_id', 'user_display', 'category_display', 'subject_preview', 'priority_display', 'status_display', 'created_at_display']
    list_filter = [TicketStatusFilter, TicketPriorityFilter, TicketCategoryFilter, ResponseStatusFilter, DateRangeFilter]
    search_fields = ['ticket_id', 'user__username', 'user__email', 'subject']
    readonly_fields = ['ticket_id', 'created_at', 'updated_at', 'resolved_at', 'admin_responded_at', 'screenshot_preview']
    list_select_related = ['user']
    
    # Check if User model has autocomplete enabled in its own admin
    # autocomplete_fields = ['user']
    row_id_fields = ['user'] 

    def user_display(self, obj):
        if obj.user:
            return format_html(f'<b>{obj.user.username}</b><br><small>{obj.user.email}</small>')
        return "-"

    def category_display(self, obj):
        return obj.get_category_display()

    def subject_preview(self, obj):
        return obj.subject[:30] + "..." if len(obj.subject) > 30 else obj.subject

    def priority_display(self, obj):
        return obj.get_priority_display()

    def status_display(self, obj):
        return obj.get_status_display()

    def created_at_display(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(f'<a href="{obj.screenshot.url}" target="_blank"><img src="{obj.screenshot.url}" width="150" /></a>')
        return "No screenshot"

    def save_model(self, request, obj, form, change):
        if obj.admin_response and not obj.admin_responded_at:
            obj.admin_responded_at = timezone.now()
        if obj.status in ['resolved', 'closed'] and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)

@admin.register(FAQ)
class FAQAdmin(ModelAdmin):
    form = FAQForm
    list_display = ['question', 'category', 'is_active', 'order']
    list_filter = [FAQCategoryFilter, FAQStatusFilter]
    
    
    
    # api/support/admin.py - শেষে এই কোড যোগ করুন

# ==================== FORCE REGISTER ALL MODELS ====================
try:
    from .models import FAQ, SupportSettings, SupportTicket
    
    registered_count = 0
    
    # Register FAQ
    if not admin.site.is_registered(FAQ):
        admin.site.register(FAQ, FAQAdmin)
        registered_count += 1
        print("[OK] Registered: FAQ")
    
    # Register SupportTicket
    if not admin.site.is_registered(SupportTicket):
        admin.site.register(SupportTicket, SupportTicketAdmin)
        registered_count += 1
        print("[OK] Registered: SupportTicket")
    
    # Register SupportSettings
    if not admin.site.is_registered(SupportSettings):
        # If SupportSettingsAdmin exists
        try:
            from .admin import SupportSettingsAdmin
            admin.site.register(SupportSettings, SupportSettingsAdmin)
        except:
            admin.site.register(SupportSettings)
        registered_count += 1
        print("[OK] Registered: SupportSettings")
    
    if registered_count > 0:
        print(f"[OK][OK][OK] {registered_count} support models registered!")
    else:
        print("[OK] All support models already registered")
        
except Exception as e:
    print(f"[ERROR] Support registration error: {e}")