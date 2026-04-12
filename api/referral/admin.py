# admin.py
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html, mark_safe
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.core.exceptions import ValidationError
from django import forms
import json
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from datetime import timedelta, datetime
import csv
import io

from .models import ReferralSettings, Referral, ReferralEarning
from api.users.models import User


# ==================== Custom Forms ====================

class ReferralSettingsForm(forms.ModelForm):
    class Meta:
        model = ReferralSettings
        fields = '__all__'
        widgets = {
            'direct_signup_bonus': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'placeholder': 'Amount in points',
                'class': 'unfold-input'
            }),
            'referrer_signup_bonus': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'placeholder': 'Amount in points',
                'class': 'unfold-input'
            }),
            'lifetime_commission_rate': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': 'Percentage (0-100)',
                'class': 'unfold-input'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        lifetime_commission_rate = cleaned_data.get('lifetime_commission_rate')
        
        # Validate commission rate
        if lifetime_commission_rate is not None:
            if lifetime_commission_rate < 0:
                raise ValidationError({
                    'lifetime_commission_rate': 'Commission rate cannot be negative.'
                })
            if lifetime_commission_rate > 100:
                raise ValidationError({
                    'lifetime_commission_rate': 'Commission rate cannot exceed 100%.'
                })
        
        return cleaned_data


class ReferralForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = '__all__'
        widgets = {
            'referrer': forms.Select(attrs={'class': 'unfold-select'}),
            'referred_user': forms.Select(attrs={'class': 'unfold-select'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        referrer = cleaned_data.get('referrer')
        referred_user = cleaned_data.get('referred_user')
        
        # Validate that referrer and referred user are different
        if referrer and referred_user and referrer == referred_user:
            raise ValidationError('A user cannot refer themselves.')
        
        # Check if referral already exists
        if referrer and referred_user:
            existing = Referral.objects.filter(
                referrer=referrer,
                referred_user=referred_user
            ).exists()
            if existing and not self.instance.pk:
                raise ValidationError('This referral relationship already exists.')
        
        return cleaned_data


class ReferralEarningForm(forms.ModelForm):
    class Meta:
        model = ReferralEarning
        fields = '__all__'
        widgets = {
            'amount': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'unfold-input'
            }),
            'commission_rate': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'max': '100',
                'class': 'unfold-input'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        commission_rate = cleaned_data.get('commission_rate')
        
        # Validate amounts
        if amount and amount < 0:
            raise ValidationError({'amount': 'Amount cannot be negative.'})
        
        if commission_rate and (commission_rate < 0 or commission_rate > 100):
            raise ValidationError({
                'commission_rate': 'Commission rate must be between 0% and 100%.'
            })
        
        return cleaned_data


# ==================== Custom Filters ====================

class DateRangeFilter(admin.SimpleListFilter):
    title = 'Date Range'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return [
            ('today', '📅 Today'),
            ('yesterday', '📅 Yesterday'),
            ('week', '📅 This Week'),
            ('month', '📅 This Month'),
            ('year', '📅 This Year'),
        ]
    
    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        elif self.value() == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif self.value() == 'week':
            week_ago = today - timedelta(days=7)
            return queryset.filter(created_at__date__gte=week_ago)
        elif self.value() == 'month':
            month_ago = today - timedelta(days=30)
            return queryset.filter(created_at__date__gte=month_ago)
        elif self.value() == 'year':
            year_ago = today - timedelta(days=365)
            return queryset.filter(created_at__date__gte=year_ago)
        return queryset


class CommissionRangeFilter(admin.SimpleListFilter):
    title = 'Commission Amount'
    parameter_name = 'commission_range'
    
    def lookups(self, request, model_admin):
        return [
            ('small', '[MONEY] Small (< 100)'),
            ('medium', '[MONEY][MONEY] Medium (100-500)'),
            ('large', '[MONEY][MONEY][MONEY] Large (500+)'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'small':
            return queryset.filter(amount__lt=100)
        elif self.value() == 'medium':
            return queryset.filter(amount__range=[100, 500])
        elif self.value() == 'large':
            return queryset.filter(amount__gt=500)
        return queryset


class ReferralStatusFilter(admin.SimpleListFilter):
    title = 'Bonus Status'
    parameter_name = 'signup_bonus_given'
    
    def lookups(self, request, model_admin):
        return [
            ('paid', '[OK] Bonus Paid'),
            ('unpaid', '[ERROR] Bonus Unpaid'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'paid':
            return queryset.filter(signup_bonus_given=True)
        elif self.value() == 'unpaid':
            return queryset.filter(signup_bonus_given=False)
        return queryset


class TopReferrersFilter(admin.SimpleListFilter):
    title = 'Top Referrers'
    parameter_name = 'top_referrers'
    
    def lookups(self, request, model_admin):
        return [
            ('top10', '[WIN] Top 10 Referrers'),
            ('top50', '[WIN] Top 50 Referrers'),
            ('active', '🎯 Active This Month'),
        ]
    
    def queryset(self, request, queryset):
        # This filter modifies the queryset to show top referrers
        if self.value() == 'top10':
            top_referrers = Referral.objects.values('referrer').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            referrer_ids = [item['referrer'] for item in top_referrers]
            return queryset.filter(referrer_id__in=referrer_ids)
        elif self.value() == 'top50':
            top_referrers = Referral.objects.values('referrer').annotate(
                count=Count('id')
            ).order_by('-count')[:50]
            referrer_ids = [item['referrer'] for item in top_referrers]
            return queryset.filter(referrer_id__in=referrer_ids)
        elif self.value() == 'active':
            month_ago = timezone.now() - timedelta(days=30)
            active_referrers = Referral.objects.filter(
                created_at__gte=month_ago
            ).values('referrer').distinct()
            referrer_ids = [item['referrer'] for item in active_referrers]
            return queryset.filter(referrer_id__in=referrer_ids)
        return queryset


class CommissionRateFilter(admin.SimpleListFilter):
    title = 'Commission Rate'
    parameter_name = 'commission_rate'
    
    def lookups(self, request, model_admin):
        return [
            ('low', '📉 Low (< 5%)'),
            ('standard', '[STATS] Standard (5-15%)'),
            ('high', '📈 High (> 15%)'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(commission_rate__lt=5)
        elif self.value() == 'standard':
            return queryset.filter(commission_rate__range=[5, 15])
        elif self.value() == 'high':
            return queryset.filter(commission_rate__gt=15)
        return queryset


# ==================== Inline Classes ====================

class ReferralEarningInline(admin.TabularInline):
    model = ReferralEarning
    extra = 0
    can_delete = False
    readonly_fields = ['created_at', 'commission_calculated']
    fields = ['amount', 'commission_rate', 'commission_calculated', 'source_task', 'created_at']
    
    def commission_calculated(self, obj):
        if obj.amount and obj.commission_rate:
            commission = (obj.amount * obj.commission_rate) / 100
            return format_html(
                '<span class="font-medium text-green-600 dark:text-green-400">${:.2f}</span>',
                commission
            )
        return '-'
    commission_calculated.short_description = 'Commission'


class ReferralInline(admin.TabularInline):
    model = Referral
    fk_name = 'referrer'
    extra = 0
    can_delete = False
    readonly_fields = ['created_at', 'total_earned_display', 'status_display']
    fields = ['referred_user', 'signup_bonus_given', 'total_earned_display', 'created_at']
    
    def total_earned_display(self, obj):
        return format_html(
            '<span class="font-medium text-green-600 dark:text-green-400">${:.2f}</span>',
            obj.total_commission_earned
        )
    total_earned_display.short_description = 'Total Earned'
    
    def status_display(self, obj):
        if obj.signup_bonus_given:
            return format_html(
                '<span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium '
                'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">'
                '[OK] Paid</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium '
            'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">'
            '⏳ Pending</span>'
        )
    status_display.short_description = 'Status'


# ==================== Model Admins ====================

@admin.register(ReferralSettings)
class ReferralSettingsAdmin(ModelAdmin):
    form = ReferralSettingsForm
    
    list_display = ['id', 'bonus_settings_display', 'commission_rate_display',
                   'status_display', 'last_updated']
    
    fieldsets = (
        ('Bonus Settings', {
            'fields': (
                ('direct_signup_bonus', 'referrer_signup_bonus'),
                'lifetime_commission_rate',
            ),
            'classes': ('unfold-card',),
            'description': 'Configure referral bonus amounts and commission rates',
        }),
        ('System Status', {
            'fields': ('is_active',),
            'classes': ('unfold-card',),
            'description': 'Enable or disable the referral system',
        }),
        ('Statistics', {
            'fields': ('stats_display',),
            'classes': ('unfold-card', 'collapse'),
            'description': 'System statistics (auto-calculated)',
        }),
    )
    
    readonly_fields = ['stats_display', 'last_updated']
    
    def has_add_permission(self, request):
        """Prevent multiple settings instances"""
        return not ReferralSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False
    
    def bonus_settings_display(self, obj):
        return format_html(
            '<div class="space-y-2">'
            '<div class="flex items-center space-x-2">'
            '<span class="text-green-600 dark:text-green-400">👤</span>'
            '<span class="font-medium">Direct Bonus:</span>'
            '<span class="text-green-600 dark:text-green-400 font-bold">${}</span>'
            '</div>'
            '<div class="flex items-center space-x-2">'
            '<span class="text-blue-600 dark:text-blue-400">🤝</span>'
            '<span class="font-medium">Referrer Bonus:</span>'
            '<span class="text-blue-600 dark:text-blue-400 font-bold">${}</span>'
            '</div>'
            '</div>',
            obj.direct_signup_bonus,
            obj.referrer_signup_bonus
        )
    bonus_settings_display.short_description = 'Bonus Settings'
    
    def commission_rate_display(self, obj):
        return format_html(
            '<div class="flex items-center space-x-2">'
            '<span class="text-purple-600 dark:text-purple-400">📈</span>'
            '<span class="font-medium">Lifetime:</span>'
            '<span class="text-purple-600 dark:text-purple-400 font-bold">{}%</span>'
            '</div>',
            obj.lifetime_commission_rate
        )
    commission_rate_display.short_description = 'Commission'
    
    def status_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium '
                'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">'
                '<span class="mr-1">[OK]</span> Active</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium '
            'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200">'
            '<span class="mr-1">[ERROR]</span> Inactive</span>'
        )
    status_display.short_description = 'Status'
    
    def stats_display(self, obj):
        """Display referral system statistics"""
        total_referrals = Referral.objects.count()
        total_commission = ReferralEarning.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        top_referrer = Referral.objects.values('referrer__username').annotate(
            count=Count('id'),
            total_earned=Sum('total_commission_earned')
        ).order_by('-count').first()
        
        today_referrals = Referral.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        return format_html(
            '<div class="space-y-3">'
            '<div class="grid grid-cols-2 gap-4">'
            '<div class="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg">'
            '<div class="text-sm text-gray-500 dark:text-gray-400">Total Referrals</div>'
            '<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{}</div>'
            '</div>'
            '<div class="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg">'
            '<div class="text-sm text-gray-500 dark:text-gray-400">Total Commission</div>'
            '<div class="text-2xl font-bold text-green-600 dark:text-green-400">${:.2f}</div>'
            '</div>'
            '</div>'
            '<div class="text-sm text-gray-600 dark:text-gray-400">'
            '<div>[WIN] Top Referrer: <span class="font-medium">{}</span> ({} referrals, ${:.2f} earned)</div>'
            '<div>[STATS] Today\'s Referrals: <span class="font-medium">{}</span></div>'
            '</div>'
            '</div>',
            total_referrals,
            total_commission,
            top_referrer['referrer__username'] if top_referrer else 'None',
            top_referrer['count'] if top_referrer else 0,
            top_referrer['total_earned'] if top_referrer else 0,
            today_referrals
        )
    stats_display.short_description = 'System Statistics'
    
    def last_updated(self, obj):
        # This method is for list display, but ReferralSettings doesn't have updated_at
        # We'll use a placeholder or implement it differently
        return format_html(
            '<span class="text-gray-500 dark:text-gray-400 text-sm">Always active</span>'
        )
    last_updated.short_description = 'Status'
    
    actions = ['activate_system', 'deactivate_system']
    
    def activate_system(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, '[OK] Referral system activated', messages.SUCCESS)
    activate_system.short_description = "Activate referral system"
    
    def deactivate_system(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, '[ERROR] Referral system deactivated', messages.WARNING)
    deactivate_system.short_description = "Deactivate referral system"


@admin.register(Referral)
class ReferralAdmin(ModelAdmin):
    form = ReferralForm
    
    list_display = ['referrer_display', 'referred_user_display', 'status_display',
                   'total_earned_display', 'created_at_display', 'actions_display']
    
    list_filter = [ReferralStatusFilter, DateRangeFilter, TopReferrersFilter]
    
    search_fields = ['referrer__username', 'referrer__email',
                    'referred_user__username', 'referred_user__email']
    
    readonly_fields = ['created_at', 'total_earned_calculated', 'referral_link_display']
    
    list_select_related = ['referrer', 'referred_user']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    # autocomplete_fields = ['referrer', 'referred_user']
    raw_id_fields = ['referrer', 'referred_user']
    
    inlines = [ReferralEarningInline]
    
    fieldsets = (
        ('Referral Relationship', {
            'fields': (
                ('referrer', 'referred_user'),
                'referral_link_display',
            ),
            'classes': ('unfold-card',),
        }),
        ('Bonus Status', {
            'fields': (
                'signup_bonus_given',
                'total_commission_earned',
                'total_earned_calculated',
            ),
            'classes': ('unfold-card',),
        }),
        ('System Information', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    def referrer_display(self, obj):
        if obj.referrer:
            return format_html(
                '<div class="flex items-center space-x-2">'
                '<div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 '
                'flex items-center justify-center text-white font-semibold text-sm">'
                '{}'
                '</div>'
                '<div>'
                '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
                '<div class="text-xs text-gray-500 dark:text-gray-400">Referrer</div>'
                '</div>'
                '</div>',
                obj.referrer.username[0].upper(),
                obj.referrer.username
            )
        return '-'
    referrer_display.short_description = 'Referrer'
    
    def referred_user_display(self, obj):
        if obj.referred_user:
            return format_html(
                '<div class="flex items-center space-x-2">'
                '<div class="w-8 h-8 rounded-full bg-gradient-to-br from-green-500 to-teal-600 '
                'flex items-center justify-center text-white font-semibold text-sm">'
                '{}'
                '</div>'
                '<div>'
                '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
                '<div class="text-xs text-gray-500 dark:text-gray-400">Referred User</div>'
                '</div>'
                '</div>',
                obj.referred_user.username[0].upper(),
                obj.referred_user.username
            )
        return '-'
    referred_user_display.short_description = 'Referred User'
    
    def status_display(self, obj):
        if obj.signup_bonus_given:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">'
                '<span class="mr-1">[OK]</span> Bonus Paid</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">'
            '<span class="mr-1">⏳</span> Pending</span>'
        )
    status_display.short_description = 'Status'
    
    def total_earned_display(self, obj):
        return format_html(
            '<div class="flex items-center space-x-2">'
            '<span class="text-green-600 dark:text-green-400">[MONEY]</span>'
            '<span class="font-bold text-green-600 dark:text-green-400">${:.2f}</span>'
            '</div>',
            obj.total_commission_earned
        )
    total_earned_display.short_description = 'Total Earned'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    def total_earned_calculated(self, obj):
        return self.total_earned_display(obj)
    total_earned_calculated.short_description = 'Total Commission Earned'
    
    def referral_link_display(self, obj):
        if obj.referrer:
            settings = ReferralSettings.objects.first()
            if settings:
                direct_bonus = settings.direct_signup_bonus
                referrer_bonus = settings.referrer_signup_bonus
                
                return format_html(
                    '<div class="space-y-2 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">'
                    '<div class="text-sm font-medium text-gray-700 dark:text-gray-300">Referral Benefits:</div>'
                    '<div class="grid grid-cols-2 gap-3">'
                    '<div class="bg-green-50 dark:bg-green-900/30 p-3 rounded">'
                    '<div class="text-xs text-gray-500 dark:text-gray-400">Direct Signup Bonus</div>'
                    '<div class="font-bold text-green-600 dark:text-green-400">${}</div>'
                    '</div>'
                    '<div class="bg-blue-50 dark:bg-blue-900/30 p-3 rounded">'
                    '<div class="text-xs text-gray-500 dark:text-gray-400">Referrer Bonus</div>'
                    '<div class="font-bold text-blue-600 dark:text-blue-400">${}</div>'
                    '</div>'
                    '</div>'
                    '</div>',
                    direct_bonus,
                    referrer_bonus
                )
        return format_html(
            '<div class="text-sm text-gray-500 dark:text-gray-400 italic">No referral settings configured</div>'
        )
    referral_link_display.short_description = 'Referral Benefits'
    
    def actions_display(self, obj):
        return format_html(
            '<div class="flex space-x-2">'
            '<a href="{}" class="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300" '
            'title="View Details">👁️</a>'
            '<a href="{}" class="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300" '
            'title="Edit">✏️</a>'
            '</div>',
            f'/admin/referral/referral/{obj.id}/change/',
            f'/admin/referral/referral/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    actions = ['mark_bonus_paid', 'mark_bonus_unpaid', 'calculate_total_earnings',
              'export_referrals_csv', 'generate_referral_report']
    
    def mark_bonus_paid(self, request, queryset):
        updated = queryset.filter(signup_bonus_given=False).update(signup_bonus_given=True)
        self.message_user(request, f'[OK] {updated} referral bonuses marked as paid', messages.SUCCESS)
    mark_bonus_paid.short_description = "Mark bonus as paid"
    
    def mark_bonus_unpaid(self, request, queryset):
        updated = queryset.filter(signup_bonus_given=True).update(signup_bonus_given=False)
        self.message_user(request, f'[ERROR] {updated} referral bonuses marked as unpaid', messages.WARNING)
    mark_bonus_unpaid.short_description = "Mark bonus as unpaid"
    
    def calculate_total_earnings(self, request, queryset):
        """Recalculate total earnings for selected referrals"""
        for referral in queryset:
            total = ReferralEarning.objects.filter(referral=referral).aggregate(
                total=Sum('amount')
            )['total'] or 0
            referral.total_commission_earned = total
            referral.save()
        
        self.message_user(request, f'[MONEY] Total earnings recalculated for {queryset.count()} referrals', messages.SUCCESS)
    calculate_total_earnings.short_description = "Recalculate earnings"
    
    def export_referrals_csv(self, request, queryset):
        """Export selected referrals to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="referrals_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Referrer', 'Referrer Email', 'Referred User', 'Referred Email',
            'Signup Bonus Paid', 'Total Commission Earned', 'Created At'
        ])
        
        for referral in queryset:
            writer.writerow([
                referral.referrer.username,
                referral.referrer.email,
                referral.referred_user.username,
                referral.referred_user.email,
                'Yes' if referral.signup_bonus_given else 'No',
                referral.total_commission_earned,
                referral.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_referrals_csv.short_description = "Export to CSV"


@admin.register(ReferralEarning)
class ReferralEarningAdmin(ModelAdmin):
    form = ReferralEarningForm
    
    list_display = ['earning_id', 'referrer_display', 'referred_user_display',
                   'amount_display', 'commission_rate_display', 'commission_calculated',
                   'source_display', 'created_at_display']
    
    list_filter = [CommissionRangeFilter, CommissionRateFilter, DateRangeFilter]
    
    search_fields = ['referrer__username', 'referrer__email',
                    'referred_user__username', 'referred_user__email',
                    'referral__id']
    
    readonly_fields = ['created_at', 'earning_id', 'commission_calculated_field']
    
    list_select_related = ['referrer', 'referred_user', 'referral', 'source_task']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    # autocomplete_fields = ['referral', 'referrer', 'referred_user', 'source_task']
    raw_id_fields = ['referral', 'referrer', 'referred_user', 'source_task']
    
    fieldsets = (
        ('Earning Information', {
            'fields': (
                'earning_id',
                ('referral', 'source_task'),
            ),
            'classes': ('unfold-card',),
        }),
        ('User Information', {
            'fields': (
                ('referrer', 'referred_user'),
            ),
            'classes': ('unfold-card',),
        }),
        ('Commission Details', {
            'fields': (
                ('amount', 'commission_rate'),
                'commission_calculated_field',
            ),
            'classes': ('unfold-card',),
        }),
        ('System Information', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    def earning_id(self, obj):
        return f"EARN-{obj.id:06d}"
    earning_id.short_description = 'Earning ID'
    
    def referrer_display(self, obj):
        if obj.referrer:
            return format_html(
                '<div class="flex items-center space-x-2">'
                '<div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 '
                'flex items-center justify-center text-white font-semibold text-sm">'
                '{}'
                '</div>'
                '<div>'
                '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
                '<div class="text-xs text-gray-500 dark:text-gray-400">Referrer</div>'
                '</div>'
                '</div>',
                obj.referrer.username[0].upper(),
                obj.referrer.username
            )
        return '-'
    referrer_display.short_description = 'Referrer'
    
    def referred_user_display(self, obj):
        if obj.referred_user:
            return format_html(
                '<div class="flex items-center space-x-2">'
                '<div class="w-8 h-8 rounded-full bg-gradient-to-br from-green-500 to-teal-600 '
                'flex items-center justify-center text-white font-semibold text-sm">'
                '{}'
                '</div>'
                '<div>'
                '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
                '<div class="text-xs text-gray-500 dark:text-gray-400">Referred User</div>'
                '</div>'
                '</div>',
                obj.referred_user.username[0].upper(),
                obj.referred_user.username
            )
        return '-'
    referred_user_display.short_description = 'Referred User'
    
    def amount_display(self, obj):
        return format_html(
            '<div class="flex items-center space-x-2">'
            '<span class="text-green-600 dark:text-green-400">[MONEY]</span>'
            '<span class="font-bold text-green-600 dark:text-green-400">${:.2f}</span>'
            '</div>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def commission_rate_display(self, obj):
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">'
            '{}%</span>',
            obj.commission_rate
        )
    commission_rate_display.short_description = 'Rate'
    
    def commission_calculated(self, obj):
        commission = (obj.amount * obj.commission_rate) / 100
        return format_html(
            '<div class="flex items-center space-x-2">'
            '<span class="text-blue-600 dark:text-blue-400">💵</span>'
            '<span class="font-bold text-blue-600 dark:text-blue-400">${:.2f}</span>'
            '</div>',
            commission
        )
    commission_calculated.short_description = 'Commission'
    
    def commission_calculated_field(self, obj):
        return self.commission_calculated(obj)
    commission_calculated_field.short_description = 'Commission Amount'
    
    def source_display(self, obj):
        if obj.source_task:
            return format_html(
                '<div class="flex items-center space-x-2">'
                '<span class="text-amber-600 dark:text-amber-400">[NOTE]</span>'
                '<div class="text-sm truncate max-w-xs" title="{}">{}</div>'
                '</div>',
                obj.source_task.title,
                obj.source_task.title[:30] + '...' if len(obj.source_task.title) > 30 else obj.source_task.title
            )
        return format_html(
            '<span class="text-gray-400 dark:text-gray-500 italic">Direct</span>'
        )
    source_display.short_description = 'Source'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    actions = ['export_earnings_csv', 'recalculate_commissions', 'generate_commission_report']
    
    def export_earnings_csv(self, request, queryset):
        """Export selected earnings to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="referral_earnings_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Earning ID', 'Referrer', 'Referred User', 'Amount', 'Commission Rate',
            'Commission Amount', 'Source Task', 'Created At'
        ])
        
        for earning in queryset:
            commission = (earning.amount * earning.commission_rate) / 100
            writer.writerow([
                f"EARN-{earning.id:06d}",
                earning.referrer.username,
                earning.referred_user.username,
                earning.amount,
                f"{earning.commission_rate}%",
                commission,
                earning.source_task.title if earning.source_task else 'Direct',
                earning.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_earnings_csv.short_description = "Export earnings to CSV"


# ==================== Custom Dashboard Views ====================

class ReferralDashboardView(ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_site.admin_view(self.dashboard_view), name='referral_dashboard'),
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='referral_analytics'),
            path('leaderboard/', self.admin_site.admin_view(self.leaderboard_view), name='referral_leaderboard'),
            path('stats-api/', self.admin_site.admin_view(self.stats_api), name='referral_stats_api'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Main referral dashboard"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get referral settings
        settings = ReferralSettings.objects.first()
        
        # Overall statistics
        total_referrals = Referral.objects.count()
        total_commission = ReferralEarning.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Today's statistics
        today_referrals = Referral.objects.filter(created_at__date=today).count()
        today_commission = ReferralEarning.objects.filter(
            created_at__date=today
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Top referrers
        top_referrers = Referral.objects.values(
            'referrer__username', 'referrer__email'
        ).annotate(
            referral_count=Count('id'),
            total_earned=Sum('total_commission_earned')
        ).order_by('-referral_count')[:10]
        
        # Recent referrals
        recent_referrals = Referral.objects.select_related(
            'referrer', 'referred_user'
        ).order_by('-created_at')[:10]
        
        # Recent earnings
        recent_earnings = ReferralEarning.objects.select_related(
            'referrer', 'referred_user'
        ).order_by('-created_at')[:10]
        
        # Status breakdown
        paid_referrals = Referral.objects.filter(signup_bonus_given=True).count()
        pending_referrals = Referral.objects.filter(signup_bonus_given=False).count()
        
        # Calculate conversion rate (if we have user stats)
        total_users = User.objects.count()
        referral_rate = (total_referrals / total_users * 100) if total_users > 0 else 0
        
        context = {
            'today': today,
            'week_ago': week_ago,
            'month_ago': month_ago,
            
            # Settings
            'settings': settings,
            
            # Overall stats
            'total_referrals': total_referrals,
            'total_commission': total_commission,
            'referral_rate': round(referral_rate, 1),
            
            # Today's stats
            'today_referrals': today_referrals,
            'today_commission': today_commission,
            
            # Status breakdown
            'paid_referrals': paid_referrals,
            'pending_referrals': pending_referrals,
            
            # Top performers
            'top_referrers': top_referrers,
            
            # Recent activity
            'recent_referrals': recent_referrals,
            'recent_earnings': recent_earnings,
            
            # Additional stats
            'avg_commission_per_referral': total_commission / total_referrals if total_referrals > 0 else 0,
            'active_referrers': Referral.objects.values('referrer').distinct().count(),
        }
        
        return render(request, 'admin/referral/dashboard.html', context)
    
    def analytics_view(self, request):
        """Advanced analytics view"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Daily referral trends
        daily_data = []
        for i in range(30, -1, -1):
            date = end_date - timedelta(days=i)
            stats = Referral.objects.filter(created_at__date=date).aggregate(
                count=Count('id'),
                paid=Count('id', filter=Q(signup_bonus_given=True)),
                total_earned=Sum('total_commission_earned')
            )
            
            daily_data.append({
                'date': date,
                'count': stats['count'] or 0,
                'paid': stats['paid'] or 0,
                'total_earned': stats['total_earned'] or 0,
                'conversion_rate': round((stats['paid'] / stats['count'] * 100) if stats['count'] else 0, 1),
            })
        
        # Commission analysis
        commission_analysis = ReferralEarning.objects.filter(
            created_at__date__gte=start_date
        ).aggregate(
            total_amount=Sum('amount'),
            avg_amount=Avg('amount'),
            max_amount=Max('amount'),
            avg_rate=Avg('commission_rate'),
        )
        
        # Top performing referrers (detailed)
        top_performers = Referral.objects.filter(
            created_at__date__gte=start_date
        ).values(
            'referrer__username', 'referrer__email'
        ).annotate(
            referral_count=Count('id'),
            paid_count=Count('id', filter=Q(signup_bonus_given=True)),
            total_earned=Sum('total_commission_earned'),
            avg_earning_per_referral=Avg('total_commission_earned')
        ).order_by('-total_earned')[:10]
        
        # Earnings by source
        earnings_by_source = ReferralEarning.objects.filter(
            created_at__date__gte=start_date
        ).values('source_task__title').annotate(
            total_earned=Sum('amount'),
            count=Count('id')
        ).order_by('-total_earned')
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'daily_data': daily_data,
            'commission_analysis': commission_analysis,
            'top_performers': top_performers,
            'earnings_by_source': earnings_by_source,
        }
        
        return render(request, 'admin/referral/analytics.html', context)
    
    def leaderboard_view(self, request):
        """Referral leaderboard view"""
        # All-time leaderboard
        all_time_leaderboard = Referral.objects.values(
            'referrer__username', 'referrer__email', 'referrer__date_joined'
        ).annotate(
            referral_count=Count('id'),
            paid_referrals=Count('id', filter=Q(signup_bonus_given=True)),
            total_earned=Sum('total_commission_earned'),
            avg_earning=Avg('total_commission_earned')
        ).order_by('-referral_count')
        
        # Monthly leaderboard
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_leaderboard = Referral.objects.filter(
            created_at__gte=month_start
        ).values(
            'referrer__username', 'referrer__email'
        ).annotate(
            referral_count=Count('id'),
            total_earned=Sum('total_commission_earned')
        ).order_by('-referral_count')[:20]
        
        # Weekly leaderboard
        week_ago = timezone.now() - timedelta(days=7)
        weekly_leaderboard = Referral.objects.filter(
            created_at__gte=week_ago
        ).values(
            'referrer__username', 'referrer__email'
        ).annotate(
            referral_count=Count('id'),
            total_earned=Sum('total_commission_earned')
        ).order_by('-referral_count')[:20]
        
        context = {
            'all_time_leaderboard': all_time_leaderboard,
            'monthly_leaderboard': monthly_leaderboard,
            'weekly_leaderboard': weekly_leaderboard,
            'month_start': month_start,
            'week_ago': week_ago,
        }
        
        return render(request, 'admin/referral/leaderboard.html', context)
    
    def stats_api(self, request):
        """API endpoint for referral statistics (for charts)"""
        stats = {
            'total_referrals': Referral.objects.count(),
            'total_commission': ReferralEarning.objects.aggregate(
                total=Sum('amount')
            )['total'] or 0,
            'active_referrers': Referral.objects.values('referrer').distinct().count(),
            'pending_bonuses': Referral.objects.filter(signup_bonus_given=False).count(),
            'paid_bonuses': Referral.objects.filter(signup_bonus_given=True).count(),
        }
        return JsonResponse(stats)


# Register custom views
# admin.site.register_view('referral_dashboard', 'Referral Dashboard', view=ReferralDashboardView().dashboard_view)
# Register custom views
# admin.site.register_view('referral_dashboard', 'Referral Dashboard', view=ReferralDashboardView().dashboard_view)  # [ERROR] এই লাইন ডিলিট করুন

# পরিবর্তে এই কোডটি যোগ করুন:
class ReferralAdminSite(admin.AdminSite):
    site_header = "Referral Administration"
    site_title = "Referral Admin"
    index_title = "Referral Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()

        view_instance = ReferralDashboardView
        
        custom_urls = [
            path('referral_dashboard/', self.admin_view(view_instance.dashboard_view), name='referral_dashboard'),
            path('referral_analytics/', self.admin_view(view_instance.analytics_view), name='referral_analytics'),
            path('referral_leaderboard/', self.admin_view(view_instance.leaderboard_view), name='referral_leaderboard'),
            path('referral_stats_api/', self.admin_view(view_instance.stats_api), name='referral_stats_api'),
        ]
        return custom_urls + urls

# কাস্টম অ্যাডমিন সাইট তৈরি
referral_admin_site = ReferralAdminSite(name='referral_admin')

# এখন আপনার মডেলগুলো এই কাস্টম সাইটে রেজিস্টার করুন:
referral_admin_site.register(ReferralSettings, ReferralSettingsAdmin)
referral_admin_site.register(Referral, ReferralAdmin)
referral_admin_site.register(ReferralEarning, ReferralEarningAdmin)

# Add custom context for badges in sidebar
def get_referral_admin_context(request):
    """Add custom context for admin badges"""
    context = {}
    
    if request.user.is_staff:
        # Add pending bonuses count for badge
        pending_bonuses = Referral.objects.filter(signup_bonus_given=False).count()
        context['pending_referral_bonuses'] = pending_bonuses
        
        # Add today's referrals for badge
        today_referrals = Referral.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        context['today_referrals_count'] = today_referrals
    
    return context

# admin.site.add_context_processor(get_referral_admin_context)  # [ERROR] এই লাইন ডিলিট করুন

# পরিবর্তে এই কোডটি যোগ করুন:
from django.template.context_processors import static

# কাস্টম context processor যোগ করার আরেকটি উপায়
def custom_admin_context(request):
    """Custom context for admin"""
    context = {}
    
    if request.user.is_staff:
        try:
            # Add pending bonuses count for badge
            from .models import Referral
            pending_bonuses = Referral.objects.filter(signup_bonus_given=False).count()
            context['pending_referral_bonuses'] = pending_bonuses
            
            # Add today's referrals for badge
            from django.utils import timezone
            today_referrals = Referral.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
            context['today_referrals_count'] = today_referrals
        except Exception:
            # If models aren't ready yet, just return empty context
            pass
    
    return context





# api/referral/admin.py - একদম শেষে এই কোড যোগ করুন

# ==================== FORCE REGISTER IN DEFAULT ADMIN ====================
from django.contrib import admin

try:
    # Check if already registered
    if not admin.site.is_registered(Referral):
        admin.site.register(Referral, ReferralAdmin)
        print("[OK] Registered: Referral in default admin")
    
    if not admin.site.is_registered(ReferralEarning):
        admin.site.register(ReferralEarning, ReferralEarningAdmin)
        print("[OK] Registered: ReferralEarning in default admin")
    
    if not admin.site.is_registered(ReferralSettings):
        admin.site.register(ReferralSettings, ReferralSettingsAdmin)
        print("[OK] Registered: ReferralSettings in default admin")
    
    print("[OK][OK][OK] All referral models registered in default admin")
    
except Exception as e:
    print(f"[ERROR] Error registering in default admin: {e}")




def _force_register_referral():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(ReferralSettings, ReferralSettingsAdmin), (Referral, ReferralAdmin), (ReferralEarning, ReferralEarningAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] referral registered {registered} models")
    except Exception as e:
        print(f"[WARN] referral: {e}")
