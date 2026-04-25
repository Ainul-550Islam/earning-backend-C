# api/payment_gateways/tracking/admin.py
from django.contrib import admin
from .models import Click, Conversion, PostbackLog, PublisherDailyStats

@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display   = ('click_id','publisher','offer','country_code','device_type','is_converted','is_fraud','is_bot','payout','created_at')
    list_filter    = ('is_converted','is_fraud','is_bot','device_type','country_code')
    search_fields  = ('click_id','publisher__email')
    readonly_fields= ('click_id','created_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('publisher','offer')

@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display   = ('conversion_id','publisher','offer','conversion_type','status','payout','cost','revenue','publisher_paid','created_at')
    list_filter    = ('status','conversion_type','publisher_paid')
    search_fields  = ('conversion_id','click_id_raw','publisher__email')
    readonly_fields= ('conversion_id','revenue','created_at')
    actions        = ['approve_conversions','reject_conversions','mark_paid']

    @admin.action(description='Approve selected conversions')
    def approve_conversions(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(status='approved', approved_at=timezone.now(), approved_by=request.user)

    @admin.action(description='Reject selected conversions')
    def reject_conversions(self, request, queryset):
        queryset.update(status='rejected')

    @admin.action(description='Mark publisher as paid')
    def mark_paid(self, request, queryset):
        from django.utils import timezone
        queryset.filter(publisher_paid=False, status='approved').update(publisher_paid=True, publisher_paid_at=timezone.now())

@admin.register(PostbackLog)
class PostbackLogAdmin(admin.ModelAdmin):
    list_display   = ('click_id','offer','status','ip_address','response_code','created_at')
    list_filter    = ('status',)
    search_fields  = ('click_id',)
    readonly_fields= ('created_at',)

@admin.register(PublisherDailyStats)
class PublisherDailyStatsAdmin(admin.ModelAdmin):
    list_display   = ('publisher','offer','date','clicks','conversions','revenue','epc','cr')
    list_filter    = ('date',)
    search_fields  = ('publisher__email',)
