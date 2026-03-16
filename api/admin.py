# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Notice, EarningTask, PaymentRequest, PaymentHistory
from django.contrib.auth import get_user_model
User = get_user_model()
# from api.notification.models import Notification    
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    Notice, Wallet, Transaction, Offer, UserOffer,
    Referral, DailyStats, Withdrawal
)

# @admin.register(User)
# class UserAdmin(admin.ModelAdmin):
#     list_display = ['username', 'user_id', 'refer_code', 'coin_balance', 'total_earned', 'date_joined']
#     search_fields = ['username', 'user_id', 'refer_code']
#     list_filter = ['date_joined']
#     readonly_fields = ['user_id', 'refer_code', 'total_earned']


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['message', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']


@admin.register(EarningTask)
class EarningTaskAdmin(admin.ModelAdmin):
    list_display = ['user', 'task_type', 'coins_earned', 'completed_at']
    list_filter = ['task_type', 'completed_at']
    search_fields = ['user__username']
    date_hierarchy = 'completed_at'


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'payment_method', 'status_badge', 'requested_at', 'action_buttons']
    list_filter = ['status', 'payment_method', 'requested_at']
    search_fields = ['user__username', 'account_number']
    readonly_fields = ['user', 'coins_deducted', 'requested_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'amount', 'coins_deducted', 'payment_method', 'account_number')
        }),
        ('Status', {
            'fields': ('status', 'transaction_id', 'admin_note')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'processed_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#17a2b8',
            'paid': '#28a745',
            'rejected': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 5px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def action_buttons(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="/admin/approve-payment/{}/">Approve</a> '
                '<a class="button" href="/admin/reject-payment/{}/">Reject</a>',
                obj.pk, obj.pk
            )
        return '-'
    action_buttons.short_description = 'Actions'
    
    actions = ['approve_payments', 'mark_as_paid', 'reject_payments']
    
    def approve_payments(self, request, queryset):
        queryset.update(status='approved')
        self.message_user(request, f'{queryset.count()} payments approved')
    approve_payments.short_description = 'Approve selected payments'
    
    def mark_as_paid(self, request, queryset):
        for payment in queryset:
            payment.status = 'paid'
            payment.processed_at = timezone.now()
            payment.save()
            
            # Add to payment history for trust building
            PaymentHistory.objects.create(
                username=payment.user.username,
                amount=payment.amount,
                payment_method=payment.payment_method,
                is_real=True
            )
        self.message_user(request, f'{queryset.count()} payments marked as paid')
    mark_as_paid.short_description = 'Mark as PAID (add to history)'
    
    def reject_payments(self, request, queryset):
        for payment in queryset:
            # Refund coins
            payment.user.coin_balance += payment.coins_deducted
            payment.user.save()
            payment.status = 'rejected'
            payment.processed_at = timezone.now()
            payment.save()
        self.message_user(request, f'{queryset.count()} payments rejected and coins refunded')
    reject_payments.short_description = 'Reject and refund coins'


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ['username', 'amount', 'payment_method', 'paid_at', 'is_real']
    list_filter = ['is_real', 'payment_method', 'paid_at']
    search_fields = ['username']
    
    # Allow adding fake payment proofs to build trust
    fieldsets = (
        ('Payment Information', {
            'fields': ('username', 'amount', 'payment_method')
        }),
        ('Verification', {
            'fields': ('is_real',),
            'description': 'Uncheck "is_real" if this is a fake payment for trust building'
        }),
    )


# Custom admin actions for bulk operations
class BulkPaymentAdmin(admin.ModelAdmin):
    """Custom view for bulk payment processing"""
    change_list_template = 'admin/bulk_payment.html'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Get pending payments
        pending_payments = PaymentRequest.objects.filter(status='pending')
        total_amount = sum(p.amount for p in pending_payments)
        
        extra_context['pending_count'] = pending_payments.count()
        extra_context['total_amount'] = total_amount
        
        return super().changelist_view(request, extra_context=extra_context)
    
# @admin.register(User)
# class UserAdmin(BaseUserAdmin):
#     list_display = ['username', 'email', 'balance', 'total_earned', 'tier', 'referral_code', 'is_verified', 'created_at']
#     list_filter = ['tier', 'is_verified', 'is_active', 'created_at']
#     search_fields = ['username', 'email', 'referral_code']
#     readonly_fields = ['uid', 'referral_code', 'balance', 'total_earned', 'created_at', 'updated_at']
# @admin.register(User) <-- এই লাইনটি বদলে নিচের মতো করুন
@admin.register(User) 
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'balance', 'total_earned', 'tier', 'referral_code', 'is_verified', 'created_at']
    # list_filter থেকে 'tier' সরিয়ে দিন যদি মডেলে না থাকে
    list_filter = ['is_verified', 'is_active', 'created_at'] 
    search_fields = ['username', 'email', 'referral_code']
    readonly_fields = ['uid', 'referral_code', 'balance', 'total_earned', 'created_at', 'updated_at']

    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Earning Pro Fields', {
            'fields': ('uid', 'balance', 'total_earned', 'referral_code', 'referred_by', 
                      'tier', 'phone_number', 'country', 'is_verified', 'last_activity')
        }),
    )
    
    actions = ['verify_users', 'upgrade_to_gold']
    
    def verify_users(self, request, queryset):
        queryset.update(is_verified=True)
        self.message_user(request, f'{queryset.count()} users verified successfully.')
    verify_users.short_description = 'Verify selected users'
    
    def upgrade_to_gold(self, request, queryset):
        queryset.update(tier='GOLD')
        self.message_user(request, f'{queryset.count()} users upgraded to Gold.')
    upgrade_to_gold.short_description = 'Upgrade to Gold tier'


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'available_balance', 'pending_balance', 'lifetime_earnings', 'total_withdrawn']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    list_filter = ['created_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'amount', 'transaction_type', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['transaction_id', 'user__username', 'reference_id']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['title', 'offer_type', 'reward_amount', 'total_completions', 'status', 'featured', 'created_at']
    list_filter = ['offer_type', 'status', 'featured', 'difficulty', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['offer_id', 'total_completions', 'created_at', 'updated_at']
    list_editable = ['status', 'featured']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('offer_id', 'title', 'description', 'offer_type', 'category', 'icon')
        }),
        ('Reward Settings', {
            'fields': ('reward_amount', 'estimated_time', 'difficulty', 'max_completions')
        }),
        ('Status & Visibility', {
            'fields': ('status', 'featured', 'expires_at')
        }),
        ('Targeting', {
            'fields': ('countries', 'min_tier')
        }),
        ('Details', {
            'fields': ('url', 'terms', 'total_completions', 'success_rate')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['feature_offers', 'pause_offers', 'activate_offers']
    
    def feature_offers(self, request, queryset):
        queryset.update(featured=True)
        self.message_user(request, f'{queryset.count()} offers marked as featured.')
    feature_offers.short_description = 'Mark as featured'
    
    def pause_offers(self, request, queryset):
        queryset.update(status='PAUSED')
        self.message_user(request, f'{queryset.count()} offers paused.')
    pause_offers.short_description = 'Pause selected offers'
    
    def activate_offers(self, request, queryset):
        queryset.update(status='ACTIVE')
        self.message_user(request, f'{queryset.count()} offers activated.')
    activate_offers.short_description = 'Activate selected offers'


@admin.register(UserOffer)
class UserOfferAdmin(admin.ModelAdmin):
    list_display = ['user', 'offer', 'status', 'reward_earned', 'started_at', 'completed_at']
    list_filter = ['status', 'started_at', 'completed_at']
    search_fields = ['user__username', 'offer__title']
    readonly_fields = ['started_at', 'completed_at', 'verified_at']
    date_hierarchy = 'started_at'
    
    actions = ['approve_completions', 'reject_completions']
    
    def approve_completions(self, request, queryset):
        count = 0
        for user_offer in queryset.filter(status='PENDING'):
            if user_offer.complete():
                count += 1
        self.message_user(request, f'{count} offers approved and users credited.')
    approve_completions.short_description = 'Approve and credit users'
    
    def reject_completions(self, request, queryset):
        queryset.update(status='REJECTED')
        self.message_user(request, f'{queryset.count()} offers rejected.')
    reject_completions.short_description = 'Reject selected completions'


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referred', 'commission_rate', 'total_earned', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['referrer__username', 'referred__username']
    readonly_fields = ['total_earned', 'created_at']


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'clicks', 'conversions', 'earnings', 'offers_completed']
    list_filter = ['date']
    search_fields = ['user__username']
    date_hierarchy = 'date'


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['withdrawal_id', 'user', 'amount', 'payment_method', 'status', 'requested_at']
    list_filter = ['status', 'payment_method', 'requested_at']
    search_fields = ['withdrawal_id', 'user__username']
    readonly_fields = ['withdrawal_id', 'requested_at', 'processed_at']
    date_hierarchy = 'requested_at'
    
    fieldsets = (
        ('Request Information', {
            'fields': ('withdrawal_id', 'user', 'amount', 'payment_method', 'payment_details')
        }),
        ('Processing', {
            'fields': ('status', 'processing_fee', 'net_amount', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'processed_at', 'processed_by')
        })
    )
    
    actions = ['approve_withdrawals', 'reject_withdrawals']
    
    def approve_withdrawals(self, request, queryset):
        count = 0
        for withdrawal in queryset.filter(status='PENDING'):
            if withdrawal.approve(processed_by=request.user):
                count += 1
        self.message_user(request, f'{count} withdrawals approved.')
    approve_withdrawals.short_description = 'Approve selected withdrawals'
    
    def reject_withdrawals(self, request, queryset):
        queryset.update(status='REJECTED', processed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} withdrawals rejected.')
    reject_withdrawals.short_description = 'Reject selected withdrawals'


# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
#     list_filter = ['notification_type', 'is_read', 'created_at']
#     search_fields = ['user__username', 'title', 'message']
#     date_hierarchy = 'created_at'
    
#     actions = ['mark_as_read']
    
#     def mark_as_read(self, request, queryset):
#         queryset.update(is_read=True)
#         self.message_user(request, f'{queryset.count()} notifications marked as read.')
#     mark_as_read.short_description = 'Mark as read'


# Admin site customization
admin.site.site_header = 'Earning Pro Admin'
admin.site.site_title = 'Earning Pro Admin Portal'
admin.site.index_title = 'Welcome to Earning Pro Administration'
