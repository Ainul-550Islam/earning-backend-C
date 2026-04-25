# api/payment_gateways/schedules/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import PaymentSchedule, ScheduledPayout, EarlyPaymentRequest

@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display  = ('user','schedule_type','payment_method','minimum_payout','next_payout_date','status')
    list_filter   = ('schedule_type','payment_method','status')
    search_fields = ('user__email','user__username')
    actions       = ['process_due_now']

    @admin.action(description='Process due payouts now')
    def process_due_now(self, request, queryset):
        from .ScheduleProcessor import ScheduleProcessor
        result = ScheduleProcessor().process_due_payouts()
        self.message_user(request, f'Processed: {result}')

@admin.register(ScheduledPayout)
class ScheduledPayoutAdmin(admin.ModelAdmin):
    list_display  = ('user','amount','currency','payment_method','status','scheduled_date','processed_at')
    list_filter   = ('status','payment_method')
    readonly_fields = ('user','amount','fee','net_amount','period_start','period_end','scheduled_date')

@admin.register(EarlyPaymentRequest)
class EarlyPaymentRequestAdmin(admin.ModelAdmin):
    list_display  = ('user','amount','early_fee','net_amount','payment_method','status','created_at')
    list_filter   = ('status','payment_method')
    actions       = ['approve_requests']

    @admin.action(description='Approve selected early payment requests')
    def approve_requests(self, request, queryset):
        approved = 0
        for req in queryset.filter(status='pending'):
            req.status      = 'approved'
            req.approved_by = request.user
            req.processed_at= timezone.now()
            req.save()
            approved += 1
        self.message_user(request, f'{approved} early payments approved')
