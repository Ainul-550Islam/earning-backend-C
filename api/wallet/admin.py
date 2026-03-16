# api/wallet/admin.py - প্রথম লাইন হিসেবে যোগ করুন
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDay
from django.core.exceptions import ValidationError
from django import forms
from django.contrib.admin import SimpleListFilter
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
import json
from django.urls import reverse
from django.db.models import F
from django.contrib import messages
from datetime import datetime, timedelta
import csv
from .models import UserPaymentMethod, WalletTransaction, WalletWebhookLog, Wallet, Withdrawal, WithdrawalRequest

# ==================== CUSTOM FILTER CLASSES ====================

class VerifiedMethodFilter(SimpleListFilter):
    """Filter payment methods by verification status"""
    title = 'Verification Status'
    parameter_name = 'verification_status'
    
    def lookups(self, request, model_admin):
        return [
            ('verified', '[OK] Verified'),
            ('unverified', '[ERROR] Unverified'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'verified':
            return queryset.filter(is_verified=True)
        elif self.value() == 'unverified':
            return queryset.filter(is_verified=False)
        return queryset


class TransactionTypeFilter(SimpleListFilter):
    """Filter transactions by type"""
    title = 'Transaction Type'
    parameter_name = 'type'
    
    def lookups(self, request, model_admin):
        return [
            ('earning', 'Earning'),
            ('reward', 'Reward'),
            ('referral', 'Referral Commission'),
            ('bonus', 'Bonus'),
            ('withdrawal', 'Withdrawal'),
            ('admin_credit', 'Admin Credit'),
            ('admin_debit', 'Admin Debit'),
            ('freeze', 'Freeze'),
            ('unfreeze', 'Unfreeze'),
            ('reversal', 'Reversal'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        return queryset


class TransactionStatusFilter(SimpleListFilter):
    """Filter transactions by status"""
    title = 'Transaction Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('completed', 'Completed'),
            ('rejected', 'Rejected'),
            ('reversed', 'Reversed'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class MethodTypeFilter(SimpleListFilter):
    """Filter payment methods by type"""
    title = 'Method Type'
    parameter_name = 'method_type'
    
    def lookups(self, request, model_admin):
        return [
            ('bkash', 'bKash'),
            ('nagad', 'Nagad'),
            ('rocket', 'Rocket'),
            ('upay', 'Upay'),
            ('bank', 'Bank Account'),
            ('card', 'Debit/Credit Card'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(method_type=self.value())
        return queryset


class WebhookTypeFilter(SimpleListFilter):
    """Filter webhook logs by type"""
    title = 'Webhook Type'
    parameter_name = 'webhook_type'
    
    def lookups(self, request, model_admin):
        return [
            ('bkash', 'bKash'),
            ('nagad', 'Nagad'),
            ('stripe', 'Stripe'),
            ('paypal', 'PayPal'),
            ('sslcommerz', 'SSLCommerz'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(webhook_type=self.value())
        return queryset


# ==================== CUSTOM FORMS ====================

class UserPaymentMethodForm(forms.ModelForm):
    """Custom form for PaymentMethod with validation"""
    class Meta:
        model = UserPaymentMethod
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        method_type = cleaned_data.get('method_type')
        account_number = cleaned_data.get('account_number')
        
        # Check for duplicate payment method
        if UserPaymentMethod.objects.filter(
            user=user, 
            method_type=method_type, 
            account_number=account_number
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError('This payment method already exists for this user.')
        
        # If setting as primary, unset other primaries for this user
        if cleaned_data.get('is_primary'):
            UserPaymentMethod.objects.filter(
                user=user,
                is_primary=True
            ).exclude(pk=self.instance.pk).update(is_primary=False)
        
        # Validate account number format based on method type
        if method_type in ['bkash', 'nagad', 'rocket'] and account_number and not account_number.startswith('01'):
            raise ValidationError(f'{method_type.title()} account number must start with 01')
        
        return cleaned_data


class TransactionForm(forms.ModelForm):
    """Custom form for Transaction with validation"""
    class Meta:
        model = WalletTransaction
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        
        # Amount validation
        if amount and amount <= 0:
            raise ValidationError('Amount must be greater than zero.')
        
        return cleaned_data


class WalletWebhookLogForm(forms.ModelForm):
    """Custom form for WalletWebhookLog"""
    class Meta:
        model = WalletWebhookLog
        fields = '__all__'
        widgets = {
            'payload': forms.Textarea(attrs={'rows': 6}),
            'headers': forms.Textarea(attrs={'rows': 4}),
        }


# ==================== PAYMENT METHOD ADMIN ====================

@admin.register(UserPaymentMethod)
class UserPaymentMethodAdmin(ModelAdmin):
    """Admin interface for UserPaymentMethod"""
    form = UserPaymentMethodForm
    
    list_display = (
        'user_display',
        'method_type_display',
        'account_number_masked',
        'account_name',
        'is_verified',      # ← সরাসরি ফিল্ড (custom method নয়)
        'is_primary',       # ← সরাসরি ফিল্ড (custom method নয়)
        'verification_badge',
        'primary_badge',
        'created_at_display',
        'actions_display'
    )
    
    list_filter = (
        MethodTypeFilter,
        VerifiedMethodFilter,
        'is_primary',
        'created_at'
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'account_number',
        'account_name',
        'method_type'
    )
    
    # list_editable = ('is_verified', 'is_primary')
    readonly_fields = (
        'created_at',
        'updated_at',
        'verified_at',
    )
    
    list_per_page = 25
    # autocomplete_fields = ['user']
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user',
                'method_type',
                'account_number',
                'account_name',
            ),
            'classes': ('unfold-card',),
        }),
        ('Verification & Settings', {
            'fields': (
                'is_verified',
                'is_primary',
                'verified_at',
            ),
            'classes': ('unfold-card',),
        }),
        ('Bank/Card Details (if applicable)', {
            'fields': (
                'bank_name',
                'branch_name',
                'routing_number',
                'card_last_four',
                'card_expiry',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
    )
    
    actions = [
        'verify_selected_methods',
        'set_as_primary',
        
    ]
    
    # Custom display methods
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<div class="flex items-center space-x-2">'
                '<div>'
                '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
                '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
                '</div>'
                '</div>',
                obj.user.username,
                obj.user.email
            )
        return '-'
    user_display.short_description = 'User'
    
    def method_type_display(self, obj):
        method_config = {
            'bkash': {'icon': '[MONEY]', 'color': 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200'},
            'nagad': {'icon': '💳', 'color': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'},
            'rocket': {'icon': '[START]', 'color': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'},
            'upay': {'icon': '📱', 'color': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'},
            'bank': {'icon': '🏦', 'color': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'},
            'card': {'icon': '💳', 'color': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200'},
        }
        
        config = method_config.get(obj.method_type, {'icon': '💳', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_method_type_display()
        )
    method_type_display.short_description = 'Method Type'
    
    def account_number_masked(self, obj):
        if obj.account_number:
            masked = '•' * (len(obj.account_number) - 4) + obj.account_number[-4:]
            return format_html(
                '<span class="font-mono tracking-wider text-sm">{}</span>',
                masked
            )
        return '-'
    account_number_masked.short_description = 'Account Number'
    
    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">'
                '<span class="mr-1">[OK]</span> Verified</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200">'
            '<span class="mr-1">[ERROR]</span> Unverified</span>'
        )
    verification_badge.short_description = 'Verification'
    
    def primary_badge(self, obj):
        if obj.is_primary:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">'
                '<span class="mr-1">★</span> Primary</span>'
            )
        return format_html('<span class="text-gray-400 dark:text-gray-500">-</span>')
    primary_badge.short_description = 'Primary'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    def actions_display(self, obj):
        return format_html(
            '<div class="flex space-x-2">'
            '<a href="{}" class="text-blue-600 hover:text-blue-800" title="View">👁️</a>'
            '<a href="{}" class="text-green-600 hover:text-green-800" title="Edit">✏️</a>'
            '</div>',
            f'/admin/wallet/paymentmethod/{obj.id}/change/',
            f'/admin/wallet/paymentmethod/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    # Action methods
    def verify_selected_methods(self, request, queryset):
        """Verify selected payment methods"""
        updated = queryset.update(
            is_verified=True,
            verified_at=timezone.now()
        )
        self.message_user(request, f'[OK] {updated} payment methods verified successfully.', level='SUCCESS')
    verify_selected_methods.short_description = "Verify selected methods"
    
    def set_as_primary(self, request, queryset):
        """Set selected methods as primary"""
        for method in queryset:
            # Unset other primaries for this user
            UserPaymentMethod.objects.filter(
                user=method.user,
                is_primary=True
            ).update(is_primary=False)
            
            # Set this as primary
            method.is_primary = True
            method.save()
        
        self.message_user(request, f'★ {queryset.count()} methods set as primary.', level='SUCCESS')
    set_as_primary.short_description = "Set as primary method"


# ==================== TRANSACTION ADMIN ====================

@admin.register(WalletTransaction)
class WalletTransactionAdmin(ModelAdmin):
    """Admin interface for Transaction"""
    form = TransactionForm
    
    list_display = (
        'transaction_id_display',
        'wallet_user_display',
        'transaction_type_display',
        'amount_display',
        'status_display',
        'balance_before_display',
        'balance_after_display',
        'created_at_display',
        'actions_display'
    )
    
    list_filter = (
        TransactionTypeFilter,
        TransactionStatusFilter,
        'created_at'
    )
    
    search_fields = (
        'transaction_id',
        'reference_id',
        'wallet__user__username',
        'wallet__user__email',
        'description'
    )
    
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'approved_at',
        'balance_before',
        'balance_after',
        'created_by',
        'approved_by',
    )
    
    list_per_page = 30
    # autocomplete_fields = ['wallet', 'created_by', 'approved_by', 'reversed_by']
    raw_id_fields = ['wallet',]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Information', {
            'fields': (
                'transaction_id',
                'wallet',
                'type',
                'amount',
                'status',
                'description',
            ),
            'classes': ('unfold-card',),
        }),
        ('References', {
            'fields': (
                'reference_id',
                'reference_type',
                'metadata',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Balance Snapshot', {
            'fields': (
                'balance_before',
                'balance_after',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Double Entry Ledger', {
            'fields': (
                'debit_account',
                'credit_account',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Reversal Information', {
            'fields': (
                'is_reversed',
                'reversed_by',
                'reversed_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Audit Information', {
            'fields': (
                'created_by',
                'approved_by',
                'approved_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
    )
    
    actions = [
        'approve_transactions',
        'reject_transactions',
    ]
    
    # Custom display methods
    def transaction_id_display(self, obj):
        return format_html(
            '<span class="font-mono text-sm">{}</span>',
            str(obj.transaction_id)[:8]
        )
    transaction_id_display.short_description = 'Transaction ID'
    
    def wallet_user_display(self, obj):
        if obj.wallet and obj.wallet.user:
            return format_html(
                '<div class="text-sm">'
                '<div class="font-medium">{}</div>'
                '<div class="text-xs text-gray-500">{}</div>'
                '</div>',
                obj.wallet.user.username,
                obj.wallet.user.email[:20] + '...' if len(obj.wallet.user.email) > 20 else obj.wallet.user.email
            )
        return '-'
    wallet_user_display.short_description = 'User'
    
    def transaction_type_display(self, obj):
        type_config = {
            'earning': {'icon': '[MONEY]', 'color': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'},
            'withdrawal': {'icon': '⬆️', 'color': 'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200'},
            'bonus': {'icon': '🎁', 'color': 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'},
            'referral': {'icon': '👥', 'color': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'},
            'reward': {'icon': '[WIN]', 'color': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'},
            'freeze': {'icon': '🔒', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'},
            'unfreeze': {'icon': '🔓', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'},
            'reversal': {'icon': '↩️', 'color': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'},
        }
        
        config = type_config.get(obj.type, {'icon': '💳', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_type_display()
        )
    transaction_type_display.short_description = 'Type'
    
    def amount_display(self, obj):
        amount_color = 'text-emerald-600' if obj.amount > 0 else 'text-rose-600'
        sign = '+' if obj.amount > 0 else ''
        
        return format_html(
            '<div class="text-right">'
            '<div class="font-medium {}">{}{:,.2f}</div>'
            '</div>',
            amount_color,
            sign,
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        status_config = {
            'pending': {'icon': '⏳', 'color': 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'},
            'approved': {'icon': '[OK]', 'color': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'},
            'completed': {'icon': '[OK]', 'color': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'},
            'rejected': {'icon': '[ERROR]', 'color': 'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200'},
            'reversed': {'icon': '↩️', 'color': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'},
        }
        
        config = status_config.get(obj.status, {'icon': '❓', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def balance_before_display(self, obj):
        return format_html(
            '<div class="text-right text-sm">'
            '<div class="font-mono">{:,.2f}</div>'
            '<div class="text-xs text-gray-500">Before</div>'
            '</div>',
            obj.balance_before
        )
    balance_before_display.short_description = 'Balance Before'
    
    def balance_after_display(self, obj):
        return format_html(
            '<div class="text-right text-sm">'
            '<div class="font-mono">{:,.2f}</div>'
            '<div class="text-xs text-gray-500">After</div>'
            '</div>',
            obj.balance_after
        )
    balance_after_display.short_description = 'Balance After'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    def actions_display(self, obj):
        return format_html(
            '<div class="flex space-x-2">'
            '<a href="{}" class="text-blue-600 hover:text-blue-800" title="View">👁️</a>'
            '<a href="{}" class="text-green-600 hover:text-green-800" title="Edit">✏️</a>'
            '</div>',
            f'/admin/wallet/transaction/{obj.id}/change/',
            f'/admin/wallet/transaction/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    # Action methods
    def approve_transactions(self, request, queryset):
        """Approve selected transactions"""
        approved_count = 0
        for transaction in queryset.filter(status='pending'):
            try:
                transaction.approve(request.user)
                approved_count += 1
            except Exception as e:
                self.message_user(request, f'Error approving transaction {transaction.transaction_id}: {str(e)}', level='ERROR')
        
        self.message_user(request, f'[OK] {approved_count} transactions approved successfully.', level='SUCCESS')
    approve_transactions.short_description = "Approve selected transactions"
    
    def reject_transactions(self, request, queryset):
        """Reject selected transactions"""
        rejected_count = 0
        for transaction in queryset.filter(status='pending'):
            transaction.reject('Rejected by admin')
            rejected_count += 1
        
        self.message_user(request, f'[ERROR] {rejected_count} transactions rejected.', level='SUCCESS')
    reject_transactions.short_description = "Reject selected transactions"


# ==================== PAYMENT WEBHOOK LOG ADMIN ====================

@admin.register(WalletWebhookLog)
class WalletWebhookLogAdmin(ModelAdmin):
    """Admin interface for WalletWebhookLog"""
    form = WalletWebhookLogForm
    
    list_display = (
        'webhook_type_display',
        'event_type',
        'reference_id_display',
        'status_badge',
        'payload_preview',
        'received_at_display',
        'actions_display'
    )
    
    list_filter = (
        WebhookTypeFilter,
        'event_type',
        'is_processed',
        'received_at'
    )
    
    search_fields = (
        'reference_id',
        'transaction_reference',
        'event_type',
        'payload'
    )
    
    readonly_fields = (
        'webhook_type',
        'event_type',
        'payload',
        'headers',
        'reference_id',
        'received_at',
        'processed_at',
        'processing_error'
    )
    
    list_per_page = 25
    
    fieldsets = (
        ('Webhook Information', {
            'fields': (
                'webhook_type',
                'event_type',
                ('reference_id', 'transaction_reference'),
            ),
            'classes': ('unfold-card',),
        }),
        ('Payload & Headers', {
            'fields': (
                'payload',
                'headers',
            ),
            'classes': ('unfold-card',),
        }),
        ('Processing Status', {
            'fields': (
                'is_processed',
                'processing_error',
                'processed_at',
            ),
            'classes': ('unfold-card',),
        }),
        ('Timestamps', {
            'fields': (
                'received_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
    )
    
    actions = [
        'mark_as_processed',
        'mark_as_unprocessed',
        'delete_old_logs',
    ]
    
    # Custom display methods
    def webhook_type_display(self, obj):
        webhook_config = {
            'bkash': {'icon': '[MONEY]', 'color': 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200'},
            'nagad': {'icon': '💳', 'color': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'},
            'stripe': {'icon': '💳', 'color': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200'},
            'paypal': {'icon': '🌐', 'color': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'},
            'sslcommerz': {'icon': '💳', 'color': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'},
        }
        
        config = webhook_config.get(obj.webhook_type, {'icon': '🌐', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_webhook_type_display()
        )
    webhook_type_display.short_description = 'Webhook Type'
    
    def reference_id_display(self, obj):
        if obj.reference_id:
            return format_html(
                '<span class="font-mono text-sm">{}</span>',
                obj.reference_id[:15] + '...' if len(obj.reference_id) > 15 else obj.reference_id
            )
        return '-'
    reference_id_display.short_description = 'Reference ID'
    
    def status_badge(self, obj):
        if obj.is_processed:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">'
                '<span class="mr-1">[OK]</span> Processed</span>'
            )
        else:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">'
                '<span class="mr-1">⏳</span> Pending</span>'
            )
    status_badge.short_description = 'Status'
    
    def payload_preview(self, obj):
        if obj.payload:
            try:
                payload_str = str(obj.payload)[:50]
                return format_html(
                    '<span class="text-sm text-gray-600" title="{}">{}...</span>',
                    str(obj.payload),
                    payload_str
                )
            except:
                return format_html('<span class="text-sm text-gray-400">-</span>')
        return '-'
    payload_preview.short_description = 'Payload Preview'
    
    def received_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.received_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.received_at).strftime('%H:%M')
        )
    received_at_display.short_description = 'Received'
    
    def actions_display(self, obj):
        return format_html(
            '<div class="flex space-x-2">'
            '<a href="{}" class="text-blue-600 hover:text-blue-800" title="View">👁️</a>'
            '<a href="{}" class="text-green-600 hover:text-green-800" title="Edit">✏️</a>'
            '</div>',
            f'/admin/wallet/paymentwebhooklog/{obj.id}/change/',
            f'/admin/wallet/paymentwebhooklog/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    # Action methods
    def mark_as_processed(self, request, queryset):
        """Mark selected webhook logs as processed"""
        updated = queryset.update(
            is_processed=True,
            processed_at=timezone.now()
        )
        self.message_user(request, f'[OK] {updated} webhook logs marked as processed.', level='SUCCESS')
    mark_as_processed.short_description = "Mark as processed"
    
    def delete_old_logs(self, request, queryset):
        """Delete webhook logs older than 30 days"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        old_logs = queryset.filter(received_at__lt=thirty_days_ago)
        count = old_logs.count()
        old_logs.delete()
        self.message_user(request, f'[DELETE] {count} old webhook logs deleted.', level='SUCCESS')
    delete_old_logs.short_description = "Delete logs older than 30 days"


# ==================== WALLET ADMIN ====================

@admin.register(Wallet)
class WalletAdmin(ModelAdmin):
    """Admin interface for Wallet"""
    
    list_display = (
        'user_display',
        'current_balance_display',
        'pending_balance_display',
        'frozen_balance_display',
        'available_balance_display',
        'total_earned_display',
        'total_withdrawn_display',
        'status_badge',
        'created_at_display'
    )
    
    list_filter = (
        'is_locked',
        'currency',
        'created_at'
    )
    
    search_fields = (
        'user__username',
        'user__email',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
        'locked_at',
    )
    
    list_per_page = 25
    # autocomplete_fields = ['user']
    raw_id_fields = ['user'] 
    
    fieldsets = (
        ('User Information', {
            'fields': (
                'user',
                'currency',
            ),
            'classes': ('unfold-card',),
        }),
        ('Balances', {
            'fields': (
                'current_balance',
                'pending_balance',
                'frozen_balance',
                'bonus_balance',
                'bonus_expires_at',
            ),
            'classes': ('unfold-card',),
        }),
        ('Statistics', {
            'fields': (
                'total_earned',
                'total_withdrawn',
            ),
            'classes': ('unfold-card',),
        }),
        ('Wallet Status', {
            'fields': (
                'is_locked',
                'locked_reason',
                'locked_at',
            ),
            'classes': ('unfold-card',),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
    )
    
    actions = [
        'lock_wallets',
        'unlock_wallets',
    ]
    
    # Custom display methods
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<div class="text-sm">'
                '<div class="font-medium">{}</div>'
                '<div class="text-xs text-gray-500">{}</div>'
                '</div>',
                obj.user.username,
                obj.user.email
            )
        return '-'
    user_display.short_description = 'User'
    
    def current_balance_display(self, obj):
        return format_html(
            '<div class="text-right font-bold text-lg">{:,.2f} {}</div>',
            obj.current_balance,
            obj.currency
        )
    current_balance_display.short_description = 'Current Balance'
    
    def pending_balance_display(self, obj):
        if obj.pending_balance > 0:
            return format_html(
                '<div class="text-right text-amber-600">{:,.2f} {}</div>',
                obj.pending_balance,
                obj.currency
            )
        return format_html('<div class="text-right text-gray-400">-</div>')
    pending_balance_display.short_description = 'Pending'
    
    def frozen_balance_display(self, obj):
        if obj.frozen_balance > 0:
            return format_html(
                '<div class="text-right text-rose-600">{:,.2f} {}</div>',
                obj.frozen_balance,
                obj.currency
            )
        return format_html('<div class="text-right text-gray-400">-</div>')
    frozen_balance_display.short_description = 'Frozen'
    
    def available_balance_display(self, obj):
        return format_html(
            '<div class="text-right font-medium text-emerald-600">{:,.2f} {}</div>',
            obj.available_balance,
            obj.currency
        )
    available_balance_display.short_description = 'Available'
    
    def total_earned_display(self, obj):
        return format_html(
            '<div class="text-right text-sm">{:,.2f} {}</div>',
            obj.total_earned,
            obj.currency
        )
    total_earned_display.short_description = 'Total Earned'
    
    def total_withdrawn_display(self, obj):
        return format_html(
            '<div class="text-right text-sm">{:,.2f} {}</div>',
            obj.total_withdrawn,
            obj.currency
        )
    total_withdrawn_display.short_description = 'Total Withdrawn'
    
    def status_badge(self, obj):
        if obj.is_locked:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200">'
                '<span class="mr-1">🔒</span> Locked</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">'
            '<span class="mr-1">🔓</span> Active</span>'
        )
    status_badge.short_description = 'Status'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    # Action methods
    def lock_wallets(self, request, queryset):
        """Lock selected wallets"""
        for wallet in queryset:
            wallet.lock('Locked by admin')
        
        self.message_user(request, f'🔒 {queryset.count()} wallets locked.', level='SUCCESS')
    lock_wallets.short_description = "Lock wallets"
    
    def unlock_wallets(self, request, queryset):
        """Unlock selected wallets"""
        for wallet in queryset:
            wallet.unlock()
        
        self.message_user(request, f'🔓 {queryset.count()} wallets unlocked.', level='SUCCESS')
    unlock_wallets.short_description = "Unlock wallets"


# ==================== WITHDRAWAL ADMIN ====================

@admin.register(Withdrawal)
class WithdrawalAdmin(ModelAdmin):
    """Admin interface for Withdrawal"""
    
    list_display = (
        'withdrawal_id_display',
        'user_display',
        'amount_display',
        'fee_display',
        'net_amount_display',
        'status_display',
        'payment_method_display',
        'created_at_display',
        'actions_display'
    )
    
    list_filter = (
        'status',
        'created_at'
    )
    
    search_fields = (
        'withdrawal_id',
        'user__username',
        'user__email',
        'payment_method__account_number',
        'gateway_reference'
    )
    
    readonly_fields = (
        'withdrawal_id',
        'created_at',
        'updated_at',
        'processed_at',
        'rejected_at',
    )
    
    list_per_page = 25
    # autocomplete_fields = ['user', 'wallet', 'payment_method', 'processed_by', 'transaction']
    raw_id_fields = ['user','wallet', 'payment_method', 'processed_by',] 
    
    fieldsets = (
        ('Withdrawal Information', {
            'fields': (
                'withdrawal_id',
                'user',
                'wallet',
                'payment_method',
                ('amount', 'fee', 'net_amount'),
                'status',
            ),
            'classes': ('unfold-card',),
        }),
        ('Processing Information', {
            'fields': (
                'transaction',
                'processed_by',
                'processed_at',
                'rejection_reason',
                'rejected_at',
            ),
            'classes': ('unfold-card',),
        }),
        ('Payment Gateway Response', {
            'fields': (
                'gateway_reference',
                'gateway_response',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('unfold-card', 'collapse'),
        }),
    )
    
    actions = [
        'process_withdrawals',
        'complete_withdrawals',
        'reject_withdrawals',
    ]
    
    # Custom display methods
    def withdrawal_id_display(self, obj):
        return format_html(
            '<span class="font-mono text-sm">{}</span>',
            str(obj.withdrawal_id)[:8]
        )
    withdrawal_id_display.short_description = 'Withdrawal ID'
    
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<div class="text-sm">'
                '<div class="font-medium">{}</div>'
                '<div class="text-xs text-gray-500">{}</div>'
                '</div>',
                obj.user.username,
                obj.user.email
            )
        return '-'
    user_display.short_description = 'User'
    
    def amount_display(self, obj):
        return format_html(
            '<div class="text-right font-bold">{:,.2f}</div>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def fee_display(self, obj):
        if obj.fee > 0:
            return format_html(
                '<div class="text-right text-rose-600">{:,.2f}</div>',
                obj.fee
            )
        return format_html('<div class="text-right text-gray-400">-</div>')
    fee_display.short_description = 'Fee'
    
    def net_amount_display(self, obj):
        return format_html(
            '<div class="text-right font-medium text-emerald-600">{:,.2f}</div>',
            obj.net_amount
        )
    net_amount_display.short_description = 'Net Amount'
    
    def status_display(self, obj):
        status_config = {
            'pending': {'icon': '⏳', 'color': 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'},
            'processing': {'icon': '⚡', 'color': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'},
            'completed': {'icon': '[OK]', 'color': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'},
            'rejected': {'icon': '[ERROR]', 'color': 'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200'},
            'failed': {'icon': '🚫', 'color': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'},
        }
        
        config = status_config.get(obj.status, {'icon': '❓', 'color': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def payment_method_display(self, obj):
        if obj.payment_method:
            return format_html(
                '<div class="text-sm">'
                '<div class="font-medium">{}</div>'
                '<div class="text-xs text-gray-500">{}</div>'
                '</div>',
                obj.payment_method.get_method_type_display(),
                obj.payment_method.account_number[-4:]
            )
        return format_html('<span class="text-gray-400">-</span>')
    payment_method_display.short_description = 'Payment Method'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="font-medium text-gray-900 dark:text-gray-100">{}</div>'
            '<div class="text-xs text-gray-500 dark:text-gray-400">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    def actions_display(self, obj):
        return format_html(
            '<div class="flex space-x-2">'
            '<a href="{}" class="text-blue-600 hover:text-blue-800" title="View">👁️</a>'
            '<a href="{}" class="text-green-600 hover:text-green-800" title="Edit">✏️</a>'
            '</div>',
            f'/admin/wallet/withdrawal/{obj.id}/change/',
            f'/admin/wallet/withdrawal/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    # Action methods
    def process_withdrawals(self, request, queryset):
        """Process selected withdrawals"""
        for withdrawal in queryset.filter(status='pending'):
            withdrawal.status = 'processing'
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.save()
        
        self.message_user(request, f'⚡ {queryset.count()} withdrawals marked as processing.', level='SUCCESS')
    process_withdrawals.short_description = "Process withdrawals"
    
    def complete_withdrawals(self, request, queryset):
        """Complete selected withdrawals"""
        for withdrawal in queryset.filter(status='processing'):
            withdrawal.status = 'completed'
            withdrawal.save()
        
        self.message_user(request, f'[OK] {queryset.count()} withdrawals completed.', level='SUCCESS')
    complete_withdrawals.short_description = "Complete withdrawals"
    
    
    def reject_withdrawals(self, request, queryset):
        """Reject selected withdrawals"""
        for withdrawal in queryset.filter(status='pending'):
            withdrawal.status = 'rejected'
            withdrawal.save()
    
        self.message_user(request, f'[ERROR] {queryset.count()} withdrawals rejected.', level='SUCCESS')
    reject_withdrawals.short_description = "Reject withdrawals"
    
    
    # ==================== 3. WITHDRAWAL REQUEST ADMIN (FIXED) ====================
@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    """
    💸 Withdrawal Request Admin - Complete & Bulletproof
    Models: WithdrawalRequest (from your models.py)
    """
    
    list_display = [
        'id_short', 'user_link', 'amount_badge', 'fee_badge',
        'method_badge', 'account_masked', 'status_badge',
        'created_at_display', 'actions_column'
    ]
    
    list_filter = [
        'status', 'method',
        ('created_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'user__username', 'user__email', 'account_number',
        'admin_note'
    ]
    
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'net_amount_calculated'
    ]
    
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('👤 User Info', {
            'fields': ('user',)
        }),
        ('[MONEY] Amount Details', {
            'fields': ('amount', 'fee', 'net_amount_calculated')
        }),
        ('💳 Payment Details', {
            'fields': ('method', 'account_number', 'admin_note')
        }),
        ('[STATS] Status', {
            'fields': ('status',)
        }),
        ('📅 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def id_short(self, obj):
        try:
            return format_html(
                '<span style="background: #9C27B0; color: white; padding: 3px 8px; '
                'border-radius: 12px; font-size: 10px;">#{}</span>',
                str(obj.id)[:8] if obj.id else '?'
            )
        except Exception:
            return '-'
    id_short.short_description = 'ID'
    
    def user_link(self, obj):
        try:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html(
                '<a href="{}" style="color: #667eea; font-weight: 500;">👤 {}</a>',
                url, obj.user.username
            )
        except Exception:
            return '-'
    user_link.short_description = 'User'
    
    def amount_badge(self, obj):
        try:
            return money_display(obj.amount)
        except Exception:
            return '-'
    amount_badge.short_description = 'Amount'
    
    def fee_badge(self, obj):
        try:
            fee = SafeDisplay.decimal_val(obj.fee, 0)
            if fee > 0:
                return format_html(
                    '<span style="color: #FF9800;">💳 {:.2f}</span>',
                    fee
                )
        except Exception:
            pass
        return '-'
    fee_badge.short_description = 'Fee'
    
    def net_amount_calculated(self, obj):
        try:
            net = SafeDisplay.decimal_val(obj.amount, 0) - SafeDisplay.decimal_val(obj.fee, 0)
            return money_display(net)
        except Exception:
            return '-'
    net_amount_calculated.short_description = 'Net Amount'
    
    def method_badge(self, obj):
        try:
            method_config = {
                'bkash': ('#E2136E', '[MONEY]'),
                'nagad': ('#F15A29', '💳'),
                'rocket': ('#0D6EFD', '[START]'),
                'bank': ('#4CAF50', '🏦'),
            }
            color, icon = method_config.get(
                obj.method.lower() if obj.method else '',
                ('#9E9E9E', '💳')
            )
            return badge(obj.method, color, icon)
        except Exception:
            return '-'
    method_badge.short_description = 'Method'
    
    def account_masked(self, obj):
        try:
            if obj.account_number:
                acc = str(obj.account_number)
                if len(acc) > 4:
                    masked = '*' * (len(acc) - 4) + acc[-4:]
                    return format_html(
                        '<code style="background: #f5f5f5; padding: 3px 8px;">{}</code>',
                        masked
                    )
        except Exception:
            pass
        return '-'
    account_masked.short_description = 'Account'
    
    def status_badge(self, obj):
        try:
            status_config = {
                'pending': ('#FF9800', '⏳'),
                'approved': ('#2196F3', '[OK]'),
                'rejected': ('#F44336', '[ERROR]'),
                'cancelled': ('#9E9E9E', '🚫'),
            }
            color, icon = status_config.get(obj.status, ('#9E9E9E', '❓'))
            return badge(obj.status.title(), color, icon)
        except Exception:
            return '-'
    status_badge.short_description = 'Status'
    
    def created_at_display(self, obj):
        try:
            return format_html(
                '<div style="text-align: center;">'
                '<span style="color: #666;">{}</span><br>'
                '<span style="color: #999;">{}</span>'
                '</div>',
                obj.created_at.strftime('%Y-%m-%d') if obj.created_at else '-',
                time_ago(obj.created_at)
            )
        except Exception:
            return '-'
    created_at_display.short_description = 'Requested'
    
    def actions_column(self, obj):
        try:
            buttons = []
            buttons.append(
                f'<a href="{reverse("admin:wallet_withdrawalrequest_change", args=[obj.id])}" '
                'style="color: #2196F3; margin-right: 5px;" title="View">👁️</a>'
            )
            if obj.status == 'pending':
                buttons.append(
                    f'<a href="#" onclick="return false;" style="color: #4CAF50; margin-right: 5px;" '
                    f'title="Approve">[OK]</a>'
                )
                buttons.append(
                    f'<a href="#" onclick="return false;" style="color: #F44336;" '
                    f'title="Reject">[ERROR]</a>'
                )
            return format_html(' '.join(buttons))
        except Exception:
            return '-'
    actions_column.short_description = 'Actions'
    
    actions = ['approve_requests', 'reject_requests', 'process_withdrawals']
    
    def approve_requests(self, request, queryset):
        """Approve withdrawal requests with safety checks"""
        try:
            count = 0
            for withdrawal in queryset.filter(status='pending'):
                try:
                    # [OK] Safety check for wallet
                    if not hasattr(withdrawal.user, 'wallet'):
                        messages.error(request, f"User {withdrawal.user} has no wallet")
                        continue
                    
                    # Create wallet transaction
                    txn = WalletTransaction.objects.create(
                        wallet=withdrawal.user.wallet,
                        type='withdrawal',
                        amount=-withdrawal.amount,
                        status='approved',
                        description=f"Withdrawal #{withdrawal.id}",
                        balance_before=withdrawal.user.wallet.balance,
                        created_by=request.user,
                        approved_by=request.user,
                        approved_at=timezone.now()
                    )
                    
                    # Update wallet balance
                    withdrawal.user.wallet.balance -= withdrawal.amount
                    withdrawal.user.wallet.save()
                    
                    txn.balance_after = withdrawal.user.wallet.balance
                    txn.save()
                    
                    # Update withdrawal request
                    withdrawal.status = 'approved'
                    withdrawal.save()
                    
                    count += 1
                    
                except Exception as e:
                    messages.error(request, f"[ERROR] Error approving #{withdrawal.id}: {e}")
            
            if count > 0:
                messages.success(request, f"[OK] Approved {count} withdrawal requests")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    approve_requests.short_description = "[OK] Approve selected"
    
    def reject_requests(self, request, queryset):
        """Reject withdrawal requests with reason"""
        from django import forms
        
        class RejectForm(forms.Form):
            reason = forms.CharField(widget=forms.Textarea, required=True)
        
        if 'apply' in request.POST:
            form = RejectForm(request.POST)
            if form.is_valid():
                reason = form.cleaned_data['reason']
                count = queryset.filter(status='pending').update(
                    status='rejected',
                    admin_note=reason
                )
                messages.success(request, f"[ERROR] Rejected {count} withdrawal requests")
                return None
        else:
            form = RejectForm()
        
        return self.render_rejection_form(request, form, queryset)
    reject_requests.short_description = "[ERROR] Reject selected"
    
    def render_rejection_form(self, request, form, queryset):
        """Render rejection reason form"""
        return render(request, 'admin/wallet/withdrawalrequest/reject_form.html', {
            'form': form,
            'queryset': queryset,
            'opts': self.model._meta,
            'action': 'reject_requests',
        })
    
    def process_withdrawals(self, request, queryset):
        """Process withdrawals (mark as completed)"""
        try:
            count = queryset.filter(status='approved').update(
                status='completed'
            )
            messages.success(request, f"[OK] Processed {count} withdrawals")
        except Exception as e:
            messages.error(request, f"[ERROR] Error: {e}")
    process_withdrawals.short_description = "[MONEY] Process withdrawals"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    
   