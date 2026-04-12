from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django import forms 
from .models import PaymentGateway, GatewayConfig
import json

from .models import (
    PaymentGateway, PaymentGatewayMethod, GatewayTransaction,
    PayoutRequest, GatewayConfig, Currency, PaymentGatewayWebhookLog
)


# Custom Forms
class PaymentGatewayForm(forms.ModelForm):
    class Meta:
        model = PaymentGateway
        fields = '__all__'
        widgets = {
            'merchant_key': forms.PasswordInput(render_value=True),
            'merchant_secret': forms.PasswordInput(render_value=True),
        }


class GatewayConfigForm(forms.ModelForm):
    class Meta:
        model = GatewayConfig
        fields = '__all__'
        widgets = {
            'value': forms.Textarea(attrs={'rows': 3}),
        }


# Custom Filters
class GatewayStatusFilter(admin.SimpleListFilter):
    title = 'Gateway Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('maintenance', 'Maintenance'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class GatewayTransactionStatusFilter(admin.SimpleListFilter):
    title = 'GatewayTransaction Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class GatewayTransactionTypeFilter(admin.SimpleListFilter):
    title = 'GatewayTransaction Type'
    parameter_name = 'GatewayTransaction_type'
    
    def lookups(self, request, model_admin):
        return [
            ('deposit', 'Deposit'),
            ('withdrawal', 'Withdrawal'),
            ('refund', 'Refund'),
            ('bonus', 'Bonus'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(GatewayTransaction_type=self.value())
        return queryset


class PayoutStatusFilter(admin.SimpleListFilter):
    title = 'Payout Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


# ==================== PAYMENT GATEWAY ADMIN ====================

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    form = PaymentGatewayForm
    list_display = (
        'name_display', 
        'status_display',
        'fee_display',
        'is_test_mode_display',
        'GatewayTransaction_fee_percentage_display',
        'min_max_amount_display',
        'created_at_display',
        'actions_display'
    )
    list_filter = (GatewayStatusFilter, 'name')
    search_fields = ('name', 'display_name', 'merchant_id')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'status', 'description')
        }),
        ('API Configuration', {
            'fields': ('merchant_id', 'merchant_key', 'merchant_secret'),
            'classes': ('collapse',)
        }),
        ('URL Configuration', {
            'fields': ('api_url', 'callback_url'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_test_mode', 'GatewayTransaction_fee_percentage', 
                      'minimum_amount', 'maximum_amount')
        }),
        ('Capabilities', {
            'fields': ('supports_deposit', 'supports_withdrawal', 'supported_currencies'),
            'classes': ('collapse',)
        }),
        ('Visual Settings', {
            'fields': ('logo', 'color_code', 'sort_order'),
            'classes': ('collapse',)
        }),
        ('Configuration Data', {
            'fields': ('config_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def name_display(self, obj):
        return format_html(
            '<div class="font-medium">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>',
            obj.get_name_display(),
            obj.display_name
        )
    name_display.short_description = 'Gateway'
    
    def status_display(self, obj):
        status_config = {
            'active': {'icon': '[OK]', 'color': 'bg-emerald-100 text-emerald-800'},
            'inactive': {'icon': '[ERROR]', 'color': 'bg-rose-100 text-rose-800'},
            'maintenance': {'icon': '🛠️', 'color': 'bg-amber-100 text-amber-800'},
        }
        
        config = status_config.get(obj.status, {'icon': '❓', 'color': 'bg-gray-100 text-gray-800'})
        
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
    
    def is_test_mode_display(self, obj):
        if obj.is_test_mode:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-blue-100 text-blue-800">'
                '<span class="mr-1">🧪</span> Test Mode</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-green-100 text-green-800">'
            '<span class="mr-1">[START]</span> Live Mode</span>'
        )
    is_test_mode_display.short_description = 'Mode'
    
    def GatewayTransaction_fee_percentage_display(self, obj):
        return format_html(
            '<div class="text-center font-medium">{:.2f}%</div>',
            obj.GatewayTransaction_fee_percentage
        )
    GatewayTransaction_fee_percentage_display.short_description = 'Fee %'
    
    def min_max_amount_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div>Min: {:,.2f}</div>'
            '<div>Max: {:,.2f}</div>'
            '</div>',
            obj.minimum_amount,
            obj.maximum_amount
        )
    min_max_amount_display.short_description = 'Amount Range'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>'
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
            f'/admin/payment_gateways/paymentgateway/{obj.id}/change/',
            f'/admin/payment_gateways/paymentgateway/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    actions = ['activate_gateways', 'deactivate_gateways', 'toggle_test_mode']
    
    def activate_gateways(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'[OK] {updated} payment gateways activated.')
    activate_gateways.short_description = "Activate gateways"
    
    def toggle_test_mode(self, request, queryset):
        for gateway in queryset:
            gateway.is_test_mode = not gateway.is_test_mode
            gateway.save()
        
        self.message_user(request, f'[LOADING] Test mode toggled for {queryset.count()} gateways.')
    toggle_test_mode.short_description = "Toggle test mode"
    
    
    def fee_display(self, obj):
        return format_html('<div class="text-right font-medium">{:.2f}%</div>', obj.GatewayTransaction_fee_percentage)
    fee_display.short_description = 'Fee %'
 


# ==================== PAYMENT GATEWAY METHOD ADMIN ====================

@admin.register(PaymentGatewayMethod)
class PaymentGatewayMethodAdmin(admin.ModelAdmin):
    list_display = (
        'user_display',
        'gateway_display',
        'account_number_masked',
        'account_name',
        'verification_badge',
        'default_badge',
        'created_at_display',
        'actions_display'
    )
    
    list_filter = ('gateway', 'is_verified', 'is_default')
    search_fields = (
        'user__username',
        'user__email',
        'account_number',
        'account_name',
        'gateway'
    )
    
    # list_editable = ('is_verified', 'is_default')
    readonly_fields = ('created_at', 'updated_at')
    
    list_per_page = 25
    # autocomplete_fields = ['user']
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'gateway', 'account_number', 'account_name')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_default')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
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
    
    def gateway_display(self, obj):
        gateway_config = {
            'bkash': {'icon': '[MONEY]', 'color': 'bg-pink-100 text-pink-800'},
            'nagad': {'icon': '💳', 'color': 'bg-yellow-100 text-yellow-800'},
            'stripe': {'icon': '💳', 'color': 'bg-indigo-100 text-indigo-800'},
            'paypal': {'icon': '🌐', 'color': 'bg-blue-100 text-blue-800'},
        }
        
        config = gateway_config.get(obj.gateway, {'icon': '💳', 'color': 'bg-gray-100 text-gray-800'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_gateway_display()
        )
    gateway_display.short_description = 'Gateway'
    
    def account_number_masked(self, obj):
        if obj.account_number:
            masked = '•' * (len(obj.account_number) - 4) + obj.account_number[-4:]
            return format_html(
                '<span class="font-mono text-sm">{}</span>',
                masked
            )
        return '-'
    account_number_masked.short_description = 'Account Number'
    
    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-emerald-100 text-emerald-800">'
                '<span class="mr-1">[OK]</span> Verified</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-rose-100 text-rose-800">'
            '<span class="mr-1">[ERROR]</span> Unverified</span>'
        )
    verification_badge.short_description = 'Verification'
    
    def default_badge(self, obj):
        if obj.is_default:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-blue-100 text-blue-800">'
                '<span class="mr-1">★</span> Default</span>'
            )
        return format_html('<span class="text-gray-400">-</span>')
    default_badge.short_description = 'Default'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>'
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
            f'/admin/payment_gateways/paymentgatewaymethod/{obj.id}/change/',
            f'/admin/payment_gateways/paymentgatewaymethod/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    actions = ['verify_methods', 'set_as_default', 'remove_default']
    
    def verify_methods(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'[OK] {updated} payment methods verified.')
    verify_methods.short_description = "Verify methods"
    
    def set_as_default(self, request, queryset):
        for method in queryset:
            # Remove default from other methods of same user
            PaymentGatewayMethod.objects.filter(
                user=method.user,
                is_default=True
            ).update(is_default=False)
            
            # Set this as default
            method.is_default = True
            method.save()
        
        self.message_user(request, f'★ {queryset.count()} methods set as default.')
    set_as_default.short_description = "Set as default"


# ==================== GATEWAY GatewayTransaction ADMIN ====================

@admin.register(GatewayTransaction)
class GatewayTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference_id_display',
        'user_display',
        'GatewayTransaction_type_display',
        'amount_display',
        'gateway_display',
        'status_display',
        'created_at_display',
        'actions_display'
    )
    
    list_filter = (
        GatewayTransactionTypeFilter,
        GatewayTransactionStatusFilter,
        'gateway',
        'created_at'
    )
    
    search_fields = (
        'reference_id',
        'gateway_reference',
        'user__username',
        'user__email',
        'notes'
    )
    
    readonly_fields = (
        'reference_id',
        'gateway_reference',
        'created_at',
        'updated_at',
    )
    
    list_per_page = 30
    # autocomplete_fields = ['user', 'payment_method']
    raw_id_fields = ['user', 'payment_method']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('GatewayTransaction Information', {
            'fields': ('reference_id', 'user', 'GatewayTransaction_type', 'gateway')
        }),
        ('Amount Details', {
            'fields': ('amount', 'fee', 'net_amount')
        }),
        ('Status & References', {
            'fields': ('status', 'gateway_reference', 'payment_method')
        }),
        ('Additional Information', {
            'fields': ('metadata', 'notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def reference_id_display(self, obj):
        return format_html(
            '<span class="font-mono text-sm">{}</span>',
            obj.reference_id[:12] + '...' if len(obj.reference_id) > 12 else obj.reference_id
        )
    reference_id_display.short_description = 'Reference ID'
    
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<div class="text-sm">'
                '<div class="font-medium">{}</div>'
                '<div class="text-xs text-gray-500">{}</div>'
                '</div>',
                obj.user.username,
                obj.user.email[:20] + '...' if len(obj.user.email) > 20 else obj.user.email
            )
        return '-'
    user_display.short_description = 'User'
    
    def GatewayTransaction_type_display(self, obj):
        type_config = {
            'deposit': {'icon': '⬇️', 'color': 'bg-emerald-100 text-emerald-800'},
            'withdrawal': {'icon': '⬆️', 'color': 'bg-rose-100 text-rose-800'},
            'refund': {'icon': '↩️', 'color': 'bg-orange-100 text-orange-800'},
            'bonus': {'icon': '🎁', 'color': 'bg-purple-100 text-purple-800'},
        }
        
        config = type_config.get(obj.GatewayTransaction_type, {'icon': '💳', 'color': 'bg-gray-100 text-gray-800'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_GatewayTransaction_type_display()
        )
    GatewayTransaction_type_display.short_description = 'Type'
    
    def amount_display(self, obj):
        return format_html(
            '<div class="text-right font-medium">{:,.2f}</div>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def gateway_display(self, obj):
        gateway_config = {
            'bkash': {'icon': '[MONEY]', 'color': 'bg-pink-100 text-pink-800'},
            'nagad': {'icon': '💳', 'color': 'bg-yellow-100 text-yellow-800'},
            'stripe': {'icon': '💳', 'color': 'bg-indigo-100 text-indigo-800'},
            'paypal': {'icon': '🌐', 'color': 'bg-blue-100 text-blue-800'},
        }
        
        config = gateway_config.get(obj.gateway, {'icon': '💳', 'color': 'bg-gray-100 text-gray-800'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.gateway.upper()
        )
    gateway_display.short_description = 'Gateway'
    
    def status_display(self, obj):
        status_config = {
            'pending': {'icon': '⏳', 'color': 'bg-amber-100 text-amber-800'},
            'processing': {'icon': '⚡', 'color': 'bg-blue-100 text-blue-800'},
            'completed': {'icon': '[OK]', 'color': 'bg-emerald-100 text-emerald-800'},
            'failed': {'icon': '[ERROR]', 'color': 'bg-rose-100 text-rose-800'},
            'cancelled': {'icon': '🚫', 'color': 'bg-gray-100 text-gray-800'},
        }
        
        config = status_config.get(obj.status, {'icon': '❓', 'color': 'bg-gray-100 text-gray-800'})
        
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
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>'
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
            f'/admin/payment_gateways/GatewayTransaction/{obj.id}/change/',
            f'/admin/payment_gateways/GatewayTransaction/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    actions = ['mark_as_completed', 'mark_as_failed', 'export_GatewayTransactions']
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='completed')
        self.message_user(request, f'[OK] {updated} GatewayTransactions marked as completed.')
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='failed')
        self.message_user(request, f'[ERROR] {updated} GatewayTransactions marked as failed.')
    mark_as_failed.short_description = "Mark as failed"


# ==================== PAYOUT REQUEST ADMIN ====================

@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        'reference_id_display',
        'user_display',
        'amount_display',
        'payout_method_display',
        'status_display',
        'created_at_display',
        'processed_at_display',
        'actions_display'
    )
    
    list_filter = (
        PayoutStatusFilter,
        'payout_method',
        'created_at'
    )
    
    search_fields = (
        'reference_id',
        'user__username',
        'user__email',
        'account_number',
        'account_name'
    )
    
    readonly_fields = (
        'reference_id',
        'net_amount',
        'created_at',
        'updated_at',
        'processed_at',
    )
    
    list_per_page = 30
    # autocomplete_fields = ['user', 'processed_by']
    raw_id_fields = ['user', 'processed_by']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('reference_id', 'user', 'amount', 'fee', 'net_amount')
        }),
        ('Payment Details', {
            'fields': ('payout_method', 'account_number', 'account_name')
        }),
        ('Status & Processing', {
            'fields': ('status', 'admin_notes', 'processed_by', 'processed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def reference_id_display(self, obj):
        return format_html(
            '<span class="font-mono text-sm">{}</span>',
            obj.reference_id[:12] + '...' if len(obj.reference_id) > 12 else obj.reference_id
        )
    reference_id_display.short_description = 'Reference ID'
    
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
            '<div class="text-right font-medium">{:,.2f}</div>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def payout_method_display(self, obj):
        method_config = {
            'bkash': {'icon': '[MONEY]', 'color': 'bg-pink-100 text-pink-800'},
            'nagad': {'icon': '💳', 'color': 'bg-yellow-100 text-yellow-800'},
            'bank': {'icon': '🏦', 'color': 'bg-green-100 text-green-800'},
            'paypal': {'icon': '🌐', 'color': 'bg-blue-100 text-blue-800'},
            'stripe': {'icon': '💳', 'color': 'bg-indigo-100 text-indigo-800'},
        }
        
        config = method_config.get(obj.payout_method, {'icon': '💳', 'color': 'bg-gray-100 text-gray-800'})
        
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">'
            '<span class="mr-1">{}</span>'
            '{}'
            '</span>',
            config['color'],
            config['icon'],
            obj.get_payout_method_display()
        )
    payout_method_display.short_description = 'Payout Method'
    
    def status_display(self, obj):
        status_config = {
            'pending': {'icon': '⏳', 'color': 'bg-amber-100 text-amber-800'},
            'approved': {'icon': '[OK]', 'color': 'bg-blue-100 text-blue-800'},
            'processing': {'icon': '⚡', 'color': 'bg-indigo-100 text-indigo-800'},
            'completed': {'icon': '[OK]', 'color': 'bg-emerald-100 text-emerald-800'},
            'rejected': {'icon': '[ERROR]', 'color': 'bg-rose-100 text-rose-800'},
            'cancelled': {'icon': '🚫', 'color': 'bg-gray-100 text-gray-800'},
        }
        
        config = status_config.get(obj.status, {'icon': '❓', 'color': 'bg-gray-100 text-gray-800'})
        
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
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    def processed_at_display(self, obj):
        if obj.processed_at:
            return format_html(
                '<div class="text-sm">'
                '<div class="text-gray-900">{}</div>'
                '<div class="text-xs text-gray-500">{}</div>'
                '</div>',
                timezone.localtime(obj.processed_at).strftime('%Y-%m-%d'),
                timezone.localtime(obj.processed_at).strftime('%H:%M')
            )
        return format_html('<span class="text-gray-400">-</span>')
    processed_at_display.short_description = 'Processed At'
    
    def actions_display(self, obj):
        return format_html(
            '<div class="flex space-x-2">'
            '<a href="{}" class="text-blue-600 hover:text-blue-800" title="View">👁️</a>'
            '<a href="{}" class="text-green-600 hover:text-green-800" title="Edit">✏️</a>'
            '</div>',
            f'/admin/payment_gateways/payoutrequest/{obj.id}/change/',
            f'/admin/payment_gateways/payoutrequest/{obj.id}/change/'
        )
    actions_display.short_description = 'Actions'
    
    actions = ['approve_payouts', 'reject_payouts', 'mark_as_processing']
    
    def approve_payouts(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f'[OK] {updated} payout requests approved.')
    approve_payouts.short_description = "Approve payouts"
    
    def mark_as_processing(self, request, queryset):
        updated = queryset.filter(status='approved').update(status='processing')
        self.message_user(request, f'⚡ {updated} payouts marked as processing.')
    mark_as_processing.short_description = "Mark as processing"


# ==================== GATEWAY CONFIG ADMIN ====================

@admin.register(GatewayConfig)
class GatewayConfigAdmin(admin.ModelAdmin):
    form = GatewayConfigForm
    list_display = (
        'gateway_display',
        'key_display',
        'value_preview',
        'is_secret_badge',
        'created_at_display'
    )
    
    list_filter = ('gateway', 'is_secret')
    search_fields = ('key', 'value', 'gateway__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
    
    fieldsets = (
        ('Configuration', {
            'fields': ('gateway', 'key', 'value', 'is_secret', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def gateway_display(self, obj):
        if obj.gateway:
            return format_html(
                '<div class="font-medium">{}</div>',
                obj.gateway.name
            )
        return '-'
    gateway_display.short_description = 'Gateway'
    
    def key_display(self, obj):
        return format_html(
            '<span class="font-mono text-sm">{}</span>',
            obj.key
        )
    key_display.short_description = 'Key'
    
    def value_preview(self, obj):
        if obj.is_secret:
            return format_html(
                '<span class="text-gray-400 italic">Hidden (Secret)</span>'
            )
        
        value_preview = str(obj.value)[:50]
        if len(str(obj.value)) > 50:
            value_preview += '...'
        
        return format_html(
            '<span class="font-mono text-sm" title="{}">{}</span>',
            str(obj.value),
            value_preview
        )
    value_preview.short_description = 'Value'
    
    def is_secret_badge(self, obj):
        if obj.is_secret:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-red-100 text-red-800">'
                '<span class="mr-1">🔒</span> Secret</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-green-100 text-green-800">'
            '<span class="mr-1">🔓</span> Public</span>'
        )
    is_secret_badge.short_description = 'Secret'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'


# ==================== CURRENCY ADMIN ====================

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'symbol_display',
        'exchange_rate_display',
        'default_badge',
        'active_badge',
        'created_at_display'
    )
    
    list_filter = ('is_default', 'is_active')
    search_fields = ('code', 'name', 'symbol')
    # list_editable = ('is_default', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
    
    fieldsets = (
        ('Currency Information', {
            'fields': ('code', 'name', 'symbol')
        }),
        ('Exchange Rate', {
            'fields': ('exchange_rate',)
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def symbol_display(self, obj):
        return format_html(
            '<div class="text-center font-bold text-lg">{}</div>',
            obj.symbol
        )
    symbol_display.short_description = 'Symbol'
    
    def exchange_rate_display(self, obj):
        return format_html(
            '<div class="text-center font-medium">{:.4f}</div>',
            obj.exchange_rate
        )
    exchange_rate_display.short_description = 'Exchange Rate'
    
    def default_badge(self, obj):
        if obj.is_default:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-blue-100 text-blue-800">'
                '<span class="mr-1">★</span> Default</span>'
            )
        return format_html('<span class="text-gray-400">-</span>')
    default_badge.short_description = 'Default'
    
    def active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
                'bg-emerald-100 text-emerald-800">'
                '<span class="mr-1">[OK]</span> Active</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium '
            'bg-rose-100 text-rose-800">'
            '<span class="mr-1">[ERROR]</span> Inactive</span>'
        )
    active_badge.short_description = 'Active'
    
    def created_at_display(self, obj):
        return format_html(
            '<div class="text-sm">'
            '<div class="text-gray-900">{}</div>'
            '<div class="text-xs text-gray-500">{}</div>'
            '</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M')
        )
    created_at_display.short_description = 'Created'
    
    actions = ['set_as_default', 'activate_currencies', 'deactivate_currencies']
    
    def set_as_default(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Please select exactly one currency to set as default.', level='error')
            return
        
        currency = queryset.first()
        Currency.objects.filter(is_default=True).update(is_default=False)
        currency.is_default = True
        currency.save()
        
        self.message_user(request, f'★ {currency.code} set as default currency.')
    set_as_default.short_description = "Set as default currency"
    
@admin.register(PaymentGatewayWebhookLog)
class PaymentGatewayWebhookLogAdmin(admin.ModelAdmin):
    # মডেলের ফিল্ড অনুযায়ী লিস্ট ডিসপ্লে সেট করা হয়েছে
    list_display = ('gateway', 'ip_address', 'processed', 'created_at')
    list_filter = ('gateway', 'processed', 'created_at')
    readonly_fields = ('gateway', 'payload', 'headers', 'ip_address', 'created_at')
    search_fields = ('gateway', 'ip_address', 'response')

    def has_add_permission(self, request):
        # সাধারণত ওয়েব হুক লগ ম্যানুয়ালি অ্যাড করা হয় না, তাই বাটন হাইড করা ভালো
        return False
    
    
    
    
    # api/payment_gateways/admin.py - একদম শেষে এই কোড যোগ করুন

# ==================== FORCE REGISTER ALL MODELS IN DEFAULT ADMIN ====================
from django.contrib import admin

try:
    from .models import (
        PaymentGateway, PaymentGatewayMethod, GatewayTransaction,
        PayoutRequest, GatewayConfig, Currency, PaymentGatewayWebhookLog
    )
    
    registered = 0
    
    # Register PaymentGateway
    if not admin.site.is_registered(PaymentGateway):
        admin.site.register(PaymentGateway, PaymentGatewayAdmin)
        registered += 1
        print("[OK] Registered: PaymentGateway")
    
    # Register PaymentGatewayMethod
    if not admin.site.is_registered(PaymentGatewayMethod):
        admin.site.register(PaymentGatewayMethod, PaymentGatewayMethodAdmin)
        registered += 1
        print("[OK] Registered: PaymentGatewayMethod")
    
    # Register GatewayTransaction
    if not admin.site.is_registered(GatewayTransaction):
        admin.site.register(GatewayTransaction, GatewayTransactionAdmin)
        registered += 1
        print("[OK] Registered: GatewayTransaction")
    
    # Register PayoutRequest
    if not admin.site.is_registered(PayoutRequest):
        admin.site.register(PayoutRequest, PayoutRequestAdmin)
        registered += 1
        print("[OK] Registered: PayoutRequest")
    
    # Register GatewayConfig
    if not admin.site.is_registered(GatewayConfig):
        admin.site.register(GatewayConfig, GatewayConfigAdmin)
        registered += 1
        print("[OK] Registered: GatewayConfig")
    
    # Register Currency
    if not admin.site.is_registered(Currency):
        admin.site.register(Currency, CurrencyAdmin)
        registered += 1
        print("[OK] Registered: Currency")
    
    # Register PaymentGatewayWebhookLog
    if not admin.site.is_registered(PaymentGatewayWebhookLog):
        admin.site.register(PaymentGatewayWebhookLog, PaymentGatewayWebhookLogAdmin)
        registered += 1
        print("[OK] Registered: PaymentGatewayWebhookLog")
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} payment_gateways models registered in default admin")
    else:
        print("[OK] All payment_gateways models already registered")
        
except Exception as e:
    print(f"[ERROR] Error registering payment_gateways models: {e}")

def _force_register_payment_gateways():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(PaymentGateway, PaymentGatewayAdmin), (PaymentGatewayMethod, PaymentGatewayMethodAdmin), (GatewayTransaction, GatewayTransactionAdmin), (PayoutRequest, PayoutRequestAdmin), (GatewayConfig, GatewayConfigAdmin), (Currency, CurrencyAdmin), (PaymentGatewayWebhookLog, PaymentGatewayWebhookLogAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] payment_gateways registered {registered} models")
    except Exception as e:
        print(f"[WARN] payment_gateways: {e}")
